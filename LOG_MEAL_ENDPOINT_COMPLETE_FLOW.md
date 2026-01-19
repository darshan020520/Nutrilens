# POST /log-meal Endpoint - Complete End-to-End Flow

## Endpoint: `POST /tracking/v2/log-meal`

**File:** `backend/app/api/tracking_v2.py` (Lines 154-213)

---

## Complete Flow

### Layer 1: API (tracking_v2.py:154-213)

```python
async def log_meal(
    request: LogMealRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: MealLoggingOrchestrator = Depends(get_tracking_orchestrator)
):
```

**Dependencies Injected:**
- `MealLoggingOrchestrator` via `get_tracking_orchestrator()`
- `User` via `get_current_user()`

**Steps:**
1. Line 179: Call `orchestrator.log_planned_meal()`
2. Line 189: Extract meal_data from orchestrator result
3. Lines 191-203: Format response to match schema
4. Return `LogMealResponse`

---

### Layer 2: Orchestrator (meal_logging_orchestrator.py:80-169)

```python
async def log_planned_meal(
    user_id: int,
    meal_log_id: int,
    portion_multiplier: float = 1.0,
    notes: Optional[str] = None
) -> Dict[str, Any]:
```

**Dependencies (Constructor):**
- `meal_tracking: MealTrackingService`
- `consumption: ConsumptionServiceV2`
- `inventory: InventoryManagementService`

**Workflow Steps:**
1. **Line 122:** Call `meal_tracking.log_meal()` → Log meal consumption
2. **Line 130:** Call `consumption.get_today_summary()` → Get updated daily summary
3. **Line 134:** Call `inventory.calculate_inventory_status()` → Check inventory status
4. **Line 137:** Call `_publish_meal_logged_events()` → Publish events
5. **Line 145:** Call `_send_meal_logged_notifications()` → Send notifications
6. **Lines 153-162:** Return comprehensive result

---

### Layer 3: Service Layer

#### Service 1: MealTrackingService.log_meal() (meal_tracking_service.py:61-147)

**Dependencies (Constructor):**
- `tracking_repo: ITrackingRepository`
- `inventory_repo: IInventoryRepository`
- `analytics_repo: IConsumptionAnalyticsRepository`
- `notification_service: NotificationService`

**Steps:**
1. **Line 87:** Call `_validate_meal_for_logging()` → Validate meal log
   - Calls `tracking_repo.get_meal_log_by_id()`
   - **DB Query 1:** `SELECT * FROM meal_logs WHERE id = ?`

2. **Line 91:** Call `tracking_repo.mark_as_consumed()` → Mark as consumed
   - **DB Query 2:** `UPDATE meal_logs SET consumed_datetime = ?, portion_multiplier = ?, notes = ? WHERE id = ?`

3. **Line 102:** Call `inventory_repo.deduct_recipe_ingredients()` → Deduct ingredients
   - **DB Query 3:** `SELECT * FROM user_inventory WHERE user_id = ? AND item_id IN (...)`
   - **DB Query 4:** `UPDATE user_inventory SET quantity_grams = ? WHERE id IN (...)`

4. **Line 110:** Call `_calculate_meal_macros()` → Calculate macros (in-memory)

5. **Line 113:** Call `analytics_repo.get_today_summary()` → Get daily totals
   - **DB Query 5:** `SELECT * FROM meal_logs WHERE user_id = ? AND DATE(planned_datetime) = CURRENT_DATE`

6. **Line 116:** Call `_generate_meal_insights()` → Generate insights (business logic)

7. **Line 119:** Call `_generate_meal_recommendations()` → Generate recommendations (business logic)

8. **Lines 127-140:** Return formatted result

---

#### Service 2: ConsumptionServiceV2.get_today_summary()

Called by orchestrator at line 130

**Steps:**
- Aggregates meal logs for today
- Calculates totals, targets, remaining macros
- **DB Query 6:** Similar to analytics_repo.get_today_summary()

---

#### Service 3: InventoryManagementService.calculate_inventory_status()

Called by orchestrator at line 134

**Steps:**
- Analyzes current inventory levels
- Identifies low stock, critical items
- **DB Query 7:** `SELECT * FROM user_inventory WHERE user_id = ?`
- **DB Query 8:** `SELECT * FROM items WHERE id IN (...)` (if needed)

---

### Layer 4: Repository Layer

#### Repository 1: TrackingRepository

**Method:** `get_meal_log_by_id(meal_log_id)`
- **DB Query:** `SELECT * FROM meal_logs WHERE id = ?`
- Returns: `MealLog` entity

**Method:** `mark_as_consumed(meal_log_id, user_id, consumed_at, portion_multiplier, notes)`
- **DB Query:** `UPDATE meal_logs SET consumed_datetime = ?, portion_multiplier = ?, notes = ? WHERE id = ? AND user_id = ?`
- Returns: Updated `MealLog` entity

---

#### Repository 2: InventoryRepository

**Method:** `deduct_recipe_ingredients(user_id, recipe, portion_multiplier)`
- Gets recipe ingredients
- **DB Query:** `SELECT * FROM recipe_ingredients WHERE recipe_id = ?`
- For each ingredient:
  - **DB Query:** `SELECT * FROM user_inventory WHERE user_id = ? AND item_id = ?`
  - **DB Query:** `UPDATE user_inventory SET quantity_grams = quantity_grams - ? WHERE id = ?`
- Returns: List of deduction results

---

#### Repository 3: ConsumptionAnalyticsRepository

**Method:** `get_today_summary(user_id)`
- **DB Query:** `SELECT * FROM meal_logs WHERE user_id = ? AND DATE(planned_datetime) = CURRENT_DATE`
- Aggregates macros
- Returns: Summary dict with totals, targets, remaining

---

## Database Queries Summary

### Total Queries: ~8-10 (depends on number of ingredients)

1. **Validate meal log:** `SELECT * FROM meal_logs WHERE id = ?`
2. **Mark consumed:** `UPDATE meal_logs SET consumed_datetime = ?, ... WHERE id = ?`
3. **Get inventory for deduction:** `SELECT * FROM user_inventory WHERE user_id = ? AND item_id IN (...)`
4. **Deduct inventory:** `UPDATE user_inventory SET quantity_grams = ? WHERE id IN (...)`
5. **Get today's meals:** `SELECT * FROM meal_logs WHERE user_id = ? AND DATE(planned_datetime) = CURRENT_DATE`
6. **Get today summary (consumption service):** Similar to #5
7. **Get all inventory (status check):** `SELECT * FROM user_inventory WHERE user_id = ?`
8. **Get items (if needed):** `SELECT * FROM items WHERE id IN (...)`

---

## Architecture Status

### ✅ Clean Architecture Compliance

**API Layer:**
- Uses dependency injection ✅
- No direct DB access ✅
- Depends only on orchestrator ✅
- Thin layer (just formatting) ✅

**Orchestrator Layer:**
- Coordinates multiple services ✅
- No direct DB access ✅
- Uses dependency injection ✅
- Handles workflow coordination ✅

**Service Layer:**
- Business logic only ✅
- Uses repositories for data access ✅
- No direct DB queries ✅
- Dependency injection ✅

**Repository Layer:**
- All DB queries isolated ✅
- Clean interfaces ✅
- Single responsibility ✅

---

## Potential Issues to Check

### Need to Verify:

1. **Inventory Deduction Query Performance**
   - Is `deduct_recipe_ingredients()` using batch queries?
   - Or does it have N+1 problem (one query per ingredient)?
   - Location: `InventoryRepository.deduct_recipe_ingredients()`

2. **Today Summary Query Duplication**
   - Called twice: in MealTrackingService AND ConsumptionServiceV2
   - Could be optimized to call only once
   - Orchestrator calls both services independently

3. **Repository Methods Async Status**
   - Are all repository methods properly async?
   - Check: `tracking_repo.mark_as_consumed()`
   - Check: `inventory_repo.deduct_recipe_ingredients()`

---

## Next Steps

1. Check `InventoryRepository.deduct_recipe_ingredients()` implementation
2. Verify no N+1 query problems in ingredient deduction
3. Check if repositories are properly using async/await
4. Verify all repository methods have interfaces

---

Ready to investigate these potential issues?
