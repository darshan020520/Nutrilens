# Implementation Changes Checklist
**Exact file changes to avoid overengineering**

---

## Day 1-2: Compile Graph Once at Startup

### Change 1: Refactor Tools to Stateless (REMOVED get_db_context - use SessionLocal directly)

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: 38-340
**Action**: REPLACE function signature and ALL 7 tool definitions

**BEFORE**:
```python
def create_nutrition_tools(db: Session, user_id: int) -> List[Tool]:
    """Creates tools with db and user_id captured in closure"""

    @tool
    def get_nutrition_stats() -> str:
        """Get nutrition stats"""
        context_builder = UserContext(db, user_id)  # ❌ Uses closure
        # ...
```

**AFTER**:
```python
def create_nutrition_tools_v2() -> List[Tool]:
    """Creates stateless tools"""

    @tool
    def get_nutrition_stats(user_id: int) -> str:
        """Get nutrition stats

        Args:
            user_id: User ID (passed by LLM from context)
        """
        from app.models.database import SessionLocal

        db = SessionLocal()  # ✅ Creates own db session
        try:
            context_builder = UserContext(db, user_id)
            # ... rest same
        finally:
            db.close()
```

**Apply to ALL 7 tools**:
1. `get_nutrition_stats(user_id: int)`
2. `check_inventory(user_id: int, show_details: bool = False)`
3. `get_meal_plan(user_id: int, days: int = 1)`
4. `suggest_recipes(user_id: int, meal_type: str, max_calories: int = None, min_protein: int = None)`
5. `get_goal_aligned_recipes(user_id: int, count: int = 5)`
6. `log_meal_consumption(user_id: int, meal_log_id: int, portions: float = 1.0)`
7. `swap_meal_recipe(user_id: int, meal_log_id: int, new_recipe_id: int)`

**Pattern for each tool**:
- Add `user_id: int` as first parameter
- Remove db/user_id from closure
- Add `from app.models.database import SessionLocal`
- Wrap logic in `db = SessionLocal()` with try/finally

---

### Change 2: Make load_context_node Stateless

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: 346-376
**Action**: UPDATE to get user_id from state

**BEFORE**:
```python
def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """Load context"""
    try:
        context_builder = UserContext(db, state["user_id"])  # ❌ db from closure
```

**AFTER**:
```python
def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """Load context"""
    try:
        from app.models.database import SessionLocal

        user_id = state["user_id"]  # ✅ From state
        db = SessionLocal()
        try:
            context_builder = UserContext(db, user_id)
            # ... rest of logic
        finally:
            db.close()
```

---

### Change 3: Rename Graph Creation Function

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: 626-669
**Action**: RENAME function and UPDATE to use stateless tools

**BEFORE**:
```python
def create_nutrition_graph(db: Session, user_id: int) -> StateGraph:
    """Create graph with user-specific tools"""
    tools = create_nutrition_tools(db, user_id)  # ❌ Closure-based

    workflow = StateGraph(NutritionState)
    # ... add nodes ...
    return workflow
```

**AFTER**:
```python
def create_nutrition_graph_structure() -> StateGraph:
    """Create stateless graph structure"""
    tools = create_nutrition_tools_v2()  # ✅ Stateless tools

    workflow = StateGraph(NutritionState)
    # ... add nodes ... (NO CHANGES to node logic)
    return workflow
```

---

### Change 4: Create Graph Instance Singleton

**File**: `backend/app/agents/graph_instance.py` (NEW FILE)
**Action**: CREATE this entire file

```python
"""Singleton compiled LangGraph instance."""

import logging
from contextlib import asynccontextmanager
from langgraph.checkpoint.mongodb import MongoDBSaver
from app.core.config import settings
from app.core.mongodb import get_mongo_sync_client

logger = logging.getLogger(__name__)

_compiled_graph = None
_checkpointer = None

@asynccontextmanager
async def initialize_nutrition_graph():
    """Initialize graph at startup."""
    global _compiled_graph, _checkpointer

    logger.info("[GraphInit] Initializing LangGraph...")

    # Create checkpointer
    client = get_mongo_sync_client()
    _checkpointer = MongoDBSaver(client=client, db_name=settings.mongodb_db)

    # Build and compile graph
    from app.agents.nutrition_graph import create_nutrition_graph_structure

    workflow = create_nutrition_graph_structure()
    _compiled_graph = workflow.compile(checkpointer=_checkpointer)

    logger.info("[GraphInit] ✅ Graph compiled successfully")

    yield  # App runs here

    logger.info("[GraphInit] Shutting down...")
    _compiled_graph = None
    _checkpointer = None

def get_compiled_graph():
    """Get singleton graph."""
    if _compiled_graph is None:
        raise RuntimeError("Graph not initialized")
    return _compiled_graph

def is_initialized() -> bool:
    """Check if initialized."""
    return _compiled_graph is not None
```

---

### Change 5: Add Lifespan to FastAPI

**File**: `backend/app/main.py`
**Lines**: Where `app = FastAPI(...)` is defined
**Action**: ADD lifespan handler

**BEFORE**:
```python
from fastapi import FastAPI

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0"
)
```

**AFTER**:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.agents.graph_instance import initialize_nutrition_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup/shutdown."""
    logger.info("🚀 Starting up...")

    async with initialize_nutrition_graph():
        logger.info("✅ Graph initialized")
        yield  # App runs here

    logger.info("👋 Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan  # ✅ ADD THIS
)
```

---

### Change 6: Update Chat Endpoint

**File**: `backend/app/api/nutrition_chat.py`
**Lines**: chat_v2 endpoint function (around line 45-80)
**Action**: REPLACE endpoint logic

**BEFORE**:
```python
@router.post("/v2")
async def chat_v2(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat endpoint"""

    # ❌ Calls process_message which rebuilds graph
    result = await process_message(
        db=db,
        user_id=current_user.id,
        message=payload.query,
        session_id=session_id
    )

    return result
```

**AFTER**:
```python
from app.agents.graph_instance import get_compiled_graph
from app.agents.nutrition_state import NutritionState
from langchain_core.messages import HumanMessage, AIMessage

@router.post("/v2")
async def chat_v2(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Chat endpoint"""
    start_time = time.time()

    # ✅ Get pre-compiled graph
    app = get_compiled_graph()

    # Prepare session ID
    session_id = payload.session_id or f"session-{current_user.id}-{int(time.time())}"

    # Prepare state
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

    # Configure with thread_id
    config = {"configurable": {"thread_id": session_id}}

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

    # Save to chat history
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

---

### Change 7: Remove Old process_message Function

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: 676-800 (approximately)
**Action**: DELETE the entire `process_message` function

We don't need it anymore since we call the graph directly from the endpoint.

---

## Day 3: Minimal Context + Tools Pattern

### Change 8: Update load_context_node to Minimal

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: load_context_node function body
**Action**: REPLACE function body

**BEFORE**:
```python
def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """Load context"""
    try:
        from app.core.database import get_db_context

        user_id = state["user_id"]

        with get_db_context() as db:
            context_builder = UserContext(db, user_id)
            user_context = context_builder.build_context(minimal=False)  # ❌ Complete context

            logger.info(f"[Node:load_context] Loaded context for user {user_id}")

            return {
                "user_context": user_context,
                "turn_count": state.get("turn_count", 0) + 1
            }
```

**AFTER**:
```python
def load_context_node(state: NutritionState) -> Dict[str, Any]:
    """Load MINIMAL context only"""
    try:
        from app.models.database import SessionLocal

        user_id = state["user_id"]
        db = SessionLocal()
        try:
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
                f"user={user_id}, goal={minimal_context['goal_type']}"
            )

            return {
                "user_context": minimal_context,
                "turn_count": state.get("turn_count", 0) + 1
            }
        finally:
            db.close()
```

**Key changes**:
- Change `build_context(minimal=False)` to building our own minimal dict
- Only include: user_id, goal_type, activity_level, dietary_restrictions, current_date, current_time
- Remove: consumed, remaining, targets, inventory, upcoming meals (tools will fetch these)

---

### Change 9: Update System Prompt to Minimal

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: generate_response_node, system prompt variable
**Action**: REPLACE entire system_prompt string

**BEFORE** (huge prompt with all data):
```python
system_prompt = f"""
You are a nutrition AI assistant.

# USER CONTEXT (COMPLETE DATA):
{json.dumps(context, indent=2)}

Today's consumption:
- Calories: {context['today']['consumed']['calories']}/{context['targets']['calories']}
- Protein: {context['today']['consumed']['protein_g']}/{context['targets']['protein_g']}g
... (lots more data formatting)

You have these tools available:
1. get_nutrition_stats
... (brief tool list)
"""
```

**AFTER** (minimal prompt, tool-focused):
```python
system_prompt = f"""You are a helpful nutrition AI assistant. Today is {context['current_date']} at {context['current_time']}.

# USER PROFILE
User ID: {context['user_id']}
Fitness Goal: {context['goal_type']}
Activity Level: {context['activity_level']}
Dietary Restrictions: {', '.join(context['dietary_restrictions']) if context['dietary_restrictions'] else 'None'}

# YOUR TOOLS - Use these to fetch data when needed

📊 **get_nutrition_stats(user_id: int)**
   Get today's consumed/remaining/targets for all macros

   When to call: User asks "How is my protein?", "What's my progress?", "Show my macros"

   Example: User says "How am I doing?" → Call get_nutrition_stats(user_id={context['user_id']})

🥘 **check_inventory(user_id: int, show_details: bool = False)**
   Get user's food inventory

   When to call: User asks "What food do I have?", "What's expiring?"

   Example: User says "What's in my pantry?" → Call check_inventory(user_id={context['user_id']})

📅 **get_meal_plan(user_id: int, days: int = 1)**
   Get upcoming scheduled meals

   When to call: User asks "What's for dinner?", "Show my meal plan"

   Example: User says "What's planned?" → Call get_meal_plan(user_id={context['user_id']})

🔍 **suggest_recipes(user_id: int, meal_type: str, max_calories: int = None, min_protein: int = None)**
   Search recipe database

   When to call: User asks "Suggest me lunch", "Find high-protein meals"

   Example: User says "Healthy breakfast?" → Call suggest_recipes(user_id={context['user_id']}, meal_type="breakfast")

🎯 **get_goal_aligned_recipes(user_id: int, count: int = 5)**
   Get recipes for user's goal ({context['goal_type']})

   When to call: User asks "Recipes for my goal", "Goal-focused meals"

✍️ **log_meal_consumption(user_id: int, meal_log_id: int, portions: float = 1.0)**
   Record meal consumed (WRITES to database)

   When to call: User says "I ate [meal]", "Log my breakfast"

🔄 **swap_meal_recipe(user_id: int, meal_log_id: int, new_recipe_id: int)**
   Change planned meal (WRITES to database)

   When to call: User says "Swap my dinner", "Different meal"

# INSTRUCTIONS

1. Understand the query
2. Decide tool strategy:
   - Stats questions? → Call get_nutrition_stats
   - Inventory questions? → Call check_inventory
   - Meal plan questions? → Call get_meal_plan
   - Recipe requests? → Call suggest_recipes or get_goal_aligned_recipes
   - Log meals? → Call log_meal_consumption
   - General chat? → No tools needed
3. Always pass user_id={context['user_id']} to tools
4. Use tool results to give helpful answers

# EXAMPLES

User: "How is my protein?"
You: [Call get_nutrition_stats(user_id={context['user_id']})] "You've consumed 45g out of 100g protein."

User: "Suggest me lunch"
You: [Call suggest_recipes(user_id={context['user_id']}, meal_type="lunch")] "Here are lunch options..."

User: "Hello!"
You: [No tools] "Hi! How can I help with your nutrition today?"

Current session: {state.get('session_id')}
"""
```

**Key changes**:
- Remove ALL embedded data (consumed, remaining, targets, inventory, meals)
- Keep only: user_id, goal, restrictions, date/time
- Add detailed tool descriptions with examples
- Add clear "When to call" guidelines
- Add instruction to always pass user_id

---

## Day 4: Message Trimming

### Change 10: Add pre_model_hook Function

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: Add BEFORE create_nutrition_graph_structure function
**Action**: ADD new function

```python
from langchain_core.messages.utils import trim_messages, count_tokens_approximately

def create_pre_model_hook():
    """Create pre-model hook for message trimming."""

    def pre_model_hook(state: NutritionState) -> Dict[str, Any]:
        """Trim messages before LLM call."""
        messages = state.get("messages", [])

        # If 5 turns or less, no trimming
        if len(messages) <= 10:
            return {}

        try:
            # Trim to last 5 turns, max 4000 tokens
            trimmed_messages = trim_messages(
                messages,
                strategy="last",
                token_counter=count_tokens_approximately,
                max_tokens=4000,
                start_on="human",
                end_on=("human", "tool"),
            )

            # Log trimming
            removed = len(messages) - len(trimmed_messages)
            if removed > 0:
                logger.info(f"[MessageTrimming] Trimmed {removed} messages")

            return {"llm_input_messages": trimmed_messages}

        except Exception as e:
            logger.warning(f"[MessageTrimming] Failed: {e}")
            return {}

    return pre_model_hook
```

---

### Change 11: Update Graph Compilation with Hook

**File**: `backend/app/agents/graph_instance.py`
**Lines**: In initialize_nutrition_graph, compilation section
**Action**: UPDATE compilation call

**BEFORE**:
```python
# Build graph
from app.agents.nutrition_graph import create_nutrition_graph_structure

workflow = create_nutrition_graph_structure()
_compiled_graph = workflow.compile(checkpointer=_checkpointer)
```

**AFTER**:
```python
# Build graph with hook
from app.agents.nutrition_graph import create_nutrition_graph_structure, create_pre_model_hook

workflow = create_nutrition_graph_structure()
pre_model_hook = create_pre_model_hook()  # ✅ ADD

_compiled_graph = workflow.compile(
    checkpointer=_checkpointer,
    pre_model_hook=pre_model_hook  # ✅ ADD
)
```

---

### Change 12: Update generate_response_node to Use Trimmed Messages

**File**: `backend/app/agents/nutrition_graph.py`
**Lines**: generate_response_node, where messages are prepared for LLM
**Action**: UPDATE message preparation

**BEFORE**:
```python
async def generate_response_node(state: NutritionState) -> Dict[str, Any]:
    # ... build system prompt ...

    messages = [
        SystemMessage(content=system_prompt),
        *state["messages"]  # ❌ Always full history
    ]

    response = await llm.bind_tools(tools).ainvoke(messages)
```

**AFTER**:
```python
async def generate_response_node(state: NutritionState) -> Dict[str, Any]:
    # ... build system prompt ...

    # ✅ Use trimmed messages if available
    conversation_messages = state.get("llm_input_messages", state.get("messages", []))

    messages = [
        SystemMessage(content=system_prompt),
        *conversation_messages  # ✅ Uses trimmed when available
    ]

    # Log if trimming occurred
    full_count = len(state.get("messages", []))
    used_count = len(conversation_messages)
    if full_count != used_count:
        logger.info(f"[Node:generate_response] Using {used_count}/{full_count} messages")

    response = await llm.bind_tools(tools).ainvoke(messages)
```

---

## Summary of ALL Changes

### Files Created (1):
1. ✅ `backend/app/agents/graph_instance.py` - Singleton graph

### Files Modified (3):
1. ✅ `backend/app/agents/nutrition_graph.py` - All major changes
2. ✅ `backend/app/main.py` - Add lifespan
3. ✅ `backend/app/api/nutrition_chat.py` - Update endpoint

### Files Deleted (0):
- No files deleted

### Total Changes:
- **12 specific changes** across 4 files (NOT 5 - removed unnecessary get_db_context function)
- Each change is precisely defined with before/after
- Tools use SessionLocal() directly with try/finally for database access
- No overengineering, only what's needed

---

## Validation Checklist

After each day, verify:

**Day 1-2**:
- [ ] App starts without errors
- [ ] Logs show "Graph compiled successfully"
- [ ] Single user query works
- [ ] Concurrent users work (no interference)
- [ ] Response time improved (no 90ms overhead)

**Day 3**:
- [ ] System prompt is ~500 tokens (not 5000)
- [ ] Stats queries call get_nutrition_stats tool
- [ ] General chat queries don't call tools
- [ ] Data is fresh after logging meals
- [ ] Cost per query <$0.0015

**Day 4**:
- [ ] Short conversations (<5 turns) not trimmed
- [ ] Long conversations (>5 turns) trimmed
- [ ] Logs show trimming messages
- [ ] No context overflow errors
- [ ] Response quality maintained

**Final**:
- [ ] All query types work
- [ ] 70%+ cost reduction achieved
- [ ] Performance improved
- [ ] No regressions in functionality

---

## Ready to Start?

This is the COMPLETE and EXACT list of changes. No surprises, no overengineering.

Shall we start with Change 1 (Database Context Manager)?
