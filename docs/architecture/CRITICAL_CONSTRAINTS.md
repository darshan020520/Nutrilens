# CRITICAL CONSTRAINTS - READ THIS FIRST

**Date**: 2025-11-24
**Status**: MANDATORY - MUST READ BEFORE ANY MIGRATION WORK

---

## 🚨 STOP AND READ THIS 🚨

If you are Claude (or any AI assistant) helping with this migration:

**BEFORE doing ANY work, answer these questions:**

1. ✅ Have I read BEHAVIOR_PRESERVATION_GUARANTEE.md?
2. ✅ Do I understand we are ONLY restructuring, NEVER changing logic?
3. ✅ Am I about to copy-paste code or rewrite it? (Must be copy-paste!)
4. ✅ Have I verified the existing behavior before moving code?

If you answered NO to any question, **STOP and read the docs first**.

---

## Core Constraint: COPY-PASTE ONLY, NEVER REWRITE

### The Golden Rule

```
IF you see this in existing code:
    if x > 0:
        result = x * 2
    else:
        result = x * 3

THEN your migrated code MUST be:
    if x > 0:           # EXACT SAME condition
        result = x * 2  # EXACT SAME calculation
    else:
        result = x * 3  # EXACT SAME calculation

NOT this (even if "better"):
    result = x * (2 if x > 0 else 3)  # ❌ WRONG - This is rewriting!
```

### What "Restructuring" Means

**ONLY ALLOWED CHANGES:**

1. ✅ **Move code to different file**
   - From: `backend/app/api/tracking.py`
   - To: `backend/app/services/meal_log_service.py`
   - Logic: IDENTICAL

2. ✅ **Rename variables for layer consistency**
   - From: `db.query(MealLog)` (in API)
   - To: `self.db.query(MealLogORM)` (in Repository)
   - Query: IDENTICAL

3. ✅ **Extract method with same logic**
   - From: 50 lines inline in API
   - To: `def method_name()` with same 50 lines
   - Logic: IDENTICAL

4. ✅ **Change dependency injection**
   - From: `agent = PlanningAgent(db)`
   - To: `orchestrator = MealPlanOrchestrator(services...)`
   - Behavior: IDENTICAL

**FORBIDDEN CHANGES:**

1. ❌ **Changing calculations**
   ```python
   # Existing
   bmr = 10 * weight + 6.25 * height - 5 * age + 5

   # ❌ FORBIDDEN
   bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
   ```

2. ❌ **Changing conditions**
   ```python
   # Existing
   if meal_log.consumed_datetime is None:

   # ❌ FORBIDDEN
   if not meal_log.consumed_datetime:  # Different behavior for datetime(0)!
   ```

3. ❌ **Changing data structures**
   ```python
   # Existing
   return {"calories": 100, "protein": 20}

   # ❌ FORBIDDEN
   return {"nutritional_info": {"calories": 100, "protein": 20}}
   ```

4. ❌ **Fixing bugs**
   ```python
   # Existing (has bug)
   return total / len(items)  # Division by zero possible

   # ❌ FORBIDDEN (even though it's a bug fix!)
   return total / len(items) if items else 0

   # ✅ CORRECT
   return total / len(items)  # TODO: Fix bug in separate PR
   ```

5. ❌ **Adding validation**
   ```python
   # Existing
   def process_meal(calories):
       return calories * 1.1

   # ❌ FORBIDDEN
   def process_meal(calories):
       if calories < 0:  # New validation!
           raise ValueError("Calories must be positive")
       return calories * 1.1
   ```

6. ❌ **Changing error messages**
   ```python
   # Existing
   raise ValueError("Invalid meal type")

   # ❌ FORBIDDEN
   raise ValueError("Meal type must be breakfast, lunch, dinner, or snack")
   ```

---

## Quick Self-Check Before Writing Code

### ASK YOURSELF:

**Q1: Am I about to write new logic?**
- ❌ If YES → STOP! You should be copy-pasting existing logic.

**Q2: Am I improving/optimizing something?**
- ❌ If YES → STOP! Keep it exactly as-is, optimize later.

**Q3: Am I fixing a bug I noticed?**
- ❌ If YES → STOP! Add TODO comment, fix bug in separate PR.

**Q4: Did I change any if/else conditions?**
- ❌ If YES → STOP! Conditions must be byte-for-byte identical.

**Q5: Did I change any calculations?**
- ❌ If YES → STOP! Formulas must be mathematically identical.

**Q6: Did I change the structure of returned data?**
- ❌ If YES → STOP! Response format must be identical.

**Q7: Can I show the old code and new code side-by-side and prove they're equivalent?**
- ✅ If YES → Proceed!
- ❌ If NO → STOP! You changed something.

---

## Code Review Checklist

When reviewing your own work OR when user reviews:

### For Each File Changed:

- [ ] I can point to the EXACT location in old code that this new code came from
- [ ] Old code and new code have IDENTICAL logic (not just similar)
- [ ] I used copy-paste (Ctrl+C, Ctrl+V), not rewriting
- [ ] Any helper methods I created just extract existing code (no new logic)
- [ ] Error messages are word-for-word identical
- [ ] Return values have identical structure (same keys, same types)
- [ ] Database queries use identical filters (same WHERE conditions)
- [ ] Side effects happen in identical order (commit then refresh, not refresh then commit)

### For Each Endpoint Migrated:

- [ ] Created comparison test (old vs new must match)
- [ ] Test covers happy path (successful case)
- [ ] Test covers error cases (same error messages)
- [ ] Test covers edge cases (empty lists, None values, zero quantities)
- [ ] Test verifies database state is identical
- [ ] Test verifies response format is identical
- [ ] Both endpoints can run side-by-side in production

---

## What To Do If You Catch Yourself Changing Logic

### STOP Immediately

1. **Undo your changes**
   ```bash
   git checkout -- <file>
   ```

2. **Re-read BEHAVIOR_PRESERVATION_GUARANTEE.md**

3. **Start over with copy-paste approach**

4. **If you found a bug or improvement:**
   - Add it to a "Future Improvements" list
   - Create a GitHub issue for it
   - Fix it AFTER migration is complete

---

## Red Flags (Warning Signs)

### 🚩 If you think any of these thoughts, STOP:

- "I can make this more efficient..."
- "This should really use a dictionary instead of if/else..."
- "Let me add validation here..."
- "This calculation looks wrong, let me fix it..."
- "The error message could be more helpful..."
- "I should handle None values better..."
- "This code is duplicated, let me DRY it up..."
- "I can simplify this logic..."

### ✅ Correct thoughts:

- "Where exactly is this code in the existing file?"
- "Did I copy-paste this correctly?"
- "Is the new code byte-for-byte identical to the old code?"
- "Can I prove these produce the same output?"
- "Where should I put the TODO for the bug I found?"

---

## Emergency Reset Protocol

### If Migration Goes Wrong:

**Scenario**: You realize you changed logic instead of just restructuring.

**Solution**:

1. **Immediately rollback**
   ```bash
   git reset --hard HEAD~1  # Undo last commit
   ```

2. **Identify what logic changed**
   - What calculation did you modify?
   - What condition did you change?
   - What validation did you add?

3. **Re-read this file and BEHAVIOR_PRESERVATION_GUARANTEE.md**

4. **Start the migration over with strict copy-paste**

5. **Add the "improvement" you wanted to make to a backlog**
   - Document it in GitHub issue
   - Label it "post-migration-improvement"
   - Fix it AFTER all 92 endpoints are migrated

---

## User Reminder Protocol

### How User Should Remind Claude:

**If Claude starts changing logic, user should say:**

> "STOP. Read CRITICAL_CONSTRAINTS.md. Are you restructuring or rewriting?"

**If Claude writes new logic, user should say:**

> "This looks like new logic, not moved code. Show me where in the existing codebase this exact logic exists."

**If Claude optimizes something, user should say:**

> "I see you improved this. Undo it. Keep the old logic exactly as-is, even if inefficient."

**If Claude fixes a bug, user should say:**

> "That's a bug fix, not a restructure. Add a TODO and keep the bug for now."

**Magic phrase to reset Claude:**

> "COPY-PASTE ONLY. Show me line numbers from existing code that you're copying."

---

## The Migration Mantra

Repeat before every migration task:

> **"I will ONLY move code, NEVER change logic."**
>
> **"I will copy-paste, NEVER rewrite."**
>
> **"I will preserve bugs, fix them later."**
>
> **"I will prove equivalence with tests."**
>
> **"When in doubt, copy-paste."**

---

## Example: Correct vs Incorrect Migration

### ❌ INCORRECT (Changing Logic)

**Existing code** (backend/app/api/tracking.py:950):
```python
# Build external meal data
external_meal_data = {
    "dish_name": request.dish_name,
    "portion_size": request.portion_size,
    "restaurant_name": request.restaurant_name,
    "cuisine_type": request.cuisine_type,
    "calories": request.calories,
    "protein_g": request.protein_g,
    "carbs_g": request.carbs_g,
    "fat_g": request.fat_g,
    "fiber_g": request.fiber_g,
    "logged_at": consumed_at.isoformat()
}
```

**WRONG Migration** (service):
```python
def build_external_meal_data(self, request, consumed_at):
    """❌ WRONG: Restructured the data, added validation, changed field names"""

    # ❌ Added validation (new logic!)
    if request.calories < 0:
        raise ValueError("Calories cannot be negative")

    # ❌ Changed structure (nested object!)
    return {
        "meal_info": {  # ❌ NEW: nested structure
            "dish_name": request.dish_name,
            "portion_size": request.portion_size,
        },
        "source": {  # ❌ NEW: grouped fields
            "restaurant_name": request.restaurant_name,
            "cuisine_type": request.cuisine_type,
        },
        "nutrition": {  # ❌ NEW: grouped macros
            "calories": round(request.calories, 2),  # ❌ NEW: rounding!
            "protein_g": request.protein_g,
            "carbs_g": request.carbs_g,
            "fat_g": request.fat_g,
            "fiber_g": request.fiber_g or 0,  # ❌ NEW: default value!
        },
        "timestamp": consumed_at.isoformat()  # ❌ Changed key name!
    }
```

### ✅ CORRECT (Copy-Paste Only)

**Existing code** (backend/app/api/tracking.py:950):
```python
# Build external meal data
external_meal_data = {
    "dish_name": request.dish_name,
    "portion_size": request.portion_size,
    "restaurant_name": request.restaurant_name,
    "cuisine_type": request.cuisine_type,
    "calories": request.calories,
    "protein_g": request.protein_g,
    "carbs_g": request.carbs_g,
    "fat_g": request.fat_g,
    "fiber_g": request.fiber_g,
    "logged_at": consumed_at.isoformat()
}
```

**CORRECT Migration** (service):
```python
def build_external_meal_data(self, request, consumed_at):
    """✅ CORRECT: Exact copy-paste from tracking.py:950-963"""

    # EXACT same structure, EXACT same fields
    external_meal_data = {
        "dish_name": request.dish_name,  # IDENTICAL
        "portion_size": request.portion_size,  # IDENTICAL
        "restaurant_name": request.restaurant_name,  # IDENTICAL
        "cuisine_type": request.cuisine_type,  # IDENTICAL
        "calories": request.calories,  # IDENTICAL (no rounding!)
        "protein_g": request.protein_g,  # IDENTICAL
        "carbs_g": request.carbs_g,  # IDENTICAL
        "fat_g": request.fat_g,  # IDENTICAL
        "fiber_g": request.fiber_g,  # IDENTICAL (no default!)
        "logged_at": consumed_at.isoformat()  # IDENTICAL key name
    }

    return external_meal_data
```

**Proof they're identical**:
```python
def test_build_external_meal_data_exact_match():
    """Verify service method produces EXACT same output as old API code."""

    # Same input
    request = LogExternalMealRequest(
        dish_name="Chicken Salad",
        portion_size="1 bowl",
        calories=350.5,
        protein_g=30.0,
        # ... all fields
    )
    consumed_at = datetime(2025, 11, 24, 12, 0, 0)

    # Old way (directly in API)
    old_result = {
        "dish_name": request.dish_name,
        "portion_size": request.portion_size,
        "restaurant_name": request.restaurant_name,
        "cuisine_type": request.cuisine_type,
        "calories": request.calories,
        "protein_g": request.protein_g,
        "carbs_g": request.carbs_g,
        "fat_g": request.fat_g,
        "fiber_g": request.fiber_g,
        "logged_at": consumed_at.isoformat()
    }

    # New way (service method)
    service = MealLogService()
    new_result = service.build_external_meal_data(request, consumed_at)

    # MUST be identical
    assert old_result == new_result  # ✅ PASS
```

---

## Summary: Your Safety Net

This document is your safety net. When in doubt:

1. **Read CRITICAL_CONSTRAINTS.md** (this file)
2. **Read BEHAVIOR_PRESERVATION_GUARANTEE.md**
3. **Find existing code location** (file:line)
4. **Copy-paste** (Ctrl+C, Ctrl+V)
5. **Test equivalence** (old == new)
6. **Never change logic**

**Remember**: We're **restructuring** a house (moving furniture to different rooms), not **rebuilding** the house (changing the blueprint).

---

**Last Updated**: 2025-11-24
**Status**: MANDATORY - Read before EVERY migration task
**Violations**: NONE TOLERATED - Migration must restart if logic is changed
