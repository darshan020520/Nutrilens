from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List, Literal
from dataclasses import dataclass
import operator
from langgraph.graph import StateGraph, END
from langgraph.runtime import Runtime
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.types import interrupt
from langgraph.errors import GraphInterrupt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.messages.utils import trim_messages
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import json
import logging
from datetime import datetime, date
from app.core.ist_datetime import today_ist

from app.core.config import settings
from app.agents.nutrition_context import UserContext
from app.infrastructure.normalization.interfaces import ITokenGovernor, IPromptRegistry
from app.orchestrators.meal_logging_orchestrator import MealLoggingOrchestrator
from app.services.external_meal_service import ExternalMealService

logger = logging.getLogger(__name__)


# ============================================================================
# MODULE-LEVEL LLM CLIENT (Created once, reused for all requests)
# ============================================================================

_whatsapp_tools = None
_whatsapp_llm = None


def _get_whatsapp_tools():
    """Lazy initialization of WhatsApp tools."""
    global _whatsapp_tools
    if _whatsapp_tools is None:
        _whatsapp_tools = create_whatsapp_tools()
        logger.info("[WhatsApp] Tools initialized (singleton)")
    return _whatsapp_tools


def _get_whatsapp_llm():
    """Lazy initialization of LLM with WhatsApp tools."""
    global _whatsapp_llm
    if _whatsapp_llm is None:
        tools = _get_whatsapp_tools()
        _whatsapp_llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.3,
            api_key=settings.openai_api_key
        ).bind_tools(tools)
        logger.info("[WhatsApp] ChatOpenAI with tools initialized (singleton)")
    return _whatsapp_llm


# ============================================================================
# CONTEXT SCHEMA - Dependency Injection Container
# ============================================================================

@dataclass
class WhatsAppContextSchema:
    """
    Context schema for WhatsApp bot dependency injection.

    Extends the nutrition bot pattern with write-operation dependencies:
    - MealLoggingOrchestrator for planned meal logging
    - ExternalMealService for external meal estimation + logging
    """
    user_context: UserContext
    governor: ITokenGovernor
    prompt_registry: IPromptRegistry
    meal_orchestrator: MealLoggingOrchestrator
    external_meal_service: ExternalMealService


# ============================================================================
# STATE SCHEMA
# ============================================================================

class WhatsAppState(TypedDict):
    """State for WhatsApp bot."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    llm_input_messages: Optional[Sequence[BaseMessage]]
    user_context: Dict[str, Any]
    user_id: int
    thread_id: str
    turn_count: int


# ============================================================================
# TOOLS (4 read + 2 write with interrupt)
# ============================================================================

def create_whatsapp_tools() -> List:
    """Create all WhatsApp bot tools (4 read + 2 write)."""

    # ---- READ TOOLS ----

    @tool
    async def get_meal_plan(
        target_date: Optional[str] = None,
        *,
        runtime: ToolRuntime[WhatsAppContextSchema]
    ) -> str:
        """Get meal plan for a specific date. Each meal includes an 'id' field needed for logging.

        Args:
            target_date: Date in YYYY-MM-DD format. If empty, returns today's plan.
        """
        try:
            user_context = runtime.context.user_context
            plan_date = date.fromisoformat(target_date) if target_date else today_ist()
            meal_logs = await user_context.tracking_repo.get_by_date(
                user_context.user_id, plan_date, active_plans_only=True
            )

            meals = []
            for meal in meal_logs:
                ext = meal.external_meal or {}
                if meal.recipe:
                    name = meal.recipe.title
                    macros = meal.recipe.macros_per_serving or {}
                elif ext:
                    name = ext.get("dish_name", "External meal")
                    macros = {"calories": ext.get("calories", 0), "protein_g": ext.get("protein_g", 0)}
                else:
                    name = "No recipe"
                    macros = {}

                meals.append({
                    "id": meal.id,
                    "meal_type": meal.meal_type,
                    "recipe": name,
                    "time": meal.planned_datetime.strftime("%H:%M") if meal.planned_datetime else "",
                    "status": "consumed" if meal.consumed_datetime else ("skipped" if meal.was_skipped else "pending"),
                    "calories": macros.get("calories", 0),
                    "protein_g": macros.get("protein_g", 0)
                })

            return json.dumps({"date": str(plan_date), "meals": meals, "count": len(meals)}, indent=2)
        except Exception as e:
            logger.error(f"[WA:get_meal_plan] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def get_nutrition_stats(
        *,
        runtime: ToolRuntime[WhatsAppContextSchema]
    ) -> str:
        """Get current nutrition statistics for today including consumed, targets, and remaining macros."""
        try:
            user_context = runtime.context.user_context
            today_data = await user_context._get_today_consumption()
            targets = await user_context._get_targets()

            return json.dumps({
                "consumed": today_data.get("consumed", {}),
                "targets": targets,
                "remaining": today_data.get("remaining", {}),
                "compliance_rate": today_data.get("compliance_rate", 0),
                "meals_consumed": today_data.get("meals_consumed", 0),
                "meals_pending": today_data.get("meals_pending", 0)
            }, indent=2)
        except Exception as e:
            logger.error(f"[WA:get_nutrition_stats] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def check_inventory(
        *,
        runtime: ToolRuntime[WhatsAppContextSchema]
    ) -> str:
        """Check user's food inventory with item names, quantities, and expiry dates."""
        try:
            user_context = runtime.context.user_context
            summary = await user_context._get_inventory_summary()
            raw_items = await user_context.inventory_repo.get_all_for_user(
                user_context.user_id, include_zero_quantity=False
            )
            item_list = [
                {
                    "name": inv.item.canonical_name if inv.item else "Unknown",
                    "quantity_grams": inv.quantity_grams,
                    "expiry_date": str(inv.expiry_date.date()) if inv.expiry_date else None
                }
                for inv in raw_items
            ]
            return json.dumps({**summary, "items": item_list}, indent=2)
        except Exception as e:
            logger.error(f"[WA:check_inventory] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def get_expiring_items(
        days_threshold: int = 3,
        *,
        runtime: ToolRuntime[WhatsAppContextSchema]
    ) -> str:
        """Get inventory items expiring soon or already expired.

        Args:
            days_threshold: Days to look ahead for expiring items (default 3).
        """
        try:
            user_context = runtime.context.user_context
            expiring = await user_context.inventory_repo.get_expiring_items(
                user_context.user_id, days_threshold=days_threshold
            )
            today = date.today()
            items = []
            for item in expiring:
                days_remaining = (item.expiry_date.date() - today).days if item.expiry_date else None
                items.append({
                    "name": item.item.canonical_name if item.item else "Unknown",
                    "quantity_grams": item.quantity_grams,
                    "expiry_date": str(item.expiry_date.date()) if item.expiry_date else None,
                    "days_remaining": days_remaining,
                    "status": "expired" if days_remaining is not None and days_remaining < 0 else "expiring_soon"
                })
            return json.dumps({
                "days_threshold": days_threshold,
                "expiring_count": len(items),
                "items": items
            }, indent=2)
        except Exception as e:
            logger.error(f"[WA:get_expiring_items] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    # ---- WRITE TOOLS (with interrupt for HITL confirmation) ----

    @tool
    async def log_planned_meal(
        meal_log_id: int,
        *,
        runtime: ToolRuntime[WhatsAppContextSchema]
    ) -> str:
        """Log a planned meal as consumed. Requires user confirmation before executing.
        Use get_meal_plan first to find the meal's ID, then call this tool with that ID.

        Args:
            meal_log_id: The ID of the meal log entry to mark as consumed.
        """
        user_context = runtime.context.user_context
        user_id = user_context.user_id
        logger.info(f"[WA:log_planned_meal] user={user_id}, meal_log_id={meal_log_id}")

        try:
            # Fetch meal details for confirmation preview (idempotent on re-execution)
            meal_logs = await user_context.tracking_repo.get_by_date(user_id, today_ist(), active_plans_only=True)
            meal = next((m for m in meal_logs if m.id == meal_log_id), None)

            if not meal:
                return json.dumps({"error": f"Meal log {meal_log_id} not found for today"})
            if meal.consumed_datetime:
                name = meal.recipe.title if meal.recipe else "Unknown"
                return json.dumps({"error": f"'{name}' is already logged as consumed"})

            macros = meal.recipe.macros_per_serving or {} if meal.recipe else {}
            summary = {
                "meal_log_id": meal_log_id,
                "meal_type": meal.meal_type,
                "recipe": meal.recipe.title if meal.recipe else "Unknown",
                "calories": macros.get("calories", 0),
                "protein_g": macros.get("protein_g", 0)
            }

            # HITL: pause graph, webhook sends confirmation to user
            confirmation = interrupt({
                "action": "log_planned_meal",
                "message": (
                    f"Log '{summary['recipe']}' ({summary['meal_type']}) as consumed?\n"
                    f"{summary['calories']} cal, {summary['protein_g']}g protein\n"
                    f"Reply 'yes' to confirm or 'no' to cancel."
                ),
                "summary": summary
            })

            if confirmation == "approve":
                orchestrator = runtime.context.meal_orchestrator
                result = await orchestrator.log_planned_meal(user_id=user_id, meal_log_id=meal_log_id)
                if result.get("success"):
                    daily = result.get("daily_summary", {})
                    return json.dumps({
                        "success": True,
                        "message": f"Logged '{summary['recipe']}' as consumed",
                        "daily_calories": daily.get("total_calories", 0),
                        "daily_protein_g": daily.get("total_protein_g", 0)
                    })
                else:
                    return json.dumps({"success": False, "error": result.get("error", "Failed to log meal")})
            else:
                return json.dumps({"success": False, "message": "Meal logging cancelled"})

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"[WA:log_planned_meal] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    async def log_external_meal(
        meal_type: str,
        dish_name: str,
        portion_size: str,
        restaurant_name: Optional[str] = None,
        meal_log_id_to_replace: Optional[int] = None,
        *,
        runtime: ToolRuntime[WhatsAppContextSchema]
    ) -> str:
        """Log an external meal (eaten outside or different from the meal plan).

        Call this ONLY after asking the user:
        1. What dish they ate and roughly how much (portion size).
        2. Whether it was INSTEAD OF their planned meal (pass meal_log_id_to_replace)
           or an EXTRA/ADDITIONAL meal (leave meal_log_id_to_replace empty).

        To get meal_log_id_to_replace: call get_meal_plan first, find the pending
        meal of the matching meal_type, and pass its id here.

        Args:
            meal_type: Type of meal (breakfast, lunch, dinner, snack).
            dish_name: Name of the dish (e.g., 'cheese pizza').
            portion_size: Portion description (e.g., '2 slices', '1 plate').
            restaurant_name: Optional restaurant name for better estimation.
            meal_log_id_to_replace: ID of the planned meal log this replaces.
                Pass this when the user ate this INSTEAD OF a planned meal.
                Leave empty when this is an extra meal with no planned equivalent.
        """
        user_context = runtime.context.user_context
        user_id = user_context.user_id
        logger.info(f"[WA:log_external_meal] user={user_id}, dish={dish_name}, replace_id={meal_log_id_to_replace}")

        try:
            # Estimate nutrition (re-runs on resume — acceptable cost)
            external_service = runtime.context.external_meal_service
            estimation = await external_service.estimate_nutrition(
                user_id=user_id,
                dish_name=dish_name,
                portion_size=portion_size,
                restaurant_name=restaurant_name
            )

            summary = {
                "dish_name": dish_name,
                "portion_size": portion_size,
                "restaurant": restaurant_name,
                "calories": estimation.get("calories", 0),
                "protein_g": estimation.get("protein_g", 0),
                "carbs_g": estimation.get("carbs_g", 0),
                "fat_g": estimation.get("fat_g", 0),
                "confidence": estimation.get("confidence", "unknown")
            }

            replacing_note = f" (replaces planned {meal_type})" if meal_log_id_to_replace else ""

            # HITL: pause graph, webhook sends confirmation to user
            confirmation = interrupt({
                "action": "log_external_meal",
                "message": (
                    f"Log '{dish_name}' ({portion_size}){replacing_note}?\n"
                    f"Estimated: {summary['calories']} cal, "
                    f"{summary['protein_g']}g protein, "
                    f"{summary['carbs_g']}g carbs, "
                    f"{summary['fat_g']}g fat\n"
                    f"Confidence: {summary['confidence']}\n"
                    f"Reply 'yes' to confirm or 'no' to cancel."
                ),
                "summary": summary
            })

            if confirmation == "approve":
                orchestrator = runtime.context.meal_orchestrator
                meal_data = {
                    "dish_name": dish_name,
                    "portion_size": portion_size,
                    "restaurant_name": restaurant_name,
                    **estimation
                }
                result = await orchestrator.log_external_meal_workflow(
                    user_id=user_id,
                    meal_data=meal_data,
                    meal_type=meal_type,
                    meal_log_id_to_replace=meal_log_id_to_replace
                )
                if result.get("success"):
                    return json.dumps({
                        "success": True,
                        "message": f"Logged '{dish_name}'",
                        "macros": result.get("macros", {}),
                        "remaining_calories": result.get("remaining_calories", 0)
                    })
                else:
                    return json.dumps({"success": False, "error": result.get("error", "Failed to log meal")})
            else:
                return json.dumps({"success": False, "message": "External meal logging cancelled"})

        except GraphInterrupt:
            raise
        except Exception as e:
            logger.error(f"[WA:log_external_meal] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    return [
        get_meal_plan,
        get_nutrition_stats,
        check_inventory,
        get_expiring_items,
        log_planned_meal,
        log_external_meal,
    ]


# ============================================================================
# GRAPH NODES
# ============================================================================

async def load_context_node(
    state: WhatsAppState,
    runtime: Runtime[WhatsAppContextSchema]
) -> Dict[str, Any]:
    """Load user context (profile + today's progress) for system prompt."""
    user_id = state["user_id"]
    logger.info(f"[WA:load_context] User {user_id}, turn {state.get('turn_count', 0) + 1}")

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

        logger.info(f"[WA:load_context] Loaded: goal={minimal_context['goal_type']}, "
                     f"cal={minimal_context['calories_consumed']}/{minimal_context['calories_target']}")

        return {
            "user_context": minimal_context,
            "turn_count": state.get("turn_count", 0) + 1
        }

    except Exception as e:
        logger.error(f"[WA:load_context] Error: {e}", exc_info=True)
        return {
            "user_context": {"error": str(e)},
            "turn_count": state.get("turn_count", 0) + 1
        }


async def trim_messages_node(state: WhatsAppState) -> Dict[str, Any]:
    """Trim messages to fit context window."""
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
        logger.info(f"[WA:trim_messages] Trimmed: {original_count} -> {len(trimmed)} messages")
        return {"llm_input_messages": trimmed}
    else:
        logger.debug(f"[WA:trim_messages] No trimming needed ({original_count} messages)")
        return {"llm_input_messages": messages}


DEFAULT_DAILY_TOKEN_LIMIT = getattr(settings, "daily_token_limit", 100000)
MAX_OUTPUT_TOKENS = 500  # WhatsApp responses are shorter than web


def _estimate_input_tokens(messages: List) -> int:
    """Rough estimate: ~4 chars per token + overhead."""
    total_chars = 0
    for msg in messages:
        content = getattr(msg, 'content', str(msg))
        total_chars += len(content) if content else 0
    return total_chars // 4 + 50


async def generate_response_node(
    state: WhatsAppState,
    runtime: Runtime[WhatsAppContextSchema]
) -> Dict[str, Any]:
    """Generate response using LLM with tools and token governance."""
    logger.info("[WA:generate_response] Starting")

    user_id = state["user_id"]
    governor = runtime.context.governor
    prompt_registry = runtime.context.prompt_registry
    reservation = 0

    try:
        context = state.get("user_context", {})
        llm = _get_whatsapp_llm()

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
                slug="whatsapp_chat_system",
                variables=prompt_variables
            )
            system_prompt = rendered_messages[0]["content"]
            logger.info(f"[WA:generate_response] System prompt from registry ({len(system_prompt)} chars)")
        except (KeyError, Exception) as e:
            logger.warning(f"[WA:generate_response] Prompt registry unavailable ({type(e).__name__}), using fallback")
            system_prompt = (
                f"You are NutriLens WhatsApp Assistant. "
                f"Today is {prompt_variables['current_date']} at {prompt_variables['current_time']}.\n\n"
                f"# User Profile\n"
                f"- Goal: {prompt_variables['goal_type']}\n"
                f"- Today: {prompt_variables['calories_consumed']}/{prompt_variables['calories_target']} cal, "
                f"{prompt_variables['protein_consumed']}g/{prompt_variables['protein_target']}g protein\n"
                f"- Meals: {prompt_variables['meals_consumed']} consumed, {prompt_variables['meals_pending']} pending\n\n"
                f"# Your Capabilities\n"
                f"You help users via WhatsApp with:\n"
                f"- Checking meal plans and nutrition stats\n"
                f"- Checking inventory and expiring items\n"
                f"- Logging planned meals as consumed\n"
                f"- Logging external meals (eaten outside)\n\n"
                f"# Rules\n"
                f"1. Keep responses SHORT and conversational (WhatsApp style, 1-3 sentences).\n"
                f"2. Use tools to fetch data. Never guess the user's numbers.\n"
                f"3. For meal logging, use the appropriate tool. The system handles confirmation.\n"
                f"4. When the user says they ate something from their plan, first call get_meal_plan "
                f"to find the meal ID, then call log_planned_meal with that ID.\n"
                f"5. When the user mentions eating something external (restaurant, outside food), "
                f"use log_external_meal.\n"
                f"6. If ambiguous whether planned or external, ask the user to clarify.\n"
                f"7. Do not use markdown formatting. Use plain text only.\n"
                f"8. Use emojis sparingly for friendliness."
            )

        conversation_messages = state["llm_input_messages"]
        messages = [SystemMessage(content=system_prompt)] + list(conversation_messages)

        # Token governance: reserve -> call -> refund
        estimated_input = _estimate_input_tokens(messages)
        reservation = estimated_input + MAX_OUTPUT_TOKENS

        allowed = await governor.reserve(user_id, reservation, DEFAULT_DAILY_TOKEN_LIMIT)
        if not allowed:
            logger.warning(f"[WA:generate_response] Token budget exceeded for user {user_id}")
            return {"messages": [AIMessage(content="You've reached your daily chat limit. Please try again tomorrow.")]}

        logger.info(f"[WA:generate_response] Reserved {reservation} tokens, calling LLM")
        response = await llm.ainvoke(messages)

        # Refund unused tokens
        token_usage = response.response_metadata.get("token_usage", {})
        actual_tokens = token_usage.get("total_tokens", 0)
        if actual_tokens > 0:
            refund = reservation - actual_tokens
            if refund > 0:
                await governor.refund(user_id, refund)

        tool_calls_count = len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0
        logger.info(f"[WA:generate_response] Response generated, tool_calls={tool_calls_count}, tokens={actual_tokens}")

        return {"messages": [response]}

    except Exception as e:
        if reservation > 0:
            await governor.refund(user_id, reservation)
        logger.error(f"[WA:generate_response] Error: {e}", exc_info=True)
        return {"messages": [AIMessage(content="Sorry, I had trouble processing that. Please try again.")]}


def should_continue(state: WhatsAppState) -> Literal["tools", "end"]:
    """Route to tools if there are tool calls, else end."""
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info("[WA:router] Tool calls detected, routing to tools")
        return "tools"

    logger.info("[WA:router] No tool calls, ending")
    return "end"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_whatsapp_graph_structure() -> StateGraph:
    """
    Create the WhatsApp graph with context_schema for DI.

    Flow:
        load_context -> trim_messages -> generate_response
                                              |
                                     [has tool calls?]
                                      yes |      | no
                                       ToolNode  END
                                          |
                                     trim_messages (loop)
    """
    tools = _get_whatsapp_tools()

    workflow = StateGraph(
        WhatsAppState,
        context_schema=WhatsAppContextSchema
    )

    workflow.add_node("load_context", load_context_node)
    workflow.add_node("trim_messages", trim_messages_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("tools", ToolNode(tools))

    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "trim_messages")
    workflow.add_edge("trim_messages", "generate_response")

    workflow.add_conditional_edges(
        "generate_response",
        should_continue,
        {"tools": "tools", "end": END}
    )

    workflow.add_edge("tools", "trim_messages")

    logger.info("[WhatsApp] Graph structure created (6 tools, single ToolNode)")

    return workflow