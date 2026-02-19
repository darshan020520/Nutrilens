# /current/with-status Endpoint Refactoring - Complete Plan

## Current State

### Endpoint: `GET /meal-plans/v2/current/with-status`
**File:** `backend/app/api/meal_plan_v2.py` (Lines 73-181)

### Current Issues:
1. **Business logic in API layer** (Lines 117-165)
   - Status map building
   - Plan data enrichment
2. **Direct repository injection in API** (Line 76)
   - API directly injects `meal_log_repo`
   - Violates clean architecture (API → Service → Repository)
3. **Debug print statements** (Lines 122, 125, 128, 130-131, 156)

---

## Refactoring Plan

### Step 1: Add Method to MealPlanServiceV2

**File:** `backend/app/services/meal_plan_service_v2.py`

**Location:** After `get_active_meal_plan()` method (after line 182)

**New Method:**
```python
async def get_active_meal_plan_with_status(self, user_id: int) -> Dict:
    """
    Get active meal plan enriched with meal log statuses.

    BUSINESS LOGIC COPY-PASTED FROM: meal_plan_v2.py:86-181

    Handles:
    1. Fetch active meal plan
    2. If no plan, return empty response
    3. Fetch meal logs for the week
    4. Build status map (logged/skipped/pending)
    5. Enrich plan data with statuses

    Args:
        user_id: User ID

    Returns:
        Dict with enriched meal plan or empty response
    """
    # COPY-PASTE lines 87-100 from API (no plan handling)
    plan = await self.get_active_meal_plan(user_id)

    if not plan:
        today = datetime.now().date()
        days_since_monday = today.weekday()
        current_week_start = today - timedelta(days=days_since_monday)

        return {
            "id": None,
            "has_plan": False,
            "week_start_date": current_week_start.isoformat(),
            "plan_data": None,
            "message": "No meal plan found for this week. Generate a new plan to get started!"
        }

    # COPY-PASTE lines 105-113 from API (fetch meal logs)
    week_start = plan.week_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    meal_logs = await self.meal_log_repo.get_by_plan_and_date_range(
        user_id=user_id,
        meal_plan_id=plan.id,
        start_datetime=week_start,
        end_datetime=week_end
    )

    # COPY-PASTE lines 117-131 from API (build status map)
    status_map = {}
    for log in meal_logs:
        key = f"{log.planned_datetime.date()}_{log.meal_type}"
        if log.consumed_datetime:
            status_map[key] = "logged"
        elif log.was_skipped:
            status_map[key] = "skipped"
        else:
            status_map[key] = "pending"

    # COPY-PASTE lines 135-165 from API (enrich plan data)
    enriched_plan_data = {}
    plan_data = plan.plan_data.get('week_plan', plan.plan_data)

    for day_index in range(7):
        day_key = f"day_{day_index}"
        day_data = plan_data.get(day_key)

        if not day_data:
            continue

        day_date = week_start + timedelta(days=day_index)
        enriched_meals = {}

        for meal_type, meal_recipe in day_data.get('meals', {}).items():
            if not meal_recipe:
                enriched_meals[meal_type] = None
                continue

            # Get status from logs
            status_key = f"{day_date.date()}_{meal_type}"
            status = status_map.get(status_key, "pending")

            # Add status to meal data
            enriched_meal = {**meal_recipe, "status": status}
            enriched_meals[meal_type] = enriched_meal

        enriched_plan_data[day_key] = {
            **day_data,
            "meals": enriched_meals
        }

    # COPY-PASTE lines 169-181 from API (return enriched plan)
    return {
        "id": plan.id,
        "user_id": plan.user_id,
        "week_start_date": plan.week_start_date.isoformat(),
        "plan_data": enriched_plan_data,
        "grocery_list": plan.grocery_list,
        "total_calories": plan.total_calories,
        "avg_macros": plan.avg_macros,
        "is_active": plan.is_active,
        "created_at": plan.created_at.isoformat(),
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "has_plan": True
    }
```

**Key Points:**
- Uses existing `self.meal_log_repo` (already injected in constructor)
- Calls `self.get_active_meal_plan()` instead of duplicating logic
- Removes all print statements
- Pure business logic, no HTTP concerns

---

### Step 2: Update API Endpoint

**File:** `backend/app/api/meal_plan_v2.py`

**Replace lines 73-181 with:**
```python
@router_v2.get("/current/with-status")
async def get_current_meal_plan_with_status_v2(
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    current_user: User = Depends(get_current_user)
):
    """
    Get user's current active meal plan with meal log status enriched.

    REFACTORED: Business logic moved to MealPlanServiceV2.
    API layer is now thin - just calls service and returns result.
    """
    return await meal_plan_service.get_active_meal_plan_with_status(current_user.id)
```

**Changes:**
1. Removed `meal_log_repo` dependency injection (Line 76) ✅
2. Removed all business logic (Lines 86-181) ✅
3. Service call replaces everything ✅

---

## Dependencies Check

### MealPlanServiceV2 Constructor (Lines 36-55)
```python
def __init__(
    self,
    meal_plan_repo: IMealPlanRepository,
    meal_log_repo: IMealLogRepository,  # ✅ Already has this
    recipe_repo: IRecipeRepository,
    inventory_service: IntelligentInventoryService
):
```

**Status:** ✅ No changes needed to constructor or dependencies.py

---

## Files to Modify

### 1. `backend/app/services/meal_plan_service_v2.py`
**Action:** Add new method `get_active_meal_plan_with_status()`
**Location:** After line 182 (after `get_active_meal_plan()`)
**Lines Added:** ~95 lines

### 2. `backend/app/api/meal_plan_v2.py`
**Action:** Replace entire endpoint implementation
**Location:** Lines 73-181 (109 lines)
**Replace with:** ~10 lines (thin API layer)
**Lines Removed:** ~99 lines

---

## Testing Validation

### Must Verify:
1. ✅ Response structure unchanged
2. ✅ Status map logic identical (logged/skipped/pending)
3. ✅ Date range calculation same (week_start to week_end)
4. ✅ Empty plan response format unchanged
5. ✅ Enrichment logic preserved

### Response Structure (MUST NOT CHANGE):
```json
{
  "id": int,
  "user_id": int,
  "week_start_date": string,
  "plan_data": {
    "day_0": {
      "meals": {
        "breakfast": {
          "id": int,
          "name": string,
          "status": "logged" | "skipped" | "pending"
        }
      }
    }
  },
  "grocery_list": {},
  "total_calories": float,
  "avg_macros": {},
  "is_active": bool,
  "created_at": string,
  "updated_at": string,
  "has_plan": true
}
```

---

## Benefits

### Before:
- Business logic in API layer ❌
- Direct repository injection in API ❌
- 109 lines in API endpoint ❌
- Debug prints in production ❌

### After:
- Business logic in Service layer ✅
- API only depends on services ✅
- 10 lines in API endpoint ✅
- Clean logging (no prints) ✅
- Reusable service method ✅

---

## Risk Analysis

### Low Risk:
- Service already has meal_log_repo ✅
- Logic is copy-paste (no changes) ✅
- API just calls service method ✅

### Medium Risk:
- Must preserve exact response structure
- Must handle None/null cases identically

### Mitigation:
- Line-by-line copy of logic
- Keep all conditionals identical
- Test with real data

---

## Implementation Order

1. Add `get_active_meal_plan_with_status()` to MealPlanServiceV2
2. Update API endpoint to call service method
3. Remove debug print statements
4. Test endpoint response structure
5. Verify status logic (logged/skipped/pending)

---

## Questions Resolved

1. **Does service have meal_log_repo?** ✅ Yes (line 39-40, 53)
2. **Need to update dependencies.py?** ❌ No changes needed
3. **Breaking changes?** ❌ None - response structure identical
4. **What about print statements?** Remove them (use logger if needed)

---

## Ready to Implement

All dependencies verified. Logic clearly defined. Response structure preserved.

Proceed?
