# MealPlanOptimizer - Complete Refactoring Plan

## Current State Analysis

### Database Operations Found:
1. **UserGoal** - 3 queries (lines 542, 775, 886)
2. **Recipe** - 2 queries (lines 552, 555)
3. **UserInventory** - 1 query (line 783)
4. **RecipeIngredient** - 1 query (line 847 - INSIDE LOOP!)
5. **UserProfile, UserPath, UserPreference** - 3 queries (lines 885-888)

### Existing Repository Coverage:

✅ **IUserProfileRepository** - COMPLETE
- `get_profile()` ✅
- `get_active_goal()` ✅
- `get_path()` ✅
- `get_preferences()` ✅
- `get_all_user_data()` ✅

✅ **IInventoryRepository** - HAS WHAT WE NEED
- `get_all_for_user()` ✅ (line 52) - Returns List[UserInventory]
- Can replace line 783 directly!

✅ **IRecipeRepository** - HAS WHAT WE NEED
- `get_ingredients_by_recipe_id()` ✅ (line 33) - Returns List[RecipeIngredient]
- Can replace line 847 directly!

❌ **IRecipeRepository** - MISSING METHODS FOR FILTERING
- No method for `filter by goal, dietary_type, allergens, prep_time`
- Need to ADD these methods

---

## Critical Finding: DUPLICATE CODE

### Issue: `_get_user_constraints()` is 100% DUPLICATE

**Lines 880-934** are **EXACT DUPLICATE** of `ConstraintBuilderService.build_constraints()`

**Proof:**
```python
# final_meal_optimizer.py:885-888
profile = self.db.query(UserProfile).filter_by(user_id=user_id).first()
goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
path = self.db.query(UserPath).filter_by(user_id=user_id).first()
preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()

# constraint_builder_service.py:47-50 (IDENTICAL!)
profile = await self.user_profile_repo.get_profile(user_id)
goal = await self.user_profile_repo.get_active_goal(user_id)
path = await self.user_profile_repo.get_path(user_id)
preferences = await self.user_profile_repo.get_preferences(user_id)
```

**Solution:** DELETE `_get_user_constraints()` entirely!

---

## Refactoring Strategy

### Phase 1: Add Missing Methods to IRecipeRepository ✅

Need to add to `IRecipeRepository`:

```python
@abstractmethod
async def get_filtered_recipes(
    self,
    user_id: int,
    goal_type: Optional[str] = None,
    dietary_type: Optional[str] = None,
    exclude_allergens: Optional[List[str]] = None,
    max_prep_time: Optional[int] = None
) -> List[Recipe]:
    """
    Get recipes filtered by user preferences and constraints.

    Args:
        user_id: User ID
        goal_type: Filter by goal (muscle_gain, fat_loss, etc.)
        dietary_type: Filter by dietary type (vegetarian, vegan, etc.)
        exclude_allergens: List of allergens to exclude
        max_prep_time: Maximum prep time in minutes

    Returns:
        List of recipes matching filters
    """
    pass

@abstractmethod
async def count_all_recipes(self) -> int:
    """Get total recipe count"""
    pass
```

### Phase 2: Refactor MealPlanOptimizer Constructor ✅

**Before:**
```python
def __init__(self, db_session: Session = None):
    self.db = db_session
```

**After:**
```python
def __init__(
    self,
    recipe_repo: IRecipeRepository,
    inventory_repo: IInventoryRepository,
    user_profile_repo: IUserProfileRepository
):
    self.recipe_repo = recipe_repo
    self.inventory_repo = inventory_repo
    self.user_profile_repo = user_profile_repo
```

### Phase 3: Replace Database Queries ✅

#### Replace 1: `_get_user_constraints()` (DELETE METHOD!)
**Lines 880-934**

**Before:**
```python
def _get_user_constraints(self, user_id):
    profile = self.db.query(UserProfile).filter_by(user_id=user_id).first()
    goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
    path = self.db.query(UserPath).filter_by(user_id=user_id).first()
    preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
    # ... build constraints
```

**After:**
```python
# DELETE THIS METHOD ENTIRELY!
# Caller should pass constraints from ConstraintBuilderService
```

**Update callers:**
```python
# Before
constraints = self._get_user_constraints(user_id)

# After
# Constraints passed from outside (already built by ConstraintBuilderService)
# No change needed - caller already provides constraints parameter!
```

#### Replace 2: `_get_filtered_recipes_fixed()` - Lines 542, 552, 555
**Before:**
```python
goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
total_recipes = self.db.query(Recipe).count()
query = self.db.query(Recipe)
# ... apply filters
```

**After:**
```python
goal = await self.user_profile_repo.get_active_goal(user_id)
total_recipes = await self.recipe_repo.count_all_recipes()
recipes = await self.recipe_repo.get_filtered_recipes(
    user_id=user_id,
    goal_type=goal.goal_type.value if goal else None,
    dietary_type=constraints.dietary_restrictions[0] if constraints.dietary_restrictions else None,
    exclude_allergens=constraints.allergens,
    max_prep_time=constraints.max_prep_time_minutes
)
```

#### Replace 3: `_score_recipes()` - Lines 775, 783, 847
**Before:**
```python
goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()  # DUPLICATE!

inventory_items = self.db.query(UserInventory).filter_by(user_id=user_id).all()
for item in inventory_items:
    user_inventory[item.item_id] = item.quantity_grams

# Inside loop:
recipe_ingredients = self.db.query(RecipeIngredient).filter_by(recipe_id=recipe['id']).all()
```

**After:**
```python
# goal already fetched in _get_filtered_recipes - pass as parameter
# OR fetch once: goal = await self.user_profile_repo.get_active_goal(user_id)

inventory_items = await self.inventory_repo.get_all_for_user(user_id)
for item in inventory_items:
    user_inventory[item.item_id] = item.quantity_grams

# Inside loop:
recipe_ingredients = await self.recipe_repo.get_ingredients_by_recipe_id(recipe['id'])
```

**OPTIMIZATION:** Batch fetch ALL recipe ingredients upfront instead of loop!
```python
# Collect all recipe IDs
recipe_ids = [r['id'] for r in recipes]

# Batch fetch (need new repository method)
all_ingredients = await self.recipe_repo.get_ingredients_for_recipes(recipe_ids)
# Returns: {recipe_id: [RecipeIngredient, ...], ...}

# Then in loop:
recipe_ingredients = all_ingredients.get(recipe['id'], [])
```

### Phase 4: Update dependencies.py ✅

**Before:**
```python
def get_meal_plan_optimizer(db: Session = Depends(get_db)) -> MealPlanOptimizer:
    return MealPlanOptimizer(db)
```

**After:**
```python
def get_meal_plan_optimizer(
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> MealPlanOptimizer:
    return MealPlanOptimizer(
        recipe_repo=recipe_repo,
        inventory_repo=inventory_repo,
        user_profile_repo=user_profile_repo
    )
```

---

## Files to Modify

### 1. IRecipeRepository (Interface)
**File:** `backend/app/repositories/interfaces/recipe_repository.py`

**Add methods:**
- `get_filtered_recipes()` - Filter recipes by goal/dietary/allergens/prep_time
- `count_all_recipes()` - Get total recipe count
- `get_ingredients_for_recipes()` - Batch fetch ingredients (OPTIMIZATION)

### 2. RecipeRepository (Implementation)
**File:** `backend/app/repositories/recipe_repository.py`

**Implement new methods**

### 3. MealPlanOptimizer
**File:** `backend/app/services/final_meal_optimizer.py`

**Changes:**
- Update `__init__()` to take repositories instead of db
- Delete `_get_user_constraints()` method entirely (lines 880-934)
- Update `_get_filtered_recipes_fixed()` to use `recipe_repo` and `user_profile_repo`
- Update `_score_recipes()` to use `inventory_repo` and `recipe_repo`
- Make all methods async where needed

### 4. dependencies.py
**File:** `backend/app/dependencies.py`

**Update:**
- `get_meal_plan_optimizer()` to inject repositories

---

## Breaking Changes

### MealPlanOptimizer.optimize() might need to be async
Currently: `def optimize(...)`
After: `async def optimize(...)` (if we use await inside)

**Impact:** All callers need to use `await optimizer.optimize(...)`

**Current caller:** `meal_plan_orchestrator.py:83`
```python
# Before
meal_plan = self.optimizer.optimize(...)

# After
meal_plan = await self.optimizer.optimize(...)
```

---

## Performance Improvements

### Before:
- 7 database queries per optimization
- RecipeIngredient query INSIDE LOOP (N+1 problem!)

### After:
- 3-4 database queries total
- Batch fetch all ingredients upfront
- Use repository caching where applicable

---

## Testing Checklist

- [ ] Optimizer can fetch filtered recipes
- [ ] Optimizer can score recipes with inventory
- [ ] Optimizer no longer calls _get_user_constraints
- [ ] Endpoint still works (constraints passed from ConstraintBuilderService)
- [ ] No database session passed to optimizer
- [ ] All repository methods return correct data

---

## Implementation Order

1. ✅ Add methods to IRecipeRepository interface
2. ✅ Implement methods in RecipeRepository
3. ✅ Delete `_get_user_constraints()` from optimizer
4. ✅ Refactor optimizer constructor
5. ✅ Update `_get_filtered_recipes_fixed()` to use repositories
6. ✅ Update `_score_recipes()` to use repositories
7. ✅ Make optimizer.optimize() async if needed
8. ✅ Update orchestrator to await optimizer.optimize()
9. ✅ Update dependencies.py
10. ✅ Test the flow

---

## Next Action

Should I proceed with:
1. Adding methods to IRecipeRepository first?
2. Or start with deleting `_get_user_constraints()` (easiest win)?

What would you prefer?
