# NutriLens Chatbot Architecture

Technical reference for the two LangGraph chatbot agents: Nutrition Bot (web) and WhatsApp Bot.

---

## 1. Architecture Overview

Both bots use the same LangGraph architecture pattern:

```
load_context -> trim_messages -> generate_response
                                       |
                              [has tool_calls?]
                                yes |      | no
                                 ToolNode  END
                                    |
                               trim_messages (loop)
```

**Nutrition Bot** (`nutrition_graph_v3.py`): 8 read-only tools, served via web API (`POST /api/nutrition/chat`).

**WhatsApp Bot** (`whatsapp_graph.py`): 4 read tools + 2 write tools with HITL via `interrupt()`, served via Twilio webhook (`POST /api/whatsapp/webhook`).

### Shared Infrastructure
- **LLM**: GPT-4o via `ChatOpenAI` (one singleton per bot)
- **Checkpointer**: `MongoDBSaver` for conversation persistence
- **Token governance**: `RedisTokenGovernor` (reserve/refund pattern)
- **System prompts**: `MongoPromptRegistry` (hot-reloadable from MongoDB, hardcoded fallback)
- **Data access**: `UserContext` class wrapping repository interfaces
- **DI mechanism**: `context_schema` + `Runtime` (nodes) + `ToolRuntime` (tools)

### What's Different Between the Bots

| Aspect | Nutrition Bot | WhatsApp Bot |
|--------|--------------|--------------|
| Tools | 8 read-only | 4 read + 2 write (with `interrupt()`) |
| Delivery | Web API, JWT auth | Twilio webhook, phone-based auth |
| Response style | 2-5 sentences, markdown OK | 1-3 sentences, plain text |
| MAX_OUTPUT_TOKENS | 1000 | 500 |
| Context schema | `NutritionContextSchema` (3 deps) | `WhatsAppContextSchema` (5 deps) |
| Prompt slug | `nutrition_chat_system` | `whatsapp_chat_system` |

---

## 2. Dependency Injection: context_schema + Runtime

### What It Is

LangGraph's `context_schema` is a way to pass non-serializable dependencies (DB sessions, service objects, API clients) to graph nodes and tools without putting them in state.

```python
# Define what dependencies the graph needs
@dataclass
class WhatsAppContextSchema:
    user_context: UserContext              # DB repos wrapped in a class
    governor: ITokenGovernor              # Redis token budgeting
    prompt_registry: IPromptRegistry      # MongoDB prompt fetcher
    meal_orchestrator: MealLoggingOrchestrator  # Write operations
    external_meal_service: ExternalMealService  # Nutrition estimation

# Graph declares it needs these deps
workflow = StateGraph(WhatsAppState, context_schema=WhatsAppContextSchema)

# Caller provides them at invocation time
context = WhatsAppContextSchema(user_context=..., governor=..., ...)
result = await graph.ainvoke(initial_state, config=config, context=context)
```

Nodes access deps via `Runtime[Schema]`, tools via `ToolRuntime[Schema]`:

```python
# In a node
async def load_context_node(state, runtime: Runtime[WhatsAppContextSchema]):
    user_context = runtime.context.user_context

# In a tool
@tool
async def get_meal_plan(target_date=None, *, runtime: ToolRuntime[WhatsAppContextSchema]):
    user_context = runtime.context.user_context
```

### Why We Use It (Concrete Reasons)

**Reason 1: State gets checkpointed — dependencies can't be serialized.**

State is persisted to MongoDB via `MongoDBSaver`. Every field in `WhatsAppState` gets serialized to JSON. You cannot serialize:
- SQLAlchemy `Session` objects (hold DB connections)
- `UserContext` (contains live repository instances with DB sessions)
- `MealLoggingOrchestrator` (contains service objects with DB sessions)
- `RedisTokenGovernor` (contains Redis client connection)

`context_schema` is explicitly designed for this: the context is **NOT** serialized to checkpoints. It's provided fresh at each `ainvoke()` call.

This is a **provable, observable fact**: if you put a DB session in state and the checkpointer tries to serialize it, you get `TypeError: Object of type Session is not JSON serializable`.

**Reason 2: Per-request DB session lifecycle.**

Each WhatsApp webhook call creates a fresh `SessionLocal()` DB session (line 98 of `whatsapp_webhook.py`). This session is closed in `finally` (line 203). All repositories for that request share this one session. The `build_whatsapp_context()` factory in `dependencies.py` wires all repos to this single session.

If tools imported services globally (module-level singletons), they'd share a single DB session across concurrent requests — which is unsafe with SQLAlchemy's non-thread-safe sessions.

**Reason 3: Typed access in tools and nodes.**

`ToolRuntime[WhatsAppContextSchema]` gives you `runtime.context.meal_orchestrator` with IDE autocomplete. This is a convenience, not a necessity. You could achieve the same with `config["configurable"]["meal_orchestrator"]` but without type safety.

### Honest Assessment: What We Don't Have Proof Of

**Claim we CANNOT make**: "context_schema is the only way to do this" or "all serious implementations use it."

- `context_schema`, `Runtime`, and `ToolRuntime` are **newer LangGraph APIs** (introduced in langgraph ~0.2.x). Many successful projects predate them.
- The official LangGraph documentation and tutorials mostly show simpler patterns (passing data via `RunnableConfig` or just state).
- We have not surveyed enough open-source LangGraph projects to claim that "successful implementations use Runtime." Many likely don't.

---

## 3. The Alternative: State + Direct Imports

### How Most LangGraph Projects Do It

The most common pattern in LangGraph examples and community projects:

```python
# Tools import services directly
from app.services.meal_service import MealService

@tool
async def log_meal(meal_id: int, config: RunnableConfig):
    user_id = config["configurable"]["user_id"]
    db = SessionLocal()  # Create DB session inside tool
    try:
        service = MealService(db)
        return await service.log_meal(user_id, meal_id)
    finally:
        db.close()
```

Or even simpler — pass user_id via state and let tools create their own DB sessions:

```python
@tool
async def get_meal_plan(state: dict):
    user_id = state["user_id"]
    db = SessionLocal()
    try:
        meals = db.query(MealLog).filter_by(user_id=user_id).all()
        return json.dumps([...])
    finally:
        db.close()
```

### Why This Works Fine

1. **No serialization problem**: user_id is just an int — serializes fine in state
2. **No DI needed**: Tools create their own deps
3. **Simpler code**: No dataclass schemas, no Runtime/ToolRuntime parameters
4. **Widely used**: This is the pattern in most LangGraph tutorials and examples

### Why We Chose context_schema Anyway

| Factor | State + Direct Imports | context_schema + Runtime |
|--------|----------------------|-------------------------|
| Simplicity | Simpler, less boilerplate | More setup code |
| Testability | Tools tightly coupled to concrete classes | Can swap implementations via schema |
| DB session sharing | Each tool creates/closes its own session | All tools share one session per request |
| Consistency with codebase | Diverges from our FastAPI DI pattern | Mirrors our FastAPI `Depends()` pattern |
| Type safety | None (dict access or RunnableConfig) | Full IDE autocomplete on `.context.` |
| Community adoption | Very common | Less common (newer API) |

**The honest truth**: Both approaches work. We chose `context_schema` because our codebase already follows a strict clean architecture pattern (repository interfaces, DI everywhere, orchestrators). Using `context_schema` keeps the LangGraph tools consistent with how the rest of the app handles dependencies. But this is a **preference, not a necessity**.

### Is Our Approach Overkill?

**For a simple chatbot**: Yes, probably. If you only need to read data by user_id, passing user_id in state and creating DB sessions in tools is simpler and works fine.

**For our specific case**: It's borderline. We have:
- 5 different dependencies in `WhatsAppContextSchema` (UserContext, governor, prompt_registry, orchestrator, external_meal_service)
- Per-request DB sessions that must be shared across tools and orchestrators
- The same clean architecture pattern used everywhere else in the codebase

The `context_schema` approach organizes this cleanly. But a developer who just passed `user_id` in state and wired deps inside each tool would achieve the same end result with less abstraction.

---

## 4. Nutrition Bot — Line-by-Line Code Explanation

**File**: `backend/app/agents/nutrition_graph_v3.py` (842 lines)

### Imports (lines 21-38)

```python
from langgraph.graph import StateGraph, END          # Graph builder and terminal node
from langgraph.runtime import Runtime                 # Access context_schema in nodes
from langgraph.prebuilt import ToolNode              # Standard tool executor
from langgraph.prebuilt.tool_node import ToolRuntime # Access context_schema in tools
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.messages.utils import trim_messages  # Message trimming utility
from langchain_core.tools import tool                # @tool decorator
from langchain_openai import ChatOpenAI              # OpenAI LLM wrapper
```

### Module-Level Singletons (lines 49-86)

```python
_read_tools = None    # Created once, reused for all requests
_llm_with_tools = None

def _get_read_tools():
    global _read_tools
    if _read_tools is None:
        _read_tools = create_read_tools()  # Calls the factory function below
    return _read_tools

def _get_llm_with_tools():
    global _llm_with_tools
    if _llm_with_tools is None:
        tools = _get_read_tools()
        _llm_with_tools = ChatOpenAI(
            model="gpt-4o", temperature=0.3, api_key=settings.openai_api_key
        ).bind_tools(tools)    # .bind_tools() tells the LLM about available tools
    return _llm_with_tools     # LLM can now generate tool_calls in its responses
```

**Why singletons?** The graph is compiled once at startup. Creating `ChatOpenAI` objects and tool definitions per request wastes ~50ms. Lazy init avoids import-time issues with settings.

### Context Schema (lines 93-110)

```python
@dataclass
class NutritionContextSchema:
    user_context: UserContext        # Wraps 6 repository interfaces for data access
    governor: ITokenGovernor         # Redis: reserve/refund token budget per user
    prompt_registry: IPromptRegistry # MongoDB: fetches system prompt by slug
```

3 dependencies. The nutrition bot is read-only, so no orchestrators needed.

### State Schema (lines 117-131)

```python
class NutritionState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]  # Chat history (append-only)
    llm_input_messages: Optional[Sequence[BaseMessage]]       # Trimmed subset for LLM
    user_context: Dict[str, Any]   # Pre-loaded profile + today's progress (serializable dict)
    user_id: int                   # Set at invocation, never changes
    session_id: str                # Thread ID for checkpointer
    turn_count: int                # Incremented each turn
```

- `messages` uses `operator.add` — LangGraph appends new messages rather than replacing
- `llm_input_messages` is recomputed by `trim_messages_node` each loop iteration
- `user_context` is a plain dict (serializable), NOT the `UserContext` class

### Tools (lines 138-547)

All 8 tools follow the same pattern:

```python
@tool
async def get_nutrition_stats(
    nutrients: Optional[str] = None,     # Parameters the LLM fills in
    *,
    runtime: ToolRuntime[NutritionContextSchema]  # Injected by LangGraph
) -> str:
    """Docstring becomes the tool description the LLM sees."""
    try:
        user_context = runtime.context.user_context  # Get UserContext from DI
        today_data = await user_context._get_today_consumption()  # Call repository method
        targets = await user_context._get_targets()
        # ... format as JSON string
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
```

Key points:
- `*` in parameters separates tool args (LLM-visible) from runtime (LangGraph-injected, hidden from LLM)
- Tools return JSON strings — the LLM sees these as tool results
- `UserContext` methods do the actual DB queries via repositories
- Every tool has `try/except` returning error JSON (never crashes the graph)

The 8 tools: `get_nutrition_stats`, `check_inventory`, `get_meal_plan`, `get_makeable_recipes`, `get_goal_aligned_recipes`, `get_consumption_history`, `get_expiring_items`, `get_weekly_summary`.

### load_context_node (lines 554-602)

```python
async def load_context_node(
    state: NutritionState,
    runtime: Runtime[NutritionContextSchema]  # DI access in nodes
) -> Dict[str, Any]:
    user_context = runtime.context.user_context

    # Pre-load the 3 most commonly needed data points
    profile = await user_context._get_profile_basic()   # goal_type, activity_level
    today = await user_context._get_today_consumption()  # calories consumed, remaining
    targets = await user_context._get_targets()          # daily targets

    # Pack into a serializable dict for the system prompt
    minimal_context = {
        "goal_type": profile.get("goal_type", "general_health"),
        "calories_consumed": today.get("consumed", {}).get("calories", 0),
        "calories_target": targets.get("calories", 2000),
        # ... more fields
    }

    return {"user_context": minimal_context, "turn_count": state.get("turn_count", 0) + 1}
```

**Why pre-load?** ~60% of queries ask about today's progress. By putting it in the system prompt, the LLM can answer "How many calories did I eat?" without calling a tool.

### trim_messages_node (lines 605-633)

```python
async def trim_messages_node(state: NutritionState) -> Dict[str, Any]:
    messages = state.get("messages", [])

    MAX_MESSAGES_THRESHOLD = 12  # Only trim if we exceed this
    MAX_MESSAGES = 10            # Keep at most this many

    if len(messages) > MAX_MESSAGES_THRESHOLD:
        trimmed = trim_messages(
            messages,
            strategy="last",           # Keep the most recent messages
            token_counter=len,         # Count by number of messages (not tokens)
            max_tokens=MAX_MESSAGES,
            start_on="human",          # First kept message must be from human
            end_on=("human", "tool"),  # Last kept message must be human or tool
            include_system=False,      # System message added separately in generate_response
        )
        return {"llm_input_messages": trimmed}
    else:
        return {"llm_input_messages": messages}
```

**Why a separate node?** After tools execute, the graph loops back through `trim_messages` before calling the LLM again. This ensures tool results are included in `llm_input_messages`. The edge is: `tools -> trim_messages -> generate_response`.

### generate_response_node (lines 654-774)

```python
async def generate_response_node(state, runtime: Runtime[NutritionContextSchema]):
    governor = runtime.context.governor
    prompt_registry = runtime.context.prompt_registry

    # 1. Build system prompt (try MongoDB registry, fall back to hardcoded)
    try:
        rendered_messages, _ = await prompt_registry.get_rendered_prompt(
            slug="nutrition_chat_system", variables=prompt_variables
        )
        system_prompt = rendered_messages[0]["content"]
    except:
        system_prompt = "You are NutriLens..."  # Hardcoded fallback

    # 2. Combine system prompt + conversation history
    messages = [SystemMessage(content=system_prompt)] + list(state["llm_input_messages"])

    # 3. Token governance: reserve pessimistically
    reservation = _estimate_input_tokens(messages) + MAX_OUTPUT_TOKENS
    allowed = await governor.reserve(user_id, reservation, DEFAULT_DAILY_TOKEN_LIMIT)
    if not allowed:
        return {"messages": [AIMessage(content="Daily limit reached.")]}

    # 4. Call LLM
    response = await llm.ainvoke(messages)

    # 5. Refund unused tokens
    actual_tokens = response.response_metadata.get("token_usage", {}).get("total_tokens", 0)
    if actual_tokens > 0:
        refund = reservation - actual_tokens
        if refund > 0:
            await governor.refund(user_id, refund)

    return {"messages": [response]}
```

Token governance works as: reserve the worst case -> make the call -> refund the difference. This prevents users from exceeding daily budgets even with concurrent requests.

### should_continue (lines 777-789)

```python
def should_continue(state) -> Literal["tools", "end"]:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"    # LLM wants to call a tool
    return "end"          # LLM responded with text, conversation turn is done
```

### Graph Construction (lines 796-842)

```python
def create_nutrition_graph_structure() -> StateGraph:
    tools = _get_read_tools()

    workflow = StateGraph(NutritionState, context_schema=NutritionContextSchema)

    workflow.add_node("load_context", load_context_node)
    workflow.add_node("trim_messages", trim_messages_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("tools", ToolNode(tools))  # Standard LangGraph ToolNode

    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "trim_messages")
    workflow.add_edge("trim_messages", "generate_response")

    workflow.add_conditional_edges(
        "generate_response", should_continue,
        {"tools": "tools", "end": END}
    )

    workflow.add_edge("tools", "trim_messages")  # Loop back after tool execution

    return workflow
```

The `ToolNode(tools)` is LangGraph's built-in tool executor. It reads `tool_calls` from the last `AIMessage`, executes each tool, and returns `ToolMessage` results.

---

## 5. WhatsApp Bot — Line-by-Line Code Explanation

**File**: `backend/app/agents/whatsapp_graph.py` (656 lines)

Everything identical to the nutrition bot except for the context schema and tools, so this section covers only the differences.

### Context Schema (lines 74-87)

```python
@dataclass
class WhatsAppContextSchema:
    user_context: UserContext              # Same as nutrition bot
    governor: ITokenGovernor              # Same
    prompt_registry: IPromptRegistry      # Same
    meal_orchestrator: MealLoggingOrchestrator   # NEW: for log_planned_meal
    external_meal_service: ExternalMealService   # NEW: for log_external_meal
```

2 extra deps for write operations. These are service objects that contain DB sessions — exactly why they're in context, not state.

### Write Tool: log_planned_meal (lines 245-312)

```python
@tool
async def log_planned_meal(
    meal_log_id: int,               # LLM provides this (from get_meal_plan results)
    *,
    runtime: ToolRuntime[WhatsAppContextSchema]
) -> str:
    """Log a planned meal as consumed. Requires user confirmation."""
    user_context = runtime.context.user_context
    user_id = user_context.user_id

    try:
        # Step 1: Fetch meal details for confirmation preview
        # This is IDEMPOTENT — safe to re-execute on resume
        meal_logs = await user_context.tracking_repo.get_by_date(user_id, date.today())
        meal = next((m for m in meal_logs if m.id == meal_log_id), None)

        if not meal:
            return json.dumps({"error": f"Meal log {meal_log_id} not found"})
        if meal.consumed_datetime:
            return json.dumps({"error": f"Already logged as consumed"})

        # Step 2: Build summary for user confirmation
        macros = meal.recipe.macros_per_serving or {} if meal.recipe else {}
        summary = {
            "meal_log_id": meal_log_id,
            "recipe": meal.recipe.title if meal.recipe else "Unknown",
            "calories": macros.get("calories", 0),
            "protein_g": macros.get("protein_g", 0)
        }

        # Step 3: INTERRUPT — graph pauses here
        # The webhook extracts the "message" field and sends it to the user via WhatsApp.
        # The graph state is saved to MongoDB. When the user replies, the webhook
        # calls graph.ainvoke(Command(resume="approve")) and execution resumes HERE.
        confirmation = interrupt({
            "action": "log_planned_meal",
            "message": f"Log '{summary['recipe']}'? {summary['calories']} cal...",
            "summary": summary
        })

        # Step 4: Handle user's response (runs AFTER resume)
        if confirmation == "approve":
            orchestrator = runtime.context.meal_orchestrator
            result = await orchestrator.log_planned_meal(user_id=user_id, meal_log_id=meal_log_id)
            return json.dumps({"success": True, "message": f"Logged '{summary['recipe']}'"})
        else:
            return json.dumps({"success": False, "message": "Cancelled"})

    except GraphInterrupt:
        raise  # CRITICAL: interrupt() raises GraphInterrupt internally.
               # If we catch it with `except Exception`, the interrupt never
               # propagates and the graph enters an infinite retry loop.
    except Exception as e:
        return json.dumps({"error": str(e)})
```

**On re-execution**: When `Command(resume=...)` is called, LangGraph re-executes the tool from the beginning. Steps 1-2 run again (meal fetch is a cheap DB query). `interrupt()` returns the resume value instead of pausing. This is by design — LangGraph docs confirm tools re-execute from scratch on resume.

### Write Tool: log_external_meal (lines 314-398)

Same pattern as `log_planned_meal`, but Step 1 calls `external_meal_service.estimate_nutrition()` (an LLM call) instead of a DB query. On resume, this LLM call re-runs — one extra GPT-4o call per confirmation. Acceptable tradeoff for WhatsApp's async nature.

### GraphInterrupt Exception Pattern

```python
except GraphInterrupt:
    raise
except Exception as e:
    ...
```

This is in every write tool. `interrupt()` raises `GraphInterrupt` (which extends `Exception`). Without the explicit `raise`, a generic `except Exception` would catch it, the tool would return an error string, and the LLM would retry — causing `GraphRecursionError: Recursion limit of 10 reached`. We hit this exact bug during development.

---

## 6. Supporting Files

### graph_instance.py / whatsapp_graph_instance.py

Singleton lifecycle management. Both follow the same pattern:

```python
_compiled_graph = None
_checkpointer = None

@asynccontextmanager
async def initialize_nutrition_graph():  # Called once in main.py lifespan
    client = get_mongo_sync_client()
    _checkpointer = MongoDBSaver(client=client, db_name=settings.mongodb_db)
    workflow = create_nutrition_graph_structure()
    _compiled_graph = workflow.compile(checkpointer=_checkpointer)
    yield
    _compiled_graph = None  # Cleanup on shutdown

def get_compiled_graph():  # Called per request
    if _compiled_graph is None:
        raise RuntimeError("Graph not initialized")
    return _compiled_graph
```

The graph is compiled ONCE at startup (avoids ~90ms overhead per request). `MongoDBSaver` persists conversation state across requests.

### whatsapp_webhook.py

The webhook handles the interrupt/resume lifecycle:

```python
# 1. Check if there's a pending interrupt
current_state = await graph.aget_state(config)
has_pending_interrupt = bool(current_state and current_state.tasks)

# 2. If yes: parse user's reply and resume
if has_pending_interrupt:
    confirmation = parse_confirmation(text)  # "yes" -> "approve", "no" -> "reject"
    result = await graph.ainvoke(Command(resume=confirmation), config=config, context=context)

# 3. If no: normal new message
else:
    result = await graph.ainvoke(initial_state, config=config, context=context)

# 4. Check if graph paused at a NEW interrupt
updated_state = await graph.aget_state(config)
if updated_state and updated_state.tasks:
    # Extract interrupt message and send to user
    interrupt_value = updated_state.tasks[0].interrupts[0].value
    response_text = interrupt_value.get("message", "Please confirm")
```

### dependencies.py: build_whatsapp_context()

Manual DI wiring for background tasks (no FastAPI `Depends()` available):

```python
async def build_whatsapp_context(user_id: int, db: Session):
    # Creates ALL repositories with the SAME db session
    tracking_repo = TrackingRepository(db)
    inventory_repo = InventoryRepository(db)
    # ... all sharing `db`

    # Creates services with those repos
    meal_tracking_service = MealTrackingService(tracking_repo=..., inventory_repo=...)
    external_meal_service = ExternalMealService(tracking_repo=..., llm_orchestrator=...)

    # Creates orchestrator
    meal_orchestrator = MealLoggingOrchestrator(meal_tracking_service=..., ...)

    # Creates UserContext (read-only data access)
    user_context = UserContext(user_id=user_id, tracking_repo=..., ...)

    # Packs everything into the schema
    return WhatsAppContextSchema(
        user_context=user_context,
        governor=get_token_governor(),
        prompt_registry=get_prompt_registry(),
        meal_orchestrator=meal_orchestrator,
        external_meal_service=external_meal_service
    )
```

---

## 7. Known Issues and Lessons Learned

### Python 3.11 Requirement

`interrupt()` does NOT work with `ainvoke()` on Python 3.10. It fails with `RuntimeError: Called get_config outside of a runnable context`. Root cause: Python 3.10's `asyncio` doesn't properly propagate `contextvars.ContextVar` through LangGraph's async execution path. Python 3.11 fixed this. LangGraph GitHub issue #5927 documents it.

**Our Dockerfile uses `python:3.11-slim`** specifically because of this.

### GraphInterrupt Must Not Be Caught

`interrupt()` raises `GraphInterrupt` (extends `Exception`). Any `except Exception` block in a tool with `interrupt()` MUST have `except GraphInterrupt: raise` before it. Otherwise the interrupt is silently swallowed, the tool returns an error, the LLM retries, and you hit the recursion limit.

### Stale Checkpoints After Code Changes

If you change the graph structure (add/remove nodes, change tool signatures) while there are existing checkpoints in MongoDB, old conversations may fail with errors like "tool_calls must be followed by tool messages." Fix: clear the relevant checkpoints from the `checkpoints` and `checkpoint_writes` collections in MongoDB.

```javascript
// In mongosh, connected to nutrilens_agent database:
db.checkpoints.deleteMany({thread_id: /^wa_/})
db.checkpoint_writes.deleteMany({thread_id: /^wa_/})
```

This is only needed after structural changes, not during normal operation. Checkpoints handle normal conversation continuity correctly.