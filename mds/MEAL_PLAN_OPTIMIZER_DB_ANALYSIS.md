# MealPlanOptimizer Database Access Analysis

## Summary
The MealPlanOptimizer has **7 direct database queries** across **5 different tables**:
- UserGoal (2 queries)
- Recipe (2 queries)
- UserInventory (1 query)
- RecipeIngredient (1 query)
- UserProfile, UserPath, UserPreference (3 queries - same as ConstraintBuilder)

---

## Database Operations by Method

### 1. `_get_filtered_recipes_fixed()` - Lines 534-685
**Purpose:** Filter recipes based on user preferences and constraints

**DB Queries:**
```python
# Line 542: Get user goal
goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()

# Line 552: Count all recipes
total_recipes = self.db.query(Recipe).count()

# Line 555: Query recipes with filters
query = self.db.query(Recipe)
# Then applies filters: goal_aligned_for, dietary_type, allergens, max_prep_time
```

**Tables Accessed:**
- `UserGoal` - Get user's goal type for recipe filtering
- `Recipe` - Fetch and filter recipes

**Data Retrieved:**
- User's goal_type (muscle_gain, fat_loss, etc.)
- Recipe list filtered by: goal alignment, dietary restrictions, allergens, prep time

---

### 2. `_score_recipes()` - Lines 770-878
**Purpose:** Score recipes based on user preferences and inventory coverage

**DB Queries:**
```python
# Line 775: Get user goal (DUPLICATE - already fetched in _get_filtered_recipes_fixed)
goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()

# Line 783: Get user inventory if not provided
inventory_items = self.db.query(UserInventory).filter_by(user_id=user_id).all()

# Line 847: Get recipe ingredients for inventory coverage calculation
recipe_ingredients = self.db.query(RecipeIngredient).filter_by(recipe_id=recipe['id']).all()
```

**Tables Accessed:**
- `UserGoal` - Get goal type for scoring (DUPLICATE)
- `UserInventory` - Get user's current inventory items and quantities
- `RecipeIngredient` - Get ingredients for each recipe to calculate inventory coverage

**Data Retrieved:**
- User's goal_type
- User's inventory items (item_id, quantity_grams)
- Recipe ingredients (item_id, quantity_grams) for coverage calculation

---

### 3. `_get_user_constraints()` - Lines 880-934
**Purpose:** Build optimization constraints from user profile data

**DB Queries:**
```python
# Line 885-888: Get ALL user profile data (EXACT DUPLICATE of ConstraintBuilderService)
profile = self.db.query(UserProfile).filter_by(user_id=user_id).first()
goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
path = self.db.query(UserPath).filter_by(user_id=user_id).first()
preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
```

**Tables Accessed:**
- `UserProfile` - BMR, TDEE, goal_calories
- `UserGoal` - macro_targets, is_active
- `UserPath` - meals_per_day
- `UserPreference` - dietary_type, allergies

**Data Retrieved:**
- Same as ConstraintBuilderService (see constraint_builder_service.py:47-50)

**ISSUE:** This is a **COMPLETE DUPLICATE** of ConstraintBuilderService logic!

---

## Summary of Tables and Access Patterns

| Table | Queries | Lines | Purpose |
|-------|---------|-------|---------|
| **UserGoal** | 3 | 542, 775, 886 | Get goal type for filtering/scoring |
| **Recipe** | 2 | 552, 555 | Fetch and count recipes |
| **UserInventory** | 1 | 783 | Get user's inventory items |
| **RecipeIngredient** | 1 | 847 | Get recipe ingredients |
| **UserProfile** | 1 | 885 | Get user profile (duplicate) |
| **UserPath** | 1 | 887 | Get meal settings (duplicate) |
| **UserPreference** | 1 | 888 | Get dietary preferences (duplicate) |

---

## Repositories Needed

### 1. **IRecipeRepository** (ALREADY EXISTS!)
**Location:** `backend/app/repositories/interfaces/recipe_repository.py`

Let me check what methods it already has:
```python
# Need to verify if it has:
- get_all_recipes() → for line 555
- count_recipes() → for line 552
- filter_by_goal() → for goal filtering
- filter_by_dietary_type() → for dietary filtering
- get_by_allergens() → for allergen filtering
```

### 2. **IUserProfileRepository** (ALREADY CREATED!)
**We just created this!**

Methods available:
- `get_profile(user_id)` ✅
- `get_active_goal(user_id)` ✅
- `get_path(user_id)` ✅
- `get_preferences(user_id)` ✅
- `get_all_user_data(user_id)` ✅

**Usage:**
- Replace lines 885-888 → `user_data = await user_profile_repo.get_all_user_data(user_id)`
- Replace lines 542, 775 → `goal = await user_profile_repo.get_active_goal(user_id)`

### 3. **IInventoryRepository** (ALREADY EXISTS!)
**Location:** `backend/app/repositories/interfaces/inventory_repository.py`

Let me check what methods it has:
```python
# Need to verify if it has:
- get_user_inventory(user_id) → for line 783
```

### 4. **IRecipeIngredientRepository** (NEW - might be needed)
**OR** add to IRecipeRepository:
```python
# Option A: New repository
class IRecipeIngredientRepository:
    def get_by_recipe_id(recipe_id) -> List[RecipeIngredient]

# Option B: Add to IRecipeRepository
class IRecipeRepository:
    def get_ingredients(recipe_id) -> List[RecipeIngredient]  # ← Add this
```

---

## Critical Issues Found

### Issue 1: **DUPLICATE QUERY - UserGoal queried 3 times**
```python
Line 542: goal = self.db.query(UserGoal).filter_by(user_id, is_active=True).first()
Line 775: goal = self.db.query(UserGoal).filter_by(user_id, is_active=True).first()  # DUPLICATE!
Line 886: goal = self.db.query(UserGoal).filter_by(user_id, is_active=True).first()  # DUPLICATE!
```

**Fix:** Query once and pass as parameter OR use repository caching

### Issue 2: **DUPLICATE LOGIC - _get_user_constraints() is identical to ConstraintBuilderService**
Lines 880-934 are **EXACT DUPLICATE** of `constraint_builder_service.py:34-94`

**Fix:** Remove `_get_user_constraints()` method entirely, inject `ConstraintBuilderService` instead

### Issue 3: **RecipeIngredient query inside loop (line 847)**
This query runs **for every recipe being scored** - could be hundreds of queries!

**Fix:**
- Batch fetch all recipe ingredients upfront
- OR add to recipe data when fetching recipes
- OR use repository with JOIN optimization

---

## Refactoring Strategy

### Phase 1: Use Existing Repositories ✅
1. **UserProfileRepository** - Replace lines 542, 775, 885-888
2. **RecipeRepository** - Replace lines 552, 555 (need to check existing methods)
3. **InventoryRepository** - Replace line 783 (need to check existing methods)

### Phase 2: Remove Duplicate Logic ✅
1. **Remove `_get_user_constraints()`** - Use `ConstraintBuilderService` instead
2. **Cache UserGoal query** - Query once, reuse result

### Phase 3: Optimize RecipeIngredient Access
1. **Check RecipeRepository** - Does it already JOIN ingredients?
2. **If not:** Add batch method to fetch ingredients for multiple recipes
3. **OR:** Create RecipeIngredientRepository

---

## Next Steps

1. ✅ Check existing RecipeRepository interface
2. ✅ Check existing InventoryRepository interface
3. ✅ Determine if we need RecipeIngredientRepository
4. ✅ Refactor MealPlanOptimizer constructor to inject repositories
5. ✅ Update all DB queries to use repositories
6. ✅ Remove _get_user_constraints() method
7. ✅ Update dependencies.py to wire repositories
