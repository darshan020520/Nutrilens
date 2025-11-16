# LangGraph Restructure - Complete Implementation Plan
**Based on ARCHITECTURE_ANALYSIS_OUR_VS_PRODUCTION.md**

**Agreed Decisions**:
1. ✅ Graph Initialization - Compile once at startup
2. ✅ Context Management - Option A: Minimal context + tools
3. ✅ Tool Usage - Keep ALL 7 tools (all valid)
4. ✅ Message History - Trim to 4-5 turns
5. ✅ Implementation Order - B: Compile Once First
6. ✅ Database Access - Approach 2: Tools create own db context

---

## Day 1-2: Priority 3 - Compile Graph Once at Startup

**Goal**: Refactor tools to be stateless, create singleton compiled graph, eliminate 90ms overhead per request

**Time**: 1-2 days
**Risk**: Medium
**Savings**: ~$300/month

### Step 1.1: Create Database Context Manager

**File**: `backend/app/core/database.py` (create or update)

**Add**:
```python
from contextlib import contextmanager
from app.core.database import SessionLocal

@contextmanager
def get_db_context():
    """
    Context manager for database sessions in tools.

    Usage:
        with get_db_context() as db:
            result = UserContext(db, user_id).build_context()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Test**:
```python
# Test the context manager works
from app.core.database import get_db_context

with get_db_context() as db:
    # Should get a valid session
    assert db is not None

# Session should be closed after context
```

### Step 1.2: Refactor Tools to Be Stateless

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: Lines 38-340 (all tool definitions)

**Current Pattern** (closure-based):
```python
def create_nutrition_tools(db: Session, user_id: int) -> List[Tool]:
    """Creates tools with db and user_id captured in closure"""

    @tool
    def get_nutrition_stats() -> str:
        # ❌ Uses db and user_id from closure
        context_builder = UserContext(db, user_id)
        return context_builder.build_context()

    return [get_nutrition_stats, ...]
```

**New Pattern** (stateless with db context):
```python
def create_nutrition_tools_v2() -> List[Tool]:
    """
    Creates stateless tools that receive user_id as parameter.
    Tools create their own db sessions using get_db_context().

    This allows a single set of tools to be shared across all users
    in a compiled graph singleton.
    """

    @tool
    def get_nutrition_stats(user_id: int) -> str:
        """Get today's nutrition statistics.

        Args:
            user_id: User ID (passed by LLM from state context)

        Returns:
            JSON with consumed/remaining/targets
        """
        try:
            from app.core.database import get_db_context

            # ✅ Tool creates own db session
            with get_db_context() as db:
                context_builder = UserContext(db, user_id)
                user_context = context_builder.build_context(minimal=True)

                consumed = user_context['today']['consumed']
                targets = user_context['targets']
                remaining = user_context['today']['remaining']

                result = {
                    "consumed": consumed,
                    "remaining": remaining,
                    "targets": targets
                }

                logger.info(f"[Tool:get_nutrition_stats] Fetched for user {user_id}")

                return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_nutrition_stats] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    def check_inventory(user_id: int, show_details: bool = False) -> str:
        """Check user's food inventory.

        Args:
            user_id: User ID
            show_details: Include detailed item list

        Returns:
            JSON with inventory summary
        """
        try:
            from app.core.database import get_db_context

            with get_db_context() as db:
                context_builder = UserContext(db, user_id)
                user_context = context_builder.build_context(minimal=True)

                inventory = user_context['inventory_summary']

                result = {
                    "available_count": inventory.get('available_count', 0),
                    "expiring_soon": inventory.get('expiring_soon', []),
                }

                if show_details:
                    result["low_stock"] = inventory.get('low_stock', [])

                logger.info(f"[Tool:check_inventory] Fetched for user {user_id}")

                return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:check_inventory] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    def get_meal_plan(user_id: int, days: int = 1) -> str:
        """Get upcoming planned meals.

        Args:
            user_id: User ID
            days: Number of days to fetch

        Returns:
            JSON with upcoming meals
        """
        try:
            from app.core.database import get_db_context

            with get_db_context() as db:
                context_builder = UserContext(db, user_id)
                user_context = context_builder.build_context(minimal=True)

                upcoming = user_context.get('upcoming', [])
                filtered_meals = upcoming[:days * 3]

                result = {
                    "meals": filtered_meals,
                    "count": len(filtered_meals),
                    "days": days
                }

                logger.info(f"[Tool:get_meal_plan] Fetched {len(filtered_meals)} meals for user {user_id}")

                return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_meal_plan] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    def suggest_recipes(
        user_id: int,
        meal_type: str,
        max_calories: Optional[int] = None,
        min_protein: Optional[int] = None
    ) -> str:
        """Search recipe database for meals matching criteria.

        Args:
            user_id: User ID
            meal_type: breakfast, lunch, dinner, snack
            max_calories: Maximum calories
            min_protein: Minimum protein

        Returns:
            JSON with matching recipes
        """
        try:
            from app.core.database import get_db_context

            with get_db_context() as db:
                context_builder = UserContext(db, user_id)
                recipes = context_builder.search_recipes(
                    meal_type=meal_type,
                    max_calories=max_calories,
                    min_protein=min_protein
                )

                result = {
                    "recipes": recipes[:5],
                    "count": len(recipes),
                    "filters": {
                        "meal_type": meal_type,
                        "max_calories": max_calories,
                        "min_protein": min_protein
                    }
                }

                logger.info(f"[Tool:suggest_recipes] Found {len(recipes)} recipes for user {user_id}")

                return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:suggest_recipes] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    def get_goal_aligned_recipes(user_id: int, count: int = 5) -> str:
        """Get recipes aligned with user's fitness goal.

        Args:
            user_id: User ID
            count: Number of recipes

        Returns:
            JSON with goal-aligned recipes
        """
        try:
            from app.core.database import get_db_context

            with get_db_context() as db:
                context_builder = UserContext(db, user_id)
                user_context = context_builder.build_context(minimal=True)
                recipes = context_builder.get_goal_aligned_recipes(count=count)

                result = {
                    "recipes": recipes,
                    "count": len(recipes),
                    "goal": user_context['profile'].get("goal_type", "general_health")
                }

                logger.info(f"[Tool:get_goal_aligned_recipes] Found {len(recipes)} recipes for user {user_id}")

                return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"[Tool:get_goal_aligned_recipes] Error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @tool
    def log_meal_consumption(user_id: int, meal_log_id: int, portions: float = 1.0) -> str:
        """Log a planned meal as consumed.

        Args:
            user_id: User ID
            meal_log_id: Meal log ID
            portions: Portions consumed

        Returns:
            JSON with success status
        """
        try:
            from app.core.database import get_db_context

            with get_db_context() as db:
                consumption_service = ConsumptionService(db)
                result = consumption_service.log_meal_consumption(
                    user_id=user_id,
                    meal_log_id=meal_log_id,
                    portions=portions
                )

                logger.info(f"[Tool:log_meal_consumption] Logged meal {meal_log_id} for user {user_id}")

                return json.dumps({
                    "success": True,
                    "message": f"Logged {portions} portion(s)",
                    "meal_log_id": meal_log_id,
                    "portions": portions
                })

        except Exception as e:
            logger.error(f"[Tool:log_meal_consumption] Error: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    @tool
    def swap_meal_recipe(user_id: int, meal_log_id: int, new_recipe_id: int) -> str:
        """Swap a planned meal with a different recipe.

        Args:
            user_id: User ID
            meal_log_id: Meal log ID
            new_recipe_id: New recipe ID

        Returns:
            JSON with success status
        """
        try:
            from app.core.database import get_db_context

            with get_db_context() as db:
                meal_plan_service = MealPlanService(db)
                result = meal_plan_service.swap_meal_recipe(
                    user_id=user_id,
                    meal_log_id=meal_log_id,
                    new_recipe_id=new_recipe_id
                )

                logger.info(f"[Tool:swap_meal_recipe] Swapped meal {meal_log_id} for user {user_id}")

                return json.dumps({
                    "success": True,
                    "message": "Meal swapped successfully",
                    "meal_log_id": meal_log_id,
                    "new_recipe_id": new_recipe_id
                })

        except Exception as e:
            logger.error(f"[Tool:swap_meal_recipe] Error: {e}", exc_info=True)
            return json.dumps({"success": False, "error": str(e)})

    # Return all 7 stateless tools
    return [
        get_nutrition_stats,
        check_inventory,
        get_meal_plan,
        suggest_recipes,
        get_goal_aligned_recipes,
        log_meal_consumption,
        swap_meal_recipe,
    ]
```

**Test Each Tool**:
```python
tools = create_nutrition_tools_v2()

# Test get_nutrition_stats
result = tools[0].invoke({"user_id": 223})
assert "consumed" in result
assert "remaining" in result

# Test check_inventory
result = tools[1].invoke({"user_id": 223})
assert "available_count" in result

# All tools should work without db/user_id closures
```

### Step 1.3: Refactor Nodes to Be Stateless

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: Lines 346-620 (node functions)

**Key Change**: Nodes access `state["user_id"]` instead of closure variables

**load_context_node**:
```python
def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """Load user context (will be changed to minimal in Day 3)."""
    try:
        from app.core.database import get_db_context

        # ✅ Get user_id from state
        user_id = state["user_id"]

        with get_db_context() as db:
            context_builder = UserContext(db, user_id)
            user_context = context_builder.build_context(minimal=False)  # Still complete for now

            logger.info(f"[Node:load_context] Loaded context for user {user_id}")

            return {
                "user_context": user_context,
                "turn_count": state.get("turn_count", 0) + 1
            }

    except Exception as e:
        logger.error(f"[Node:load_context] Error: {e}", exc_info=True)
        return {
            "user_context": {"error": str(e)},
            "turn_count": state.get("turn_count", 0) + 1
        }
```

**classify_intent_node** and **generate_response_node** - no changes needed (they already use state)

### Step 1.4: Update Graph Creation to Be Stateless

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: Lines 626-669

**Before**:
```python
def create_nutrition_graph(db: Session, user_id: int) -> StateGraph:
    """Create graph with user-specific tools"""
    tools = create_nutrition_tools(db, user_id)  # Closure-based
    # ...
```

**After**:
```python
def create_nutrition_graph_structure() -> StateGraph:
    """
    Create stateless graph structure.

    This graph can be compiled once and reused for all users.
    User-specific data flows through state, not closures.
    """
    # ✅ Create stateless tools (no db/user_id parameters)
    tools = create_nutrition_tools_v2()

    # Create graph
    workflow = StateGraph(NutritionState)

    # Add nodes (all stateless)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("tools", ToolNode(tools))

    # Define flow
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "classify_intent")
    workflow.add_edge("classify_intent", "generate_response")
    workflow.add_conditional_edges(
        "generate_response",
        should_use_tools,
        {"tools": "tools", "end": END}
    )
    workflow.add_edge("tools", "generate_response")

    logger.info("[Graph] Created stateless nutrition graph structure")

    return workflow
```

### Step 1.5: Create Graph Instance Singleton

**Create New File**: `backend/app/agents/graph_instance.py`

```python
"""
Singleton compiled LangGraph instance for nutrition assistant.

This module initializes a single compiled graph at application startup
and provides access to it for all requests. This eliminates the 90ms
overhead of graph creation and compilation per request.
"""

import logging
from typing import Optional
from contextlib import asynccontextmanager

from langgraph.graph import StateGraph
from langgraph.checkpoint.mongodb import MongoDBSaver

from app.core.config import settings
from app.core.mongodb import get_mongo_sync_client

logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================

_compiled_graph = None
_checkpointer = None

# ============================================================================
# INITIALIZATION
# ============================================================================

@asynccontextmanager
async def initialize_nutrition_graph():
    """
    Initialize the nutrition graph at application startup.

    Should be called in FastAPI lifespan context manager.
    Compiles the graph once and stores it globally.
    """
    global _compiled_graph, _checkpointer

    logger.info("[GraphInit] 🚀 Initializing nutrition LangGraph...")

    try:
        # 1. Create MongoDB checkpointer
        logger.info("[GraphInit] Creating MongoDB checkpointer...")
        client = get_mongo_sync_client()
        _checkpointer = MongoDBSaver(
            client=client,
            db_name=settings.mongodb_db
        )
        logger.info(f"[GraphInit] ✅ Checkpointer connected: {settings.mongodb_db}")

        # 2. Build graph structure
        logger.info("[GraphInit] Building stateless graph structure...")
        from app.agents.nutrition_graph import create_nutrition_graph_structure

        workflow = create_nutrition_graph_structure()
        logger.info("[GraphInit] ✅ Graph structure created")

        # 3. Compile graph with checkpointer
        logger.info("[GraphInit] Compiling graph...")
        _compiled_graph = workflow.compile(checkpointer=_checkpointer)
        logger.info("[GraphInit] ✅ Graph compiled successfully")

        # 4. Log summary
        logger.info("[GraphInit] " + "="*60)
        logger.info("[GraphInit] ✅ NUTRITION GRAPH READY")
        logger.info("[GraphInit] - Nodes: load_context, classify_intent, generate_response, tools")
        logger.info("[GraphInit] - Tools: 7 stateless tools")
        logger.info("[GraphInit] - Checkpointer: MongoDB")
        logger.info("[GraphInit] - Pattern: Singleton (compiled once)")
        logger.info("[GraphInit] " + "="*60)

        yield  # Application runs here

    except Exception as e:
        logger.error(f"[GraphInit] ❌ Failed to initialize graph: {e}", exc_info=True)
        raise

    finally:
        # Cleanup on shutdown
        logger.info("[GraphInit] 👋 Shutting down nutrition graph...")
        _compiled_graph = None
        _checkpointer = None

# ============================================================================
# ACCESSORS
# ============================================================================

def get_compiled_graph():
    """
    Get the singleton compiled nutrition graph.

    Returns:
        Compiled LangGraph instance

    Raises:
        RuntimeError: If graph not initialized
    """
    if _compiled_graph is None:
        raise RuntimeError(
            "Nutrition graph not initialized. "
            "Ensure initialize_nutrition_graph() is called in FastAPI lifespan."
        )
    return _compiled_graph

def is_initialized() -> bool:
    """Check if graph has been initialized."""
    return _compiled_graph is not None
```

### Step 1.6: Update FastAPI Main

**File**: `backend/app/main.py`

**Before**:
```python
from fastapi import FastAPI

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0"
)
```

**After**:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.agents.graph_instance import initialize_nutrition_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown:
    - Startup: Initialize LangGraph singleton
    - Shutdown: Cleanup resources
    """
    # Startup
    logger.info("🚀 Starting Nutrilens API...")

    # Initialize LangGraph (compile once)
    async with initialize_nutrition_graph():
        logger.info("✅ All systems initialized")

        yield  # Application runs here

    # Shutdown
    logger.info("👋 Shutting down Nutrilens API...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan  # ✅ Add lifespan handler
)

# Include routers (same as before)
app.include_router(auth.router, prefix="/api/auth")
app.include_router(nutrition_chat.router, prefix="/api/nutrition/chat")
# ... other routers ...
```

### Step 1.7: Update API Endpoint

**File**: `backend/app/api/nutrition_chat.py`
**Location**: Around line 45-80 (chat_v2 endpoint)

**Before**:
```python
@router.post("/v2")
async def chat_v2(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat endpoint using LangGraph."""

    # ❌ Call process_message which rebuilds graph
    result = await process_message(
        db=db,
        user_id=current_user.id,
        message=payload.query,
        session_id=session_id
    )

    return result
```

**After**:
```python
@router.post("/v2")
async def chat_v2(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat endpoint using LangGraph."""

    start_time = time.time()

    # ✅ Get pre-compiled graph (singleton)
    from app.agents.graph_instance import get_compiled_graph
    from langchain_core.messages import HumanMessage

    app = get_compiled_graph()

    # Prepare session ID
    session_id = payload.session_id or f"session-{current_user.id}-{int(time.time())}"

    # Prepare initial state
    from app.agents.nutrition_state import NutritionState

    initial_state: NutritionState = {
        "messages": [HumanMessage(content=payload.query)],
        "user_context": {},
        "intent": None,
        "confidence": 0.0,
        "entities": {},
        "user_id": current_user.id,  # ✅ User ID in state
        "session_id": session_id,
        "turn_count": 0,
        "processing_time_ms": 0,
        "cost_usd": 0.0
    }

    # Configure with thread_id for conversation isolation
    config = {"configurable": {"thread_id": session_id}}

    logger.info(f"[API] Invoking graph: user={current_user.id}, session={session_id}")

    # ✅ Invoke pre-compiled graph
    result = await app.ainvoke(initial_state, config=config)

    # Extract response
    messages = result.get("messages", [])
    assistant_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
    last_message = assistant_messages[-1] if assistant_messages else None

    if last_message:
        response_text = last_message.content
        intent = result.get("intent", "unknown")
    else:
        response_text = "I'm sorry, I couldn't process your request."
        intent = "error"

    # Calculate metrics
    processing_time = (time.time() - start_time) * 1000

    # Save to MongoDB chat history
    await save_chat_message(
        user_id=current_user.id,
        session_id=session_id,
        role="user",
        content=payload.query
    )

    await save_chat_message(
        user_id=current_user.id,
        session_id=session_id,
        role="assistant",
        content=response_text,
        intent=intent
    )

    return {
        "response": response_text,
        "intent": intent,
        "session_id": session_id,
        "processing_time_ms": processing_time
    }
```

### Step 1.8: Remove Old process_message Function

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: Lines 676-800

**Delete or comment out** the old `process_message()` function since we're now calling the graph directly from the endpoint.

### Testing Day 1-2

**Test 1: Application Startup**
```bash
# Start the server
python -m uvicorn app.main:app --reload

# Check logs - should see:
# [GraphInit] 🚀 Initializing nutrition LangGraph...
# [GraphInit] ✅ Graph compiled successfully
# [GraphInit] ✅ NUTRITION GRAPH READY
```

**Test 2: Single User Query**
```python
response = client.post("/api/nutrition/chat/v2",
    headers={"Authorization": f"Bearer {token}"},
    json={"query": "How is my protein today?"}
)

assert response.status_code == 200
assert "protein" in response.json()["response"].lower()
```

**Test 3: Concurrent Users**
```python
import asyncio

async def user_query(user_token, query):
    response = await client.post("/api/nutrition/chat/v2",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"query": query}
    )
    return response

# 10 users simultaneously
tasks = [user_query(user_tokens[i], "How is my protein?") for i in range(10)]
results = await asyncio.gather(*tasks)

# All should succeed
assert all(r.status_code == 200 for r in results)

# Each should get their own data (not mixed up)
for i, result in enumerate(results):
    user_id = get_user_id_from_token(user_tokens[i])
    expected_protein = get_user_protein(user_id)
    assert str(expected_protein) in result.json()["response"]
```

**Test 4: Performance - No Compilation Overhead**
```python
import time

start = time.time()
response = client.post("/api/nutrition/chat/v2",
    headers={"Authorization": f"Bearer {token}"},
    json={"query": "Hello"}
)
duration = (time.time() - start) * 1000

# Should be fast (no 90ms compilation overhead)
assert duration < 1000  # Under 1 second
assert response.json()["processing_time_ms"] < 1000
```

**Success Criteria for Day 1-2**:
- ✅ Application starts successfully
- ✅ Graph compiled once at startup (logs confirm)
- ✅ All 7 tools work with user_id parameter
- ✅ Single user queries work
- ✅ Concurrent users work (no interference)
- ✅ Response time improved (no 90ms overhead)
- ✅ No errors in logs

---

## Day 3: Priority 4 - Minimal Context + Tools Pattern

**Goal**: Switch to minimal context (~500 tokens), let tools fetch data on demand

**Time**: 1 day
**Risk**: Medium
**Savings**: $1,500/month

### Step 3.1: Update load_context_node to Minimal

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: load_context_node function

**Replace with**:
```python
def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """
    Load MINIMAL user context.

    Strategy: Load only essential metadata. Tools fetch detailed data on demand.

    Minimal context (~50 tokens):
    - user_id: For tool calls
    - goal_type: For understanding intent
    - dietary_restrictions: For recipe filtering
    - current_date/time: For temporal context

    Detailed data (consumed, remaining, inventory, meals) fetched by tools when LLM needs them.
    This matches production LangGraph patterns and reduces tokens by 90%.
    """
    try:
        from app.core.database import get_db_context

        user_id = state["user_id"]

        with get_db_context() as db:
            context_builder = UserContext(db, user_id)

            # ✅ Fetch only profile data
            profile = context_builder.get_profile()

            # ✅ Build minimal context
            minimal_context = {
                "user_id": user_id,
                "goal_type": profile.get("goal_type", "general_health"),
                "activity_level": profile.get("activity_level", "moderate"),
                "dietary_restrictions": profile.get("dietary_restrictions", []),
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "current_time": datetime.now().strftime("%H:%M"),
            }

            logger.info(
                f"[Node:load_context] ✅ Loaded minimal context: "
                f"user={user_id}, goal={minimal_context['goal_type']}, "
                f"restrictions={len(minimal_context['dietary_restrictions'])}"
            )

            return {
                "user_context": minimal_context,
                "turn_count": state.get("turn_count", 0) + 1
            }

    except Exception as e:
        logger.error(f"[Node:load_context] Error: {e}", exc_info=True)
        return {
            "user_context": {
                "user_id": state["user_id"],
                "goal_type": "general_health",
                "dietary_restrictions": [],
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "current_time": datetime.now().strftime("%H:%M"),
                "error": str(e)
            },
            "turn_count": state.get("turn_count", 0) + 1
        }
```

### Step 3.2: Update System Prompt to Minimal + Tool-Focused

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: generate_response_node, system prompt section

**Replace system prompt with**:
```python
system_prompt = f"""You are a helpful nutrition AI assistant. Today is {context['current_date']} at {context['current_time']}.

# USER PROFILE
User ID: {context['user_id']}
Fitness Goal: {context['goal_type']}
Activity Level: {context['activity_level']}
Dietary Restrictions: {', '.join(context['dietary_restrictions']) if context['dietary_restrictions'] else 'None'}

# YOUR TOOLS - Use these to fetch data when needed

📊 **get_nutrition_stats(user_id: int)**
   Get today's consumed/remaining/targets for all macros (calories, protein, carbs, fat)

   When to call:
   - User asks: "How is my protein?", "What's my progress?", "Show my macros", "Am I on track?"

   Example: User says "How am I doing today?" → Call get_nutrition_stats(user_id={context['user_id']})

🥘 **check_inventory(user_id: int, show_details: bool = False)**
   Get user's food inventory (items available, expiring soon, low stock)

   When to call:
   - User asks: "What food do I have?", "What's in my pantry?", "What's expiring?"

   Example: User says "What can I cook?" → Call check_inventory(user_id={context['user_id']})

📅 **get_meal_plan(user_id: int, days: int = 1)**
   Get upcoming scheduled meals with times and macros

   When to call:
   - User asks: "What's for dinner?", "Show my meal plan", "What meals are planned?"

   Example: User says "What's planned today?" → Call get_meal_plan(user_id={context['user_id']}, days=1)

🔍 **suggest_recipes(user_id: int, meal_type: str, max_calories: int = None, min_protein: int = None)**
   Search recipe database by meal type, calories, protein, and restrictions

   When to call:
   - User asks: "Suggest me lunch", "Find high-protein meals", "What should I eat?"

   Example: User says "I want a healthy breakfast" → Call suggest_recipes(user_id={context['user_id']}, meal_type="breakfast")

🎯 **get_goal_aligned_recipes(user_id: int, count: int = 5)**
   Get recipes specifically for user's goal ({context['goal_type']})

   When to call:
   - User asks: "Recipes for my goal", "What fits my plan?", "Goal-focused meals"

   Example: User says "What should I eat for {context['goal_type']}?" → Call this tool

✍️ **log_meal_consumption(user_id: int, meal_log_id: int, portions: float = 1.0)**
   Record that user consumed a meal (WRITES to database)

   When to call:
   - User says: "I ate [meal]", "Log my breakfast", "Mark meal as eaten"

   Example: User says "I had my lunch" → Call log_meal_consumption

🔄 **swap_meal_recipe(user_id: int, meal_log_id: int, new_recipe_id: int)**
   Change a planned meal to different recipe (WRITES to database)

   When to call:
   - User says: "Swap my dinner", "Change meal to [recipe]", "Different meal"

   Example: User says "I don't like that recipe" → Call swap_meal_recipe

# IMPORTANT INSTRUCTIONS

1. **Understand the query**: What is the user asking for?

2. **Decide tool strategy**:
   - Stats/progress questions? → Call get_nutrition_stats first
   - Inventory questions? → Call check_inventory first
   - Meal plan questions? → Call get_meal_plan first
   - Recipe requests? → Call suggest_recipes or get_goal_aligned_recipes
   - Log meals? → Call log_meal_consumption
   - General chat? → No tools needed, respond naturally

3. **Call tools with user_id**: Always pass user_id={context['user_id']} to tools

4. **Use tool results**: Fetch fresh data, then give helpful, conversational answer

5. **Be proactive**: If related info might help, mention it

6. **Multiple needs**: You can call multiple tools if needed

# EXAMPLES

User: "How is my protein today?"
You: [Call get_nutrition_stats(user_id={context['user_id']})] "You've consumed 45g out of 100g protein. You have 55g remaining."

User: "What should I eat for lunch?"
You: [Call suggest_recipes(user_id={context['user_id']}, meal_type="lunch")] "Here are great lunch options: [recipes]"

User: "Am I on track?"
You: [Call get_nutrition_stats(user_id={context['user_id']})] "Let's check your progress..."

User: "Hello!"
You: [No tools] "Hi! How can I help with your nutrition today?"

Current session: {state.get('session_id')}
"""
```

### Testing Day 3

**Test 1: Stats Query - Should Call Tool**
```python
response = client.post("/api/nutrition/chat/v2",
    json={"query": "How is my protein today?"}
)

# Check tool was called
logs = get_recent_logs()
assert "[Tool:get_nutrition_stats]" in logs
assert "Fetched for user" in logs

# Response should be accurate
assert "45" in response.json()["response"]  # User's actual protein
assert "100" in response.json()["response"]  # User's target
```

**Test 2: General Chat - NO Tool Calls**
```python
response = client.post("/api/nutrition/chat/v2",
    json={"query": "Hello, how are you?"}
)

# No tool calls
logs = get_recent_logs()
assert "[Tool:" not in logs  # No tool executed

# Conversational response
assert "hello" in response.json()["response"].lower() or "hi" in response.json()["response"].lower()
```

**Test 3: Fresh Data After Action**
```python
# Step 1: Check stats
response1 = client.post("/api/nutrition/chat/v2",
    json={"query": "How is my protein?", "session_id": "test123"}
)
assert "45" in response1.json()["response"]

# Step 2: Log meal (adds 12g protein)
response2 = client.post("/api/nutrition/chat/v2",
    json={"query": "I ate 2 eggs for breakfast", "session_id": "test123"}
)
assert "success" in response2.json()["response"].lower()

# Step 3: Check stats again - should show UPDATED data
response3 = client.post("/api/nutrition/chat/v2",
    json={"query": "How is my protein now?", "session_id": "test123"}
)
# Should show 57g (45 + 12), NOT stale 45g
assert "57" in response3.json()["response"]
assert "45" not in response3.json()["response"]  # Old value should NOT appear
```

**Test 4: Cost Validation**
```python
costs = []
for i in range(100):
    query = random.choice([
        "How is my protein?",      # Data query (tool call)
        "Suggest me lunch",        # Recipe query (tool call)
        "Hello",                   # Chat (no tool)
        "What's in my pantry?",    # Inventory query (tool call)
        "Thanks!",                 # Chat (no tool)
    ])

    response = client.post("/api/nutrition/chat/v2", json={"query": query})
    # Estimate cost based on tokens
    cost = estimate_cost(response)
    costs.append(cost)

avg_cost = sum(costs) / len(costs)

print(f"Average cost: ${avg_cost:.5f}")
assert avg_cost < 0.0015  # Target: <$0.0015/query
assert avg_cost < 0.0037  # Must be better than original
```

**Success Criteria for Day 3**:
- ✅ System prompt is minimal (~500 tokens, not 5000)
- ✅ LLM calls tools appropriately (stats queries → tool called)
- ✅ LLM doesn't call tools unnecessarily (general chat → no tool)
- ✅ Data is always fresh (logged meal → updated stats)
- ✅ Average cost <$0.0015 per query
- ✅ All query types work correctly

---

## Day 4: Priority 2 - Message Trimming

**Goal**: Prevent unbounded message history growth

**Time**: 0.5 days
**Risk**: Low
**Savings**: $4,200/month

### Step 4.1: Add pre_model_hook Function

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: Add before create_nutrition_graph_structure function

```python
from langchain_core.messages.utils import trim_messages, count_tokens_approximately

def create_pre_model_hook():
    """
    Create pre-model hook for message trimming.

    Automatically trims message history to prevent unbounded growth
    while preserving full history in checkpointer.

    Strategy: Keep last 5 turns (10 messages), max 4000 tokens
    """

    def pre_model_hook(state: NutritionState) -> Dict[str, Any]:
        """
        Trim messages before LLM call.

        Returns dict with 'llm_input_messages' to pass trimmed messages to LLM
        while keeping full history in state["messages"] and checkpointer.
        """
        messages = state.get("messages", [])

        # If 5 turns or less, no trimming needed
        if len(messages) <= 10:  # 5 turns = 10 messages (human + AI)
            return {}  # Use original messages

        try:
            # Trim to last 5 turns, max 4000 tokens
            trimmed_messages = trim_messages(
                messages,
                strategy="last",  # Keep most recent
                token_counter=count_tokens_approximately,
                max_tokens=4000,
                start_on="human",  # Start with human message
                end_on=("human", "tool"),  # End with human or tool
            )

            # Log trimming
            original_count = len(messages)
            trimmed_count = len(trimmed_messages)
            removed = original_count - trimmed_count

            if removed > 0:
                logger.info(
                    f"[MessageTrimming] Trimmed {removed} messages "
                    f"({original_count} → {trimmed_count})"
                )

            # Return trimmed messages for LLM input
            # Full history stays in state["messages"] and checkpointer
            return {"llm_input_messages": trimmed_messages}

        except Exception as e:
            logger.warning(f"[MessageTrimming] Failed: {e}. Using original messages.")
            return {}

    return pre_model_hook
```

### Step 4.2: Update Graph Compilation

**File**: `backend/app/agents/graph_instance.py`
**Location**: In initialize_nutrition_graph function

**Update compilation**:
```python
# 2. Build graph structure
logger.info("[GraphInit] Building stateless graph structure...")
from app.agents.nutrition_graph import create_nutrition_graph_structure, create_pre_model_hook

workflow = create_nutrition_graph_structure()
pre_model_hook = create_pre_model_hook()  # ✅ Add hook
logger.info("[GraphInit] ✅ Graph structure created")

# 3. Compile graph with checkpointer AND hook
logger.info("[GraphInit] Compiling graph with message trimming...")
_compiled_graph = workflow.compile(
    checkpointer=_checkpointer,
    pre_model_hook=pre_model_hook  # ✅ Add to compilation
)
logger.info("[GraphInit] ✅ Graph compiled with message trimming")
```

### Step 4.3: Update Nodes to Use Trimmed Messages

**File**: `backend/app/agents/nutrition_graph.py`
**Location**: generate_response_node

**Update to use llm_input_messages if available**:
```python
async def generate_response_node(state: NutritionState) -> Dict[str, Any]:
    """Generate response using GPT-4 with tools."""

    # ... build system prompt ...

    # ✅ Use trimmed messages if available (from pre_model_hook)
    # Otherwise use full message history
    conversation_messages = state.get("llm_input_messages", state.get("messages", []))

    messages = [
        SystemMessage(content=system_prompt),
        *conversation_messages  # ✅ Uses trimmed messages when available
    ]

    # Log if trimming occurred
    full_count = len(state.get("messages", []))
    used_count = len(conversation_messages)
    if full_count != used_count:
        logger.info(
            f"[Node:generate_response] Using {used_count}/{full_count} messages "
            f"(trimmed by pre_model_hook)"
        )

    # ... rest of function ...
```

### Testing Day 4

**Test 1: Short Conversation - No Trimming**
```python
session_id = "test-trim-1"

# 3 turns
for i in range(3):
    response = client.post("/api/nutrition/chat/v2",
        json={"query": f"Query {i}", "session_id": session_id}
    )

# Check logs - no trimming should occur
logs = get_recent_logs()
assert "Trimmed" not in logs  # No trimming for short conversations
```

**Test 2: Long Conversation - Trimming Activates**
```python
session_id = "test-trim-2"

# 10 turns (20 messages)
for i in range(10):
    response = client.post("/api/nutrition/chat/v2",
        json={"query": f"Query {i}", "session_id": session_id}
    )

# After turn 6, trimming should activate
logs = get_recent_logs()
assert "Trimmed" in logs
assert "messages" in logs  # Should show message counts

# Latest response should still be correct
assert response.status_code == 200
```

**Test 3: Very Long Conversation - Bounded Growth**
```python
session_id = "test-trim-3"

# 50 turns
for i in range(50):
    response = client.post("/api/nutrition/chat/v2",
        json={"query": f"Query {i}", "session_id": session_id}
    )

# Check that token count stays bounded
# (Can't easily check directly, but no errors means it worked)
assert response.status_code == 200

# Logs should show consistent trimming
logs = get_recent_logs()
assert "Trimmed" in logs
```

**Success Criteria for Day 4**:
- ✅ Short conversations (<5 turns) not trimmed
- ✅ Long conversations (>5 turns) automatically trimmed
- ✅ Token count bounded to ~4000-5000 per request
- ✅ No context overflow errors in long conversations
- ✅ Response quality maintained (recent context preserved)
- ✅ Full history still in checkpointer (for debugging)

---

## Day 5-6: Integration Testing & Validation

**Goal**: Validate complete system end-to-end

**Time**: 2 days
**Risk**: Low

### Test Suite 1: Feature Completeness

**Test all query types**:
```python
test_cases = [
    {"query": "How is my protein?", "expected_tool": "get_nutrition_stats"},
    {"query": "What's in my pantry?", "expected_tool": "check_inventory"},
    {"query": "What's for dinner?", "expected_tool": "get_meal_plan"},
    {"query": "Suggest me lunch", "expected_tool": "suggest_recipes"},
    {"query": "Recipes for muscle gain", "expected_tool": "get_goal_aligned_recipes"},
    {"query": "I ate 2 eggs", "expected_tool": "log_meal_consumption"},
    {"query": "Hello", "expected_tool": None},  # No tool
]

for test in test_cases:
    response = client.post("/api/nutrition/chat/v2", json=test)

    assert response.status_code == 200

    logs = get_recent_logs()
    if test["expected_tool"]:
        assert f"[Tool:{test['expected_tool']}]" in logs
    else:
        assert "[Tool:" not in logs
```

### Test Suite 2: Cost Validation

**Measure actual costs**:
```python
# Run 1000 mixed queries
costs = []
for i in range(1000):
    query = random.choice([
        "How is my protein?",
        "Suggest me lunch",
        "What's in my pantry?",
        "Hello",
        "What's for dinner?",
        "Thanks!",
    ])

    response = client.post("/api/nutrition/chat/v2", json={"query": query})
    cost = estimate_cost_from_response(response)
    costs.append(cost)

# Calculate metrics
avg_cost = sum(costs) / len(costs)
total_cost = sum(costs)
monthly_projection = avg_cost * 300000

print(f"Average cost per query: ${avg_cost:.5f}")
print(f"Total cost (1000 queries): ${total_cost:.2f}")
print(f"Monthly projection (300K): ${monthly_projection:.2f}")

# Validate targets
assert avg_cost < 0.0015  # Target
assert monthly_projection < 500  # Budget
```

### Test Suite 3: Performance Validation

**Measure response times**:
```python
times = []

for i in range(100):
    start = time.time()
    response = client.post("/api/nutrition/chat/v2",
        json={"query": "How is my protein?"}
    )
    duration = (time.time() - start) * 1000
    times.append(duration)

# Calculate metrics
avg_time = sum(times) / len(times)
p95_time = sorted(times)[94]  # 95th percentile
p99_time = sorted(times)[98]  # 99th percentile

print(f"Average: {avg_time:.0f}ms")
print(f"P95: {p95_time:.0f}ms")
print(f"P99: {p99_time:.0f}ms")

# Validate targets
assert avg_time < 1100  # Target: <1100ms average
assert p95_time < 1500  # Target: <1500ms p95
assert p99_time < 2000  # Target: <2000ms p99
```

### Test Suite 4: Concurrent Load

**Test 100 concurrent users**:
```python
import asyncio

async def user_session(user_id):
    # Each user makes 5 queries
    for i in range(5):
        response = await client.post("/api/nutrition/chat/v2",
            headers=auth_header(user_id),
            json={"query": f"Query {i}"}
        )
        assert response.status_code == 200

# 100 users, 5 queries each = 500 total
tasks = [user_session(i) for i in range(100)]
await asyncio.gather(*tasks)

# All should succeed
print("✅ 500 concurrent requests handled successfully")
```

### Final Validation Checklist

**Architecture**:
- ✅ Graph compiled once at startup
- ✅ Tools are stateless (accept user_id parameter)
- ✅ Minimal context loaded (~500 tokens)
- ✅ Message history trimmed (bounded to 4000 tokens)
- ✅ All 7 tools working correctly

**Cost**:
- ✅ Average cost <$0.0015 per query
- ✅ Monthly projection <$500 (300K queries)
- ✅ 67%+ savings vs original

**Performance**:
- ✅ Average response time <1100ms
- ✅ P95 <1500ms, P99 <2000ms
- ✅ No compilation overhead (90ms saved)
- ✅ Handles 100+ concurrent users

**Quality**:
- ✅ All query types work correctly
- ✅ LLM calls appropriate tools
- ✅ Data always fresh (no stale context)
- ✅ Conversation memory works across turns
- ✅ No regressions vs original functionality

---

## Summary

**Total Implementation Time**: 5-6 days

**Expected Results**:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| System prompt tokens | 5,000 | 500 | 90% reduction |
| Cost per query | $0.0037 | $0.001 | 73% reduction |
| Monthly cost (300K) | $1,110 | $300 | $810 saved |
| Response time | 1200ms | 900ms | 25% faster |
| Graph compilation | Per request (90ms) | Once (0ms) | Eliminated |
| Message history | Unbounded | Bounded (4000 tokens) | Fixed |
| Data freshness | Stale after actions | Always fresh | Fixed |

**Success Metrics**:
- ✅ 73% cost reduction
- ✅ 25% performance improvement
- ✅ All architectural issues fixed
- ✅ Production-standard implementation
- ✅ No regressions in functionality

---

## Ready to Start?

We can begin with **Day 1-2: Compile Graph Once at Startup**.

Shall we proceed with Step 1.1 (Create Database Context Manager)?
