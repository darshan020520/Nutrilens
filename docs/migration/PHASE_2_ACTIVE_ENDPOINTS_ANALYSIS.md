# Phase 2: Tracking Endpoints - Active Usage Analysis

**Date**: 2025-11-25
**Analyzer**: Claude Code Migration Assistant
**Purpose**: Identify actively used tracking endpoints for Phase 2 migration
**Approach**: Data-driven frontend usage analysis (same as Phase 1)

---

## 📊 Executive Summary

### Total Tracking Endpoints: 12

**Backend File**: `backend/app/api/tracking.py`

**Breakdown**:
- ✅ **Active (Used by Frontend)**: **9 endpoints** (75%)
- ❌ **Inactive (Not Used)**: **3 endpoints** (25%)

**Recommendation**: Migrate only the 9 active endpoints (following Phase 1 data-driven approach)

**Time Savings**: ~25% effort reduction by skipping unused endpoints

---

## 📋 Complete Endpoint Inventory

### POST Endpoints (Actions) - 6 Total

| # | Endpoint | Line | Status | Frontend Usage |
|---|----------|------|--------|----------------|
| 1 | POST /tracking/log-meal | 120 | ✅ **ACTIVE** | `TodayView.tsx:79` |
| 2 | POST /tracking/skip-meal | 208 | ✅ **ACTIVE** | `TodayView.tsx:106` |
| 3 | POST /tracking/update-inventory | 290 | ❌ **INACTIVE** | Not found in frontend |
| 4 | POST /tracking/manual-entry | 357 | ❌ **INACTIVE** | Not found in frontend |
| 5 | POST /tracking/estimate-external-meal | 854 | ✅ **ACTIVE** | `ExternalMealDialog.tsx:76` |
| 6 | POST /tracking/log-external-meal | 907 | ✅ **ACTIVE** | `ExternalMealDialog.tsx:102` |

### GET Endpoints (Queries) - 6 Total

| # | Endpoint | Line | Status | Frontend Usage |
|---|----------|------|--------|----------------|
| 7 | GET /tracking/today | 474 | ✅ **ACTIVE** | `TodayView.tsx:71` |
| 8 | GET /tracking/history | 533 | ✅ **ACTIVE** | `MealHistory.tsx:56` |
| 9 | GET /tracking/patterns | 612 | ❌ **INACTIVE** | Not found in frontend |
| 10 | GET /tracking/inventory-status | 683 | ✅ **ACTIVE** | `useTracking.ts:44` |
| 11 | GET /tracking/expiring-items | 739 | ✅ **ACTIVE** | `useTracking.ts:19` |
| 12 | GET /tracking/restock-list | 800 | ✅ **ACTIVE** | `useTracking.ts:32` |

---

## ✅ Active Endpoints (9) - TO BE MIGRATED

### Group 1: Core Meal Tracking (3 endpoints)

#### 1. POST /tracking/log-meal
**Line**: 120
**Frontend**: `frontend/src/app/dashboard/meals/components/TodayView.tsx:79`
**Usage Context**:
```typescript
const response = await api.post("/tracking/log-meal", {
  meal_log_id: mealLog.id,
  portion_multiplier: 1.0,
  notes: ""
});
```

**Behavior**:
1. Marks meal as consumed
2. Auto-deducts ingredients from inventory
3. Updates daily consumption totals
4. Checks for achievements
5. Broadcasts WebSocket updates
6. Queues notifications

**Dependencies**:
- `TrackingAgent` (agent)
- `MealLog` model
- WebSocket broadcasting (if implemented)
- Achievement system (if implemented)

**Complexity**: 🟡 **MEDIUM** - Agent-based, multiple side effects

---

#### 2. POST /tracking/skip-meal
**Line**: 208
**Frontend**: `frontend/src/app/dashboard/meals/components/TodayView.tsx:106`
**Usage Context**:
```typescript
const response = await api.post("/tracking/skip-meal", {
  meal_log_id: mealLog.id,
  reason: skipReason
});
```

**Behavior**:
1. Marks meal as skipped with reason
2. Updates adherence statistics
3. Analyzes skip patterns
4. Provides adherence recommendations

**Dependencies**:
- `TrackingAgent` (agent)
- `MealLog` model

**Complexity**: 🟢 **LOW** - Simple agent call, minimal side effects

---

#### 3. GET /tracking/today
**Line**: 474
**Frontend**: `frontend/src/app/dashboard/meals/components/TodayView.tsx:71`
**Usage Context**:
```typescript
queryFn: async () => (await api.get("/tracking/today")).data,
```

**Behavior**:
1. Returns today's consumption summary
2. Meals planned, consumed, skipped
3. Total calories and macros
4. Remaining targets
5. Compliance rate
6. Detailed meal breakdown

**Dependencies**:
- `ConsumptionService` (service)
- `MealLog` model

**Complexity**: 🟢 **LOW** - Read-only service call

---

### Group 2: External Meal Logging (2 endpoints)

#### 4. POST /tracking/estimate-external-meal
**Line**: 854
**Frontend**: `frontend/src/app/dashboard/meals/components/ExternalMealDialog.tsx:76`
**Usage Context**:
```typescript
const response = await api.post("/tracking/estimate-external-meal", {
  dish_name: dishName,
  portion_size: portionSize,
  restaurant_name: restaurantName,
  cuisine_type: cuisineType
});
```

**Behavior**:
1. Takes dish description and portion size
2. Uses OpenAI LLM to estimate macronutrients
3. Returns estimate with confidence score
4. **Does NOT create database entries** (estimate only)

**Dependencies**:
- `estimate_nutrition_with_llm` (LLM service)
- OpenAI API

**Complexity**: 🟢 **LOW** - Stateless LLM call, no DB writes

---

#### 5. POST /tracking/log-external-meal
**Line**: 907
**Frontend**: `frontend/src/app/dashboard/meals/components/ExternalMealDialog.tsx:102`
**Usage Context**:
```typescript
const response = await api.post("/tracking/log-external-meal", {
  dish_name: dishName,
  portion_size: portionSize,
  restaurant_name: restaurantName,
  calories: estimatedNutrition.calories,
  protein_g: estimatedNutrition.protein_g,
  // ... other macros
  meal_log_id_to_replace: selectedMealLogId,
  meal_type: mealType,
  notes: notes
});
```

**Behavior**:
1. Can replace a planned meal OR add as new meal
2. Stores nutrition in `external_meal` JSON field
3. Updates daily consumption totals
4. Returns remaining meals that could be adjusted
5. Provides insights and recommendations

**Dependencies**:
- `ConsumptionService` (service)
- `MealLog` model
- `Recipe` model (for remaining meals)

**Complexity**: 🟡 **MEDIUM** - Complex logic with two paths (replace vs add new)

---

### Group 3: Consumption History & Analytics (1 endpoint)

#### 6. GET /tracking/history
**Line**: 533
**Frontend**: `frontend/src/app/dashboard/meals/components/MealHistory.tsx:56`
**Usage Context**:
```typescript
const response = await api.get("/tracking/history", {
  params: { days: selectedDays }
});
```

**Behavior**:
1. Get historical consumption data (1-90 days)
2. Meal-by-meal breakdown
3. Statistics (total meals, logged, skipped, adherence)
4. Trends analysis

**Dependencies**:
- `ConsumptionService` (service)
- `MealLog` model

**Complexity**: 🟡 **MEDIUM** - Complex data aggregation, multi-day queries

---

### Group 4: Inventory Management (3 endpoints)

#### 7. GET /tracking/inventory-status
**Line**: 683
**Frontend**: `frontend/src/app/dashboard/inventory/hooks/useTracking.ts:44`
**Usage Context**:
```typescript
const response = await api.get("/tracking/inventory-status");
```

**Behavior**:
1. Total items count
2. Items by category
3. Overall stock level percentage
4. Low stock and critical items
5. Expiring items
6. Overstocked items
7. Intelligent recommendations

**Dependencies**:
- `TrackingAgent` (agent)
- `UserInventory` model

**Complexity**: 🟡 **MEDIUM** - Complex inventory analytics

---

#### 8. GET /tracking/expiring-items
**Line**: 739
**Frontend**: `frontend/src/app/dashboard/inventory/hooks/useTracking.ts:19`
**Usage Context**:
```typescript
const response = await api.get(`/tracking/expiring-items?days=${days}`);
```

**Behavior**:
1. Items expiring within specified days (1-14)
2. Filter modes: date_only, consumption_only, both
3. Expiry urgency levels
4. Recipe suggestions to use them
5. Action recommendations

**Dependencies**:
- `TrackingAgent` (agent)
- `UserInventory` model
- Recipe matching logic

**Complexity**: 🟡 **MEDIUM** - Smart filtering with consumption pattern analysis

---

#### 9. GET /tracking/restock-list
**Line**: 800
**Frontend**: `frontend/src/app/dashboard/inventory/hooks/useTracking.ts:32`
**Usage Context**:
```typescript
const response = await api.get("/tracking/restock-list");
```

**Behavior**:
1. Items that are low or out of stock
2. Priority levels (urgent, soon, routine)
3. Usage frequency data
4. Days until depletion estimates
5. Shopping strategy recommendations

**Dependencies**:
- `TrackingAgent` (agent)
- `UserInventory` model

**Complexity**: 🟡 **MEDIUM** - Complex predictive analytics

---

## ❌ Inactive Endpoints (3) - TO BE SKIPPED

### 1. POST /tracking/update-inventory
**Line**: 290
**Reason**: Not found in frontend code
**Purpose**: Bulk update inventory items (add, deduct, or set quantities)

**Analysis**:
- Searched `frontend/` for: `/tracking/update-inventory`, `update-inventory`, `updateInventory`
- **No matches found**
- Likely replaced by receipt scanning flow or never implemented in UI
- Uses `TrackingAgent.update_inventory()`

**Decision**: ⏸️ **DEFER** - Skip for now, can migrate later if needed

---

### 2. POST /tracking/manual-entry
**Line**: 357
**Reason**: Not found in frontend code
**Purpose**: Log a manually entered food item (not from meal plan)

**Analysis**:
- Searched `frontend/` for: `/tracking/manual-entry`, `manual-entry`, `manualEntry`
- **No matches found**
- Overlaps with `/tracking/log-external-meal` functionality
- Uses `IntelligentItemNormalizer` and `ConsumptionService`

**Decision**: ⏸️ **DEFER** - Skip for now, external meal logging covers this use case

---

### 3. GET /tracking/patterns
**Line**: 612
**Reason**: Not found in frontend code
**Purpose**: Get consumption pattern analysis and insights

**Analysis**:
- Searched `frontend/` for: `/tracking/patterns`, `patterns`, `consumption-patterns`
- **No matches found**
- Advanced analytics feature likely not exposed in current UI
- Uses `ConsumptionService.generate_consumption_analytics()`

**Decision**: ⏸️ **DEFER** - Advanced analytics, can add later if UI supports it

---

## 🏗️ Architecture Analysis

### Current Dependencies

**Services Used**:
1. `TrackingAgent` (agent) - Used by 5 endpoints
2. `ConsumptionService` (service) - Used by 3 endpoints
3. `estimate_nutrition_with_llm` (LLM service) - Used by 1 endpoint
4. `IntelligentItemNormalizer` (RAG service) - Used by 1 endpoint (inactive)

**Models Used**:
1. `MealLog` - Primary model for all meal tracking
2. `UserInventory` - Used by inventory endpoints
3. `Recipe` - Used for meal details and alternatives
4. `User` - Authentication

### Migration Strategy

**Option 1: Migrate TrackingAgent Directly** (RECOMMENDED)
- Keep `TrackingAgent` as is (it's already well-structured)
- Create thin orchestrator layer only if needed
- Create repositories for data access
- Extract services from agent methods

**Pros**:
- ✅ Faster migration (agent already encapsulates logic)
- ✅ Less code duplication
- ✅ Maintains working code

**Cons**:
- ⚠️ Agent pattern doesn't follow repository pattern strictly
- ⚠️ May need refactoring later for consistency

**Option 2: Full Refactor to Repository Pattern**
- Extract all data access to repositories
- Extract business logic to services
- Create orchestrators for complex flows
- API calls services/orchestrators directly

**Pros**:
- ✅ Full architectural consistency
- ✅ Better testability
- ✅ Clear separation of concerns

**Cons**:
- ⚠️ More work (2-3x effort)
- ⚠️ Higher risk (more code changes)
- ⚠️ May introduce bugs during refactoring

---

## 🎯 Recommended Migration Approach

### Strategy: **Hybrid Approach** (Best of Both Worlds)

**Phase 2A: Quick Migration** (1 week)
1. Create `TrackingRepository` for data access
2. Keep `TrackingAgent` but make it use repository
3. Keep `ConsumptionService` as is
4. Create `tracking_v2.py` API file
5. Copy-paste logic with repository calls

**Phase 2B: Gradual Refactoring** (Optional, future)
1. Extract service methods from `TrackingAgent`
2. Create proper orchestrators for complex flows
3. Migrate remaining inactive endpoints if needed

**Benefits**:
- ✅ Fast delivery (1 week for 9 endpoints)
- ✅ Lower risk (minimal changes)
- ✅ Incremental improvement
- ✅ Can refactor later without blocking frontend

---

## 📦 Required Components for Phase 2

### Repositories to Create

#### 1. TrackingRepository
**Purpose**: Data access for meal logs and tracking

**Methods**:
```python
class TrackingRepository(IRepository[MealLog]):
    # Core CRUD
    def get_meal_log_by_id(user_id: int, meal_log_id: int) -> MealLog
    def get_todays_meal_logs(user_id: int) -> List[MealLog]
    def get_meal_logs_by_date_range(user_id: int, start: date, end: date) -> List[MealLog]

    # Meal logging
    def mark_meal_consumed(meal_log_id: int, consumed_at: datetime, macros: dict) -> MealLog
    def mark_meal_skipped(meal_log_id: int, reason: str) -> MealLog
    def create_external_meal_log(user_id: int, meal_data: dict) -> MealLog

    # Analytics queries
    def get_consumption_stats(user_id: int, days: int) -> dict
    def get_adherence_rate(user_id: int, days: int) -> float
```

#### 2. InventoryRepository
**Purpose**: Data access for user inventory

**Methods**:
```python
class InventoryRepository(IRepository[UserInventory]):
    # Core CRUD
    def get_user_inventory(user_id: int) -> List[UserInventory]
    def get_inventory_item(user_id: int, item_id: int) -> UserInventory

    # Inventory operations
    def bulk_update_inventory(user_id: int, changes: List[dict]) -> List[UserInventory]
    def deduct_recipe_ingredients(user_id: int, recipe_id: int, multiplier: float) -> List[dict]

    # Analytics queries
    def get_expiring_items(user_id: int, days: int) -> List[UserInventory]
    def get_low_stock_items(user_id: int) -> List[UserInventory]
    def get_inventory_status(user_id: int) -> dict
```

### Services to Create/Update

#### 1. TrackingService (New)
**Purpose**: Business logic for meal tracking

**Methods**:
```python
class TrackingService:
    def log_meal_consumption(meal_log_id: int, portion: float) -> dict
    def skip_meal(meal_log_id: int, reason: str) -> dict
    def get_today_summary(user_id: int) -> dict
    def get_consumption_history(user_id: int, days: int) -> dict
    def log_external_meal(user_id: int, meal_data: dict) -> dict
```

#### 2. InventoryService (New)
**Purpose**: Business logic for inventory management

**Methods**:
```python
class InventoryService:
    def get_inventory_status(user_id: int) -> dict
    def get_expiring_items(user_id: int, days: int, filter_mode: str) -> dict
    def generate_restock_list(user_id: int) -> dict
    def deduct_ingredients_for_meal(user_id: int, recipe_id: int, portion: float) -> dict
```

#### 3. ConsumptionService (Keep as is)
**Already exists**: `backend/app/services/consumption_services.py`

**Already has methods**:
- `get_today_summary()`
- `get_consumption_history()`
- `generate_consumption_analytics()`

**Decision**: ✅ **Keep and reuse** (no migration needed)

### Orchestrators to Create

#### 1. MealLoggingOrchestrator (Optional)
**Purpose**: Coordinate meal logging with inventory deductions

**When to Use**: If we want complex workflows with events

**Methods**:
```python
class MealLoggingOrchestrator(BaseOrchestrator):
    def log_meal_with_inventory_update(meal_log_id: int, portion: float) -> dict:
        # 1. Mark meal as consumed (TrackingService)
        # 2. Deduct ingredients (InventoryService)
        # 3. Update daily totals (ConsumptionService)
        # 4. Publish MealLoggedEvent
        # 5. Check achievements (if implemented)
```

**Decision**: ⏸️ **OPTIONAL** - Start without orchestrator, add if complexity warrants it

---

## 📊 Migration Scope Summary

### Work Breakdown

| Component Type | To Create | Estimated LOC | Complexity |
|----------------|-----------|---------------|------------|
| **Repositories** | 2 (Tracking, Inventory) | ~600 lines | 🟡 Medium |
| **Services** | 2 (Tracking, Inventory) | ~800 lines | 🟡 Medium |
| **Orchestrators** | 0 (optional later) | 0 lines | - |
| **API Endpoints** | 1 file (9 endpoints) | ~800 lines | 🟢 Low (copy-paste) |
| **Total** | 5 files | ~2200 lines | 🟡 Medium |

### Time Estimate

**Detailed Breakdown**:
1. **Repository Creation** (2 files)
   - TrackingRepository: 1.5 days
   - InventoryRepository: 1.5 days
   - Subtotal: 3 days

2. **Service Creation** (2 files)
   - TrackingService: 1 day
   - InventoryService: 1 day
   - Subtotal: 2 days

3. **API Migration** (1 file)
   - Create `tracking_v2.py`: 1 day
   - Wire up dependencies: 0.5 days
   - Subtotal: 1.5 days

4. **Testing & Verification**
   - Syntax validation: 0.5 days
   - Behavior comparison: 1 day
   - Subtotal: 1.5 days

**Total Estimate**: **8 days** (1.6 weeks)

**With Buffer (20%)**: **10 days** (2 weeks)

---

## 🚀 Recommended Execution Plan

### Week 1: Repository & Service Layer

**Day 1-2**: TrackingRepository
- Create interface and implementation
- All meal log data access methods
- Analytics query methods

**Day 3-4**: InventoryRepository
- Create interface and implementation
- All inventory data access methods
- Expiry and restock query methods

**Day 5**: Services Layer
- TrackingService (wrap agent methods)
- InventoryService (wrap agent methods)
- Update dependency injection

### Week 2: API Migration & Testing

**Day 6-7**: API Endpoints
- Create `tracking_v2.py`
- Copy-paste all 9 active endpoints
- Replace agent calls with service calls
- Add source line comments

**Day 8-9**: Testing & Verification
- Syntax validation (py_compile)
- Behavior comparison (v1 vs v2)
- Create journey comparison doc

**Day 10**: Documentation & Deployment Prep
- Update PHASE_2_COMPLETE.md
- Create deployment checklist
- Feature flag setup

---

## ✅ Success Criteria

**Phase 2 is COMPLETE when**:

1. ✅ **All 9 active endpoints migrated** to v2
2. ✅ **Zero logic changes** (100% copy-paste with refactoring)
3. ✅ **All syntax valid** (python -m py_compile passes)
4. ✅ **No old agent dependencies** in new code (use services/repos)
5. ✅ **Documentation complete** (journey comparison, architecture docs)
6. ✅ **Behavior verified** (v1 and v2 produce same results)
7. ✅ **Ready for deployment** (side-by-side with feature flags)

---

## 📝 Next Steps

**Immediate Actions**:

1. ✅ **User Approval** - Confirm scope (9 endpoints, 2 weeks)
2. ⏳ **Start Repository Creation** - TrackingRepository first
3. ⏳ **Parallel Service Creation** - While repo is in progress
4. ⏳ **API Migration** - After repos and services are ready

**Questions for User**:

1. **Approve 9-endpoint scope?** (vs all 12)
2. **Approve 2-week timeline?** (8-10 days)
3. **Keep TrackingAgent approach?** (vs full refactor)
4. **Deploy Phase 1 first?** (or continue to Phase 2)

---

## 📚 Related Documents

**Previous Phases**:
- [Phase 0 Complete](PHASE_0_COMPLETE.md)
- [Phase 1 Complete](PHASE_1_COMPLETE.md)
- [Phase 1 Active Endpoints Analysis](PHASE_1_ACTIVE_ENDPOINTS_ANALYSIS.md)

**Architecture**:
- [Systematic Migration Approach](../architecture/SYSTEMATIC_MIGRATION_APPROACH.md)
- [Repository Pattern](../architecture/DESIGN_PATTERNS_APPLICATION.md)
- [Migration Guardrails](../MIGRATION_EXECUTION_GUARDRAILS.md)

**Status**:
- [Complete Migration Status](COMPLETE_MIGRATION_STATUS.md)

---

**Document Status**: ✅ COMPLETE
**Next Action**: User approval and Phase 2 execution
**Prepared By**: Claude Code Migration Assistant
**Review Date**: 2025-11-25