# backend/app/agents/nutrition_graph_v3.py
"""
Simplified Nutrition Bot - LangGraph Implementation with Clean Architecture

Architecture:
1. load_context → Fetch minimal user profile via UserContext
2. trim_messages → Keep conversation within context limits
3. generate_response → LLM with tools decides what data it needs
4. [ToolNode] → Execute tool calls using standard LangGraph ToolNode
5. [Loop] → Back to generate for synthesis

Key Design:
- Uses context_schema for dependency injection (UserContext, Governor, PromptRegistry)
- Tools use ToolRuntime to access context (standard LangGraph pattern)
- Standard ToolNode from langgraph.prebuilt (no custom implementation)
- LLM uses its own knowledge for food nutrition estimation

Author: NutriLens AI Team
"""

from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List, Literal
from dataclasses import dataclass
import operator
from langgraph.graph import StateGraph, END
from langgraph.runtime import Runtime
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolRuntime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.messages.utils import trim_messages
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import json
import logging
from datetime import datetime, date, timedelta
from app.core.ist_datetime import today_ist

from app.core.config import settings
from app.agents.nutrition_context import UserContext
from app.infrastructure.normalization.interfaces import ITokenGovernor, IPromptRegistry

logger = logging.getLogger(__name__)


# ============================================================================
# MODULE-LEVEL LLM CLIENT (Created once, reused for all requests)
# ============================================================================

# Tools and LLM are created once when module loads (graph compiles at startup)
# This avoids per-request overhead of creating ChatOpenAI instances
_read_tools = None
_llm_with_tools = None


def _get_read_tools():
    """
    Lazy initialization of read tools.

    Created once on first use, then reused for all requests.
    """
    global _read_tools

    if _read_tools is None:
        _read_tools = create_read_tools()
        logger.info("[Module] Read tools initialized (singleton)")

    return _read_tools


def _get_llm_with_tools():
    """
    Lazy initialization of LLM with tools.

    Created once on first use, then reused for all requests.
    Uses lazy init to avoid issues with settings not being loaded at import time.
    """
    global _llm_with_tools

    if _llm_with_tools is None:
        tools = _get_read_tools()
        _llm_with_tools = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            api_key=settings.openai_api_key
        ).bind_tools(tools)
        logger.info("[Module] ChatOpenAI with tools initialized (singleton)")

    return _llm_with_tools


# ============================================================================
# CONTEXT SCHEMA - Dependency Injection Container
# ============================================================================

@dataclass
class NutritionContextSchema:
    """
    Context schema for dependency injection into the graph.

    Contains:
    - UserContext: Provides all data access methods for tools
    - ITokenGovernor: Manages token budget for LLM calls
    - IPromptRegistry: Fetches system prompts from MongoDB (hot-reloadable)

    Passed at runtime via graph.invoke(..., context=schema).
    Accessed in nodes/tools via Runtime[NutritionContextSchema].

    Not serialized to checkpoints - fresh for each invocation.
    """
    user_context: UserContext
    governor: ITokenGovernor
    prompt_registry: IPromptRegistry


# ============================================================================
# STATE SCHEMA
# ============================================================================

class NutritionState(TypedDict):
    """State for nutrition bot."""
    # Messages (automatically appended via operator.add)
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Trimmed messages for LLM input (recalculated each turn, not persisted)
    llm_input_messages: Optional[Sequence[BaseMessage]]

    # User context data (refreshed each turn)
    user_context: Dict[str, Any]

    # Session tracking
    user_id: int
    session_id: str
    turn_count: int


# ============================================================================
# READ-ONLY TOOLS (using ToolRuntime for dependency injection)
# ============================================================================

def create_read_tools() -> List:
    """
    Create read-only tools for nutrition queries.

    Tools receive UserContext via ToolRuntime (standard LangGraph pattern).
    This keeps tools thin - all business logic is in UserContext.
    """

    @tool
    async def get_nutrition_stats(
        nutrients: Optional[str] = None,
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Get current nutrition statistics for today.

        Args:
            nutrients: Comma-separated nutrients to query (e.g., "protein,calories").
                      If empty, returns all macros.

        Returns:
            JSON string with nutrition stats including consumed, targets, remaining
        """
        try:
            user_context = runtime.context.user_context
            logger.info(f"[Tool:get_nutrition_stats] Called for user {user_context.user_id}")

            # Use UserContext methods
            today_data = await user_context._get_today_consumption()
            targets = await user_context._get_targets()

            consumed = today_data.get("consumed", {})
            remaining = today_data.get("remaining", {})

            # Filter nutrients if specified
            if nutrients:
                nutrient_list = [n.strip().lower() for n in nutrients.split(",")]
                consumed = {k: v for k, v in consumed.items() if any(n in k.lower() for n in nutrient_list)}
                targets = {k: v for k, v in targets.items() if any(n in k.lower() for n in nutrient_list)}
                remaining = {k: v for k, v in remaining.items() if any(n in k.lower() for n in nutrient_list)}

            result = {
                "consumed": consumed,
                "targets": targets,
                "remaining": remaining,
                "compliance_rate": today_data.get("compliance_rate", 0),
                "meals_consumed": today_data.get("meals_consumed", 0),
                "meals_pending": today_data.get("meals_pending", 0)
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_nutrition_stats] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def check_inventory(
        search_term: Optional[str] = None,
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Check user's food inventory.

        Args:
            search_term: Optional ingredient name to search for.
                        If empty, returns summary of all inventory.

        Returns:
            JSON string with inventory information
        """
        try:
            user_context = runtime.context.user_context
            logger.info(f"[Tool:check_inventory] Called for user {user_context.user_id}")

            summary = await user_context._get_inventory_summary()

            # Fetch inventory items (only extract minimal fields for LLM)
            raw_items = await user_context.inventory_repo.get_all_for_user(
                user_context.user_id,
                include_zero_quantity=False
            )
            item_list = [
                {
                    "name": inv.item.canonical_name if inv.item else "Unknown",
                    "quantity_grams": inv.quantity_grams,
                    "expiry_date": str(inv.expiry_date.date()) if inv.expiry_date else None
                }
                for inv in raw_items
            ]

            if search_term:
                item_list = [
                    i for i in item_list
                    if search_term.lower() in i["name"].lower()
                ]
                result = {
                    "search_term": search_term,
                    "found": len(item_list) > 0,
                    "items": item_list,
                    "count": len(item_list)
                }
            else:
                result = {
                    **summary,
                    "items": item_list
                }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:check_inventory] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def get_meal_plan(
        target_date: Optional[str] = None,
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Get meal plan for a specific date.

        Args:
            target_date: Date in YYYY-MM-DD format. If empty, returns today's plan.

        Returns:
            JSON string with planned meals
        """
        try:
            user_context = runtime.context.user_context
            logger.info(f"[Tool:get_meal_plan] Called for user {user_context.user_id}")

            # Get all meals for the target date (consumed + pending + skipped)
            plan_date = date.fromisoformat(target_date) if target_date else today_ist()
            meal_logs = await user_context.tracking_repo.get_by_date(
                user_context.user_id,
                plan_date,
                active_plans_only=True
            )
            meals = []
            for meal in meal_logs:
                ext = meal.external_meal or {}
                if meal.recipe:
                    name = meal.recipe.title
                    macros = meal.recipe.macros_per_serving or {}
                elif ext:
                    name = ext.get("dish_name", "External meal")
                    macros = {
                        "calories": ext.get("calories", 0),
                        "protein_g": ext.get("protein_g", 0)
                    }
                else:
                    name = "No recipe"
                    macros = {}

                meals.append({
                    "meal_type": meal.meal_type,
                    "recipe": name,
                    "time": meal.planned_datetime.strftime("%H:%M") if meal.planned_datetime else "",
                    "status": "consumed" if meal.consumed_datetime else ("skipped" if meal.was_skipped else "pending"),
                    "calories": macros.get("calories", 0),
                    "protein_g": macros.get("protein_g", 0)
                })
            result = {
                "date": str(plan_date),
                "meals": meals,
                "count": len(meals)
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_meal_plan] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def get_makeable_recipes(
        min_protein: Optional[float] = None,
        max_calories: Optional[float] = None,
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Get recipes that can be made with current inventory.

        Args:
            min_protein: Minimum protein in grams (optional filter)
            max_calories: Maximum calories (optional filter)

        Returns:
            JSON string with makeable recipes
        """
        try:
            user_context = runtime.context.user_context
            logger.info(f"[Tool:get_makeable_recipes] Called for user {user_context.user_id}")
            print(f"\n[DEBUG Tool:get_makeable_recipes] >>> TOOL CALLED for user {user_context.user_id}")

            # Use UserContext method
            recipes = await user_context.get_makeable_recipes(limit=10)

            print(f"[DEBUG Tool:get_makeable_recipes] raw recipes from UserContext: {recipes}")

            # Apply additional filters if specified
            if min_protein is not None or max_calories is not None:
                filtered = []
                for recipe in recipes:
                    protein = recipe.get("protein_g", 0)
                    calories = recipe.get("calories", 0)

                    if min_protein is not None and protein < min_protein:
                        continue
                    if max_calories is not None and calories > max_calories:
                        continue

                    filtered.append(recipe)
                recipes = filtered

            result = {
                "recipes": recipes,
                "count": len(recipes),
                "filters_applied": {
                    "min_protein": min_protein,
                    "max_calories": max_calories
                }
            }

            json_output = json.dumps(result, indent=2)
            print(f"[DEBUG Tool:get_makeable_recipes] JSON returned to LLM:\n{json_output}")
            return json_output

        except Exception as e:
            logger.error(f"[Tool:get_makeable_recipes] Error: {e}", exc_info=True)
            print(f"[DEBUG Tool:get_makeable_recipes] EXCEPTION: {e}")
            return json.dumps({"error": str(e)})

    @tool
    async def get_goal_aligned_recipes(
        count: int = 5,
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Get recipes aligned with user's nutrition goals.

        Args:
            count: Number of recipes to return (default 5)

        Returns:
            JSON string with goal-aligned recipes
        """
        try:
            user_context = runtime.context.user_context
            logger.info(f"[Tool:get_goal_aligned_recipes] Called for user {user_context.user_id}")

            # Use UserContext method
            recipes = await user_context.get_goal_aligned_recipes(count=count)

            # Get goal type for response
            profile = await user_context._get_profile_basic()
            goal_type = profile.get("goal_type", "general_health")

            result = {
                "recipes": recipes,
                "count": len(recipes),
                "goal": goal_type
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_goal_aligned_recipes] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def get_consumption_history(
        days: int = 7,
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Get consumption history and trends for the past N days.

        Args:
            days: Number of days to look back (default 7, max 30).

        Returns:
            JSON string with daily totals, average macros, adherence rate, and trends
        """
        try:
            user_context = runtime.context.user_context
            days = min(days, 30)
            logger.info(f"[Tool:get_consumption_history] Called for user {user_context.user_id}, days={days}")

            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            daily_totals = await user_context.analytics_repo.get_daily_totals(
                user_context.user_id, start_date, end_date
            )
            trends = await user_context.analytics_repo.get_consumption_trends(
                user_context.user_id, days=days
            )

            result = {
                "period_days": days,
                "daily_totals": daily_totals[:days] if daily_totals else [],
                "averages": {
                    "avg_daily_calories": trends.get("avg_daily_calories", 0) if trends else 0,
                    "avg_daily_protein": trends.get("avg_daily_protein", 0) if trends else 0,
                    "avg_daily_carbs": trends.get("avg_daily_carbs", 0) if trends else 0,
                    "avg_daily_fat": trends.get("avg_daily_fat", 0) if trends else 0,
                },
                "adherence_rate": trends.get("adherence_rate", 0) if trends else 0,
            }

            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            logger.error(f"[Tool:get_consumption_history] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def get_expiring_items(
        days_threshold: int = 3,
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Get inventory items that are expiring soon or already expired.

        Args:
            days_threshold: Number of days to look ahead for expiring items (default 3).

        Returns:
            JSON string with expiring items, their quantities, days remaining, and categories
        """
        try:
            user_context = runtime.context.user_context
            logger.info(f"[Tool:get_expiring_items] Called for user {user_context.user_id}, days={days_threshold}")

            expiring = await user_context.inventory_repo.get_expiring_items(
                user_context.user_id, days_threshold=days_threshold
            )

            items = []
            today = date.today()
            for item in expiring:
                days_remaining = (item.expiry_date.date() - today).days if item.expiry_date else None
                items.append({
                    "name": item.item.canonical_name if item.item else "Unknown",
                    "quantity_grams": item.quantity_grams,
                    "expiry_date": str(item.expiry_date.date()) if item.expiry_date else None,
                    "days_remaining": days_remaining,
                    "status": "expired" if days_remaining is not None and days_remaining < 0 else "expiring_soon",
                    "category": item.item.category if item.item else None,
                })

            result = {
                "days_threshold": days_threshold,
                "expiring_count": len(items),
                "items": items,
            }

            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            logger.error(f"[Tool:get_expiring_items] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def get_weekly_summary(
        *,
        runtime: ToolRuntime[NutritionContextSchema]
    ) -> str:
        """Get weekly nutrition summary with trends, adherence, and meal patterns.

        Returns:
            JSON string with weekly averages, adherence rate, meal completion stats, and trends
        """
        try:
            user_context = runtime.context.user_context
            logger.info(f"[Tool:get_weekly_summary] Called for user {user_context.user_id}")

            trends = await user_context.analytics_repo.get_consumption_trends(
                user_context.user_id, days=7
            )
            meal_stats = await user_context.analytics_repo.get_meal_completion_stats(
                user_context.user_id, days=7
            )
            adherence = await user_context.tracking_repo.get_adherence_rate(
                user_context.user_id, days=7
            )

            result = {
                "period": "last_7_days",
                "averages": {
                    "avg_daily_calories": trends.get("avg_daily_calories", 0) if trends else 0,
                    "avg_daily_protein": trends.get("avg_daily_protein", 0) if trends else 0,
                    "avg_daily_carbs": trends.get("avg_daily_carbs", 0) if trends else 0,
                    "avg_daily_fat": trends.get("avg_daily_fat", 0) if trends else 0,
                },
                "adherence_rate": adherence if adherence else 0,
                "meal_completion": meal_stats if meal_stats else {},
            }

            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            logger.error(f"[Tool:get_weekly_summary] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    return [
        get_nutrition_stats,
        check_inventory,
        get_meal_plan,
        get_makeable_recipes,
        get_goal_aligned_recipes,
        get_consumption_history,
        get_expiring_items,
        get_weekly_summary,
    ]


# ============================================================================
# GRAPH NODES
# ============================================================================

async def load_context_node(
    state: NutritionState,
    runtime: Runtime[NutritionContextSchema]
) -> Dict[str, Any]:
    """
    Load user context using UserContext from runtime.

    Pre-loads profile AND today's consumption summary so the system prompt
    can include current progress. This eliminates the most common tool call
    (~60% of queries ask about today's progress).
    """
    user_id = state["user_id"]
    logger.info(f"[Node:load_context] User {user_id}, turn {state.get('turn_count', 0) + 1}")

    try:
        user_context = runtime.context.user_context

        profile = await user_context._get_profile_basic()
        today = await user_context._get_today_consumption()
        targets = await user_context._get_targets()

        minimal_context = {
            "user_id": user_id,
            "goal_type": profile.get("goal_type", "general_health"),
            "activity_level": profile.get("activity_level", "moderate"),
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_time": datetime.now().strftime("%H:%M"),
            "calories_consumed": today.get("consumed", {}).get("calories", 0),
            "calories_target": targets.get("calories", 2000),
            "protein_consumed": today.get("consumed", {}).get("protein_g", 0),
            "protein_target": targets.get("protein_g", 100),
            "meals_consumed": today.get("meals_consumed", 0),
            "meals_pending": today.get("meals_pending", 0),
        }

        logger.info(f"[Node:load_context] Loaded: goal={minimal_context['goal_type']}, "
                     f"cal={minimal_context['calories_consumed']}/{minimal_context['calories_target']}")

        return {
            "user_context": minimal_context,
            "turn_count": state.get("turn_count", 0) + 1
        }

    except Exception as e:
        logger.error(f"[Node:load_context] Error: {e}", exc_info=True)
        return {
            "user_context": {"error": str(e)},
            "turn_count": state.get("turn_count", 0) + 1
        }


async def trim_messages_node(state: NutritionState) -> Dict[str, Any]:
    """
    Trim messages to fit context window.

    Always returns {"llm_input_messages": ...} following official LangGraph pattern.
    This ensures generate_response_node always has messages to work with.
    """

    messages = state.get("messages", [])
    original_count = len(messages)

    MAX_MESSAGES_THRESHOLD = 12
    MAX_MESSAGES = 10

    if original_count > MAX_MESSAGES_THRESHOLD:
        trimmed = trim_messages(
            messages,
            strategy="last",
            token_counter=len,
            max_tokens=MAX_MESSAGES,
            start_on="human",
            end_on=("human", "tool"),
            include_system=False,
        )
        logger.info(f"[Node:trim_messages] Trimmed: {original_count} → {len(trimmed)} messages")
        return {"llm_input_messages": trimmed}
    else:
        logger.debug(f"[Node:trim_messages] No trimming needed ({original_count} messages)")
        return {"llm_input_messages": messages}


# Default daily token limit (from settings or fallback)
DEFAULT_DAILY_TOKEN_LIMIT = getattr(settings, "daily_token_limit", 100000)
MAX_OUTPUT_TOKENS = 1000  # Conservative estimate for chat responses


def _estimate_input_tokens(messages: List) -> int:
    """
    Rough estimate of input tokens from messages.

    Uses ~4 chars per token approximation (conservative).
    """
    total_chars = 0
    for msg in messages:
        content = getattr(msg, 'content', str(msg))
        total_chars += len(content) if content else 0
    return total_chars // 4 + 50  # +50 for message overhead


async def generate_response_node(
    state: NutritionState,
    runtime: Runtime[NutritionContextSchema]
) -> Dict[str, Any]:
    """
    Generate response using LLM with tools.

    Includes token governance:
    1. Reserve tokens before LLM call (pessimistic)
    2. Track actual usage from response metadata
    3. Refund unused tokens after call
    """
    logger.info("[Node:generate_response] Starting")

    user_id = state["user_id"]
    governor = runtime.context.governor
    prompt_registry = runtime.context.prompt_registry
    reservation = 0

    try:
        context = state.get("user_context", {})

        # Get module-level LLM with tools (created once, reused)
        llm = _get_llm_with_tools()

        # Build prompt variables from pre-loaded context
        prompt_variables = {
            "current_date": context.get('current_date', 'unknown'),
            "current_time": context.get('current_time', 'unknown'),
            "user_id": str(user_id),
            "goal_type": context.get('goal_type', 'general_health'),
            "activity_level": context.get('activity_level', 'moderate'),
            "calories_consumed": context.get('calories_consumed', 0),
            "calories_target": context.get('calories_target', 2000),
            "protein_consumed": context.get('protein_consumed', 0),
            "protein_target": context.get('protein_target', 100),
            "meals_consumed": context.get('meals_consumed', 0),
            "meals_pending": context.get('meals_pending', 0),
        }

        # Try hot-reloadable prompt from registry, fall back to hardcoded
        try:
            rendered_messages, _ = await prompt_registry.get_rendered_prompt(
                slug="nutrition_chat_system",
                variables=prompt_variables
            )
            system_prompt = rendered_messages[0]["content"]
            print(f"System prompt loaded from registry:\n{system_prompt}\n")
            logger.info(f"[Node:generate_response] ✅ System prompt loaded from registry ({len(system_prompt)} chars)")
        except (KeyError, Exception) as e:
            logger.warning(f"[Node:generate_response] Prompt registry unavailable ({type(e).__name__}), using fallback")
            system_prompt = (
                f"You are NutriLens, a personal nutrition assistant. "
                f"Today is {prompt_variables['current_date']} at {prompt_variables['current_time']}.\n\n"
                f"# User Profile\n"
                f"- Goal: {prompt_variables['goal_type']}\n"
                f"- Activity Level: {prompt_variables['activity_level']}\n"
                f"- Today's Progress: {prompt_variables['calories_consumed']}/{prompt_variables['calories_target']} cal, "
                f"{prompt_variables['protein_consumed']}g/{prompt_variables['protein_target']}g protein\n"
                f"- Meals: {prompt_variables['meals_consumed']} consumed, {prompt_variables['meals_pending']} pending\n\n"
                f"# Your Capabilities\n"
                f"You help users understand their nutrition data, meal plans, inventory, and provide dietary guidance. "
                f"Use your tools to fetch real data before answering data-dependent questions. "
                f"For general nutrition knowledge questions, use your training knowledge directly.\n\n"
                f"# Rules\n"
                f"1. Use tools to FETCH the user's data (stats, inventory, meal plans). Never guess numbers.\n"
                f"2. For creative or generative tasks (recipe suggestions, meal ideas, dietary advice), "
                f"use your own knowledge. Combine it with any user data already available in the conversation.\n"
                f"3. If the user's question is ambiguous, ask for clarification instead of guessing.\n"
                f"4. Keep responses concise and conversational (2-5 sentences for data queries).\n"
                f"5. Never provide medical advice. Recommend consulting a healthcare professional.\n"
                f"6. When presenting data, highlight metrics most relevant to the user's goal.\n"
                f"7. If a tool returns an error or empty results, use your own knowledge with available context."
            )
            
        # Get conversation messages (refreshed by trim_messages_node on every iteration,
        # including after tool results, via the tools → trim_messages edge)
        conversation_messages = state["llm_input_messages"]

        # Build final messages list
        messages = [SystemMessage(content=system_prompt)] + list(conversation_messages)

        # GOVERNANCE STEP 1: Estimate and reserve tokens
        estimated_input = _estimate_input_tokens(messages)
        reservation = estimated_input + MAX_OUTPUT_TOKENS

        allowed = await governor.reserve(user_id, reservation, DEFAULT_DAILY_TOKEN_LIMIT)
        if not allowed:
            logger.warning(f"[Node:generate_response] Token budget exceeded for user {user_id}")
            error_msg = AIMessage(content="You've reached your daily chat limit. Please try again tomorrow.")
            return {"messages": [error_msg]}

        logger.info(f"[Node:generate_response] Reserved {reservation} tokens, calling LLM with {len(messages)} messages")

        # GOVERNANCE STEP 2: Make LLM call
        print(f"\n[DEBUG generate_response] Sending {len(messages)} messages to LLM")
        print(f"[DEBUG generate_response] User query: {messages[-1].content if messages else 'N/A'}")
        response = await llm.ainvoke(messages)

        # GOVERNANCE STEP 3: Get actual usage and refund
        token_usage = response.response_metadata.get("token_usage", {})
        actual_tokens = token_usage.get("total_tokens", 0)

        if actual_tokens > 0:
            refund_amount = reservation - actual_tokens
            if refund_amount > 0:
                await governor.refund(user_id, refund_amount)
                logger.debug(f"[Node:generate_response] Actual={actual_tokens}, refunded={refund_amount}")

        tool_calls = response.tool_calls if hasattr(response, 'tool_calls') and response.tool_calls else []
        tool_calls_count = len(tool_calls)
        logger.info(f"[Node:generate_response] Response generated, tool_calls={tool_calls_count}, tokens={actual_tokens}")

        if tool_calls:
            print(f"[DEBUG generate_response] LLM decided to call tools: {[tc['name'] for tc in tool_calls]}")
            for tc in tool_calls:
                print(f"  tool={tc['name']}, args={tc.get('args', {})}")
        else:
            print(f"[DEBUG generate_response] LLM did NOT call any tools — responding directly")
            print(f"[DEBUG generate_response] LLM response content: {response.content[:300] if response.content else '(empty)'}")

        return {"messages": [response]}

    except Exception as e:
        # Full refund on failure
        if reservation > 0:
            await governor.refund(user_id, reservation)
            logger.debug(f"[Node:generate_response] Error occurred, refunded {reservation} tokens")

        logger.error(f"[Node:generate_response] Error: {e}", exc_info=True)
        error_msg = AIMessage(content="I'm having trouble processing that. Could you try again?")
        return {"messages": [error_msg]}


def should_continue(state: NutritionState) -> Literal["tools", "end"]:
    """Route to tools if there are tool calls, else end."""
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info("[Router] Tool calls detected, routing to tools")
        return "tools"

    logger.info("[Router] No tool calls, ending")
    return "end"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_nutrition_graph_structure() -> StateGraph:
    """
    Create the nutrition graph with context_schema for dependency injection.

    Flow:
        load_context → trim_messages → generate_response
                                            ↓
                                   [has tool calls?]
                                      ↓ yes     ↓ no
                                   ToolNode    END
                                      ↓
                                generate_response (loop)
    """
    # Get module-level tools (created once, reused)
    tools = _get_read_tools()

    # Create graph with context_schema for DI
    workflow = StateGraph(
        NutritionState,
        context_schema=NutritionContextSchema
    )

    # Add nodes
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("trim_messages", trim_messages_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("tools", ToolNode(tools))

    # Define flow
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "trim_messages")
    workflow.add_edge("trim_messages", "generate_response")

    # Conditional: tools or end
    workflow.add_conditional_edges(
        "generate_response",
        should_continue,
        {"tools": "tools", "end": END}
    )

    # After tools, re-trim before next LLM call (mirrors pre_model_hook pattern).
    # This ensures llm_input_messages includes tool results from the current iteration.
    workflow.add_edge("tools", "trim_messages")

    logger.info("[Graph] Nutrition graph created with context_schema and standard ToolNode")

    return workflow