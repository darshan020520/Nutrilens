# Nutrition Agent - Complete Architecture Documentation

**Last Updated**: 2025-11-08
**Status**: Implementation Phase
**Version**: 1.0

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Vision & Purpose](#vision--purpose)
3. [System Architecture](#system-architecture)
4. [Component Details](#component-details)
5. [Implementation Plan](#implementation-plan)
6. [Current State](#current-state)
7. [Architectural Decisions](#architectural-decisions)
8. [Known Blockers](#known-blockers)

---

## Executive Summary

### What We're Building
A context-aware AI nutrition assistant that eliminates the pain of repeatedly explaining your history to ChatGPT. It knows your complete nutrition data and provides intelligent suggestions, insights, and actions.

### Core Value Propositions
1. **Context-Aware Intelligence**: Already knows your goals, history, preferences - no need to explain
2. **Hybrid Approach**: Rule-based (fast, free) + LLM (intelligent, flexible)
3. **Action-Oriented**: Not just answers - can suggest meals, order food, log meals automatically
4. **Service Orchestration**: No duplicate logic - leverages existing services

### Key Metrics
- **Target Response Time**: <500ms (rule-based), <2s (LLM)
- **Cost Per Query**: $0 (rule-based), ~$0.002-0.005 (LLM)
- **Cache Hit Rate**: >90% for user context
- **Accuracy**: >95% for nutrition lookups

---

## Vision & Purpose

### The Problem We're Solving

**Traditional ChatGPT Experience**:
```
User: "How's my protein intake?"
ChatGPT: "I don't have access to your data. Please tell me:
  - What did you eat today?
  - What's your weight and height?
  - What's your daily protein target?"

[User has to type everything manually]
```

**NutriLens Agent Experience**:
```
User: "How's my protein intake?"
Agent: "You've consumed 85g protein today (65% of 130g target).
        You typically hit 75% on weekdays. Add 45g more to reach
        your goal - try a protein shake or chicken breast."

[Instant, context-aware response]
```

### Core Features

#### Feature 1: Enhanced Meal Suggestions
**Components**:
1. **Next Planned Meal** - Show what's scheduled from meal plan
2. **Track Record Insights** - Daily/weekly consumption analysis
3. **Makeable Recipes** - Filtered by inventory availability
4. **AI-Enhanced Suggestions** - LLM-powered personalized recommendations
5. **Zomato Integration** - Order food and auto-log as external meal

**User Flow**:
```
User opens "Suggest Meal" →
  Shows next planned: "Lunch at 1 PM - Grilled Chicken"
  Shows insights: "You're at 65% protein, 85% compliance this week"
  Shows makeable: "Based on your inventory, you can make..."
  [Optional] Click "Get AI Suggestions" → LLM analyzes & recommends
  [Optional] Click "Order Food" → Zomato integration
```

#### Feature 2: Contextual Nutrition Chatbot
**Capabilities**:
- Simple stats: "How much protein today?" → Rule-based (instant)
- What-if scenarios: "What if I eat 2 samosas?" → Hybrid (calculate + LLM)
- Recommendations: "What should I eat?" → Hybrid (score + LLM)
- Complex queries: "Am I consistent with breakfast?" → Full LLM

**Example Queries**:
```
✅ "How am I doing today?"
✅ "What would happen if I eat 2 samosas?"
✅ "Will I reach my muscle gain goal?"
✅ "What should I cook for dinner that's high protein?"
✅ "Am I consistent with breakfast?"
```

#### Feature 3: Zomato Food Ordering
**Flow**:
```
1. User wants to order food
2. Agent gets user preferences (cuisines, dietary restrictions)
3. Agent gets user history (favorite dishes, patterns)
4. Agent calls Zomato MCP with intelligent query
5. Agent scores results (nutrition match, preference alignment)
6. Agent presents top 5 options with LLM explanation
7. User confirms order
8. Agent places order via Zomato API
9. Agent logs meal as "external" with estimated macros
10. Agent tracks order status
```

---

## System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                         │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐     │
│  │   Meal     │  │    Chat    │  │     Zomato       │     │
│  │ Suggestions│  │   Widget   │  │   Integration    │     │
│  └────────────┘  └────────────┘  └──────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  NUTRITION AGENT (Brain)                    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  1. CONTEXT BUILDER                                   │ │
│  │     Gathers ALL user data in one place               │ │
│  │     • Profile (age, weight, goals)                   │ │
│  │     • Targets (calories, macros)                     │ │
│  │     • Today's consumption                            │ │
│  │     • Weekly stats & patterns                        │ │
│  │     • Inventory status                               │ │
│  │     • Preferences & history                          │ │
│  │     • Upcoming meals                                 │ │
│  │                                                        │ │
│  │     Cache: Memory (5min) → Redis (15min) → DB       │ │
│  └──────────────────────────────────────────────────────┘ │
│                           ↓                                 │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  2. INTELLIGENCE LAYER (Hybrid Approach)             │ │
│  │                                                        │ │
│  │     Route 1: RULE-BASED (70% of queries)            │ │
│  │     • Simple stats: "How much protein?"              │ │
│  │     • Basic calculations                             │ │
│  │     • Cost: $0, Speed: <100ms                       │ │
│  │                                                        │ │
│  │     Route 2: HYBRID (20% of queries)                │ │
│  │     • What-if scenarios                              │ │
│  │     • Recommendations with explanations              │ │
│  │     • Cost: ~$0.002, Speed: <1s                     │ │
│  │                                                        │ │
│  │     Route 3: FULL LLM (10% of queries)              │ │
│  │     • Complex reasoning                              │ │
│  │     • Conversational follow-ups                      │ │
│  │     • Cost: ~$0.005, Speed: <2s                     │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  3. INTEGRATION LAYER                                 │ │
│  │     • Zomato MCP Client                              │ │
│  │     • External meal logger                           │ │
│  │     • Order tracking                                 │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│         EXISTING SERVICES (Orchestration Layer)             │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Consumption  │  │  Planning    │  │  Inventory   │    │
│  │  Service     │  │   Agent      │  │   Service    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Onboarding  │  │  FDC Service │  │   Tracking   │    │
│  │   Service    │  │  (Nutrition) │  │    Agent     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Postgres   │  │     Redis    │  │   External   │    │
│  │   Database   │  │     Cache    │  │     APIs     │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```
User Query: "What should I eat for dinner?"
             ↓
┌────────────────────────────────────────────┐
│ 1. CONTEXT BUILDER                         │
│    Check cache → Build from services       │
│    Time: 50-200ms                          │
└────────────────────────────────────────────┘
             ↓
┌────────────────────────────────────────────┐
│ 2. INTENT CLASSIFIER                       │
│    Pattern match query type                │
│    Result: "recommendation"                │
│    Time: <5ms                              │
└────────────────────────────────────────────┘
             ↓
┌────────────────────────────────────────────┐
│ 3. INTELLIGENCE ROUTER                     │
│    Route to: Hybrid approach               │
│    (Rule-based scoring + LLM explanation)  │
└────────────────────────────────────────────┘
             ↓
┌────────────────────────────────────────────┐
│ 4a. RULE-BASED SCORING                     │
│     • Get makeable recipes from inventory  │
│     • Score by macro fit (math)            │
│     • Score by goal alignment              │
│     • Score by context                     │
│     Time: 100-300ms                        │
└────────────────────────────────────────────┘
             ↓
┌────────────────────────────────────────────┐
│ 4b. LLM EXPLANATION                        │
│     • Send context + top 3 recipes to LLM  │
│     • Generate natural language response   │
│     Time: 500-1500ms                       │
└────────────────────────────────────────────┘
             ↓
┌────────────────────────────────────────────┐
│ 5. RESPONSE FORMATTING                     │
│    Combine scored recipes + LLM text       │
│    Total time: ~1-2s                       │
└────────────────────────────────────────────┘
             ↓
        Return to user
```

---

## Component Details

### Component 1: Context Builder

**File**: `backend/app/agents/nutrition_agent_context.py`

**Purpose**: Single source of truth for all user context data.

**Interface**:
```python
class UserContext:
    def __init__(self, db: Session, user_id: int)

    def build_complete_context() -> Dict[str, Any]
    def _get_profile() -> Dict
    def _get_targets() -> Dict
    def _get_today_consumption() -> Dict
    def _get_weekly_stats() -> Dict
    def _get_inventory_summary() -> Dict
    def _get_preferences() -> Dict
    def _get_meal_history(days: int = 7) -> List[Dict]
    def _get_upcoming_meals() -> List[Dict]
    def _get_recent_achievements() -> List[str]
```

**Context Structure**:
```json
{
  "profile": {
    "age": 28,
    "weight_kg": 75,
    "height_cm": 178,
    "sex": "male",
    "goal_type": "muscle_gain",
    "activity_level": "moderately_active"
  },
  "targets": {
    "calories": 2500,
    "protein_g": 130,
    "carbs_g": 280,
    "fat_g": 80
  },
  "today": {
    "calories": 1450,
    "protein_g": 85,
    "carbs_g": 150,
    "fat_g": 45,
    "meals_consumed": 2,
    "meals_pending": 2,
    "compliance_rate": 75
  },
  "week": {
    "avg_calories": 2350,
    "compliance_rate": 82,
    "protein_consistency": 78,
    "favorite_meals": ["Oatmeal", "Chicken Rice Bowl", "Protein Shake"]
  },
  "inventory": {
    "total_items": 45,
    "expiring_soon": 3,
    "low_stock": 5,
    "makeable_recipes": 12
  },
  "preferences": {
    "cuisines": ["Indian", "Asian"],
    "dietary": ["high_protein"],
    "allergies": [],
    "spice_level": "medium"
  },
  "history": [
    {
      "meal": "Oatmeal with Protein",
      "meal_type": "breakfast",
      "time": "2025-11-08 08:00",
      "calories": 450
    }
  ],
  "upcoming": [
    {
      "meal_type": "lunch",
      "recipe": "Grilled Chicken with Rice",
      "time": "13:00",
      "calories": 650
    }
  ],
  "achievements": [
    "Logged all meals for 3 days straight!",
    "Hit protein target 5 days this week"
  ]
}
```

**Caching Strategy**:
```
Level 1: In-Memory Cache
- TTL: 5 minutes
- Storage: Python dict
- Use case: Same user, multiple requests

Level 2: Redis Cache
- TTL: 15 minutes
- Storage: Redis hash
- Use case: Across API instances

Level 3: Database
- TTL: N/A (always fresh)
- Storage: Postgres
- Use case: Cache miss
```

**Performance**:
- Cache hit: <10ms
- Cache miss: 100-200ms (parallel service calls)
- Cache invalidation: On meal log, goal change, inventory update

---

### Component 2: Intelligence Layer

**File**: `backend/app/agents/nutrition_intelligence.py`

**Purpose**: Route queries to optimal handler (rule-based vs LLM).

**Decision Matrix**:

| Query Type | Handler | Speed | Cost | Example |
|------------|---------|-------|------|---------|
| Simple Stat | Rule-based | <100ms | $0 | "How much protein today?" |
| What-If | Hybrid | <1s | $0.002 | "What if I eat 2 samosas?" |
| Recommendation | Hybrid | <1.5s | $0.003 | "What should I eat?" |
| Conversational | Full LLM | <2s | $0.005 | "Am I consistent?" |

**Intent Classification**:
```python
def _classify_intent(query: str) -> str:
    """
    Fast pattern matching - no LLM needed

    Categories:
    - simple_stat: stat keywords + question
    - what_if: "what if", "what would"
    - recommendation: "suggest", "recommend", "should i"
    - conversational: everything else
    """

    query_lower = query.lower()

    # Simple stats
    if any(kw in query_lower for kw in ["how much", "how many", "am i"]):
        return "simple_stat"

    # What-if scenarios
    if "what if" in query_lower or "what would" in query_lower:
        return "what_if"

    # Recommendations
    if any(kw in query_lower for kw in ["suggest", "recommend", "should i"]):
        return "recommendation"

    return "conversational"
```

**Handler Implementations**:

1. **Rule-Based Handler** (70% of queries):
```python
def _handle_stat_query(query: str) -> Dict:
    """
    Pure computation - no LLM

    Examples:
    - "How much protein?" → Query today's consumption
    - "How many calories left?" → Calculate remaining
    - "Am I on track?" → Check compliance rate
    """

    ctx = self.context.build_complete_context()

    # Pattern match query
    if "protein" in query:
        consumed = ctx["today"]["protein_g"]
        target = ctx["targets"]["protein_g"]
        remaining = target - consumed
        percentage = (consumed / target * 100)

        return {
            "answer": f"You've consumed {consumed}g protein ({percentage:.0f}% of {target}g target). {remaining}g remaining.",
            "method": "rule_based",
            "cost": 0
        }
```

2. **Hybrid Handler** (20% of queries):
```python
def _handle_what_if(query: str) -> Dict:
    """
    Calculate impact with rules, explain with LLM

    Steps:
    1. Extract food item (pattern match or simple LLM)
    2. Lookup nutrition (FDC service or database)
    3. Calculate impact (math)
    4. Format response (LLM)
    """

    food_item = self._extract_food_item(query)  # Pattern match
    nutrition = self._lookup_food_nutrition(food_item)  # DB/FDC

    # Calculate impact (pure math)
    new_calories = ctx["today"]["calories"] + nutrition["calories"]
    remaining = ctx["targets"]["calories"] - new_calories

    # LLM for natural explanation
    prompt = f"""
User ate {food_item} ({nutrition['calories']} cal).
New total: {new_calories} cal
Remaining: {remaining} cal

Explain impact in 2-3 sentences.
"""

    return {"answer": llm.generate(prompt), "method": "hybrid"}
```

3. **Full LLM Handler** (10% of queries):
```python
def _handle_with_llm(query: str) -> Dict:
    """
    Complex reasoning requiring full LLM

    Use for:
    - Historical analysis
    - Pattern recognition
    - Open-ended questions
    """

    ctx = self.context.build_complete_context()

    prompt = f"""
You are NutriLens AI with full access to user's nutrition data.

USER CONTEXT:
{json.dumps(ctx, indent=2)}

USER QUERY: {query}

Provide helpful, data-driven response (2-4 sentences).
"""

    return {"answer": llm.generate(prompt), "method": "llm_full"}
```

---

### Component 3: Zomato Integration

**File**: `backend/app/integrations/zomato_integration.py`

**Purpose**: Order food from Zomato and automatically log as external meal.

**Flow Diagram**:
```
User clicks "Order Food"
        ↓
Get user preferences & history
        ↓
Build intelligent Zomato query
    - Location: User's saved address
    - Cuisines: User's favorite (Indian, Asian)
    - Dietary: User's restrictions (vegetarian, etc.)
    - Budget: Based on user tier
    - Nutrition: Target this meal's macros
        ↓
Call Zomato MCP Server
    - Search restaurants in area
    - Get menu items
    - Filter by cuisine/dietary
        ↓
Score each dish (rule-based)
    - Nutrition match (40%): How well does it fit meal targets?
    - Preference alignment (30%): Matches favorite cuisines?
    - Restaurant rating (20%): Quality/reviews
    - Price (10%): Within budget?
        ↓
Top 5 dishes selected
        ↓
LLM generates recommendation text
    "Based on your love for Indian food and need for 50g protein,
     I recommend Chicken Tikka Masala from Tandoor Palace.
     It provides 48g protein and fits your 650 calorie target."
        ↓
Present to user with:
    - Dish name, restaurant, price
    - Estimated nutrition
    - Delivery time
    - "Why recommended" explanation
        ↓
User confirms order
        ↓
Place order via Zomato API
        ↓
Create MealLog entry:
    - recipe_id: NULL (external meal)
    - is_external: true
    - external_meal_name: "Chicken Tikka Masala from Tandoor Palace"
    - external_meal_macros: {estimated nutrition}
    - notes: "Ordered via Zomato - Order ID: ABC123"
    - zomato_order_id: "ABC123"
        ↓
Update daily consumption
        ↓
Track order status (background job)
```

**Nutrition Estimation Strategy**:
```python
def _estimate_dish_nutrition(dish_name: str, description: str, cuisine: str) -> Dict:
    """
    Multi-strategy approach to estimate restaurant dish nutrition

    Priority:
    1. Check our database for similar dishes
    2. Call FDC service for brand/chain restaurants
    3. Use LLM to estimate based on ingredients
    4. Apply cuisine-specific adjustments
    """

    # Strategy 1: Database lookup
    similar = db.query(Recipe).filter(
        Recipe.title.ilike(f"%{dish_name}%")
    ).first()

    if similar:
        return similar.macros_per_serving

    # Strategy 2: FDC for chains
    if is_chain_restaurant(restaurant_name):
        fdc_result = fdc_service.search_branded(f"{restaurant_name} {dish_name}")
        if fdc_result:
            return fdc_result

    # Strategy 3: LLM estimation
    prompt = f"""
Estimate nutrition for restaurant dish:

Dish: {dish_name}
Description: {description}
Cuisine: {cuisine}

Consider:
- Restaurant portions are 1.5x larger than homemade
- {cuisine} dishes typically use more oil/cream
- Include estimated serving size

Return JSON: {{"calories": X, "protein_g": X, "carbs_g": X, "fat_g": X}}
"""

    return llm.generate(prompt)
```

**Order Tracking**:
```python
async def track_order(order_id: str, user_id: int):
    """
    Background job to track Zomato order status

    Updates:
    1. Order placed → Notification sent
    2. Order accepted → Update meal log notes
    3. Order out for delivery → Send notification
    4. Order delivered → Mark meal as "consumed" automatically
    """

    while True:
        status = await zomato_mcp.get_order_status(order_id)

        if status == "delivered":
            # Automatically mark meal as consumed
            meal_log = db.query(MealLog).filter_by(
                zomato_order_id=order_id
            ).first()

            meal_log.consumed_datetime = datetime.utcnow()
            db.commit()

            # Send notification
            await notification_service.send_meal_reminder(
                user_id=user_id,
                title="Meal Delivered!",
                body="Your food has arrived. Enjoy your meal!",
                priority=NotificationPriority.NORMAL
            )

            break

        await asyncio.sleep(30)  # Check every 30 seconds
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

#### 1.1 Context Builder [PRIORITY: HIGH]
- [x] Create `UserContext` class
- [ ] Implement `build_complete_context()`
- [ ] Implement service delegation methods
- [ ] Add caching (Memory + Redis)
- [ ] Write unit tests
- [ ] Test with real user data

**Files to create**:
- `backend/app/agents/nutrition_agent_context.py`
- `backend/tests/test_context_builder.py`

**Dependencies**:
- ConsumptionService ✅ (exists)
- PlanningAgent ✅ (exists)
- InventoryService ✅ (exists)
- OnboardingService ✅ (exists)

#### 1.2 Intelligence Layer - Rule-Based [PRIORITY: HIGH]
- [ ] Create `NutritionIntelligence` class
- [ ] Implement intent classifier
- [ ] Implement rule-based stat handler
- [ ] Add simple pattern matching
- [ ] Write tests for common queries

**Files to create**:
- `backend/app/agents/nutrition_intelligence.py`
- `backend/tests/test_intelligence_layer.py`

#### 1.3 API Endpoints [PRIORITY: HIGH]
- [ ] Create `/nutrition/chat` endpoint
- [ ] Create `/nutrition/suggest-meal-enhanced` endpoint
- [ ] Add request/response models
- [ ] Add error handling
- [ ] Add rate limiting

**Files to modify**:
- `backend/app/api/nutrition.py`
- `backend/app/schemas/nutrition.py`

### Phase 2: LLM Integration (Week 2)

#### 2.1 LLM Service Setup [PRIORITY: HIGH]
- [ ] Choose LLM provider (Claude vs GPT-4)
- [ ] Create LLM wrapper class
- [ ] Add API key configuration
- [ ] Implement rate limiting
- [ ] Add error handling & retries
- [ ] Add cost tracking

**Files to create**:
- `backend/app/services/llm_service.py`
- `backend/app/core/config.py` (update)

#### 2.2 Hybrid Intelligence [PRIORITY: MEDIUM]
- [ ] Implement what-if handler
- [ ] Implement recommendation handler
- [ ] Add food item extraction
- [ ] Add nutrition lookup
- [ ] Write tests

#### 2.3 Full LLM Handler [PRIORITY: MEDIUM]
- [ ] Implement conversational handler
- [ ] Add prompt templates
- [ ] Add response formatting
- [ ] Test with various queries

### Phase 3: Enhanced Meal Suggestions (Week 3)

#### 3.1 Refactor `suggest_next_meal()` [PRIORITY: HIGH]
- [x] Update to orchestrate services
- [x] Add context-aware scoring
- [x] Add "WHY" explanations
- [ ] Add AI-enhanced suggestions option
- [ ] Test with real data

**Status**: Partially complete (basic orchestration done)

#### 3.2 Track Record Component [PRIORITY: MEDIUM]
- [ ] Create daily insights formatter
- [ ] Create weekly insights formatter
- [ ] Add trend analysis
- [ ] Add visualization data

### Phase 4: Zomato Integration (Week 4)

#### 4.1 Learn Zomato MCP [PRIORITY: HIGH]
- [ ] Get Zomato MCP documentation
- [ ] Understand API capabilities
- [ ] Test with sandbox environment
- [ ] Document endpoints

**Blocker**: Need Zomato MCP server details

#### 4.2 Zomato Integration Class [PRIORITY: MEDIUM]
- [ ] Create `ZomatoIntegration` class
- [ ] Implement restaurant search
- [ ] Implement dish scoring
- [ ] Implement order placement
- [ ] Implement nutrition estimation

#### 4.3 External Meal Logging [PRIORITY: HIGH]
- [ ] Add external meal fields to MealLog model
- [ ] Implement auto-logging after order
- [ ] Implement order tracking
- [ ] Add order history view

**Files to create**:
- `backend/app/integrations/zomato_integration.py`
- `backend/alembic/versions/add_external_meal_fields.py`

### Phase 5: Testing & Optimization (Week 5)

#### 5.1 Performance Optimization
- [ ] Profile slow queries
- [ ] Optimize cache strategy
- [ ] Add database indexes
- [ ] Load testing

#### 5.2 Cost Optimization
- [ ] Implement query similarity matching
- [ ] Add response caching
- [ ] Optimize LLM prompts
- [ ] Track cost per user

#### 5.3 Error Handling
- [ ] Add graceful degradation
- [ ] Add fallback responses
- [ ] Add monitoring & alerts
- [ ] Add retry logic

---

## Current State

### Completed ✅
1. **Notification System Fixes**
   - Achievement spam fixed with Redis deduplication
   - Inventory alerts unified with scheduled approach
   - Progress updates verified working
   - Meal reminders verified working

2. **Nutrition Agent - Basic Structure**
   - `suggest_next_meal()` refactored with service orchestration
   - Service injection added (ConsumptionService, PlanningAgent, InventoryService)
   - Context-aware scoring implemented
   - "WHY" explanation method added

3. **Supporting Services** (Already Built)
   - ConsumptionService ✅
   - PlanningAgent ✅
   - InventoryService ✅
   - OnboardingService ✅
   - TrackingAgent ✅
   - FDC Service ✅

### In Progress 🔄
1. **Nutrition Agent Architecture**
   - Documentation (this file) ✅
   - Context Builder (next)
   - Intelligence Layer (next)

### Not Started ❌
1. LLM Integration
2. Zomato Integration
3. Chatbot UI
4. External meal logging enhancements

---

## Architectural Decisions

### Decision 1: Hybrid Intelligence (Rule-Based + LLM)

**Decision**: Use rule-based logic for 70% of queries, LLM for 30%.

**Rationale**:
- **Cost**: Rule-based is free, LLM costs $0.002-0.005 per query
- **Speed**: Rule-based is <100ms, LLM is 500-2000ms
- **Reliability**: Rule-based is deterministic, LLM can hallucinate
- **Quality**: LLM provides better conversational experience

**Trade-offs**:
- ✅ 70% cost savings
- ✅ Faster average response time
- ❌ More code complexity (two paths)
- ❌ Need to maintain intent classification

**When to pivot**: If LLM costs drop significantly (90%+) or query patterns show mostly complex queries.

### Decision 2: Context-First Architecture

**Decision**: Always build complete context before any intelligence.

**Rationale**:
- **Quality**: Rich context = better LLM responses
- **Consistency**: Same context format for all handlers
- **Caching**: Context reused across multiple queries in conversation
- **Debugging**: Easy to inspect what LLM "knows"

**Trade-offs**:
- ✅ Significantly better response quality
- ✅ Easier to debug issues
- ❌ 100-200ms overhead on first query
- ❌ More memory usage

**When to pivot**: If context building becomes performance bottleneck (>500ms consistently).

### Decision 3: Multi-Level Caching

**Decision**: Memory (5min) → Redis (15min) → Database.

**Rationale**:
- **Performance**: 90%+ queries served from cache
- **Freshness**: 15min max staleness acceptable for nutrition data
- **Scalability**: Redis shared across API instances

**Trade-offs**:
- ✅ 10-20x faster response times
- ✅ Reduced database load
- ❌ Cache invalidation complexity
- ❌ Stale data possible

**When to pivot**: If users report stale data issues frequently, reduce TTL to 5 minutes for Redis.

### Decision 4: Service Orchestration (No Duplication)

**Decision**: Nutrition Agent delegates to existing services, never reimplements.

**Rationale**:
- **DRY**: Single source of truth for each capability
- **Maintenance**: Fix bugs in one place
- **Consistency**: Same logic across all features
- **Trust**: Services are already tested

**Trade-offs**:
- ✅ Much easier maintenance
- ✅ No duplicate bugs
- ❌ Dependency on service interfaces
- ❌ Less control over performance

**When to pivot**: Never. This is a fundamental principle.

### Decision 5: Gradual LLM Enhancement

**Decision**: Basic features work without LLM, LLM is optional enhancement.

**Rationale**:
- **Reliability**: Always get a response, even if LLM fails
- **Cost Control**: Users can opt-out of AI suggestions
- **Graceful Degradation**: System works even with LLM downtime

**Trade-offs**:
- ✅ More reliable system
- ✅ Better cost control
- ❌ More code paths to maintain
- ❌ Potential UI complexity

**When to pivot**: If users always prefer AI suggestions (>95%), make it default but keep fallback.

---

## Known Blockers

### Blocker 1: Zomato MCP Server Access
**Status**: CRITICAL
**Impact**: Cannot implement food ordering feature
**Action Required**:
- Get Zomato MCP server documentation
- Understand API capabilities (search, menu, order)
- Get sandbox access for testing
- Understand nutrition data availability

**Workaround**: Implement other features first, add Zomato later.

### Blocker 2: LLM Provider Choice
**Status**: MEDIUM
**Impact**: Cannot implement chatbot until decided
**Options**:
1. **Claude (Anthropic)**: Better at following instructions, more expensive
2. **GPT-4 (OpenAI)**: Cheaper, good quality, wider adoption

**Decision Needed**:
- Budget constraints?
- Response quality requirements?
- Latency requirements?

**Recommendation**: Start with GPT-4 (cheaper), switch to Claude if quality issues.

### Blocker 3: External Meal Schema
**Status**: LOW
**Impact**: Need database migration for Zomato integration
**Fields Needed**:
```python
class MealLog:
    is_external: bool = False
    external_meal_name: Optional[str]
    external_meal_macros: Optional[JSON]
    zomato_order_id: Optional[str]
    delivery_status: Optional[str]
```

**Action**: Create migration when ready to implement Zomato.

### Blocker 4: Rate Limiting & Cost Control
**Status**: MEDIUM
**Impact**: Could have high LLM costs without limits
**Solution Needed**:
- Per-user rate limits (e.g., 50 queries/day)
- Cost tracking per user
- Fallback to rule-based when limit exceeded

**Action**: Implement before LLM goes to production.

---

## Testing Strategy

### Unit Tests
```python
# test_context_builder.py
def test_context_builder_cache():
    """Test that context is cached correctly"""

def test_context_builder_freshness():
    """Test that context updates after meal log"""

# test_intelligence_layer.py
def test_intent_classification():
    """Test query intent is classified correctly"""

def test_rule_based_handler():
    """Test rule-based responses are accurate"""

def test_hybrid_handler():
    """Test hybrid responses combine rules + LLM"""
```

### Integration Tests
```python
def test_suggest_meal_end_to_end():
    """Test complete flow from API to response"""

def test_chat_conversation():
    """Test multi-turn conversation maintains context"""

def test_zomato_order_flow():
    """Test order placement and meal logging"""
```

### Performance Tests
```python
def test_context_builder_performance():
    """Context should build in <200ms"""

def test_rule_based_latency():
    """Rule-based queries should respond in <100ms"""

def test_cache_hit_rate():
    """Cache hit rate should be >90%"""
```

---

## Monitoring & Metrics

### Key Metrics to Track

1. **Performance**
   - Average response time by query type
   - Cache hit rate
   - P95/P99 latency

2. **Cost**
   - LLM cost per query
   - Daily/monthly LLM spend
   - Cost per user

3. **Quality**
   - User feedback ratings
   - Error rate
   - Fallback rate

4. **Usage**
   - Queries per day
   - Query type distribution
   - Feature adoption (AI suggestions, Zomato orders)

### Alerts
- Response time > 5s
- Error rate > 5%
- Daily LLM cost > $50
- Cache hit rate < 80%

---

## Next Steps

### Immediate (This Week)
1. ✅ Complete architecture documentation (this file)
2. [ ] Implement `UserContext` class
3. [ ] Implement rule-based intelligence
4. [ ] Create `/chat` API endpoint
5. [ ] Test with sample queries

### Short-term (Next 2 Weeks)
1. [ ] Choose & integrate LLM provider
2. [ ] Implement hybrid intelligence
3. [ ] Enhance `suggest_next_meal()` with AI option
4. [ ] Basic chatbot UI

### Long-term (Next Month)
1. [ ] Zomato MCP integration
2. [ ] External meal logging
3. [ ] Performance optimization
4. [ ] Cost optimization

---

## Contact & Questions

For questions or clarifications about this architecture:
- Review this document first
- Check implementation plan for current status
- Refer to architectural decisions for "why"
- Check known blockers for dependencies

**Document Version Control**:
- v1.0 (2025-11-08): Initial architecture
- Updates should include version bump and changelog

---

**END OF DOCUMENT**
