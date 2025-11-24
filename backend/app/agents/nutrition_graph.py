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
    Node 3: Generate response using LLM with tools.

    The LLM decides whether to:
    - Call tools to get data
    - Respond directly
    """
    logger.info(f"[Node:generate_response] Intent={state.get('intent')}")

    try:
        # Create stateless tools (no db/user_id needed)
        tools = create_nutrition_tools_v2()

        # Create LLM with tools bound
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            openai_api_key=settings.openai_api_key
        ).bind_tools(tools)

        # Build rich system prompt with context
        context = state.get("user_context", {})
        profile = context.get("profile", {})
        today = context.get("today", {})
        consumed = today.get("consumed", {})
        targets = context.get("targets", {})
        remaining = today.get("remaining", {})
        inventory = context.get("inventory_summary", {})

        # DEBUG: Log FULL context data
        import json
        context_json = json.dumps(context, default=str, indent=2)
        print(f"\n{'='*100}")
        print(f"[1] FULL CONTEXT DICTIONARY SENT TO LLM:")
        print(f"{'='*100}")
        print(context_json)
        print(f"{'='*100}\n")

        # OPTIMIZED: Minimal system prompt (~50 tokens)
        # Tool definitions are sent automatically by OpenAI API - no need to duplicate
        system_prompt = f"""You are a nutrition AI assistant. Today is {context['current_date']} at {context['current_time']}.

User {context['user_id']} | Goal: {context['goal_type']} | Activity: {context['activity_level']}
{f"Restrictions: {', '.join(context['dietary_restrictions'])}" if context['dietary_restrictions'] else ""}

Use available tools to fetch current data when needed. Always pass user_id={context['user_id']}.
Be helpful and conversational.

Session: {state.get('session_id')}
"""

        # Get conversation messages
        # Use trimmed messages if available (from previous invocation), otherwise use full history
        conversation_messages = state.get("llm_input_messages", state.get("messages", []))
        original_count = len(state.get("messages", []))

        print(f"\n{'='*80}")
        print(f"[TRIM] Messages in state: {original_count}")
        print(f"[TRIM] Using: {'llm_input_messages' if 'llm_input_messages' in state else 'messages'}")
        print(f"{'='*80}\n")

        # Build final messages list for LLM
        messages = [SystemMessage(content=system_prompt)] + list(conversation_messages)

        # DEBUG: Log FULL system prompt sent to LLM
        print(f"\n{'='*100}")
        print(f"[2] COMPLETE SYSTEM PROMPT SENT TO LLM:")
        print(f"{'='*100}")
        print(system_prompt)
        print(f"{'='*100}")
        print(f"Prompt size: {len(system_prompt)} chars, ~{len(system_prompt)//4} tokens\n")

        # DEBUG: Log conversation messages
        print(f"\n{'='*100}")
        print(f"[3] CONVERSATION MESSAGES ({len(conversation_messages)}/{original_count}):")
        print(f"{'='*100}")
        for i, msg in enumerate(messages):
            print(f"Message {i+1} ({type(msg).__name__}):")
            print(f"  Content: {str(msg.content)[:200]}..." if len(str(msg.content)) > 200 else f"  Content: {msg.content}")
            print()
        print(f"{'='*100}\n")

        print(f"[4] CALLING LLM (GPT-4o)...")
        response = await llm.ainvoke(messages)
        print(f"[4] LLM RESPONDED!")

        # Get ACTUAL token usage from OpenAI API response
        if hasattr(response, 'response_metadata') and 'token_usage' in response.response_metadata:
            token_usage = response.response_metadata['token_usage']
            print(f"\n{'='*80}")
            print(f"[ACTUAL_TOKENS_FROM_OPENAI_API]")
            print(f"  Prompt tokens:     {token_usage.get('prompt_tokens', 0):,}")
            print(f"  Completion tokens: {token_usage.get('completion_tokens', 0):,}")
            print(f"  Total tokens:      {token_usage.get('total_tokens', 0):,}")
            print(f"{'='*80}\n")

        tool_calls_count = len(response.tool_calls) if hasattr(response, 'tool_calls') else 0
        print(f"[Node:generate_response] Response generated, tool_calls={tool_calls_count}")

        # DEBUG: Log LLM response details
        print(f"\n{'='*100}")
        print(f"[5] LLM RESPONSE:")
        print(f"{'='*100}")
        print(f"Response type: {type(response)}")
        print(f"Response content: {response.content[:500]}..." if len(str(response.content)) > 500 else f"Response content: {response.content}")
        print(f"Tool calls: {tool_calls_count}")

        if tool_calls_count > 0:
            print(f"\n⚠️  TOOL CALLS DETECTED:")
            for tc in response.tool_calls:
                print(f"  - Tool: {tc.get('name', 'unknown')}")
                print(f"    Args: {tc.get('args', {})}")
            print(f"\nQUESTION: {state.get('messages', [])[-1].content if state.get('messages') else 'unknown'}")
        else:
            print(f"\n✅ NO TOOL CALLS - LLM used context data directly")

        print(f"{'='*100}\n")

        return {"messages": [response]}

    except Exception as e:
        logger.error(f"[Node:generate_response] Error: {e}", exc_info=True)
        error_msg = AIMessage(content=f"I encountered an error: {str(e)}")
        return {"messages": [error_msg]}


def should_use_tools(state: NutritionState) -> Literal["tools", "end"]:
    """
    Conditional edge: Check if LLM wants to call tools.

    Routes to:
    - "tools" if LLM made tool calls
    - "end" if LLM responded directly
    """
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info(f"[Edge:should_use_tools] Tools requested: {len(last_message.tool_calls)}")
        return "tools"
    else:
        logger.info("[Edge:should_use_tools] No tools needed, ending")
        return "end"


# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_nutrition_graph_structure() -> StateGraph:
    """
    Create the stateless LangGraph workflow structure.

    This function is called ONCE at startup to create the graph structure.
    Tools and nodes are stateless - they get user_id from state and create
    their own database sessions.

    Flow:
    1. load_context → Fetch user data
    2. classify_intent → Classify query
    3. generate_response → LLM with tools
    4. [Conditional] → Tools if needed, else end
    5. [Loop] → Back to generate_response after tools
    """
    # Create stateless tools (no db/user_id needed - tools accept user_id as parameter)
    tools = create_nutrition_tools_v2()

    # Create graph
    workflow = StateGraph(NutritionState)

    # Add nodes (all stateless - get data from state)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("trim_messages", trim_messages_node)  # Trim before LLM call
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("tools", ToolNode(tools))

    # Define flow
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "classify_intent")
    workflow.add_edge("classify_intent", "trim_messages")  # Trim before generating response
    workflow.add_edge("trim_messages", "generate_response")

    # Conditional edge: tools or end
    workflow.add_conditional_edges(
        "generate_response",
        should_use_tools,
        {
            "tools": "tools",
            "end": END
        }
    )

    # After tools, loop back to trim_messages (not generate_response directly)
    # This ensures we trim before every LLM call
    workflow.add_edge("tools", "trim_messages")

    logger.info("[Graph] Stateless nutrition graph structure created with 4 nodes + conditional routing")

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
