# Production LLM Architecture for Nutrilens

## Executive Summary

This document defines the complete, production-grade architecture for all LLM workloads in Nutrilens: **Normalizer**, **Nutrient Estimator**, and **Chatbot**.

This is NOT a minimal fix. This is a ground-up redesign following industry best practices from LangChain, LiteLLM, and Instructor.

---

## Current State Analysis (Problems)

### 1. Normalizer (batch_normalizer.py)
```
API → Service → BatchNormalizer → LLM Adapter → OpenAI
```
**Issues:**
- No crash recovery (if OpenAI fails mid-batch, lose all state)
- No retry logic (single call, hope it works)
- No schema enforcement (hope LLM returns valid JSON)
- Prompt embedded in code (can't update without redeploy)
- No cost tracking
- No semantic caching (repeated "milk" calls waste money)

### 2. Nutrition Estimator (llm_nutrition_estimator.py)
```python
# Line 10: SYNC client (blocks event loop)
from openai import OpenAI

# Line 19: NEW client per request (no connection reuse)
self.client = OpenAI(api_key=api_key)

# Line 47: Synchronous call in async context
response = self.client.chat.completions.create(...)
```
**Issues:**
- **Synchronous OpenAI client** - blocks entire event loop
- **New client per request** - no connection pooling
- No retry logic, no failover
- No caching

### 3. Chatbot (future)
- Will need conversation memory
- Will need tool calling
- Will need streaming

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI (Driving Adapter)                         │
│  • Extract tenant_id, user_id                                               │
│  • Initialize thread_id for LangGraph state isolation                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Semantic Cache (Redis + Embeddings)                  │
│  • Cosine similarity threshold: 0.2 distance (≈0.9 similarity)              │
│  • Per-tenant isolation via metadata filter                                 │
│  • 24hr TTL                                                                 │
│  • Saves ~80% cost on common items ("milk", "chicken", "rice")              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                          ┌───────────┴───────────┐
                          ▼                       ▼
                     Cache HIT              Cache MISS
                          │                       │
                          ▼                       ▼
                    Return cached         Continue to LangGraph
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph (Orchestration Runtime)                   │
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │   Normalizer Graph  │  │   Estimator Graph   │  │    Chatbot Graph    │  │
│  │                     │  │                     │  │                     │  │
│  │  START              │  │  START              │  │  START              │  │
│  │    │                │  │    │                │  │    │                │  │
│  │    ▼                │  │    ▼                │  │    ▼                │  │
│  │  parse_input        │  │  lookup_db          │  │  understand         │  │
│  │    │                │  │    │                │  │    │                │  │
│  │    ▼                │  │    ▼                │  │    ▼                │  │
│  │  extract_structure  │  │  estimate_llm       │  │  retrieve_rag       │  │
│  │    │                │  │    │                │  │    │                │  │
│  │    ▼                │  │    ▼                │  │    ▼                │  │
│  │  match_chain        │  │  validate           │  │  tool_call?         │  │
│  │    │                │  │    │                │  │    │                │  │
│  │    ▼                │  │    ▼                │  │    ▼                │  │
│  │  convert_units      │  │  END                │  │  respond            │  │
│  │    │                │  │                     │  │    │                │  │
│  │    ▼                │  │                     │  │    ▼                │  │
│  │  END                │  │                     │  │  END                │  │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │
│                                                                             │
│  State: TypedDict per graph (request-scoped, NOT singleton)                 │
│  Checkpointer: PostgresSaver (crash recovery)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Instructor (Schema Enforcement)                     │
│  • Pydantic models define expected output                                   │
│  • Automatic validation retries (max_retries=3)                             │
│  • Field validators for business rules                                      │
│  • If LLM returns string for quantity, auto-retry with error feedback       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Prompt Registry (PromptOps)                         │
│  • Versioned prompts: "normalizer_extract_v1.2.0"                           │
│  • Environment tags: dev, staging, production                               │
│  • A/B testing support                                                      │
│  • Hot-update without redeploy                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LiteLLM Proxy (AI Gateway) - SINGLETON                 │
│  • Retries: exponential backoff on 429, 500                                 │
│  • Failover: GPT-4o → Claude → GPT-4o-mini                                  │
│  • Rate limiting: per-tenant quotas                                         │
│  • Cost tracking: tokens per request, aggregated per user/tenant            │
│  • Circuit breaker: cooldown after 3 failures                               │
│  • 8ms P95 latency at 1k RPS                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HTTP Client (AsyncOpenAI) - SINGLETON                  │
│  • Connection pooling via httpx                                             │
│  • Single instance for entire application lifecycle                         │
│  • Initialized in FastAPI lifespan                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LLM Providers                                  │
│  • OpenAI (primary)                                                         │
│  • Anthropic (failover)                                                     │
│  • Local models via vLLM (optional, cost optimization)                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Semantic Cache (Redis + Vector DB)

**Purpose:** Reduce LLM costs by returning cached responses for semantically similar queries.

**Implementation:**
```python
from redisvl.extensions.cache.llm import SemanticCache

cache = SemanticCache(
    name="nutrilens_llm_cache",
    redis_url="redis://localhost:6379",
    distance_threshold=0.2,  # Cosine distance, lower = stricter
    vectorizer=HFTextVectorizer("sentence-transformers/all-mpnet-base-v2"),
    ttl=86400,  # 24 hours
    filterable_fields=[
        {"name": "tenant_id", "type": "tag"},
        {"name": "cache_type", "type": "tag"}  # normalizer, estimator, chat
    ]
)
```

**Multi-Tenant Isolation:**
```python
# Store with tenant isolation
cache.store(
    prompt="2 cups milk",
    response={"item_id": 123, "grams": 480},
    filters={"tenant_id": "tenant_abc", "cache_type": "normalizer"}
)

# Query with tenant filter
cached = cache.check(
    prompt="2 cups of milk",
    filter_expression="@tenant_id:{tenant_abc}"
)
```

**Sources:**
- [Redis Semantic Caching](https://redis.io/blog/what-is-semantic-caching/)
- [RedisVL LLM Cache](https://redis.io/docs/latest/develop/ai/redisvl/user_guide/llmcache/)

---

### 2. LangGraph Orchestration

**Purpose:** Convert probabilistic LLM calls into deterministic state machines with crash recovery.

#### Normalizer Graph

```python
from typing import TypedDict, List, Dict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

class NormalizerState(TypedDict):
    """State flows through the graph"""
    raw_lines: List[str]
    structures: List[Dict]           # After extraction
    match_results: List[Dict]        # After matching
    normalized_items: List[Dict]     # After unit conversion
    errors: List[str]
    current_step: str

def parse_input(state: NormalizerState) -> dict:
    """Node 1: Parse raw text into lines"""
    lines = state["raw_lines"]
    return {"structures": [], "current_step": "parsed"}

def extract_structure(state: NormalizerState) -> dict:
    """Node 2: LLM extracts quantity, unit, item_text"""
    # Uses Instructor for schema enforcement
    # Pulls prompt from registry
    return {"structures": [...], "current_step": "extracted"}

def match_chain(state: NormalizerState) -> dict:
    """Node 3: Run through existing matcher chain"""
    # ExactMatcher → AliasMatcher → VectorMatcher → LLMMatcher
    return {"match_results": [...], "current_step": "matched"}

def convert_units(state: NormalizerState) -> dict:
    """Node 4: Convert to grams"""
    return {"normalized_items": [...], "current_step": "converted"}

def route_next(state: NormalizerState) -> Literal["extract", "match", "convert", "end"]:
    """Conditional routing based on current step"""
    if state["errors"]:
        return "end"
    step_map = {
        "parsed": "extract",
        "extracted": "match",
        "matched": "convert",
        "converted": "end"
    }
    return step_map.get(state["current_step"], "end")

# Build graph
normalizer_graph = StateGraph(NormalizerState)
normalizer_graph.add_node("parse", parse_input)
normalizer_graph.add_node("extract", extract_structure)
normalizer_graph.add_node("match", match_chain)
normalizer_graph.add_node("convert", convert_units)

normalizer_graph.add_edge(START, "parse")
normalizer_graph.add_conditional_edges("parse", route_next)
normalizer_graph.add_conditional_edges("extract", route_next)
normalizer_graph.add_conditional_edges("match", route_next)
normalizer_graph.add_edge("convert", END)

# Compile with checkpointer
checkpointer = PostgresSaver(connection_pool)
compiled_normalizer = normalizer_graph.compile(checkpointer=checkpointer)
```

**Crash Recovery:**
```python
# If server crashes after "extract" completes, resume from "match"
config = {"configurable": {"thread_id": f"normalizer:{request_id}"}}
result = await compiled_normalizer.ainvoke({"raw_lines": lines}, config)
```

**Sources:**
- [LangGraph Docs](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph Checkpointing](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)

---

### 3. Instructor Schema Enforcement

**Purpose:** Guarantee structured output from LLM. No more "hope it returns JSON".

```python
import instructor
from pydantic import BaseModel, Field, field_validator
from openai import AsyncOpenAI

client = instructor.from_openai(AsyncOpenAI())

class ExtractedItem(BaseModel):
    """Schema for extracted food item"""
    quantity: float = Field(gt=0, description="Numeric quantity")
    unit: str = Field(description="Unit of measurement")
    item_text: str = Field(min_length=1, description="Food item name")

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v):
        valid = {'g', 'kg', 'ml', 'l', 'cup', 'tbsp', 'tsp', 'piece', 'unit', 'oz', 'lb'}
        normalized = v.lower().strip()
        if normalized not in valid:
            raise ValueError(f"Unit must be one of {valid}, got {v}")
        return normalized

class BatchExtractionResult(BaseModel):
    """Schema for batch extraction response"""
    items: List[ExtractedItem]
    unrecognized: List[str] = Field(default_factory=list)

# LLM call with guaranteed schema
async def extract_structures(lines: List[str]) -> BatchExtractionResult:
    return await client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=BatchExtractionResult,
        max_retries=3,  # Auto-retry on validation failure
        messages=[
            {"role": "system", "content": get_prompt("extract_structure_v1")},
            {"role": "user", "content": "\n".join(lines)}
        ]
    )
```

**What happens on validation failure:**
1. LLM returns `{"quantity": "two", ...}` (string instead of float)
2. Instructor catches Pydantic validation error
3. Instructor sends error back to LLM: "quantity must be float, got string 'two'"
4. LLM retries with corrected output: `{"quantity": 2.0, ...}`
5. If still fails after max_retries, raises exception

**Sources:**
- [Instructor Docs](https://python.useinstructor.com/)
- [Instructor Validation](https://python.useinstructor.com/concepts/validation/)

---

### 4. Prompt Registry

**Purpose:** Treat prompts as versioned code. Update without redeploy.

**Option A: File-based (Simple)**
```
backend/
  prompts/
    normalizer/
      extract_structure_v1.0.0.txt
      extract_structure_v1.1.0.txt
      verify_match_v1.0.0.txt
    estimator/
      estimate_macros_v1.0.0.txt
    chatbot/
      system_v1.0.0.txt
```

```python
# prompts/registry.py
import os
from pathlib import Path

PROMPT_DIR = Path(__file__).parent

def get_prompt(name: str, version: str = "latest") -> str:
    """
    Get prompt by name and version.

    Args:
        name: Prompt name (e.g., "normalizer/extract_structure")
        version: Semantic version or "latest"
    """
    category, prompt_name = name.split("/")
    prompt_path = PROMPT_DIR / category

    if version == "latest":
        # Find highest version
        files = list(prompt_path.glob(f"{prompt_name}_v*.txt"))
        if not files:
            raise ValueError(f"No prompts found for {name}")
        latest = sorted(files)[-1]
        return latest.read_text()
    else:
        file_path = prompt_path / f"{prompt_name}_v{version}.txt"
        if not file_path.exists():
            raise ValueError(f"Prompt not found: {name} v{version}")
        return file_path.read_text()
```

**Option B: Database-backed (Scalable)**
```python
# For A/B testing and analytics
class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    version = Column(String)
    content = Column(Text)
    environment = Column(String)  # dev, staging, prod
    created_at = Column(DateTime)
    is_active = Column(Boolean, default=False)
```

**Option C: PromptLayer/LangSmith (Enterprise)**
- Built-in versioning
- A/B testing
- Usage analytics
- Team collaboration

**Sources:**
- [PromptLayer Registry](https://docs.promptlayer.com/features/prompt-registry/overview)
- [LangSmith Prompts](https://docs.smith.langchain.com/old/evaluation/faq/manage-prompts)

---

### 5. LiteLLM AI Gateway

**Purpose:** Single point for retries, failover, cost tracking, rate limiting.

**Deployment:**
```yaml
# docker-compose.yml
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    ports:
      - "4000:4000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - LITELLM_MASTER_KEY=sk-nutrilens-master
    command: ["--config", "/app/config.yaml", "--num_workers", "4"]
```

**Configuration:**
```yaml
# litellm_config.yaml
model_list:
  # Primary model for extraction
  - model_name: gpt-4o-mini
    litellm_params:
      model: gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY

  # High-quality model for complex tasks
  - model_name: gpt-4o
    litellm_params:
      model: gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  # Failover model
  - model_name: claude-sonnet
    litellm_params:
      model: anthropic/claude-sonnet-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 3
  timeout: 30
  retry_after: 5

  # Redis for distributed rate limiting
  redis_host: redis
  redis_port: 6379

litellm_settings:
  # Failover chain
  fallbacks:
    - gpt-4o-mini: [claude-sonnet]
    - gpt-4o: [claude-sonnet, gpt-4o-mini]

  # Cooldown after failures
  allowed_fails: 3
  cooldown_time: 60

  # Cost tracking callback
  success_callback: ["langfuse"]  # or custom webhook

general_settings:
  master_key: sk-nutrilens-master
  database_url: postgresql://user:pass@postgres:5432/litellm
```

**Usage from Application:**
```python
from openai import AsyncOpenAI

# Point to LiteLLM proxy instead of OpenAI directly
client = AsyncOpenAI(
    base_url="http://litellm:4000/v1",
    api_key="sk-nutrilens-master"
)

# Same OpenAI SDK interface, but with retries/failover/tracking
response = await client.chat.completions.create(
    model="gpt-4o-mini",  # LiteLLM routes this
    messages=[...]
)
```

**Sources:**
- [LiteLLM Production Best Practices](https://docs.litellm.ai/docs/proxy/prod)
- [LiteLLM Routing](https://docs.litellm.ai/docs/routing)

---

### 6. State Checkpointer (PostgresSaver)

**Purpose:** Crash recovery. Never lose progress mid-workflow.

**Setup:**
```python
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Connection pool (singleton)
pool = AsyncConnectionPool(
    conninfo="postgresql://user:pass@localhost:5432/nutrilens",
    max_size=20,
    kwargs={
        "autocommit": True,
        "prepare_threshold": 0,
    }
)

# Checkpointer (singleton)
checkpointer = AsyncPostgresSaver(pool)
await checkpointer.setup()  # Creates checkpoint tables
```

**Thread ID Strategy:**
```python
def create_thread_config(
    workflow: str,     # "normalizer", "estimator", "chatbot"
    tenant_id: str,
    user_id: str,
    request_id: str
) -> dict:
    """Create config for LangGraph invocation"""
    return {
        "configurable": {
            "thread_id": f"{workflow}:{tenant_id}:{user_id}:{request_id}",
            "checkpoint_ns": f"tenant:{tenant_id}"
        }
    }
```

**Sources:**
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [PostgresSaver](https://reference.langchain.com/python/langgraph/checkpoints/)

---

## Directory Structure

```
backend/
├── app/
│   ├── api/                          # FastAPI routes (unchanged)
│   │
│   ├── core/
│   │   ├── config.py                 # Settings
│   │   └── clients.py                # Singleton HTTP clients
│   │
│   ├── infrastructure/
│   │   ├── cache/
│   │   │   └── semantic_cache.py     # Redis + vector cache
│   │   │
│   │   ├── llm/
│   │   │   ├── gateway.py            # LiteLLM client wrapper
│   │   │   └── checkpointer.py       # PostgresSaver setup
│   │   │
│   │   └── prompts/
│   │       ├── registry.py           # Prompt loading
│   │       └── templates/            # Versioned prompt files
│   │           ├── normalizer/
│   │           ├── estimator/
│   │           └── chatbot/
│   │
│   ├── domain/
│   │   ├── normalizer/
│   │   │   ├── schemas.py            # Pydantic models (Instructor)
│   │   │   ├── graph.py              # LangGraph definition
│   │   │   ├── nodes/                # Graph node implementations
│   │   │   │   ├── parse.py
│   │   │   │   ├── extract.py
│   │   │   │   ├── match.py
│   │   │   │   └── convert.py
│   │   │   └── matchers/             # Existing matcher chain
│   │   │       ├── exact.py
│   │   │       ├── alias.py
│   │   │       ├── vector.py
│   │   │       └── llm.py
│   │   │
│   │   ├── estimator/
│   │   │   ├── schemas.py
│   │   │   ├── graph.py
│   │   │   └── nodes/
│   │   │
│   │   └── chatbot/
│   │       ├── schemas.py
│   │       ├── graph.py
│   │       ├── nodes/
│   │       └── memory.py             # Conversation memory
│   │
│   └── services/                     # Orchestration layer
│       ├── normalizer_service.py     # Calls domain graph
│       ├── estimator_service.py
│       └── chatbot_service.py
│
├── prompts/                          # Prompt templates (version controlled)
│   ├── normalizer/
│   │   ├── extract_structure_v1.0.0.txt
│   │   └── verify_match_v1.0.0.txt
│   ├── estimator/
│   │   └── estimate_macros_v1.0.0.txt
│   └── chatbot/
│       └── system_v1.0.0.txt
│
└── docker-compose.yml                # Includes LiteLLM service
```

---

## Migration Path

### Phase 1: Infrastructure Setup
1. Deploy LiteLLM proxy (Docker)
2. Setup PostgreSQL tables for checkpointing
3. Configure Redis semantic cache
4. Create prompt file structure

### Phase 2: Normalizer Migration
1. Define `NormalizerState` TypedDict
2. Define Pydantic schemas with Instructor
3. Implement graph nodes
4. Build and compile LangGraph
5. Update service layer to use graph
6. Remove old `BatchNormalizer`

### Phase 3: Estimator Migration
1. Convert sync → async
2. Define `EstimatorState` and schemas
3. Implement graph
4. Remove old `LLMNutritionEstimator`

### Phase 4: Chatbot Implementation
1. Define `ChatbotState` with memory
2. Implement RAG retrieval node
3. Implement tool calling node
4. Implement response generation node
5. Add conversation memory management

### Phase 5: Observability
1. Add Langfuse/LangSmith integration
2. Setup cost tracking dashboards
3. Add prompt performance analytics
4. Setup alerting for failures

---

## Key Principles

1. **Graphs are request-scoped** - New state per request, NOT singleton
2. **Infrastructure is singleton** - HTTP clients, cache, checkpointer
3. **Prompts are code** - Versioned, tested, deployed independently
4. **Schema is law** - Instructor + Pydantic, no "hope it works"
5. **Failure is expected** - Retries, failover, checkpointing built-in
6. **Multi-tenancy is mandatory** - tenant_id filter on all queries

---

## Sources

- [LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph Checkpointing Best Practices 2025](https://sparkco.ai/blog/mastering-langgraph-checkpointing-best-practices-for-2025)
- [Instructor Documentation](https://python.useinstructor.com/)
- [LiteLLM Production Best Practices](https://docs.litellm.ai/docs/proxy/prod)
- [LiteLLM Routing & Failover](https://docs.litellm.ai/docs/routing)
- [Redis Semantic Caching](https://redis.io/blog/what-is-semantic-caching/)
- [RedisVL LLM Cache](https://redis.io/docs/latest/develop/ai/redisvl/user_guide/llmcache/)
- [PromptLayer Registry](https://docs.promptlayer.com/features/prompt-registry/overview)

---

## Architecture Verification Against ALL Use Cases

### Complete Use Case Inventory (13 Total)

| # | Use Case | File | Model | Async | Streaming | Memory | Tools | Structured Output |
|---|----------|------|-------|-------|-----------|--------|-------|-------------------|
| 1 | Recipe Generation | llm_recipe_generator.py | gpt-4o-2024-08-06 | ✓ | ✗ | ✗ | ✗ | `.parse()` |
| 2 | Nutrition Estimation | llm_nutrition_estimator.py | gpt-4o | **SYNC** | ✗ | ✗ | ✗ | JSON mode |
| 3 | Text Embeddings | openai_embedding_service.py | text-embedding-3-small | ✓ | ✗ | ✗ | ✗ | N/A |
| 4 | Item Normalization | item_normalizer.py | gpt-4o-mini | ✓ | ✗ | ✗ | ✗ | JSON mode |
| 5 | RAG Item Normalization | item_normalizer_rag.py | gpt-4o-mini | ✓ | ✗ | ✗ | ✗ | JSON mode |
| 6 | Recipe Ingredient Processing | recipe_ingredient_processor.py | gpt-4o-2024-08-06 | ✗ | ✗ | ✗ | ✗ | JSON mode |
| 7 | Receipt Item Enrichment | receipt_item_enricher.py | gpt-4o-mini | ✓ | ✗ | ✗ | ✗ | JSON mode |
| 8 | Item Seeding Script | ai_assisted_item_seeding.py | gpt-4o | ✗ | ✗ | ✗ | ✗ | JSON mode |
| 9 | LLM Adapter (Function Calling) | openai_llm_adapter.py | gpt-4o-mini | ✓ | ✗ | ✗ | **✓** | Function calling |
| 10 | LLM Transport Layer | openai_transport.py | configurable | ✓ | ✗ | ✗ | ✗ | Passthrough |
| 11 | Nutrition Chat Agent | nutrition_graph.py | gpt-4o/Claude | ✓ | ✗ | **✓** | **✓** | LangGraph tools |
| 12 | Unified LLM Client | llm_client.py | Claude/GPT-4o | ✓ | ✗ | ✗ | ✗ | Auto JSON |
| 13 | LLM Runtime | llm_runtime.py | configurable | ✓ | ✗ | ✗ | **✓** | Pydantic validate |

---

### Verification Matrix: Does Architecture Support Each Use Case?

#### 1. Recipe Generation (Structured Outputs with `.parse()`)
**Current:** Uses `client.beta.chat.completions.parse()` with Pydantic model
**Architecture Support:** ✅ YES

- **Instructor** supports OpenAI's structured outputs mode
- Can use `instructor.Mode.TOOLS` or `instructor.Mode.JSON`
- Pydantic model (`RecipeStructured`) works directly with Instructor
- LiteLLM proxy transparently passes through structured output requests

```python
# Current code (works as-is through LiteLLM):
response = await client.beta.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    response_format=RecipeStructured,
    messages=[...]
)

# With Instructor (equivalent):
client = instructor.from_openai(AsyncOpenAI(base_url="http://litellm:4000/v1"))
response = await client.chat.completions.create(
    model="gpt-4o-2024-08-06",
    response_model=RecipeStructured,
    messages=[...]
)
```

#### 2. Nutrition Estimation (SYNC → ASYNC migration needed)
**Current:** Synchronous `OpenAI` client, new instance per request
**Architecture Support:** ✅ YES (requires migration)

- Convert to async using `AsyncOpenAI`
- Use singleton client through LiteLLM
- Instructor for schema enforcement (replaces JSON mode hope)

```python
# Before (BROKEN):
self.client = OpenAI(api_key=api_key)  # New client per request!
response = self.client.chat.completions.create(...)  # SYNC blocks event loop

# After:
class NutrientEstimate(BaseModel):
    calories: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    # ... with validators

response = await instructor_client.chat.completions.create(
    model="gpt-4o",
    response_model=NutrientEstimate,
    messages=[...]
)
```

#### 3. Text Embeddings
**Current:** `client.embeddings.create()` with batch support
**Architecture Support:** ✅ YES

- LiteLLM supports embedding models
- Singleton client pattern works
- No schema enforcement needed (returns vectors)

```yaml
# litellm_config.yaml addition:
model_list:
  - model_name: text-embedding-3-small
    litellm_params:
      model: text-embedding-3-small
      api_key: os.environ/OPENAI_API_KEY
```

#### 4 & 5. Item Normalization (Traditional + RAG)
**Current:** Multiple LLM calls for matching and conversion
**Architecture Support:** ✅ YES

- Becomes nodes in Normalizer LangGraph
- Existing matcher chain (Exact → Alias → Vector → LLM) preserved
- Vector search uses pgvector (unchanged)
- LLM verification uses Instructor for schema

#### 6. Recipe Ingredient Processing (SYNC → ASYNC needed)
**Current:** Sync calls, FDC search + LLM selection
**Architecture Support:** ✅ YES (requires migration)

- Can be a separate graph or part of recipe generation
- FDC search is external API (no LLM change needed)
- LLM selection uses Instructor for structured response

#### 7. Receipt Item Enrichment
**Current:** Two LLM calls (normalize name + select FDC match)
**Architecture Support:** ✅ YES

- Can be part of Normalizer graph or separate
- Both calls use Instructor for schema
- Semantic cache helps for repeated items

#### 8. Item Seeding Script (One-time script)
**Current:** Batch generation script
**Architecture Support:** ✅ YES

- Scripts can use same LiteLLM proxy
- Not critical for production architecture
- Can remain as standalone script using shared client

#### 9. LLM Adapter (Function Calling)
**Current:** Uses `functions` parameter (deprecated)
**Architecture Support:** ✅ YES

- Instructor handles function calling via `tools` parameter
- Migration from `functions` → `tools` is straightforward
- LiteLLM transparently supports both

```python
# Current (deprecated):
response = await client.chat.completions.create(
    functions=[...],
    function_call={"name": "verify_match"}
)

# With Instructor:
class VerifyMatchResult(BaseModel):
    is_match: bool
    confidence: float
    reasoning: str

result = await client.chat.completions.create(
    response_model=VerifyMatchResult,
    messages=[...]
)
```

#### 10. LLM Transport Layer
**Current:** Passthrough abstraction
**Architecture Support:** ✅ REPLACED

- This layer becomes unnecessary
- LiteLLM provides the transport abstraction
- Direct client calls through Instructor

#### 11. Nutrition Chat Agent (LangGraph + Tools + Memory)
**Current:** Already uses LangGraph with MongoDB checkpointing
**Architecture Support:** ✅ YES (minor changes)

**Current Implementation:**
- LangGraph with `MongoDBSaver`
- Tools via `bind_tools()`
- Conversation memory in MongoDB

**Architecture Alignment:**
- Keep LangGraph (already using it!)
- Can migrate to `PostgresSaver` for consistency (optional)
- LiteLLM proxy for LLM calls
- Tools pattern unchanged

```python
# Current (already correct pattern):
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools(tools)

# With LiteLLM (just change base_url):
llm = ChatOpenAI(
    model="gpt-4o",
    base_url="http://litellm:4000/v1",
    api_key="sk-nutrilens-master"
)
```

#### 12. Unified LLM Client
**Current:** Custom wrapper for Claude + OpenAI
**Architecture Support:** ✅ REPLACED by LiteLLM

- LiteLLM provides unified interface
- Cost tracking built-in
- Retry logic built-in
- This custom code becomes unnecessary

#### 13. LLM Runtime
**Current:** Custom runtime with caching and tool support
**Architecture Support:** ✅ REPLACED

- LangGraph provides runtime
- Semantic cache provides caching
- Instructor provides schema validation
- This custom code becomes unnecessary

---

### Gap Analysis: What's Missing from Architecture?

#### GAP 1: OpenAI Structured Outputs (`.parse()` method)
**Issue:** Recipe generator uses `client.beta.chat.completions.parse()`
**Resolution:** ✅ Instructor supports this via `response_model` parameter

#### GAP 2: Embedding API
**Issue:** Architecture focuses on chat completions, embeddings mentioned briefly
**Resolution:** ✅ Add explicit embedding support

```python
# Add to architecture:
class EmbeddingService:
    def __init__(self, client: AsyncOpenAI):
        self.client = client  # Points to LiteLLM

    async def embed(self, texts: List[str]) -> List[List[float]]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )
        return [e.embedding for e in response.data]
```

#### GAP 3: Streaming Support
**Issue:** Architecture mentions streaming but no implementation
**Current Usage:** Not used in any existing code
**Resolution:** ✅ Add as future capability (not blocking)

```python
# Future: Instructor supports streaming
async for partial in client.chat.completions.create_partial(
    model="gpt-4o",
    response_model=RecipeStructured,
    messages=[...],
    stream=True
):
    yield partial
```

#### GAP 4: MongoDB vs PostgreSQL Checkpointing
**Issue:** Chatbot uses `MongoDBSaver`, architecture proposes `PostgresSaver`
**Resolution:** ⚠️ DECISION NEEDED

Options:
1. **Keep MongoDB** for chatbot (already working), PostgreSQL for others
2. **Migrate all to PostgreSQL** for consistency
3. **Keep both** with clear separation

**Recommendation:** Keep MongoDB for chatbot (proven), PostgreSQL for new graphs

#### GAP 5: Batch Processing
**Issue:** Normalizer processes multiple items in one LLM call
**Resolution:** ✅ Supported via Instructor with `List[ExtractedItem]` response model

```python
class BatchExtractionResult(BaseModel):
    items: List[ExtractedItem]  # Handles batch in single call

result = await client.chat.completions.create(
    response_model=BatchExtractionResult,
    messages=[{"role": "user", "content": "\n".join(lines)}]
)
```

#### GAP 6: Temperature Variation for Retries
**Issue:** Recipe generator increases temperature on retry for variety
**Resolution:** ✅ Can be handled in graph node logic

```python
async def generate_recipe_node(state: RecipeState) -> dict:
    temperature = 0.8 + (state["retry_count"] * 0.1)
    result = await client.chat.completions.create(
        model="gpt-4o-2024-08-06",
        response_model=RecipeStructured,
        temperature=temperature,
        messages=[...]
    )
    return {"recipe": result}
```

#### GAP 7: Vector Similarity for Deduplication
**Issue:** Recipe generator checks embedding similarity before accepting
**Resolution:** ✅ Supported via pgvector (unchanged)

```python
# Existing pattern works:
async def check_duplicate(embedding: List[float], threshold: float = 0.92):
    result = await db.execute(text("""
        SELECT id, 1 - (embedding <=> :emb) as similarity
        FROM recipes
        WHERE 1 - (embedding <=> :emb) > :threshold
        LIMIT 1
    """), {"emb": embedding, "threshold": threshold})
    return result.first()
```

---

### Final Verification: All Use Cases Covered

| Use Case | Supported | Migration Effort |
|----------|-----------|------------------|
| Recipe Generation | ✅ | Low (change client base_url) |
| Nutrition Estimation | ✅ | Medium (sync → async) |
| Text Embeddings | ✅ | Low (add to LiteLLM config) |
| Item Normalization | ✅ | Medium (new LangGraph) |
| RAG Item Normalization | ✅ | Medium (integrate into graph) |
| Recipe Ingredient Processing | ✅ | Medium (sync → async) |
| Receipt Item Enrichment | ✅ | Low (use Instructor) |
| Item Seeding Script | ✅ | Low (use shared client) |
| LLM Adapter | ✅ | Low (use Instructor) |
| LLM Transport | ✅ | Removed (replaced by LiteLLM) |
| Nutrition Chat Agent | ✅ | Low (keep LangGraph, change client) |
| Unified LLM Client | ✅ | Removed (replaced by LiteLLM) |
| LLM Runtime | ✅ | Removed (replaced by LangGraph) |

---

### Updated Architecture Decision: Checkpointer Strategy

Given existing MongoDB usage for chatbot:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Checkpointing Strategy                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Chatbot (nutrition_graph.py)                                   │
│  └── MongoDBSaver (keep existing, proven)                       │
│      - Long-running conversations                                │
│      - Already integrated with chat history                      │
│      - Working in production                                     │
│                                                                  │
│  Normalizer Graph (new)                                         │
│  └── PostgresSaver OR MemorySaver                               │
│      - Short-lived requests (< 30 seconds)                      │
│      - May not need persistence (request-scoped)                │
│      - PostgresSaver only if crash recovery critical            │
│                                                                  │
│  Estimator Graph (new)                                          │
│  └── MemorySaver (no persistence needed)                        │
│      - Single LLM call workflow                                  │
│      - Too fast to benefit from checkpointing                    │
│                                                                  │
│  Recipe Generator Graph (new)                                   │
│  └── PostgresSaver                                              │
│      - Multi-step with deduplication                             │
│      - May have retries                                          │
│      - Crash recovery valuable                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Architecture Completeness: VERIFIED ✅

The proposed architecture supports ALL 13 existing use cases:

1. **Chat completions** → LiteLLM + Instructor
2. **Structured outputs** → Instructor with `response_model`
3. **Function/tool calling** → Instructor or LangGraph `bind_tools`
4. **Embeddings** → LiteLLM proxy (add to config)
5. **Conversation memory** → MongoDB (chatbot), PostgreSQL (others)
6. **Batch processing** → Instructor with `List[T]` response model
7. **Multi-provider** → LiteLLM failover (OpenAI → Claude)
8. **Cost tracking** → LiteLLM built-in
9. **Retry logic** → LiteLLM + Instructor `max_retries`
10. **Schema enforcement** → Instructor + Pydantic validators
11. **Semantic caching** → Redis + vector similarity
12. **State machines** → LangGraph
13. **Crash recovery** → PostgresSaver/MongoDBSaver
