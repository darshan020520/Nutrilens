# Behavior Preservation Guarantee - Zero Logic Changes

**Date**: 2025-11-24
**Critical Principle**: **ONLY RESTRUCTURE, NEVER CHANGE LOGIC**

---

## Core Principle

> **"If the current code calculates 2 + 2 = 4, the migrated code MUST calculate 2 + 2 = 4 using the exact same formula, just in a different location."**

---

## What We ARE Doing (Restructuring)

### ✅ ALLOWED: Moving Code to Different Layers

**Example: Meal Logging**

**BEFORE** (tracking.py:907-1095 - 188 lines in API):
```python
@router.post("/log-external-meal")
async def log_external_meal(request, current_user, db):
    # BUILD meal data (business logic in API)
    external_meal_data = {
        "dish_name": request.dish_name,
        "portion_size": request.portion_size,
        "calories": request.calories,
        "protein_g": request.protein_g,
        "carbs_g": request.carbs_g,
        "fat_g": request.fat_g,
        "fiber_g": request.fiber_g,
        "logged_at": consumed_at.isoformat()
    }

    # QUERY DB (data access in API)
    existing_pending_meal = db.query(MealLog).filter(
        MealLog.user_id == user_id,
        MealLog.meal_type == meal_type,
        MealLog.consumed_datetime.is_(None)
    ).first()

    # BUSINESS LOGIC (in API)
    if existing_pending_meal:
        existing_pending_meal.consumed_datetime = consumed_at
        existing_pending_meal.external_meal = external_meal_data
        meal_log = existing_pending_meal
    else:
        meal_log = MealLog(...)
        db.add(meal_log)

    db.commit()
```

**AFTER** (Restructured - EXACT SAME LOGIC):
```python
# ===== API Layer (HTTP handling only) =====
@router.post("/log-external-meal")
async def log_external_meal(
    request: LogExternalMealRequest,
    orchestrator: TrackingOrchestrator = Depends(),
    current_user: User = Depends(get_current_user)
):
    """API delegates - NO logic change"""
    result = await orchestrator.log_external_meal(
        user_id=current_user.id,
        meal_data=request  # SAME data
    )
    return LogExternalMealResponse.from_domain(result)


# ===== Orchestrator (Workflow coordination) =====
class TrackingOrchestrator:
    async def log_external_meal(self, user_id, meal_data):
        """Coordinates services - NO logic change"""

        # Step 1: Check for pending meal (SAME query logic)
        pending_meal = await self.meal_log_service.get_pending_meal(
            user_id=user_id,
            meal_type=meal_data.meal_type
        )

        # Step 2: Create or update (SAME business logic)
        if pending_meal:
            meal_log = await self.meal_log_service.update_with_external_data(
                meal_log=pending_meal,
                external_data=meal_data
            )
        else:
            meal_log = await self.meal_log_service.create_external_meal(
                user_id=user_id,
                external_data=meal_data
            )

        return meal_log


# ===== Service (Business logic) =====
class MealLogService:
    async def update_with_external_data(self, meal_log, external_data):
        """EXACT SAME business logic, just extracted"""

        # BUILD meal data (SAME structure)
        external_meal_dict = {
            "dish_name": external_data.dish_name,
            "portion_size": external_data.portion_size,
            "calories": external_data.calories,
            "protein_g": external_data.protein_g,
            "carbs_g": external_data.carbs_g,
            "fat_g": external_data.fat_g,
            "fiber_g": external_data.fiber_g,
            "logged_at": datetime.utcnow().isoformat()  # SAME timestamp logic
        }

        # UPDATE meal log (SAME field assignments)
        meal_log.consumed_datetime = datetime.utcnow()
        meal_log.external_meal = external_meal_dict
        meal_log.recipe_id = None  # SAME clearing of recipe_id

        # Delegate to repository
        return await self.meal_log_repo.update(meal_log)


# ===== Repository (Database access) =====
class MealLogRepository:
    async def get_pending_meal(self, user_id, meal_type):
        """EXACT SAME query, just extracted"""
        db_meal = self.db.query(MealLogORM).filter(
            MealLogORM.user_id == user_id,
            MealLogORM.meal_type == meal_type,
            MealLogORM.consumed_datetime.is_(None)  # SAME condition
        ).first()

        return MealLog.from_orm(db_meal) if db_meal else None

    async def update(self, meal_log):
        """EXACT SAME commit logic"""
        db_meal = self.db.query(MealLogORM).filter_by(id=meal_log.id).first()
        db_meal.consumed_datetime = meal_log.consumed_datetime  # SAME assignment
        db_meal.external_meal = meal_log.external_meal  # SAME assignment
        db_meal.recipe_id = meal_log.recipe_id  # SAME assignment

        self.db.commit()  # SAME commit
        self.db.refresh(db_meal)  # SAME refresh

        return MealLog.from_orm(db_meal)
```

**What Changed**: WHERE the code lives (API → Orchestrator → Service → Repository)
**What Stayed IDENTICAL**:
- ✅ Query logic (same filters, same conditions)
- ✅ Business logic (same if/else, same assignments)
- ✅ Data structure (same JSON fields)
- ✅ Behavior (same result, same side effects)

---

## What We ARE NOT Doing (Logic Changes)

### ❌ FORBIDDEN: Changing Calculations

**Example: BMR Calculation**

**WRONG** (Don't do this):
```python
# OLD (onboarding.py:70-81)
def calculate_bmr(weight, height, age, sex):
    if sex == "male":
        return 10 * weight + 6.25 * height - 5 * age + 5
    else:
        return 10 * weight + 6.25 * height - 5 * age - 161

# WRONG: Changing formula during migration
def calculate_bmr(weight, height, age, sex):
    # ❌ WRONG: Using different formula
    if sex == "male":
        return 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    # ❌ This is Harris-Benedict, not Mifflin-St Jeor!
```

**RIGHT** (Copy-paste exact formula):
```python
# NEW (domain/user/value_objects.py)
@dataclass(frozen=True)
class BMR:
    value: float

    @classmethod
    def calculate(cls, weight_kg, height_cm, age, sex):
        """
        EXACT COPY from onboarding.py:70-81
        Mifflin-St Jeor Formula
        """
        if sex == "male":
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5  # IDENTICAL
        else:
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161  # IDENTICAL

        return cls(value=bmr)
```

### ❌ FORBIDDEN: Changing Business Rules

**Example: Meal Plan Activation**

**WRONG**:
```python
# OLD: Deactivate ALL old plans
await meal_plan_repo.deactivate_active_plans(user_id)

# ❌ WRONG: Only deactivate plans older than 7 days
if (datetime.now() - old_plan.created_at).days > 7:
    await meal_plan_repo.deactivate_active_plans(user_id)
# ❌ This changes behavior!
```

**RIGHT**:
```python
# OLD: Deactivate ALL old plans
await meal_plan_repo.deactivate_active_plans(user_id)

# ✅ RIGHT: Deactivate ALL (same behavior)
await meal_plan_repo.deactivate_active_plans(user_id)
```

### ❌ FORBIDDEN: Changing Data Transformations

**Example: Response Formatting**

**WRONG**:
```python
# OLD: Return calories rounded to 1 decimal
return {"calories": round(meal_log.calories, 1)}

# ❌ WRONG: Changing to integer
return {"calories": int(meal_log.calories)}  # Different precision!
```

**RIGHT**:
```python
# OLD: Return calories rounded to 1 decimal
return {"calories": round(meal_log.calories, 1)}

# ✅ RIGHT: Same rounding
return {"calories": round(meal_log.calories, 1)}
```

---

## Behavior Preservation Checklist

For EVERY piece of code we move:

### Before Moving Code

1. **[ ] Read the existing code completely**
   - Understand what it does
   - Note all edge cases
   - Note all error conditions
   - Note all calculations
   - Note all database queries

2. **[ ] Document the exact behavior**
   ```python
   # Example behavior documentation:
   # INPUT: user_id=123, meal_type="breakfast"
   # QUERY: SELECT * FROM meal_logs WHERE user_id=123 AND meal_type='breakfast' AND consumed_datetime IS NULL
   # IF found: UPDATE consumed_datetime, external_meal
   # IF not found: INSERT new MealLog
   # COMMITS: Always commits once at the end
   # RETURNS: MealLog with populated fields
   ```

3. **[ ] Take screenshots or note line numbers**
   - Where is this code? (file:line)
   - What does it depend on?
   - What depends on it?

### During Migration

4. **[ ] Copy-paste, don't rewrite**
   - Use Ctrl+C, Ctrl+V
   - Don't "improve" the code
   - Don't "optimize" the code
   - Don't "refactor" the logic

5. **[ ] Keep the EXACT same logic**
   - Same if/else conditions
   - Same loop logic
   - Same calculations
   - Same string formatting
   - Same rounding
   - Same error messages

6. **[ ] Preserve query logic exactly**
   ```python
   # OLD
   db.query(MealLog).filter(
       MealLog.user_id == user_id,
       MealLog.consumed_datetime.is_(None)
   ).first()

   # NEW (in repository)
   self.db.query(MealLogORM).filter(
       MealLogORM.user_id == user_id,
       MealLogORM.consumed_datetime.is_(None)  # EXACT same condition
   ).first()
   ```

### After Migration

7. **[ ] Write comparison tests**
   ```python
   def test_old_vs_new_behavior():
       """Ensure new implementation matches old exactly."""

       # Call old endpoint
       old_response = call_old_endpoint(user_id=123, ...)

       # Call new endpoint
       new_response = call_new_endpoint(user_id=123, ...)

       # Compare EVERYTHING
       assert old_response["calories"] == new_response["calories"]
       assert old_response["protein"] == new_response["protein"]
       assert old_response["meal_log_id"] == new_response["meal_log_id"]
       # ... compare ALL fields
   ```

8. **[ ] Run side-by-side in production**
   - Both endpoints live simultaneously
   - Route 1% of traffic to new endpoint
   - Compare results
   - Monitor errors
   - Gradually increase to 100%

9. **[ ] Verify database state**
   ```python
   # After calling endpoint, verify DB state is IDENTICAL
   def test_database_state_matches():
       # Call old endpoint
       call_old_endpoint(...)
       db_state_old = get_db_snapshot()

       # Call new endpoint
       call_new_endpoint(...)
       db_state_new = get_db_snapshot()

       # Compare
       assert db_state_old == db_state_new
   ```

---

## Copy-Paste Strategy (Our Approach)

### Step-by-Step Process

**Example: Migrating grocery list calculation**

**Step 1: Find existing logic**
```python
# backend/app/agents/planning_agent.py:204-230
def calculate_grocery_list(self, meal_plan, user_id):
    """Current implementation - 27 lines"""
    grocery_items = {}

    for day in meal_plan['week_plan']:
        for meal_type, meal in day.items():
            if meal_type == 'day':
                continue

            recipe_id = meal.get('recipe_id')
            portions = meal.get('portions', 1)

            # Get recipe ingredients
            recipe = self.db.query(Recipe).filter_by(id=recipe_id).first()

            for ingredient in recipe.ingredients:
                item_id = ingredient.item_id
                quantity = ingredient.quantity_grams * portions

                if item_id in grocery_items:
                    grocery_items[item_id]['quantity'] += quantity
                else:
                    grocery_items[item_id] = {
                        'item_name': ingredient.item.canonical_name,
                        'quantity': quantity
                    }

    return grocery_items
```

**Step 2: Copy-paste to new location (Service)**
```python
# backend/app/services/grocery_service.py
class GroceryService:
    """New service for grocery calculations."""

    def __init__(self, recipe_repo: IRecipeRepository):
        self.recipe_repo = recipe_repo

    async def calculate_for_plan(self, meal_plan_data, user_id):
        """
        EXACT COPY-PASTE from planning_agent.py:204-230
        ZERO logic changes, just moved location
        """
        grocery_items = {}  # SAME initialization

        for day in meal_plan_data['week_plan']:  # SAME loop
            for meal_type, meal in day.items():  # SAME nested loop
                if meal_type == 'day':  # SAME skip condition
                    continue

                recipe_id = meal.get('recipe_id')  # SAME extraction
                portions = meal.get('portions', 1)  # SAME default value

                # Get recipe via repository (same query result)
                recipe = await self.recipe_repo.get_by_id(recipe_id)

                for ingredient in recipe.ingredients:  # SAME ingredient loop
                    item_id = ingredient.item_id  # SAME field
                    quantity = ingredient.quantity_grams * portions  # SAME calculation

                    if item_id in grocery_items:  # SAME accumulation logic
                        grocery_items[item_id]['quantity'] += quantity
                    else:
                        grocery_items[item_id] = {
                            'item_name': ingredient.item.canonical_name,  # SAME field
                            'quantity': quantity
                        }

        return grocery_items  # SAME return
```

**Step 3: Update caller to use new service**
```python
# backend/app/orchestrators/meal_plan_orchestrator.py
class MealPlanOrchestrator:
    async def generate_weekly_meal_plan(self, ...):
        # OLD: agent.calculate_grocery_list(meal_plan, user_id)
        # NEW: Use service (SAME result)
        grocery_list = await self.grocery_service.calculate_for_plan(
            meal_plan_data=optimized_plan,
            user_id=user_id
        )
        # grocery_list has EXACT same structure
```

**Step 4: Test equivalence**
```python
def test_grocery_calculation_equivalence():
    """Verify new service produces EXACT same output as old agent."""

    # Test data
    meal_plan = {...}  # Sample meal plan

    # OLD way (agent)
    agent = PlanningAgent(db)
    old_result = agent.calculate_grocery_list(meal_plan, user_id=123)

    # NEW way (service)
    service = GroceryService(recipe_repo)
    new_result = await service.calculate_for_plan(meal_plan, user_id=123)

    # Compare
    assert old_result == new_result  # MUST be identical
```

---

## Testing Strategy for Zero Logic Changes

### Test Level 1: Unit Tests (Per Method)

For EVERY method we move:

```python
def test_moved_method_behaves_identically():
    """Test that moved method produces same output."""

    # Arrange: Same input
    input_data = {...}

    # Act: Call both old and new
    old_result = call_old_implementation(input_data)
    new_result = call_new_implementation(input_data)

    # Assert: EXACT match
    assert old_result == new_result
```

### Test Level 2: Integration Tests (Per Endpoint)

For EVERY endpoint we migrate:

```python
@pytest.mark.integration
def test_endpoint_behavior_preserved():
    """Test that new endpoint behaves identically to old."""

    # Arrange: Create test user, meal plan, etc.
    setup_test_data()

    # Act: Call both endpoints
    old_response = client.post("/tracking/log-meal", json={...})
    new_response = client.post("/tracking/v2/log-meal", json={...})

    # Assert: Same status code
    assert old_response.status_code == new_response.status_code

    # Assert: Same response body
    assert old_response.json() == new_response.json()

    # Assert: Same database state
    verify_database_state_identical()
```

### Test Level 3: Comparison Tests (Side-by-Side)

```python
def test_old_and_new_produce_identical_results():
    """Run both implementations and compare ALL outputs."""

    test_cases = [
        {"user_id": 1, "meal_type": "breakfast", "portion": 1.0},
        {"user_id": 2, "meal_type": "lunch", "portion": 1.5},
        {"user_id": 3, "meal_type": "dinner", "portion": 0.5},
        # ... 100+ test cases covering edge cases
    ]

    for case in test_cases:
        old_result = call_old_endpoint(**case)
        new_result = call_new_endpoint(**case)

        assert old_result == new_result, f"Mismatch for {case}"
```

### Test Level 4: Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(
    user_id=st.integers(min_value=1, max_value=10000),
    meal_type=st.sampled_from(["breakfast", "lunch", "dinner", "snack"]),
    portion=st.floats(min_value=0.1, max_value=3.0)
)
def test_property_old_equals_new(user_id, meal_type, portion):
    """Property: For ANY valid input, old and new produce same output."""

    old_result = call_old_endpoint(user_id, meal_type, portion)
    new_result = call_new_endpoint(user_id, meal_type, portion)

    assert old_result == new_result
```

---

## Migration Safety Guardrails

### Guardrail 1: Copy-Paste, Never Rewrite

```python
# ❌ WRONG: Rewriting
# OLD
if user_goal.goal_type == "muscle_gain":
    target_protein = weight * 2.0
elif user_goal.goal_type == "fat_loss":
    target_protein = weight * 1.6
else:
    target_protein = weight * 1.2

# WRONG: Rewriting with dictionary
protein_multipliers = {"muscle_gain": 2.0, "fat_loss": 1.6}
target_protein = weight * protein_multipliers.get(user_goal.goal_type, 1.2)
# ❌ This is "better" but changes behavior if goal_type has unexpected value


# ✅ RIGHT: Exact copy-paste
if user_goal.goal_type == "muscle_gain":
    target_protein = weight * 2.0
elif user_goal.goal_type == "fat_loss":
    target_protein = weight * 1.6
else:
    target_protein = weight * 1.2
```

### Guardrail 2: Preserve Error Behavior

```python
# OLD: Returns None on error
def get_meal_plan(user_id):
    plan = db.query(MealPlan).filter_by(user_id=user_id).first()
    if not plan:
        return None  # Returns None
    return plan

# ❌ WRONG: Raising exception instead
async def get_meal_plan(user_id):
    plan = await meal_plan_repo.get_by_user(user_id)
    if not plan:
        raise ValueError("Plan not found")  # ❌ Different behavior!
    return plan

# ✅ RIGHT: Same return behavior
async def get_meal_plan(user_id):
    plan = await meal_plan_repo.get_by_user(user_id)
    if not plan:
        return None  # ✅ Same as old
    return plan
```

### Guardrail 3: Preserve Side Effects Order

```python
# OLD: Order matters
meal_log.consumed_datetime = datetime.now()  # 1. Set timestamp
meal_log.external_meal = data  # 2. Set data
db.commit()  # 3. Commit
db.refresh(meal_log)  # 4. Refresh

# ❌ WRONG: Different order
db.commit()  # ❌ Commit before setting fields?
meal_log.consumed_datetime = datetime.now()
meal_log.external_meal = data
db.refresh(meal_log)

# ✅ RIGHT: Same order
meal_log.consumed_datetime = datetime.now()  # 1. Same
meal_log.external_meal = data  # 2. Same
db.commit()  # 3. Same
db.refresh(meal_log)  # 4. Same
```

---

## What If We Find a Bug?

**Q**: What if the current code has a bug? Should we fix it during migration?

**A**: **NO! Keep the bug, fix it later.**

```python
# OLD CODE (has bug - doesn't handle None)
def calculate_average_calories(meal_logs):
    total = sum(log.calories for log in meal_logs)  # ❌ Bug if meal_logs is empty
    return total / len(meal_logs)  # ❌ Division by zero!

# ❌ WRONG: Fixing during migration
async def calculate_average_calories(meal_logs):
    if not meal_logs:  # Fixing the bug
        return 0
    total = sum(log.calories for log in meal_logs)
    return total / len(meal_logs)

# ✅ RIGHT: Keep the bug (fix in separate PR)
async def calculate_average_calories(meal_logs):
    # TODO: Fix division by zero bug in separate PR
    total = sum(log.calories for log in meal_logs)  # Same bug
    return total / len(meal_logs)  # Same bug
```

**Why?**
- If we change behavior (even to fix bugs), we can't verify migration correctness
- Fix bugs in SEPARATE PRs after migration is complete
- Each PR should have ONE purpose: restructure OR fix bug, never both

---

## Final Verification Process

### Before Cutover Checklist

For EACH endpoint before going live:

- [ ] **Comparison tests pass** (old vs new produce identical output)
- [ ] **Integration tests pass** (new endpoint works end-to-end)
- [ ] **Database state verified** (same records created/updated)
- [ ] **Side effects verified** (same notifications sent, same events published)
- [ ] **Error cases verified** (same error messages, same HTTP status codes)
- [ ] **Edge cases verified** (empty lists, None values, zero quantities)
- [ ] **Performance verified** (new endpoint not slower than old)
- [ ] **Code review approved** ("Is this copy-paste or rewrite?")

---

## Summary

### ✅ What We DO

1. **Move code** from API → Orchestrator → Service → Repository
2. **Copy-paste** existing logic (don't rewrite)
3. **Preserve behavior** exactly (same inputs → same outputs)
4. **Test equivalence** (old vs new must match)
5. **Restructure** layers (better organization)

### ❌ What We DON'T DO

1. **Change calculations** (keep exact formulas)
2. **Change business rules** (keep exact conditions)
3. **Fix bugs** (keep bugs, fix later)
4. **Optimize code** (keep inefficiencies, optimize later)
5. **"Improve" logic** (keep it exactly as-is)

### Our Promise

> **"After migration completes, if you call the same endpoint with the same input, you will get the EXACT same output, create the EXACT same database records, and trigger the EXACT same side effects. The ONLY difference is WHERE the code lives, not WHAT it does."**

---

**STATUS**: ✅ BEHAVIOR PRESERVATION STRATEGY DOCUMENTED

**Next Step**: Proceed with Phase 0 (Preparation) with confidence that we will **ONLY restructure, NEVER change logic**
