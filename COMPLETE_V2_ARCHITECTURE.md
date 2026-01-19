# COMPLETE V2 BACKEND ARCHITECTURE - ALL MODULES

**Migration Status:** Clean Architecture Phases 1-8 Complete
**Date:** 2025-12-18
**Total Code:** ~15,000+ lines across all layers

---

## OVERVIEW - ARCHITECTURE LAYERS

```
┌─────────────────────────────────────────────────────┐
│  LAYER 1: API ENDPOINTS (FastAPI Routes)           │
│  - 8 v2 API modules                                 │
│  - 35+ total endpoints                              │
│  - Thin layer: validation + delegation              │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  LAYER 2: ORCHESTRATORS (Workflow Coordination)    │
│  - MealLoggingOrchestrator (641 lines)              │
│  - DashboardOrchestrator (373 lines)                │
│  - MealPlanOrchestrator (140 lines)                 │
│  - Coordinate multiple services                     │
│  - Transaction management                           │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  LAYER 3: SERVICES (Business Logic)                │
│  - 3 v2 services + 7 new services                   │
│  - IntelligentInventoryServiceV2 (882 lines)        │
│  - ConsumptionServiceV2 (631 lines)                 │
│  - MealPlanServiceV2 (382 lines)                    │
│  - MealTrackingService (619 lines)                  │
│  - ExternalMealService (504 lines)                  │
│  - InventoryManagementService (826 lines)           │
│  - GroceryService (201 lines)                       │
│  - ItemNormalizerRAG (771 lines)                    │
│  - Plus legacy services still in use                │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  LAYER 4: REPOSITORIES (Data Access)                │
│  - 10 repository implementations                    │
│  - InventoryRepository (1129 lines)                 │
│  - TrackingRepository (1226 lines)                  │
│  - ConsumptionAnalyticsRepository (1047 lines)      │
│  - MealLogRepository (365 lines)                    │
│  - RecipeRepository (299 lines)                     │
│  - ReceiptRepository (394 lines)                    │
│  - MealPlanRepository (210 lines)                   │
│  - OnboardingRepository (235 lines)                 │
│  - AuthRepository (146 lines)                       │
│  - ActivityRepository (106 lines)                   │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  LAYER 5: DATABASE MODELS (SQLAlchemy ORM)         │
│  - PostgreSQL with pgvector extension               │
└─────────────────────────────────────────────────────┘
```

---

## LAYER 1: API ENDPOINTS (8 modules, 35+ endpoints)

### **1. inventory_v2.py** (392 lines, 8 endpoints)
**Router:** `/inventory/v2`
**Dependencies:** IntelligentInventoryServiceV2, InventoryRepository

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/add-items` | POST | Add items from text input (AI normalization) |
| `/confirm-item` | POST | Confirm medium-confidence item |
| `/status` | GET | Get inventory status with AI insights |
| `/items` | GET | Get inventory items with filters |
| `/deduct-meal` | POST | Deduct ingredients for meal |
| `/makeable-recipes` | GET | Get recipes user can make |
| `/check-recipe/{id}` | GET | Check recipe availability |
| `/item/{id}` | DELETE | Remove inventory item |

---

### **2. tracking_v2.py** (732 lines, 10 endpoints)
**Router:** `/tracking/v2`
**Dependencies:** MealLoggingOrchestrator, ExternalMealService, InventoryManagementService, ConsumptionServiceV2

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/log-meal` | POST | Log meal consumption (planned meal) |
| `/skip-meal` | POST | Skip a planned meal |
| `/today` | GET | Today's consumption summary |
| `/history` | GET | Historical consumption data |
| `/inventory-status` | GET | Current inventory analytics |
| `/expiring-items` | GET | Items expiring soon |
| `/restock-list` | GET | Shopping recommendations |
| `/estimate-external-meal` | POST | LLM nutrition estimation |
| `/log-external-meal` | POST | Log external/restaurant meal |
| `/health` | GET | Health check |

**Pattern:** Uses MealLoggingOrchestrator to coordinate complex workflows

---

### **3. receipt_v2.py** (503 lines, 4 endpoints)
**Router:** `/receipt/v2`
**Dependencies:** ReceiptRepository, IntelligentInventoryService (v1), ReceiptItemEnricher

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/upload` | POST | Upload receipt image, OCR, normalize items |
| `/{receipt_id}/pending` | GET | Get pending items for confirmation |
| `/confirm-and-seed` | POST | Confirm items and add to inventory |
| `/history` | GET | Get receipt upload history |

**Note:** Still uses v1 IntelligentInventoryService, not migrated to v2 pattern fully

---

### **4. recipes_v2.py** (218 lines, 2 endpoints)
**Router:** `/recipes/v2`
**Dependencies:** RecipeRepository

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Get recipes with filters (goal, category, prep time) |
| `/{recipe_id}` | GET | Get recipe details |

**Pattern:** Directly uses RecipeRepository (simple CRUD)

---

### **5. auth_v2.py** (208 lines, 4 endpoints)
**Router:** `/auth/v2`
**Dependencies:** AuthRepository

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/register` | POST | Register new user |
| `/login` | POST | Login user (JWT tokens) |
| `/me` | GET | Get current user info |
| `/refresh` | POST | Refresh access token |

**Pattern:** Directly uses AuthRepository

---

### **6. onboarding_v2.py** (268 lines, 5 endpoints)
**Router:** `/onboarding/v2`
**Dependencies:** OnboardingRepository

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/basic-info` | POST | Save basic user info (age, height, weight) |
| `/goal-selection` | POST | Save fitness goal |
| `/path-selection` | POST | Save dietary path |
| `/preferences` | POST | Save food preferences |
| `/calculated-targets` | GET | Get calculated nutrition targets |

**Pattern:** Directly uses OnboardingRepository

---

### **7. dashboard_v2.py** (167 lines, 2 endpoints)
**Router:** `/dashboard/v2`
**Dependencies:** DashboardOrchestrator

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/summary` | GET | Dashboard summary (goals, consumption, inventory) |
| `/recent-activity` | GET | Recent user activity feed |

**Pattern:** Uses DashboardOrchestrator to aggregate data from multiple services

---

### **8. meal_plan_v2.py** (313 lines, 0 active endpoints)
**Router:** `/meal-plan/v2`
**Dependencies:** MealPlanOrchestrator, MealPlanServiceV2

**Note:** File exists but has no active endpoints defined (commented out or in development)

---

## LAYER 2: ORCHESTRATORS (3 orchestrators, 1154 lines)

### **MealLoggingOrchestrator** (641 lines)
**File:** `app/orchestrators/meal_logging_orchestrator.py`
**Purpose:** Coordinate complex meal logging workflows

**Constructor Dependencies (7):**
```python
def __init__(
    self,
    meal_tracking_service: MealTrackingService,
    external_meal_service: ExternalMealService,
    inventory_service: InventoryManagementService,
    consumption_service: ConsumptionServiceV2,
    notification_service: NotificationService,
    event_publisher: MealEventPublisher,
    db: Session
):
```

**Key Methods:**
- `log_planned_meal(user_id, meal_log_id, consumed_at)` - Log meal from plan
- `skip_meal(user_id, meal_log_id, reason)` - Skip planned meal
- `log_external_meal(user_id, meal_data)` - Log restaurant/external meal
- `get_today_summary(user_id, date)` - Aggregate today's consumption
- `get_history(user_id, start_date, end_date)` - Historical data
- `get_inventory_analytics(user_id)` - Inventory status
- `get_expiring_items(user_id, days)` - Items expiring soon
- `get_restock_list(user_id)` - Shopping recommendations

**Workflow Example (log_planned_meal):**
```
1. Get meal log from meal_tracking_service
2. Deduct ingredients from inventory (inventory_service)
3. Record consumption (consumption_service)
4. Calculate nutrition totals
5. Send notifications (notification_service)
6. Publish events (event_publisher)
7. Commit transaction OR rollback on error
```

---

### **DashboardOrchestrator** (373 lines)
**File:** `app/orchestrators/dashboard_orchestrator.py`
**Purpose:** Aggregate dashboard data from multiple sources

**Constructor Dependencies (5):**
```python
def __init__(
    self,
    consumption_service: ConsumptionServiceV2,
    inventory_service: InventoryManagementService,
    meal_plan_service: MealPlanServiceV2,
    activity_repo: ActivityRepository,
    db: Session
):
```

**Key Methods:**
- `get_dashboard_summary(user_id, date)` - Complete dashboard
- `get_recent_activity(user_id, limit)` - Activity feed

**Aggregates:**
- Daily nutrition goals vs actual
- Calorie/macro progress
- Inventory status (items, weight, expiring)
- Upcoming meals from plan
- Recent activity (logs, receipts, plans)

---

### **MealPlanOrchestrator** (140 lines)
**File:** `app/orchestrators/meal_plan_orchestrator.py`
**Purpose:** Coordinate meal planning workflows

**Constructor Dependencies (3):**
```python
def __init__(
    self,
    meal_plan_service: MealPlanServiceV2,
    inventory_service: InventoryManagementService,
    db: Session
):
```

**Key Methods:**
- `generate_meal_plan(user_id, preferences)` - Generate new plan
- `adjust_plan(user_id, plan_id, changes)` - Modify existing plan

---

## LAYER 3: SERVICES (10 core services, ~5800 lines)

### **V2 Services (Clean Architecture)**

#### **1. IntelligentInventoryServiceV2** (882 lines)
**File:** `app/services/intelligent_inventory_service_v2.py`
**Dependencies:** IInventoryRepository, RAGItemNormalizer, Session

**Responsibilities:**
- Inventory CRUD with smart features
- AI-powered item normalization
- Recipe matching and availability
- Expiry date management (auto-assign by category)
- Batch management
- Receipt processing
- Status reports with AI recommendations

**Public Methods (9):**
- `add_item(user_id, item_id, quantity_grams, expiry_date, source)`
- `deduct_item(user_id, item_id, quantity_grams)`
- `add_items_from_text(user_id, text_input)`
- `deduct_for_meal(user_id, recipe_id, portion_multiplier)`
- `get_inventory_status(user_id)`
- `get_user_inventory(user_id, category, low_stock_only, expiring_soon)`
- `check_recipe_availability(user_id, recipe_id)`
- `get_makeable_recipes(user_id, limit, partial_threshold)`
- `process_receipt_items(user_id, receipt_items, auto_add_threshold)`

---

#### **2. ConsumptionServiceV2** (631 lines)
**File:** `app/services/consumption_service_v2.py`
**Dependencies:** ConsumptionAnalyticsRepository, MealLogRepository

**Responsibilities:**
- Track daily consumption
- Calculate nutrition totals
- Track goals progress
- Historical analytics
- Macro/micro nutrient tracking

**Public Methods:**
- `record_consumption(user_id, meal_log_id, consumed_at, nutrition)`
- `get_daily_summary(user_id, date)`
- `get_consumption_history(user_id, start_date, end_date)`
- `calculate_daily_totals(user_id, date)`
- `get_goals_progress(user_id, date)`

---

#### **3. MealPlanServiceV2** (382 lines)
**File:** `app/services/meal_plan_service_v2.py`
**Dependencies:** MealPlanRepository

**Responsibilities:**
- Generate meal plans
- Adjust plans
- Track plan adherence
- Nutrition target matching

---

### **New Services (Clean Architecture)**

#### **4. MealTrackingService** (619 lines)
**File:** `app/services/meal_tracking_service.py`
**Dependencies:** MealLogRepository, TrackingRepository

**Responsibilities:**
- Create meal logs
- Update meal status (pending → consumed → skipped)
- Track meal timing
- Link meals to recipes or external meals

**Public Methods:**
- `create_meal_log(user_id, meal_type, recipe_id, planned_for)`
- `get_meal_log(meal_log_id)`
- `update_meal_status(meal_log_id, status, consumed_at)`
- `skip_meal(meal_log_id, reason)`
- `get_user_meals(user_id, date)`

---

#### **5. ExternalMealService** (504 lines)
**File:** `app/services/external_meal_service.py`
**Dependencies:** MealLogRepository, LLMNutritionEstimator

**Responsibilities:**
- Estimate nutrition for restaurant/external meals
- Use LLM to guess nutrition when data unavailable
- Store external meal data
- Link to meal logs

**Public Methods:**
- `estimate_nutrition(meal_description, serving_size)`
- `log_external_meal(user_id, meal_data)`
- `get_external_meal(external_meal_id)`

---

#### **6. InventoryManagementService** (826 lines)
**File:** `app/services/inventory_management_service.py`
**Dependencies:** InventoryRepository, ItemNormalizer

**Responsibilities:**
- Inventory CRUD operations
- Quantity tracking
- Expiry management
- Deduction for meals
- Analytics

**Public Methods:**
- `add_item_to_inventory(user_id, item_id, quantity_grams)`
- `deduct_item_from_inventory(user_id, item_id, quantity_grams)`
- `get_inventory_summary(user_id)`
- `get_expiring_items(user_id, days_threshold)`
- `deduct_recipe_ingredients(user_id, recipe_id, portion_multiplier)`

---

#### **7. GroceryService** (201 lines)
**File:** `app/services/grocery_service.py`
**Dependencies:** InventoryRepository, MealPlanRepository

**Responsibilities:**
- Generate shopping lists
- Calculate missing ingredients for meal plans
- Track restock needs
- Suggest quantities

**Public Methods:**
- `generate_grocery_list(user_id, meal_plan_id)`
- `get_restock_recommendations(user_id)`

---

#### **8. RAGItemNormalizer** (771 lines)
**File:** `app/services/item_normalizer_rag.py`
**Dependencies:** List[Item], Session, OpenAI API key

**Responsibilities:**
- Match user input to database items
- Vector similarity search (pgvector + OpenAI embeddings)
- LLM verification for ambiguous matches
- Unit conversion (intelligent + fallback)
- Structure extraction from text

**Matching Pipeline:**
1. Exact match (canonical_name)
2. Alias match (item.aliases)
3. Vector search (cosine similarity >= 0.90 → auto-accept)
4. LLM verification (0.75-0.90 → verify with context)
5. Return alternatives (< 0.75)

**Unit Conversion:**
- Standard: kg→1000g, lb→453.6g, oz→28.35g
- Intelligent: "1 egg"→50g (item-specific via LLM)

---

## LAYER 4: REPOSITORIES (10 repositories, ~5100 lines)

### **1. InventoryRepository** (1129 lines)
**Interface:** IInventoryRepository
**Model:** UserInventory

**Method Categories (38 methods):**
- Basic CRUD (7): get_all, get_by_id, create, update, delete, get_all_for_user, get_by_item_id
- Quantity ops (4): add_quantity, deduct_quantity, set_quantity, bulk_update_quantities
- Recipe ops (2): deduct_recipe_ingredients, check_recipe_ingredients_availability
- Expiry queries (4): get_expiring_items, get_expired_items, get_items_without_expiry
- Stock queries (4): get_low_stock_items, get_out_of_stock_items, get_well_stocked_items
- Categorization (2): get_inventory_by_category, get_inventory_by_source
- Analytics (5): calculate_total_inventory_weight, get_inventory_status_summary, etc.
- Bulk ops (3): bulk_create_inventory, bulk_delete_inventory, reset_user_inventory

---

### **2. TrackingRepository** (1226 lines)
**Interface:** ITrackingRepository
**Models:** MealLog, UserInventory

**Responsibilities:**
- Meal log CRUD
- Inventory tracking operations
- Consumption history
- Meal plan adherence tracking

---

### **3. ConsumptionAnalyticsRepository** (1047 lines)
**Interface:** IConsumptionAnalyticsRepository
**Models:** DailyConsumption, MealLog

**Responsibilities:**
- Daily nutrition aggregation
- Historical analytics
- Goal progress tracking
- Macro/micro nutrient summaries

---

### **4. MealLogRepository** (365 lines)
**Interface:** IMealLogRepository
**Model:** MealLog

**Responsibilities:**
- Meal log CRUD
- Status management (pending/consumed/skipped)
- Date-based queries
- Link to recipes or external meals

---

### **5. RecipeRepository** (299 lines)
**Interface:** IRecipeRepository
**Model:** Recipe, RecipeIngredient

**Responsibilities:**
- Recipe CRUD
- Recipe search (by goal, category, prep time)
- Ingredient management
- Nutrition calculation

---

### **6. ReceiptRepository** (394 lines)
**Interface:** IReceiptRepository
**Model:** Receipt, PendingReceiptItem

**Responsibilities:**
- Receipt upload tracking
- Pending items management
- Confirmation workflow
- History

---

### **7. MealPlanRepository** (210 lines)
**Interface:** IMealPlanRepository
**Model:** MealPlan, MealPlanEntry

**Responsibilities:**
- Meal plan CRUD
- Plan adherence tracking
- Weekly/monthly plans

---

### **8-10. Other Repositories:**
- **OnboardingRepository** (235 lines) - User profiles, preferences
- **AuthRepository** (146 lines) - User authentication, tokens
- **ActivityRepository** (106 lines) - Activity feed, recent actions

---

## DEPENDENCY INJECTION (dependencies.py)

**Key DI Functions:**

```python
# Repositories
def get_inventory_repository(db: Session) -> IInventoryRepository
def get_tracking_repository(db: Session) -> ITrackingRepository
def get_consumption_analytics_repository(db: Session) -> IConsumptionAnalyticsRepository
def get_meal_log_repository(db: Session) -> IMealLogRepository
def get_recipe_repository(db: Session) -> IRecipeRepository
# ... etc for all repositories

# Services
def get_intelligent_inventory_service_v2(
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    db: Session = Depends(get_db)
) -> IntelligentInventoryServiceV2:
    # Load ALL items for normalizer
    items_list = db.query(Item).all()
    normalizer = RAGItemNormalizer(items_list, db, settings.openai_api_key)
    return IntelligentInventoryServiceV2(inventory_repo, normalizer, db)

def get_consumption_service_v2(...) -> ConsumptionServiceV2
def get_meal_tracking_service(...) -> MealTrackingService
def get_external_meal_service(...) -> ExternalMealService
def get_inventory_management_service(...) -> InventoryManagementService
# ... etc

# Orchestrators
def get_tracking_orchestrator(
    meal_tracking_service = Depends(get_meal_tracking_service),
    external_meal_service = Depends(get_external_meal_service),
    inventory_service = Depends(get_inventory_management_service),
    consumption_service = Depends(get_consumption_service_v2),
    notification_service = Depends(get_notification_service),
    event_publisher = Depends(get_meal_event_publisher),
    db: Session = Depends(get_db)
) -> MealLoggingOrchestrator:
    return MealLoggingOrchestrator(...)

def get_dashboard_orchestrator(...) -> DashboardOrchestrator
def get_meal_plan_orchestrator(...) -> MealPlanOrchestrator
```

---

## CRITICAL ARCHITECTURAL ISSUES

### **Issue 1: Incomplete Repository Adoption**
Many services still use `db.query()` directly instead of repositories:
- `IntelligentInventoryServiceV2` uses `db.query(Item)`, `db.query(Recipe)`
- `ConsumptionServiceV2` may have direct DB access
- Services have both repository AND db session injected

**Impact:** Repository pattern not fully realized

---

### **Issue 2: Service Responsibilities Too Broad**
- `IntelligentInventoryServiceV2` does: inventory + recipes + AI + expiry + batch management
- Should be split into focused services

---

### **Issue 3: Normalizer Re-initialization**
```python
def get_intelligent_inventory_service_v2(...):
    items_list = db.query(Item).all()  # 400+ items loaded EVERY request
    normalizer = RAGItemNormalizer(items_list, ...)  # New instance EVERY request
```

**Impact:** Performance penalty, no caching

---

### **Issue 4: Duplicate Service Implementations**
- `InventoryManagementService` (826 lines) vs `IntelligentInventoryServiceV2` (882 lines)
- Both do similar things, used in different places
- No clear distinction

---

### **Issue 5: Orchestrator vs Service Boundary Unclear**
- `MealLoggingOrchestrator` has business logic (calculating nutrition, rollback logic)
- Services also have workflow logic
- Unclear when to use orchestrator vs service directly

---

### **Issue 6: Quantity Conversion Bug**
In `item_normalizer_rag.py:699-714`:
```python
if result.item:
    grams = await self.convert_to_grams_intelligent(...)
    result.quantity_grams = grams
else:
    # BUG: No conversion when item not matched
    pass  # quantity_grams stays None
```

---

### **Issue 7: Confidence Logic Duplication**
Confidence thresholds (0.85, 0.6, 0.4) checked in multiple places:
- `IntelligentInventoryServiceV2.add_items_from_text()`
- `IntelligentInventoryServiceV2.process_receipt_items()`
- Should be in normalizer

---

## WHAT WORKS WELL

1. ✅ Orchestrator pattern for complex workflows
2. ✅ Comprehensive repository methods (38 in InventoryRepository)
3. ✅ Dependency injection throughout
4. ✅ Interface definitions for repositories
5. ✅ Async/await throughout API and services
6. ✅ Event publishing for real-time updates
7. ✅ Transaction management in orchestrators
8. ✅ RAG pipeline (exact → alias → vector → LLM)
9. ✅ SQL optimization (eager loading, pre-filtering)
10. ✅ Separation of API, Service, Repository layers

---

## CODE STATISTICS

**Total Lines by Layer:**
- API Layer (8 files): ~2,800 lines
- Orchestrators (3 files): ~1,150 lines
- Services (10 core): ~5,800 lines
- Repositories (10 files): ~5,100 lines
- Interfaces (10 files): ~1,000 lines
- **Total V2 Architecture: ~15,850 lines**

**Endpoint Count:**
- Inventory: 8
- Tracking: 10
- Receipt: 4
- Recipes: 2
- Auth: 4
- Onboarding: 5
- Dashboard: 2
- Meal Plan: 0 (in development)
- **Total: 35 active endpoints**

---

## FILES REFERENCE

**API Endpoints:**
- `backend/app/api/inventory_v2.py` (392 lines)
- `backend/app/api/tracking_v2.py` (732 lines)
- `backend/app/api/receipt_v2.py` (503 lines)
- `backend/app/api/recipes_v2.py` (218 lines)
- `backend/app/api/auth_v2.py` (208 lines)
- `backend/app/api/onboarding_v2.py` (268 lines)
- `backend/app/api/dashboard_v2.py` (167 lines)
- `backend/app/api/meal_plan_v2.py` (313 lines)

**Orchestrators:**
- `backend/app/orchestrators/meal_logging_orchestrator.py` (641 lines)
- `backend/app/orchestrators/dashboard_orchestrator.py` (373 lines)
- `backend/app/orchestrators/meal_plan_orchestrator.py` (140 lines)

**Services:**
- `backend/app/services/intelligent_inventory_service_v2.py` (882 lines)
- `backend/app/services/consumption_service_v2.py` (631 lines)
- `backend/app/services/meal_plan_service_v2.py` (382 lines)
- `backend/app/services/meal_tracking_service.py` (619 lines)
- `backend/app/services/external_meal_service.py` (504 lines)
- `backend/app/services/inventory_management_service.py` (826 lines)
- `backend/app/services/grocery_service.py` (201 lines)
- `backend/app/services/item_normalizer_rag.py` (771 lines)

**Repositories:**
- `backend/app/repositories/inventory_repository.py` (1129 lines)
- `backend/app/repositories/tracking_repository.py` (1226 lines)
- `backend/app/repositories/consumption_analytics_repository.py` (1047 lines)
- `backend/app/repositories/meal_log_repository.py` (365 lines)
- `backend/app/repositories/recipe_repository.py` (299 lines)
- `backend/app/repositories/receipt_repository.py` (394 lines)
- `backend/app/repositories/meal_plan_repository.py` (210 lines)
- `backend/app/repositories/onboarding_repository.py` (235 lines)
- `backend/app/repositories/auth_repository.py` (146 lines)
- `backend/app/repositories/activity_repository.py` (106 lines)

---

## END OF COMPLETE V2 ARCHITECTURE MAP

This document covers ALL v2 clean architecture components across the entire backend.
All line counts, endpoint lists, and dependency relationships verified from actual code.
