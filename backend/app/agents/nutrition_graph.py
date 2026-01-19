# backend/app/agents/nutrition_graph.py
"""
Production LangGraph Implementation for Nutrition Intelligence Agent

Architecture:
1. load_context → Fetch latest user data from DB
2. classify_intent → LLM classifies user query intent
3. generate_response → LLM with tools generates response
4. [Conditional] → Tools execution if LLM calls them
5. [Loop back] → LLM synthesizes final answer from tool results

Features:
- Stateful conversations with MongoDB checkpointing
- Tool-based actions (log meals, swap recipes, query data)
- Conversation memory across sessions
- Production-ready error handling
- Compatible with existing API

Author: NutriLens AI Team
Created: 2025-01-11
"""

from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List, Literal
import operator
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session
import json
import time
import logging
from datetime import datetime, date

from app.core.config import settings
from app.core.mongodb import save_chat_message, get_mongo_sync_client
from app.agents.nutrition_context import UserContext
from app.services.consumption_services import ConsumptionService
from app.services.meal_plan_service import MealPlanService
from app.services.inventory_service import IntelligentInventoryService

logger = logging.getLogger(__name__)


# ============================================================================
# STATE SCHEMA
# ============================================================================

class NutritionState(TypedDict):
    """
    Agent state - persisted to MongoDB via checkpointing.

    Follows LangGraph best practice: Simple state with only essential data.

    REFACTORED (2025-01): Added fields for:
    - Pre-fetched data (replaces read tool calls)
    - HITL confirmation workflow
    - Clarification mode
    - Structured error handling
    """
    # Messages (automatically appended by operator.add)
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # Trimmed messages for LLM input (not persisted, recalculated each turn)
    llm_input_messages: Optional[Sequence[BaseMessage]]

    # User context (refreshed each turn)
    user_context: Dict[str, Any]

    # Intent classification
    intent: Optional[str]
    confidence: float
    entities: Dict[str, Any]

    # Session tracking
    user_id: int
    session_id: str
    turn_count: int

    # Metrics
    processing_time_ms: float
    cost_usd: float

    # === NEW FIELDS (Refactoring 2025-01) ===

    # Pre-fetched data based on intent (replaces read tool calls)
    fetched_data: Dict[str, Any]

    # Human-in-the-loop fields for write operations
    pending_tool_call: Optional[Dict[str, Any]]  # {name, args, id, message}
    requires_confirmation: bool
    user_confirmation: Optional[str]  # Response from interrupt ("approved"/"declined")

    # Clarification mode (when intent confidence is low)
    clarification_mode: bool

    # Error context for friendly error messages
    fetch_error: Optional[Dict[str, Any]]  # {source, error_type, message}


# ============================================================================
# TOOLS - Functions the LLM can call
# ============================================================================

def create_nutrition_tools_v2() -> List:
    """
    Create stateless tool functions (no closure, no db/user_id captured).

    These tools are exposed to the LLM via function calling.
    Tools accept user_id as parameter and create their own database sessions.
    """

    @tool
    def get_nutrition_stats(user_id: int, nutrients: Optional[str] = None) -> str:
        """Get current nutrition statistics for today.

        Args:
            user_id: User ID to fetch stats for
            nutrients: Comma-separated nutrients to query (e.g., "protein,calories").
                      If empty, returns all macros.
                      Options: calories, protein, carbs, fat, fiber

        Returns:
            JSON string with nutrition stats
        """
        from app.models.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info(f"[Tool:get_nutrition_stats] Called for user {user_id}")

            context_builder = UserContext(db, user_id)
            user_context = context_builder.build_context(minimal=True)

            # Extract data from context dictionary
            consumed = user_context['today']['consumed']
            targets = user_context['targets']
            remaining = user_context['today']['remaining']

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
                "compliance_rate": user_context['today'].get("compliance_rate", 0),
                "meals_consumed": user_context['today'].get("meals_consumed", 0),
                "meals_pending": user_context['today'].get("meals_pending", 0)
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_nutrition_stats] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
        finally:
            db.close()

    @tool
    def check_inventory(user_id: int, search_term: Optional[str] = None) -> str:
        """Check user's food inventory.

        Args:
            user_id: User ID to fetch inventory for
            search_term: Optional ingredient name to search for.
                        If empty, returns summary of all inventory.

        Returns:
            JSON string with inventory information
        """
        from app.models.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info(f"[Tool:check_inventory] Called for user {user_id}")

            context_builder = UserContext(db, user_id)
            user_context = context_builder.build_context(minimal=True)
            inventory = user_context['inventory_summary']

            if search_term:
                # Filter items matching search term
                items = [
                    item for item in inventory.get("items", [])
                    if search_term.lower() in item.get("name", "").lower()
                ]
                result = {
                    "search_term": search_term,
                    "found": len(items) > 0,
                    "items": items,
                    "count": len(items)
                }
            else:
                result = inventory

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:check_inventory] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
        finally:
            db.close()

    @tool
    def get_meal_plan(user_id: int, target_date: Optional[str] = None) -> str:
        """Get meal plan for a specific date.

        Args:
            user_id: User ID to fetch meal plan for
            target_date: Date in YYYY-MM-DD format. If empty, returns today's plan.

        Returns:
            JSON string with meal plan
        """
        from app.models.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info(f"[Tool:get_meal_plan] Called for user {user_id}")

            context_builder = UserContext(db, user_id)
            user_context = context_builder.build_context(minimal=False)  # Need full context for 'upcoming'
            planned_meals = user_context.get('upcoming', [])

            result = {
                "date": target_date or str(date.today()),
                "meals": planned_meals,
                "count": len(planned_meals)
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_meal_plan] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
        finally:
            db.close()

    @tool
    def get_makeable_recipes(user_id: int, min_protein: Optional[float] = None, max_calories: Optional[float] = None) -> str:
        """Get recipes that can be made with current inventory.

        Args:
            user_id: User ID to fetch recipes for
            min_protein: Minimum protein in grams (optional)
            max_calories: Maximum calories (optional)

        Returns:
            JSON string with makeable recipes
        """
        from app.models.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info(f"[Tool:get_makeable_recipes] Called for user {user_id}")

            context = UserContext(db, user_id)
            recipes = context.get_makeable_recipes(limit=10)

            # Filter by nutrition criteria
            if min_protein is not None:
                recipes = [r for r in recipes if r.get("protein_g", 0) >= min_protein]

            if max_calories is not None:
                recipes = [r for r in recipes if r.get("calories", 0) <= max_calories]

            result = {
                "recipes": recipes,
                "count": len(recipes),
                "filters_applied": {
                    "min_protein": min_protein,
                    "max_calories": max_calories
                }
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_makeable_recipes] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
        finally:
            db.close()

    @tool
    def get_goal_aligned_recipes(user_id: int, count: int = 5) -> str:
        """Get recipes aligned with user's nutrition goals.

        Args:
            user_id: User ID to fetch recipes for
            count: Number of recipes to return (default 5)

        Returns:
            JSON string with goal-aligned recipes
        """
        from app.models.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info(f"[Tool:get_goal_aligned_recipes] Called for user {user_id}")

            context_builder = UserContext(db, user_id)
            user_context = context_builder.build_context(minimal=True)
            recipes = context_builder.get_goal_aligned_recipes(count=count)

            result = {
                "recipes": recipes,
                "count": len(recipes),
                "goal": user_context['profile'].get("goal_type", "general_health")
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_goal_aligned_recipes] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
        finally:
            db.close()

    @tool
    def log_meal_consumption(user_id: int, meal_log_id: int, portions: float = 1.0) -> str:
        """Log a planned meal as consumed.

        Args:
            user_id: User ID performing the action
            meal_log_id: ID of the meal log to mark as consumed
            portions: Number of portions consumed (default 1.0)

        Returns:
            JSON string with result
        """
        from app.models.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info(f"[Tool:log_meal_consumption] Called for user {user_id}, meal_log_id {meal_log_id}")

            consumption_service = ConsumptionService(db)
            result = consumption_service.log_meal_consumption(
                user_id=user_id,
                meal_log_id=meal_log_id,
                portions=portions
            )

            return json.dumps({
                "success": True,
                "message": f"Successfully logged {portions} portion(s) of meal",
                "meal_log_id": meal_log_id,
                "portions": portions
            })

        except Exception as e:
            logger.error(f"[Tool:log_meal_consumption] Error: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
        finally:
            db.close()

    @tool
    def swap_meal_recipe(user_id: int, meal_log_id: int, new_recipe_id: int) -> str:
        """Swap a planned meal with a different recipe.

        Args:
            user_id: User ID performing the action
            meal_log_id: ID of the meal log to swap
            new_recipe_id: ID of the new recipe to use

        Returns:
            JSON string with result
        """
        from app.models.database import SessionLocal

        db = SessionLocal()
        try:
            logger.info(f"[Tool:swap_meal_recipe] Called for user {user_id}, meal_log_id {meal_log_id}")

            meal_plan_service = MealPlanService(db)
            result = meal_plan_service.swap_meal(
                meal_log_id=meal_log_id,
                new_recipe_id=new_recipe_id
            )

            return json.dumps({
                "success": True,
                "message": "Meal swapped successfully",
                "meal_log_id": meal_log_id,
                "new_recipe_id": new_recipe_id
            })

        except Exception as e:
            logger.error(f"[Tool:swap_meal_recipe] Error: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})
        finally:
            db.close()

    return [
        get_nutrition_stats,
        check_inventory,
        get_meal_plan,
        get_makeable_recipes,
        get_goal_aligned_recipes,
        log_meal_consumption,
        swap_meal_recipe
    ]


# ============================================================================
# GRAPH NODES
# ============================================================================

def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node 1: Load MINIMAL user context from database.

    Loads only essential profile data (~500 tokens):
    - user_id, goal_type, activity_level, dietary_restrictions
    - current date and time

    Tools will fetch detailed data (consumed, targets, inventory) on demand.
    This reduces initial system prompt from ~5000 tokens to ~500 tokens.

    Creates its own database session (stateless pattern).
    """
    from app.models.database import SessionLocal

    user_id = state["user_id"]
    logger.info(f"[Node:load_context] User {user_id}, turn {state.get('turn_count', 0) + 1}")

    db = SessionLocal()
    try:
        context_builder = UserContext(db, user_id)

        # Fetch only profile data (minimal)
        profile = context_builder._get_profile_basic()

        # Build minimal context
        minimal_context = {
            "user_id": user_id,
            "goal_type": profile.get("goal_type", "general_health"),
            "activity_level": profile.get("activity_level", "moderate"),
            "dietary_restrictions": [],  # TODO: Add if available in profile
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_time": datetime.now().strftime("%H:%M"),
        }

        logger.info(
            f"[Node:load_context] ✅ Loaded minimal context: "
            f"user={user_id}, goal={minimal_context['goal_type']}, "
            f"activity={minimal_context['activity_level']}"
        )

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
    finally:
        db.close()


async def classify_intent_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node 2: Classify user intent using GPT-4o with JSON mode.

    Classifies into: STATS, WHAT_IF, MEAL_SUGGESTION, MEAL_PLAN, INVENTORY, CONVERSATIONAL
    """
    logger.info("[Node:classify_intent] Starting classification")

    try:
        # Get user's latest message
        messages = state.get("messages", [])
        user_message = next(
            (msg.content for msg in reversed(messages) if isinstance(msg, HumanMessage)),
            None
        )

        if not user_message:
            logger.warning("[Node:classify_intent] No user message found")
            return {"intent": "error", "confidence": 0.0, "entities": {}}

        # Build context summary from MINIMAL context fields only
        # Note: Intent classification doesn't need detailed stats/inventory - just the user's message
        context = state.get("user_context", {})

        # Classification prompt (using only minimal context)
        prompt = f"""Classify this nutrition app query into ONE intent.

User Context:
- User ID: {context.get('user_id', 'unknown')}
- Goal: {context.get('goal_type', 'unknown')}
- Activity Level: {context.get('activity_level', 'unknown')}
- Dietary Restrictions: {', '.join(context.get('dietary_restrictions', [])) if context.get('dietary_restrictions') else 'None'}

Available Intents:
1. STATS - User wants nutrition statistics (e.g., "how is my protein?", "show my macros", "am I on track?")
2. WHAT_IF - Simulate food addition (e.g., "what if I eat pizza?", "can I fit samosas?")
3. MEAL_SUGGESTION - Get meal recommendations (e.g., "what should I eat?", "suggest lunch")
4. MEAL_PLAN - View/modify planned meals (e.g., "show my meal plan", "what's for dinner?")
5. INVENTORY - Check ingredients (e.g., "do I have eggs?", "what can I make?")
6. CONVERSATIONAL - General nutrition questions (e.g., "is protein important?", "explain macros")

User Query: "{user_message}"

Respond with ONLY valid JSON (no markdown, no extra text):
{{"intent": "stats", "confidence": 0.95, "entities": {{"nutrients": ["protein", "calories"]}}}}"""

        # Call LLM with JSON mode
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1,
            openai_api_key=settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}}
        )

        response = await llm.ainvoke([
            SystemMessage(content="You are a precise intent classifier. Respond with valid JSON only."),
            HumanMessage(content=prompt)
        ])

        # Parse result
        result = json.loads(response.content)
        intent = result.get("intent", "unknown").lower()
        confidence = float(result.get("confidence", 0.0))
        entities = result.get("entities", {})

        logger.info(f"[Node:classify_intent] Intent={intent}, confidence={confidence:.2f}")

        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities
        }

    except Exception as e:
        logger.error(f"[Node:classify_intent] Error: {e}", exc_info=True)
        return {"intent": "error", "confidence": 0.0, "entities": {}}


# ============================================================================
# CONFIDENCE ROUTING & CLARIFICATION
# ============================================================================

def route_by_confidence(state: NutritionState) -> Literal["clarify", "fetch"]:
    """
    Conditional edge after classify_intent.

    Routes to:
    - "clarify" if confidence < 0.6 OR intent == "unknown"/"error"
    - "fetch" if confidence >= 0.6

    Research basis: Low confidence queries benefit from natural LLM clarification
    rather than guessing (see: Johns Hopkins interruption handling research).
    """
    confidence = state.get("confidence", 0.0)
    intent = state.get("intent", "unknown").lower()

    if confidence < 0.6 or intent in ["unknown", "error"]:
        logger.info(f"[Edge:route_by_confidence] Low confidence ({confidence:.2f}), routing to clarification")
        return "clarify"
    else:
        logger.info(f"[Edge:route_by_confidence] High confidence ({confidence:.2f}), routing to fetch")
        return "fetch"


def set_clarification_mode_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node: Set clarification mode flag.

    When intent confidence is low, this flag tells generate_response_node
    to ask clarifying questions instead of guessing.
    """
    logger.info("[Node:set_clarification_mode] Setting clarification mode")
    return {"clarification_mode": True}


# ============================================================================
# DATA PRE-FETCHING (Replaces Read Tools)
# ============================================================================

def fetch_data_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node: Pre-fetch data based on classified intent.

    Eliminates tool call overhead (~1,400-3,500 tokens for tool schemas)
    by deterministically fetching required data based on intent.

    Intent -> Data Mapping:
    - STATS/WHAT_IF -> nutrition stats (consumed, targets, remaining)
    - INVENTORY -> inventory_summary + makeable_recipes
    - MEAL_PLAN -> upcoming meals + today's consumption
    - MEAL_SUGGESTION -> inventory + goal_aligned_recipes + makeable_recipes
    - CONVERSATIONAL -> no additional data (profile already in context)

    Research basis: Pre-fetching adds ~0.24ms/token input overhead vs
    200-400ms per tool call round-trip (OpenAI latency optimization guide).
    """
    from app.models.database import SessionLocal

    intent = state.get("intent", "").lower()
    user_id = state["user_id"]

    logger.info(f"[Node:fetch_data] Intent={intent}, user_id={user_id}")

    # Skip if in clarification mode
    if state.get("clarification_mode"):
        logger.info("[Node:fetch_data] Skipping - clarification mode")
        return {"fetched_data": {}, "fetch_error": None}

    db = SessionLocal()
    try:
        context_builder = UserContext(db, user_id)
        fetched_data = {}
        fetch_error = None

        try:
            if intent in ["stats", "what_if"]:
                # Nutrition statistics - most common query
                user_context = context_builder.build_context(minimal=True)
                fetched_data = {
                    "nutrition_stats": {
                        "consumed": user_context["today"]["consumed"],
                        "targets": user_context["targets"],
                        "remaining": user_context["today"]["remaining"],
                        "compliance_rate": user_context["today"].get("compliance_rate", 0),
                        "meals_consumed": user_context["today"].get("meals_consumed", 0),
                        "meals_pending": user_context["today"].get("meals_pending", 0)
                    }
                }

            elif intent == "inventory":
                # Inventory + makeable recipes
                user_context = context_builder.build_context(minimal=True)
                makeable = context_builder.get_makeable_recipes(limit=10)
                fetched_data = {
                    "inventory_summary": user_context["inventory_summary"],
                    "makeable_recipes": makeable
                }

            elif intent == "meal_plan":
                # Upcoming meals with full context
                user_context = context_builder.build_context(minimal=False)
                fetched_data = {
                    "upcoming_meals": user_context.get("upcoming", []),
                    "today_consumption": user_context["today"]
                }

            elif intent == "meal_suggestion":
                # Full context for meal suggestions
                user_context = context_builder.build_context(minimal=True)
                makeable = context_builder.get_makeable_recipes(limit=10)
                goal_aligned = context_builder.get_goal_aligned_recipes(count=10)
                fetched_data = {
                    "inventory_summary": user_context["inventory_summary"],
                    "makeable_recipes": makeable,
                    "goal_aligned_recipes": goal_aligned,
                    "remaining": user_context["today"]["remaining"]
                }

            elif intent == "conversational":
                # General questions - profile already loaded in user_context
                fetched_data = {}

            else:
                # Unknown intent fallback - fetch basic stats
                user_context = context_builder.build_context(minimal=True)
                fetched_data = {
                    "nutrition_stats": {
                        "consumed": user_context["today"]["consumed"],
                        "targets": user_context["targets"],
                        "remaining": user_context["today"]["remaining"]
                    }
                }

        except Exception as e:
            logger.error(f"[Node:fetch_data] Error fetching for intent={intent}: {e}")
            fetch_error = {
                "source": "fetch_data_node",
                "error_type": type(e).__name__,
                "message": str(e),
                "intent": intent
            }

        logger.info(f"[Node:fetch_data] Fetched {len(fetched_data)} data categories")

        return {
            "fetched_data": fetched_data,
            "fetch_error": fetch_error
        }

    finally:
        db.close()


# ============================================================================
# WRITE-ONLY TOOLS (For HITL Confirmation)
# ============================================================================

def create_write_tools_only() -> List:
    """
    Create only write tools for LLM function calling.

    Read tools have been replaced by fetch_data_node.
    These tools require HITL confirmation before execution.
    """
    @tool
    def log_meal_consumption(user_id: int, meal_log_id: int, portions: float = 1.0) -> str:
        """Log a planned meal as consumed.

        Args:
            user_id: User ID performing the action
            meal_log_id: ID of the meal log to mark as consumed
            portions: Number of portions consumed (default 1.0)

        Returns:
            Confirmation message (requires user approval before execution)
        """
        # Tool definition only - actual execution in execute_write_node
        return "PENDING_CONFIRMATION"

    @tool
    def swap_meal_recipe(user_id: int, meal_log_id: int, new_recipe_id: int) -> str:
        """Swap a planned meal with a different recipe.

        Args:
            user_id: User ID performing the action
            meal_log_id: ID of the meal log to swap
            new_recipe_id: ID of the new recipe to use

        Returns:
            Confirmation message (requires user approval before execution)
        """
        return "PENDING_CONFIRMATION"

    return [log_meal_consumption, swap_meal_recipe]


async def trim_messages_node(state: NutritionState) -> Dict[str, Any]:
    """
    Trim messages to fit context window (official LangGraph pattern).

    Returns trimmed messages under 'llm_input_messages' key to preserve
    full history in state while sending only trimmed version to LLM.
    """
    try:
        from langchain_core.messages.utils import trim_messages, count_tokens_approximately

        messages = state.get("messages", [])
        original_count = len(messages)

        # Trim if conversation is getting long
        MAX_MESSAGES_THRESHOLD = 10
        MAX_MESSAGES = 5  # Keep last 5 messages only

        if original_count > MAX_MESSAGES_THRESHOLD:
            print(f"\n[TRIM] Messages in state: {original_count}")

            # Use token_counter=len to count messages instead of tokens
            # Source: https://python.langchain.com/docs/how_to/trim_messages/
            trimmed = trim_messages(
                messages,
                strategy="last",
                token_counter=len,  # Count messages, not tokens
                max_tokens=MAX_MESSAGES,  # Keep last 8 messages
                start_on="human",
                end_on=("human", "tool"),  # Official pattern - preserves tool call sequences
                include_system=False,  # Don't include old system messages
            )

            removed = original_count - len(trimmed)
            trimmed_count = len(trimmed)
            print(f"[TRIM] ✂️ Trimmed: {original_count} → {trimmed_count} messages (removed {removed})")

            return {"llm_input_messages": trimmed}
        else:
            print(f"[TRIM] ✅ No trimming needed ({original_count} messages)")
            return {}  # No trimming needed

    except Exception as e:
        logger.error(f"[trim_messages_node] Error: {e}")
        return {}  # Fall back to full history


async def generate_response_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node: Generate response using LLM.

    REFACTORED (2025-01):
    - Uses pre-fetched data from fetch_data_node instead of read tool calls
    - Only write tools (log_meal_consumption, swap_meal_recipe) available
    - Handles clarification mode and errors gracefully
    - Improved uncertainty handling in system prompt
    """
    logger.info(f"[Node:generate_response] Intent={state.get('intent')}, clarification={state.get('clarification_mode')}")

    try:
        # Get context and state
        context = state.get("user_context", {})
        fetched_data = state.get("fetched_data", {})
        clarification_mode = state.get("clarification_mode", False)
        fetch_error = state.get("fetch_error")

        # Create LLM with only write tools bound (read tools removed)
        write_tools = create_write_tools_only()
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            openai_api_key=settings.openai_api_key
        ).bind_tools(write_tools)

        # Build system prompt based on mode
        if clarification_mode:
            # Low confidence - ask for clarification
            system_prompt = f"""You are a nutrition AI assistant for NutriLens. Today is {context.get('current_date', 'unknown')} at {context.get('current_time', 'unknown')}.

User {context.get('user_id')} | Goal: {context.get('goal_type', 'general_health')} | Activity: {context.get('activity_level', 'moderate')}

CLARIFICATION MODE: The user's query was unclear or ambiguous.

YOUR TASK:
1. Politely acknowledge you're not sure what they meant
2. Ask a clarifying question
3. Offer 2-3 specific options they might mean:
   - Check nutrition stats (calories, protein, etc.)
   - View meal plan or suggestions
   - Check inventory or what they can cook
   - General nutrition advice

Do NOT guess or make assumptions. Be friendly and helpful.

Session: {state.get('session_id')}
"""

        elif fetch_error:
            # Data fetch failed - apologize gracefully
            system_prompt = f"""You are a nutrition AI assistant for NutriLens. Today is {context.get('current_date', 'unknown')} at {context.get('current_time', 'unknown')}.

User {context.get('user_id')} | Goal: {context.get('goal_type', 'general_health')}

NOTE: There was an issue fetching your data. Error type: {fetch_error.get('error_type', 'unknown')}

YOUR TASK:
1. Apologize briefly for the technical difficulty
2. Explain you're having trouble accessing the requested information
3. Offer to help with something else

Do NOT expose technical error details. Be helpful and reassuring.

Session: {state.get('session_id')}
"""

        else:
            # Normal mode - use pre-fetched data
            fetched_data_json = json.dumps(fetched_data, indent=2, default=str) if fetched_data else "{}"

            system_prompt = f"""You are a nutrition AI assistant for NutriLens. Today is {context.get('current_date', 'unknown')} at {context.get('current_time', 'unknown')}.

User {context.get('user_id')} | Goal: {context.get('goal_type', 'general_health')} | Activity: {context.get('activity_level', 'moderate')}

=== YOUR AVAILABLE DATA ===
{fetched_data_json}

=== INSTRUCTIONS ===
1. Answer based ONLY on the data provided above
2. If the data doesn't contain what you need, say "I don't have that information right now"
3. NEVER hallucinate or make up nutrition numbers, recipes, or meal data
4. For medical/health advice questions, recommend consulting a healthcare professional
5. Be conversational and helpful

=== AVAILABLE ACTIONS ===
You can help the user:
- log_meal_consumption: Mark a meal as eaten (requires user confirmation)
- swap_meal_recipe: Change a planned meal to a different recipe (requires user confirmation)

When calling these tools, always include user_id={context.get('user_id')}.

Session: {state.get('session_id')}
"""

        # Get conversation messages
        conversation_messages = state.get("llm_input_messages", state.get("messages", []))

        # Build final messages list for LLM
        messages = [SystemMessage(content=system_prompt)] + list(conversation_messages)

        logger.info(f"[Node:generate_response] Calling LLM with {len(messages)} messages")
        response = await llm.ainvoke(messages)

        # Log token usage if available
        if hasattr(response, 'response_metadata') and 'token_usage' in response.response_metadata:
            token_usage = response.response_metadata['token_usage']
            logger.info(f"[Node:generate_response] Tokens: prompt={token_usage.get('prompt_tokens', 0)}, completion={token_usage.get('completion_tokens', 0)}")

        # Check for write tool calls - set up for HITL confirmation
        tool_calls_count = len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0
        logger.info(f"[Node:generate_response] Response generated, tool_calls={tool_calls_count}")

        if tool_calls_count > 0:
            # Write tool called - set up for HITL confirmation
            tool_call = response.tool_calls[0]  # Handle first tool call
            logger.info(f"[Node:generate_response] Write tool called: {tool_call['name']}, setting up for confirmation")

            return {
                "messages": [response],
                "pending_tool_call": {
                    "name": tool_call["name"],
                    "args": tool_call["args"],
                    "id": tool_call["id"]
                },
                "requires_confirmation": True
            }

        # No tool calls - direct response
        return {"messages": [response]}

    except Exception as e:
        logger.error(f"[Node:generate_response] Error: {e}", exc_info=True)
        error_msg = AIMessage(content="I'm sorry, I encountered an issue processing your request. Could you please try again?")
        return {"messages": [error_msg]}


# ============================================================================
# HITL (Human-in-the-Loop) NODES
# ============================================================================

def route_after_response(state: NutritionState) -> Literal["confirm", "end"]:
    """
    Conditional edge after generate_response.

    Routes to:
    - "confirm" if a write tool was called and needs confirmation
    - "end" if no tool calls (direct response)
    """
    if state.get("requires_confirmation") and state.get("pending_tool_call"):
        logger.info("[Edge:route_after_response] Write tool pending, routing to confirmation")
        return "confirm"
    else:
        logger.info("[Edge:route_after_response] No confirmation needed, ending")
        return "end"


def confirm_write_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node: Request human confirmation for write operations.

    Uses LangGraph's interrupt() to pause execution and wait for user confirmation.
    The graph will resume when the API calls Command(resume=...).

    Research basis: HITL confirmation for write operations prevents accidental
    data modifications (LangChain HITL best practices).
    """
    pending_tool = state.get("pending_tool_call")

    if not pending_tool:
        logger.warning("[Node:confirm_write] No pending tool call")
        return {"user_confirmation": None}

    tool_name = pending_tool["name"]
    tool_args = pending_tool["args"]

    # Build human-readable confirmation message
    if tool_name == "log_meal_consumption":
        message = f"Log meal (ID: {tool_args.get('meal_log_id')}) as consumed with {tool_args.get('portions', 1.0)} portion(s)?"
    elif tool_name == "swap_meal_recipe":
        message = f"Swap meal (ID: {tool_args.get('meal_log_id')}) to recipe ID {tool_args.get('new_recipe_id')}?"
    else:
        message = f"Execute {tool_name}?"

    logger.info(f"[Node:confirm_write] Requesting confirmation: {message}")

    # interrupt() pauses execution and returns when resumed via Command(resume=...)
    user_response = interrupt({
        "action": tool_name,
        "params": tool_args,
        "message": message,
        "confirmation_required": True
    })

    # This code runs AFTER the user resumes with Command(resume=...)
    logger.info(f"[Node:confirm_write] User response: {user_response}")

    return {"user_confirmation": user_response}


def execute_write_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node: Execute write tool after user confirmation.

    Only executes if user approved. Otherwise returns cancellation message.
    """
    from langchain_core.messages import ToolMessage
    from app.models.database import SessionLocal

    pending_tool = state.get("pending_tool_call")
    user_confirmation = state.get("user_confirmation")

    if not pending_tool:
        return {"messages": [AIMessage(content="No action was pending.")]}

    # Check if user approved
    approved_values = ["approved", "yes", "confirm", "ok", "sure", True]
    is_approved = user_confirmation in approved_values or (
        isinstance(user_confirmation, str) and user_confirmation.lower() in approved_values
    )

    if not is_approved:
        logger.info(f"[Node:execute_write] User declined: {user_confirmation}")
        return {
            "messages": [AIMessage(content="Okay, I've cancelled that action. Is there anything else I can help with?")],
            "pending_tool_call": None,
            "requires_confirmation": False
        }

    # Execute the tool
    db = SessionLocal()
    try:
        tool_name = pending_tool["name"]
        tool_args = pending_tool["args"]
        user_id = state["user_id"]

        logger.info(f"[Node:execute_write] Executing {tool_name} with args {tool_args}")

        if tool_name == "log_meal_consumption":
            service = ConsumptionService(db)
            result = service.log_meal_consumption(
                user_id=user_id,
                meal_data={
                    "meal_log_id": tool_args.get("meal_log_id"),
                    "portion_multiplier": tool_args.get("portions", 1.0)
                }
            )
            result_json = json.dumps(result, indent=2, default=str)

        elif tool_name == "swap_meal_recipe":
            service = MealPlanService(db)
            result = service.swap_meal(
                meal_log_id=tool_args.get("meal_log_id"),
                new_recipe_id=tool_args.get("new_recipe_id")
            )
            result_json = json.dumps(result, indent=2, default=str)

        else:
            result_json = json.dumps({"error": f"Unknown tool: {tool_name}"})

        db.commit()
        logger.info(f"[Node:execute_write] Executed {tool_name} successfully")

        # Return ToolMessage for LLM to synthesize response
        tool_message = ToolMessage(
            content=result_json,
            tool_call_id=pending_tool.get("id", "unknown")
        )

        return {
            "messages": [tool_message],
            "pending_tool_call": None,
            "requires_confirmation": False
        }

    except Exception as e:
        db.rollback()
        logger.error(f"[Node:execute_write] Error: {e}", exc_info=True)
        return {
            "messages": [AIMessage(content=f"Sorry, the action couldn't be completed. Please try again.")],
            "pending_tool_call": None,
            "requires_confirmation": False
        }
    finally:
        db.close()


async def synthesize_response_node(state: NutritionState) -> Dict[str, Any]:
    """
    Node: Generate final response after tool execution.

    Takes the tool result and has LLM create a friendly, conversational response.
    """
    messages = state.get("messages", [])

    # Check if last message is a ToolMessage (successful execution)
    if messages and hasattr(messages[-1], 'content'):
        last_content = messages[-1].content
        try:
            # Try to parse tool result
            tool_result = json.loads(last_content) if isinstance(last_content, str) else last_content
        except json.JSONDecodeError:
            tool_result = {"raw": last_content}
    else:
        tool_result = {}

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        openai_api_key=settings.openai_api_key
    )

    system_prompt = """You are a nutrition assistant. A user action was just completed successfully.

Summarize the result in a friendly, conversational way:
- Be concise (1-2 sentences)
- Confirm what was done
- Optionally mention any relevant follow-up info

Do NOT include technical details or raw JSON."""

    context = state.get("user_context", {})
    user_message = f"Action completed. Result: {json.dumps(tool_result, default=str)[:500]}"

    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ])

    return {"messages": [response]}


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_nutrition_graph_structure() -> StateGraph:
    """
    Create the refactored LangGraph workflow structure.

    REFACTORED (2025-01):
    - Read tools replaced by deterministic fetch_data_node
    - Confidence-based routing for clarification
    - HITL (Human-in-the-Loop) for write operations via interrupt()

    NEW FLOW:
    load_context → classify_intent → [confidence check]
                                        ↓ (low confidence)
                                  set_clarification_mode → trim → generate → END
                                        ↓ (high confidence)
                                  fetch_data → trim → generate
                                                        ↓ [has write tool?]
                                                        ↓ (yes)
                                  confirm_write (interrupt) → execute_write → synthesize → END
                                                        ↓ (no)
                                                       END
    """
    # Create graph
    workflow = StateGraph(NutritionState)

    # Add all nodes
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("set_clarification_mode", set_clarification_mode_node)
    workflow.add_node("fetch_data", fetch_data_node)
    workflow.add_node("trim_messages", trim_messages_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("confirm_write", confirm_write_node)
    workflow.add_node("execute_write", execute_write_node)
    workflow.add_node("synthesize_response", synthesize_response_node)

    # Define entry point
    workflow.set_entry_point("load_context")

    # Initial flow: load_context → classify_intent
    workflow.add_edge("load_context", "classify_intent")

    # Confidence-based routing after classify_intent
    workflow.add_conditional_edges(
        "classify_intent",
        route_by_confidence,
        {
            "clarify": "set_clarification_mode",
            "fetch": "fetch_data"
        }
    )

    # Clarification path: set_clarification_mode → trim → generate → END
    workflow.add_edge("set_clarification_mode", "trim_messages")

    # Normal path: fetch_data → trim → generate
    workflow.add_edge("fetch_data", "trim_messages")
    workflow.add_edge("trim_messages", "generate_response")

    # After generate_response: check for write tool calls
    workflow.add_conditional_edges(
        "generate_response",
        route_after_response,
        {
            "confirm": "confirm_write",
            "end": END
        }
    )

    # HITL write confirmation flow
    workflow.add_edge("confirm_write", "execute_write")
    workflow.add_edge("execute_write", "synthesize_response")
    workflow.add_edge("synthesize_response", END)

    logger.info("[Graph] Refactored nutrition graph created with HITL support (9 nodes)")

    return workflow


# ============================================================================
# MAIN INTERFACE
# ============================================================================
#
# NOTE: The process_message function has been REMOVED.
#
# The graph is now compiled ONCE at application startup (see graph_instance.py)
# and invoked directly from the API endpoint (see api/nutrition_chat.py).
#
# This eliminates the 90ms graph compilation overhead on every request.
#
# To use the graph:
#   from app.agents.graph_instance import get_compiled_graph
#   app = get_compiled_graph()
#   result = await app.ainvoke(initial_state, config={"configurable": {"thread_id": session_id}})
#
