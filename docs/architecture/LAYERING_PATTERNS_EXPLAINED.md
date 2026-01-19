# Architectural Layering Patterns Explained

**Date**: 2025-11-24
**Purpose**: Clarify when and why we use different architectural patterns

---

## Your Questions

1. **"Not all endpoints follow API → Orchestrator → Service → Repository"**
   - Why do some go directly: API → Service → Database?

2. **"Recipe alternatives is strange: Repository → Service → Repository?"**
   - How is that structured and why?

---

## The Answer: Pragmatic Architecture

**We use DIFFERENT patterns for DIFFERENT complexity levels.**

Not every endpoint needs the full stack. We apply the **minimum necessary architecture** for each use case.

---

## Pattern 1: Simple CRUD - API → Service → Repository → DB

**Used for**: Simple data access operations

**Example**: `get_active_meal_plan()`

```
API: meal_plan_v2.py
    ↓
Service: meal_plan_service_v2.py
    ↓ get_active_meal_plan(user_id)
    ↓
Repository: meal_plan_repository.py
    ↓ get_active_plan(user_id)
    ↓ db.query(MealPlan).filter_by(user_id, is_active=True).first()
    ↓
Database
```

**Why this pattern?**
- Simple query with no business logic
- Repository isolates SQL from service
- Service can be easily tested with mock repository

---

## Pattern 2: Complex Orchestration - API → Orchestrator → Services → Repositories → DB

**Used for**: Multi-step workflows that coordinate multiple services

**Example**: `generate_meal_plan()`

```
API: meal_plan_v2.py
    ↓
Orchestrator: meal_plan_orchestrator.py
    ↓ Coordinate 5 services:
    ↓
    ├─► ConstraintBuilderService (build optimization constraints)
    ├─► MealPlanOptimizer (run LP optimizer)
    ├─► GroceryService (calculate grocery list)
    ├─► MealPlanServiceV2 (save plan + logs)
    │   ↓
    │   ├─► MealPlanRepository (save MealPlan)
    │   └─► MealLogRepository (bulk create MealLogs)
    │       ↓
    │       Database
    └─► EventPublisher (publish events)
```

**Why this pattern?**
- **Multi-service coordination**: 5 different services must work together
- **Transaction management**: Need to ensure all-or-nothing (save plan + logs atomically)
- **Event-driven**: Publish events for future features (notifications, analytics)
- **Complexity justification**: This is a complex workflow with multiple steps

**When NOT to use orchestrator?**
- Single service operations (no coordination needed)
- Simple CRUD (no complex workflow)
- Direct data retrieval (no business logic)

---

## Pattern 3: Direct Service → DB (Old Code, Being Phased Out)

**Used for**: Legacy code that hasn't been migrated to repositories yet

**Example**: `current/with-status` endpoint (partially)

```
API: meal_plan_v2.py
    ↓
Service: Get active plan via repository ✅
    ↓
API: Direct MealLog query ⚠️ (not yet refactored)
    ↓ db.query(MealLog).filter(...)
    ↓
Database
```

**Why this pattern exists?**
- **Temporary**: We copy-pasted the exact logic to ensure zero behavior change
- **Pragmatic**: Extracting complex queries to repositories can introduce bugs
- **Safe approach**: Get it working first, refactor later

**Future**: Will extract to `MealLogRepository.get_by_plan_with_status()` in Phase 6

---

## Pattern 4: Service → Repository → Service (Your Question!)

**Used for**: When a service needs a repository for **data access**, then applies **business logic**

**Example**: `get_alternatives_for_meal()`

```
API: meal_plan_v2.py
    ↓
Service: meal_plan_service_v2.py
    ↓ get_alternatives_for_meal(recipe_id, user_id, count)
    ↓
    ├─► RecipeRepository.get_by_id(recipe_id)
    │   ↓ db.query(Recipe).filter_by(id)
    │   ↓ Returns: Recipe object
    │
    └─► RecipeRepository.get_alternatives(original_recipe, user_id, count)
        ↓ Business logic:
        ↓   - Query all recipes (SQL)
        ↓   - Filter by dietary type (SQL)
        ↓   - Filter by calorie range (Python)
        ↓   - Filter by meal time (Python)
        ↓   - Score by macro similarity (Python)
        ↓   - Score by goal alignment (Python)
        ↓   - Sort and return top N (Python)
        ↓
        Returns: List of scored alternatives
```

**Why this pattern?**
1. **Service coordinates**: "I need alternatives for this recipe"
2. **Repository gets data**: Fetch original recipe from DB
3. **Repository contains complex logic**: 140-line algorithm for finding alternatives
4. **Service delegates**: Service doesn't need to know the algorithm details

**Why is the algorithm in the repository?**

This is the **debatable part**. Let me explain both sides:

### Option A: Algorithm in Repository (Current Implementation)
```python
# RecipeRepository
def get_alternatives(self, original_recipe, user_id, count):
    """Complex 140-line algorithm"""
    # Query recipes
    # Filter by calories, meal time, dietary type
    # Score by macro similarity
    # Score by goal alignment
    # Sort and return top N
```

**Pros**:
- ✅ All recipe-related queries in one place
- ✅ Easy to find: "Where is alternatives logic?" → RecipeRepository
- ✅ Can be reused by other services

**Cons**:
- ❌ Mixes data access (SQL) with business logic (scoring)
- ❌ Repository is now "fat" (140 lines)
- ❌ Harder to test business logic separately from DB

### Option B: Algorithm in Service (Alternative)
```python
# RecipeRepository
def get_recipes_for_alternatives(self, recipe_id, dietary_type, calorie_range):
    """Simple query - just get candidate recipes"""
    # Query recipes with basic filters
    return recipes

# MealPlanServiceV2
def get_alternatives_for_meal(self, recipe_id, user_id, count):
    """Business logic - scoring and filtering"""
    original = self.recipe_repo.get_by_id(recipe_id)
    candidates = self.recipe_repo.get_recipes_for_alternatives(...)

    # Score by macro similarity (Python)
    # Score by goal alignment (Python)
    # Sort and return top N
    return scored_alternatives
```

**Pros**:
- ✅ Repository only does data access
- ✅ Service contains business logic
- ✅ Easier to test scoring logic

**Cons**:
- ❌ Service becomes larger
- ❌ Logic spread across service + repository

### Our Decision: Keep in Repository (For Now)

**Rationale**:
1. **Copy-paste principle**: Old code had this in `MealPlanService`
2. **Zero logic changes**: Safest to keep algorithm together
3. **Future refactoring**: Can extract to `AlternativesService` in Phase 6

**Future ideal architecture**:
```
API
 ↓
MealPlanServiceV2
 ↓
AlternativesService (new)
 ↓ Complex scoring algorithm
 ↓
RecipeRepository (simple queries only)
 ↓
Database
```

---

## Pattern 5: Multi-table Aggregation - Service → Direct DB

**Used for**: Complex read-only queries across multiple tables

**Example**: `GroceryService.calculate_for_plan()`

```
Service: grocery_service.py
    ↓ calculate_for_plan(meal_plan, user_id)
    ↓
    ├─► db.query(RecipeIngredient).filter(...)
    ├─► db.query(Item).filter(...)
    ├─► db.query(UserInventory).filter(...)
    └─► db.query(Recipe).filter(...)
        ↓ Aggregate quantities
        ↓ Subtract inventory
        ↓ Categorize items
        ↓
        Returns: Grocery list dict
```

**Why no repository?**

**Reasons**:
1. **No single "owner"**: Queries span 4 tables (RecipeIngredient, Item, UserInventory, Recipe)
2. **Read-only aggregation**: Not creating/updating entities
3. **Complex business logic**: Heavy transformations and calculations
4. **Cross-cutting concern**: Doesn't belong to any single repository

**Which repository would own this?**
- RecipeIngredientRepository? (But also queries Items and Inventory)
- GroceryListRepository? (But grocery list isn't a database entity)
- MealPlanRepository? (But doesn't directly query MealPlan)

**Answer**: **None!** This is a **service-level operation** that coordinates multiple data sources.

**Pattern rule**: When querying 3+ unrelated tables for aggregation → Service does direct DB access

---

## Architectural Decision Matrix

| Scenario | Pattern | Example |
|----------|---------|---------|
| **Simple CRUD** | API → Service → Repository → DB | `get_active_meal_plan()` |
| **Multi-service workflow** | API → Orchestrator → Services → Repos → DB | `generate_meal_plan()` |
| **Complex single-table query** | API → Service → Repository → DB | `swap_meal()` |
| **Multi-table aggregation** | API → Service → Direct DB | `calculate_grocery_list()` |
| **Complex algorithm with data** | API → Service → Repository (with logic) → DB | `get_alternatives()` ⚠️ |
| **Legacy not refactored** | API → Direct DB ❌ | `current/with-status` (MealLog query) |

---

## Key Architectural Principles

### 1. Repository Pattern - When to Use

**USE Repository when**:
✅ CRUD operations (Create, Read, Update, Delete)
✅ Single entity ownership (e.g., MealPlan, Recipe, MealLog)
✅ Queries that will be reused across services
✅ Need to mock data access in tests

**DON'T use Repository when**:
❌ Complex multi-table aggregations (3+ tables)
❌ Read-only analytical queries
❌ Heavy business logic transformations
❌ No clear entity "owner"

### 2. Service Pattern - When to Use

**USE Service when**:
✅ Business logic that spans multiple repositories
✅ Transformations and calculations
✅ Workflow coordination (but not too complex)
✅ Reusable business operations

**DON'T use Service when**:
❌ Just passing data through (repository is enough)
❌ Too complex (use orchestrator instead)

### 3. Orchestrator Pattern - When to Use

**USE Orchestrator when**:
✅ Coordinating 3+ services
✅ Multi-step transactions
✅ Event publishing
✅ Complex workflows with rollback logic

**DON'T use Orchestrator when**:
❌ Single service operation
❌ Simple CRUD
❌ No coordination needed

---

## Real-World Analogies

### Restaurant Kitchen Analogy

**Pattern 1: Simple CRUD**
- Customer: "Can I see the menu?"
- Waiter → Chef → Retrieves menu from storage
- **Direct path, no complexity**

**Pattern 2: Complex Orchestration**
- Customer: "I want the chef's special 7-course meal"
- Waiter → Head Chef (Orchestrator)
  - Calls Appetizer Chef
  - Calls Main Course Chef
  - Calls Pastry Chef
  - Coordinates timing
  - Ensures all courses ready
- **Multiple specialists, coordination required**

**Pattern 3: Multi-table Aggregation**
- Customer: "What ingredients do you have for this recipe?"
- Waiter → Chef checks:
  - Pantry (RecipeIngredient)
  - Fridge (Item)
  - Current inventory (UserInventory)
  - Recipe book (Recipe)
  - Aggregates and calculates what's needed
- **Cross-cutting inventory check, no single owner**

**Pattern 4: Service → Repository → Service**
- Customer: "I don't like tomatoes, what can I substitute?"
- Waiter → Chef → Recipe Book (Repository)
  - Get original recipe
  - Get similar recipes (complex algorithm)
  - Score by ingredient similarity
  - Score by dietary compatibility
  - Return top 5 alternatives
- **Data access + complex algorithm in one place**

---

## Summary: Why Different Patterns?

**The principle**: **Use the simplest pattern that meets the requirements**

1. **Simple query?** → Repository is enough
2. **Business logic + data?** → Service + Repository
3. **Multiple services?** → Orchestrator
4. **Multi-table aggregation?** → Service with direct DB
5. **Complex algorithm?** → Could be in Repository OR Service (pragmatic choice)

**Current State**:
- ✅ Most endpoints use clean patterns
- ⚠️ Some have direct DB queries (temporary, will refactor)
- ⚠️ Some have "fat repositories" with business logic (acceptable for now)

**Future State** (Phase 6):
- Extract complex algorithms to dedicated services
- Move all direct DB queries to repositories
- Add `AlternativesService`, `StatusEnrichmentService`, etc.

---

## Your Specific Question: Recipe Alternatives Flow

**Current Flow**:
```
API: meal_plan_v2.py:267-291
    ↓ get_meal_alternatives_v2()
    ↓
Service: meal_plan_service_v2.py:284-307
    ↓ get_alternatives_for_meal()
    ↓
    ├─► RecipeRepository.get_by_id(recipe_id)
    │   ↓ SQL: Get original recipe
    │   ↓ Returns: Recipe object
    │
    └─► RecipeRepository.get_alternatives(original, user_id, count)
        ↓ SQL: Query candidate recipes
        ↓ Python: Filter by calories, meal time
        ↓ Python: Score by macros
        ↓ Python: Score by goals
        ↓ Python: Sort and return top N
        ↓
        Returns: List[Dict] with scores
```

**Why Service → Repository → Service?**

It's not really "Service → Repository → Service". It's:

**Service → Repository (for data) → Repository (for algorithm) → Service (returns result)**

The service is just **orchestrating**:
1. "Get me the original recipe" → RecipeRepository.get_by_id()
2. "Get me alternatives for this recipe" → RecipeRepository.get_alternatives()
3. "Return the result to the API" → Service returns

The RecipeRepository does TWO things:
1. **Data access**: `get_by_id()` - Simple query
2. **Complex algorithm**: `get_alternatives()` - 140-line algorithm

**Is this ideal?** No, but it's **pragmatic**:
- ✅ Zero logic changes (copy-pasted from old service)
- ✅ All recipe logic in one place
- ✅ Works correctly
- ⚠️ Could be refactored to `AlternativesService` later

---

## Conclusion

**Your observation is correct**: Not all endpoints follow the full stack.

**Reason**: We use **pragmatic architecture** based on complexity:
- Simple operations → Minimal layers
- Complex workflows → More layers
- Multi-table queries → Service-level DB access
- Legacy code → Temporary direct DB access

**This is not a flaw**, it's **intentional design** to avoid over-engineering.

**Rule of thumb**: "Use the minimum architecture needed for the task"

---

**Next Steps**:
1. ✅ Fix grocery-list endpoint (DONE)
2. ✅ Understand layering patterns (THIS DOCUMENT)
3. Next: Testing and validation

**Questions?** Ask about any specific pattern or endpoint!
