# LangGraph Migration Plan - NutriLens AI Architecture Upgrade

## **Executive Summary**

**Goal**: Migrate from custom intent-routing to LangGraph-based agent architecture for production-ready, stateful, tool-enabled conversational AI.

**Timeline**: 3-5 days for MVP, 1-2 weeks for production-ready

**Risk**: Medium - We'll maintain backward compatibility during migration

**Storage Strategy**:
- ✅ **MongoDB** for agent state, checkpoints, and conversation history (no bloat to PostgreSQL)
- ✅ **PostgreSQL** remains for core application data only (users, meals, recipes, etc.)

---

## **Current Architecture (What We Have)**

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT SYSTEM                            │
├─────────────────────────────────────────────────────────────┤
│  Frontend: /dashboard/nutrition/chat                        │
│      ↓                                                       │
│  API: POST /api/nutrition/chat                              │
│      ↓                                                       │
│  NutritionIntelligence.process_query()                      │
│      ↓                                                       │
│  UserContext.build_context() (Gathers data)                 │
│      ↓                                                       │
│  IntentClassifier.classify() (GPT-4o)                       │
│      ↓                                                       │
│  Route to Handler:                                          │
│    - _handle_stats() [Rule-based]                           │
│    - _handle_what_if() [LLM]                                │
│    - _handle_meal_suggestion() [LLM]                        │
│    - _handle_inventory() [Rule-based]                       │
│    - _handle_meal_plan() [Rule-based]                       │
│    - _handle_conversational() [LLM]                         │
│      ↓                                                       │
│  Return IntelligenceResponse                                │
└─────────────────────────────────────────────────────────────┘
```

**Limitations:**
- ❌ No state persistence (stateless)
- ❌ No conversation memory
- ❌ No tool execution (can't perform actions)
- ❌ No human-in-the-loop
- ❌ No multi-step workflows
- ❌ Can't handle "log this meal", "swap dinner", etc.

---

## **Target Architecture (LangGraph)**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH SYSTEM                                  │
├──────────────────────────────────────────────────────────────────────────┤
│  Frontend: /dashboard/nutrition/chat                                     │
│      ↓                                                                    │
│  API: POST /api/nutrition/agent (NEW!)                                   │
│      ↓                                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │               LangGraph Agent Workflow                             │  │
│  │                                                                    │  │
│  │   [Load State] → [Build Context] → [LLM Decides] → [Execute]     │  │
│  │        ↓              ↓                  ↓              ↓         │  │
│  │    MongoDB      UserContext        GPT-4o + Tools    Tools       │  │
│  │   Checkpoints                      Function Calling               │  │
│  │                                                                    │  │
│  │   Available Tools:                                                │  │
│  │     • log_meal(meal_log_id, portions)                            │  │
│  │     • search_recipes(criteria)                                   │  │
│  │     • swap_meal(meal_log_id, new_recipe_id)                      │  │
│  │     • check_inventory(item_name)                                 │  │
│  │     • get_stats(nutrient)                                        │  │
│  │     • log_external_meal(description, macros)                     │  │
│  │                                                                    │  │
│  │   State Management:                                               │  │
│  │     • Conversation history (last 10 messages)                    │  │
│  │     • User context (cached for session)                          │  │
│  │     • Pending actions (awaiting confirmation)                    │  │
│  │     • Tool execution history                                     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│      ↓                                                                    │
│  [Save Checkpoint] → [Return Response + State]                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Capabilities:**
- ✅ State persistence across conversations
- ✅ Memory of previous interactions
- ✅ Tool execution for actions
- ✅ Human-in-the-loop for confirmations
- ✅ Multi-step workflows
- ✅ Handles "log this meal", "swap dinner", etc.
- ✅ Streaming responses
- ✅ Debugging with LangSmith

---

## **Migration Strategy: 3 Phases**

### **Phase 1: Foundation (Days 1-2)**

**Goal**: Set up LangGraph infrastructure without breaking existing system

**Tasks:**
1. Install dependencies (LangGraph, MongoDB drivers)
2. Set up MongoDB connection and collections
3. Create indexes for optimal query performance
4. Define state schema
5. Create basic graph with single node
6. Test MongoDB checkpointer
7. Add new endpoint `/api/nutrition/agent` (keep old one working)

**Deliverable**: Parallel system running, no features yet

**MongoDB Setup:**
```bash
# Install MongoDB (if not already)
# Or use MongoDB Atlas (cloud)

# Create database and user
use nutrilens_agent
db.createUser({
  user: "nutrilens_agent",
  pwd: "your_password",
  roles: [{ role: "readWrite", db: "nutrilens_agent" }]
})

# Create collections (auto-created, but we set indexes)
db.createCollection("checkpoints")
db.createCollection("chat_history")

# Create indexes
db.chat_history.createIndex({ user_id: 1, session_id: 1 })
db.chat_history.createIndex({ created_at: -1 })
db.checkpoints.createIndex({ thread_id: 1, checkpoint_ns: 1 })

# Optional: TTL index to auto-delete old chats after 90 days
db.chat_history.createIndex({ created_at: 1 }, { expireAfterSeconds: 7776000 })
```

---

### **Phase 2: Tool Migration (Days 3-4)**

**Goal**: Migrate existing handlers to tools + add action tools

**Tasks:**
1. Convert each handler to a tool definition
2. Add new action tools (log_meal, swap_meal, etc.)
3. Implement tool execution node
4. Add conversation history
5. Test basic workflows

**Deliverable**: Agent can answer questions AND execute actions

---

### **Phase 3: Production Ready (Days 5-7)**

**Goal**: Polish, error handling, monitoring

**Tasks:**
1. Add human-in-the-loop for confirmations
2. Implement streaming responses
3. Add proper error handling
4. Frontend updates for new capabilities
5. Add LangSmith integration (optional)
6. Comprehensive testing

**Deliverable**: Production-ready agent system

---

## **Detailed Technical Design**

### **1. State Schema**

```python
from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import add_messages

class Message(TypedDict):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str

class NutritionState(TypedDict):
    """
    Complete state for nutrition agent conversation
    Persisted to MongoDB between requests
    """
    # Conversation
    messages: Annotated[List[Message], add_messages]  # Auto-managed by LangGraph

    # User context (cached)
    user_id: int
    user_context: Optional[dict]  # Profile, targets, today's consumption
    context_fetched_at: Optional[str]

    # Pending actions (for human-in-the-loop)
    pending_action: Optional[dict]  # {"tool": "log_meal", "params": {...}}
    awaiting_confirmation: bool

    # Tool execution tracking
    tool_calls: List[dict]  # History of tools called
    last_tool_result: Optional[dict]

    # Session metadata
    session_id: str
    created_at: str
    updated_at: str
```

---

### **2. Tool Definitions**

```python
from langchain_core.tools import tool
from typing import Optional

@tool
def get_nutrition_stats(nutrient: Optional[str] = None) -> str:
    """
    Get current nutrition statistics for the user.

    Args:
        nutrient: Specific nutrient to check (protein, calories, carbs, fat) or None for all

    Returns:
        Formatted nutrition stats with emojis
    """
    # Delegates to existing _handle_stats()
    pass

@tool
def log_meal(meal_log_id: int, portions: float = 1.0) -> str:
    """
    Log a meal as consumed.

    Args:
        meal_log_id: ID of the meal log from meal plan
        portions: Number of portions consumed (default 1.0)

    Returns:
        Confirmation message with updated nutrition stats
    """
    # Delegates to ConsumptionService
    pass

@tool
def search_recipes(
    query: Optional[str] = None,
    min_protein: Optional[float] = None,
    max_calories: Optional[float] = None,
    cuisine: Optional[str] = None
) -> str:
    """
    Search for recipes matching criteria.

    Args:
        query: Free-text search query
        min_protein: Minimum protein in grams
        max_calories: Maximum calories
        cuisine: Cuisine type filter

    Returns:
        List of matching recipes with nutrition info
    """
    # Delegates to RecipeService
    pass

@tool
def swap_meal(meal_log_id: int, new_recipe_id: int) -> str:
    """
    Swap a planned meal with a different recipe.

    Args:
        meal_log_id: ID of the meal to swap
        new_recipe_id: ID of the replacement recipe

    Returns:
        Confirmation with updated meal plan
    """
    # Delegates to PlanningAgent
    pass

@tool
def check_inventory(item_name: Optional[str] = None) -> str:
    """
    Check inventory status.

    Args:
        item_name: Specific item to check, or None for full inventory

    Returns:
        Inventory status with expiring items
    """
    # Delegates to InventoryService
    pass

@tool
def log_external_meal(
    description: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    meal_type: str
) -> str:
    """
    Log a meal eaten outside (not from meal plan).

    Args:
        description: Meal description
        calories: Calories consumed
        protein_g: Protein in grams
        carbs_g: Carbs in grams
        fat_g: Fat in grams
        meal_type: breakfast, lunch, dinner, snack

    Returns:
        Confirmation with updated daily stats
    """
    # Creates external meal log
    pass

@tool
def analyze_hypothetical_food(food_description: str) -> str:
    """
    Analyze if a hypothetical food fits user's remaining macros.

    Args:
        food_description: Description of food item (e.g., "2 samosas")

    Returns:
        Analysis with macro fit and recommendations
    """
    # Delegates to existing _handle_what_if() logic
    pass
```

---

### **3. Graph Structure**

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

# Define nodes
def load_user_context_node(state: NutritionState):
    """Load or refresh user context"""
    if not state.get("user_context") or needs_refresh(state):
        context = UserContext(db, state["user_id"]).build_context()
        state["user_context"] = context
        state["context_fetched_at"] = datetime.now().isoformat()
    return state

def agent_node(state: NutritionState):
    """
    Main agent: Decides what to do based on conversation
    Uses GPT-4o with function calling
    """
    messages = state["messages"]
    user_context = state["user_context"]

    # Build system prompt with context
    system_prompt = build_system_prompt(user_context)

    # Call GPT-4o with tools
    response = llm_with_tools.invoke([
        {"role": "system", "content": system_prompt},
        *messages
    ])

    # Check if tool calls requested
    if response.tool_calls:
        state["tool_calls"].append(response.tool_calls)
        # Will route to tool execution

    return state

def tool_execution_node(state: NutritionState):
    """Execute requested tools"""
    tool_calls = state["tool_calls"][-1]  # Latest

    results = []
    for tool_call in tool_calls:
        result = execute_tool(tool_call)
        results.append(result)

    state["last_tool_result"] = results
    return state

def should_execute_tools(state: NutritionState) -> str:
    """Conditional edge: decide if we need to execute tools"""
    if state.get("tool_calls") and not state.get("last_tool_result"):
        return "execute_tools"
    return "generate_response"

def should_ask_confirmation(state: NutritionState) -> str:
    """Check if action needs human confirmation"""
    if state.get("pending_action") and not state.get("awaiting_confirmation"):
        # Destructive actions need confirmation
        if state["pending_action"]["tool"] in ["log_meal", "swap_meal"]:
            state["awaiting_confirmation"] = True
            return "ask_confirmation"
    return "continue"

# Build graph
workflow = StateGraph(NutritionState)

# Add nodes
workflow.add_node("load_context", load_user_context_node)
workflow.add_node("agent", agent_node)
workflow.add_node("execute_tools", tool_execution_node)
workflow.add_node("generate_response", agent_node)  # Final response generation

# Define flow
workflow.set_entry_point("load_context")
workflow.add_edge("load_context", "agent")

workflow.add_conditional_edges(
    "agent",
    should_execute_tools,
    {
        "execute_tools": "execute_tools",
        "generate_response": "generate_response"
    }
)

workflow.add_edge("execute_tools", "generate_response")
workflow.add_edge("generate_response", END)

# Compile with MongoDB checkpointer
mongo_client = MongoClient(MONGODB_URL)
checkpointer = MongoDBSaver(
    client=mongo_client,
    db_name="nutrilens_agent",
    collection_name="checkpoints"
)
app = workflow.compile(checkpointer=checkpointer)
```

---

### **4. MongoDB Schema**

```javascript
// MongoDB Database: nutrilens_agent

// Collection: checkpoints (auto-managed by LangGraph MongoDBSaver)
{
  _id: ObjectId,
  thread_id: String,  // Session ID
  checkpoint_ns: String,
  checkpoint_id: String,
  parent_checkpoint_id: String,
  checkpoint: Binary,  // Pickled state
  metadata: Object,
  created_at: ISODate
}

// Collection: chat_history (manually managed)
{
  _id: ObjectId,
  user_id: Number,  // Reference to PostgreSQL users.id
  session_id: String,
  role: String,  // "user" or "assistant"
  content: String,
  intent: String,
  tool_calls: Array,  // If tools were called
  created_at: ISODate,
  metadata: {
    processing_time_ms: Number,
    model: String,
    tokens_used: Number
  }
}

// Indexes
db.chat_history.createIndex({ user_id: 1, session_id: 1 });
db.chat_history.createIndex({ created_at: -1 });
db.chat_history.createIndex({ user_id: 1, created_at: -1 });
db.checkpoints.createIndex({ thread_id: 1, checkpoint_ns: 1 });
```

**Benefits of MongoDB:**
- ✅ No foreign key constraints (decoupled from PostgreSQL)
- ✅ Flexible schema for evolving agent state
- ✅ Better performance for conversation history queries
- ✅ Easy to archive/purge old conversations
- ✅ Native support for nested documents (tool_calls, metadata)
- ✅ TTL indexes for auto-cleanup of old chats

---

### **5. API Integration**

```python
# app/api/nutrition_agent.py (NEW FILE)

from fastapi import APIRouter, Depends
from langchain_core.messages import HumanMessage, AIMessage
from app.agents.nutrition_graph import app as agent_app, NutritionState

router = APIRouter(prefix="/nutrition/agent", tags=["Nutrition Agent"])

@router.post("/chat")
async def chat_with_agent(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Chat with LangGraph-powered nutrition agent
    Maintains state across conversations
    """
    # Generate session ID (or get from request)
    session_id = request.session_id or f"user_{current_user.id}_{datetime.now().date()}"

    # Prepare initial state
    config = {
        "configurable": {
            "thread_id": session_id,  # LangGraph uses this for checkpointing
            "user_id": current_user.id
        }
    }

    # Add user message
    user_message = HumanMessage(content=request.query)

    # Invoke agent (with state persistence)
    result = await agent_app.ainvoke(
        {
            "messages": [user_message],
            "user_id": current_user.id,
            "session_id": session_id
        },
        config=config
    )

    # Extract response
    assistant_message = result["messages"][-1]

    # Save to history table
    save_to_history(current_user.id, session_id, request.query, assistant_message.content)

    return ChatResponse(
        success=True,
        response=assistant_message.content,
        session_id=session_id,
        tool_calls=result.get("tool_calls", []),
        state_saved=True
    )

@router.get("/history")
async def get_chat_history(
    session_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get conversation history"""
    query = db.query(NutritionChatHistory).filter(
        NutritionChatHistory.user_id == current_user.id
    )

    if session_id:
        query = query.filter(NutritionChatHistory.session_id == session_id)

    history = query.order_by(NutritionChatHistory.created_at.desc()).limit(limit).all()

    return {"history": [h.to_dict() for h in history]}

@router.post("/confirm")
async def confirm_action(
    session_id: str,
    confirmed: bool,
    current_user: User = Depends(get_current_user)
):
    """Confirm a pending action"""
    config = {"configurable": {"thread_id": session_id}}

    # Get current state
    state = await agent_app.aget_state(config)

    if confirmed:
        # Execute pending action
        pending = state.values.get("pending_action")
        result = execute_tool(pending["tool"], **pending["params"])

        # Continue conversation
        confirmation_message = HumanMessage(content="yes, confirm")
        result = await agent_app.ainvoke(
            {"messages": [confirmation_message]},
            config=config
        )
    else:
        # Cancel
        result = {"cancelled": True}

    return result
```

---

## **Backward Compatibility Plan**

**During Migration:**
1. Keep `/api/nutrition/chat` endpoint working (old system)
2. Add `/api/nutrition/agent` endpoint (new LangGraph system)
3. Frontend can switch via feature flag
4. Both systems read same database

**After Migration:**
1. Deprecate old endpoint with 30-day notice
2. Migrate all sessions to new system
3. Remove old code

---

## **Comparison: Before & After**

| Feature | Current System | LangGraph System |
|---------|---------------|------------------|
| **Conversation Memory** | ❌ None | ✅ Full history with checkpoints |
| **Multi-turn Conversations** | ❌ Single-turn only | ✅ Maintains context |
| **Action Execution** | ❌ Can't log meals/swap | ✅ Full tool execution |
| **Human-in-the-Loop** | ❌ No confirmations | ✅ Built-in |
| **State Persistence** | ❌ Stateless | ✅ MongoDB checkpoints |
| **Streaming** | ❌ Not supported | ✅ Supported |
| **Debugging** | ❌ Console logs only | ✅ LangSmith integration |
| **Multi-agent** | ❌ Single agent | ✅ Can add specialist agents |
| **Error Recovery** | ❌ Fails completely | ✅ Retries & fallbacks |

---

## **Risk Assessment**

| Risk | Mitigation |
|------|------------|
| **Learning Curve** | Start with simple graph, iterate |
| **Breaking Changes** | Run both systems in parallel |
| **Performance** | Cache context, use connection pooling |
| **State Size** | Prune old messages, compress context |
| **Cost** | Monitor token usage with LangSmith |

---

## **Success Metrics**

**Phase 1 (Foundation)**
- ✅ Graph compiles without errors
- ✅ Can load/save state from MongoDB
- ✅ Basic conversation works
- ✅ MongoDB connection established

**Phase 2 (Tools)**
- ✅ All 7 tools working
- ✅ Can log meals via chat
- ✅ Can swap meals via chat
- ✅ Conversation history persists

**Phase 3 (Production)**
- ✅ <3s response time for 95% of requests
- ✅ Streaming responses working
- ✅ Human-in-the-loop confirmations
- ✅ Error rate <1%
- ✅ Handles 100 concurrent users

---

## **Next Steps**

1. **Review this plan** - Does this fit your vision?
2. **Approve migration** - Ready to start?
3. **Set up environment** - Install dependencies
4. **Phase 1 execution** - Build foundation

**Estimated Timeline:**
- Review & Setup: 2-4 hours
- Phase 1: 1-2 days
- Phase 2: 2-3 days
- Phase 3: 2-3 days
- **Total: 5-8 days for production-ready system**

---

## **Questions for You**

1. Do you want to keep the old system running during migration?
2. Should we add LangSmith from the start (helps debugging)?
3. Any other tools/actions you want to support?
4. Timeline pressure? Can we take 5-8 days?

Ready to proceed? 🚀
