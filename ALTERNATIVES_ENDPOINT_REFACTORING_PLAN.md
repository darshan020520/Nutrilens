# Get Alternatives Endpoint - Complete Refactoring Plan

## Current Issue

**Location:** `RecipeRepository.get_alternatives()` (Lines 234-235)

```python
# ARCHITECTURE VIOLATION: Recipe repository querying user tables!
preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
user_goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
```

**Problem:**
- `RecipeRepository` should ONLY query `recipes` table
- Cross-repository queries violate clean architecture
- Repository pattern says: one repository = one aggregate root

---

## Solution Overview

### Step 1: Service Layer Fetches User Data
`MealPlanServiceV2.get_alternatives_for_meal()` should:
1. Get user preferences from `UserProfileRepository`
2. Get user goal from `UserProfileRepository`
3. Pass them to `RecipeRepository.get_alternatives()`

### Step 2: Repository Only Queries Recipes
`RecipeRepository.get_alternatives()` should:
1. Accept preferences and goal as parameters
2. ONLY query `recipes` table
3. Remove direct DB queries to user tables

---

## Detailed Implementation Plan

### File 1: MealPlanServiceV2 (backend/app/services/meal_plan_service_v2.py)

**Current Code (Lines 429-452):**
```python
async def get_alternatives_for_meal(self, recipe_id: int, user_id: int, count: int = 5) -> List[Dict]:
    # Get original recipe (using repository)
    original = self.recipe_repo.get_by_id(recipe_id)
    if not original:
        logger.warning(f"Recipe {recipe_id} not found")
        return []

    # Delegate to repository for complex logic
    return self.recipe_repo.get_alternatives(original, user_id, count)
```

**New Code:**
```python
async def get_alternatives_for_meal(self, recipe_id: int, user_id: int, count: int = 5) -> List[Dict]:
    """
    Get alternative recipes with similar macros for meal swapping.

    REFACTORED: Now fetches user data via UserProfileRepository first.
    Original: meal_plan_service.py:399-539

    Args:
        recipe_id: Original recipe ID
        user_id: User requesting alternatives
        count: Number of alternatives to return (default 5)

    Returns:
        List of alternative recipes with scores and macro differences
    """
    # Get original recipe (using repository)
    original = self.recipe_repo.get_by_id(recipe_id)
    if not original:
        logger.warning(f"Recipe {recipe_id} not found")
        return []

    # REFACTORED: Fetch user data from UserProfileRepository
    # Instead of letting RecipeRepository query user tables
    preferences = await self.user_profile_repo.get_preferences(user_id)
    user_goal = await self.user_profile_repo.get_active_goal(user_id)

    # Delegate to repository with user data
    return self.recipe_repo.get_alternatives(
        original_recipe=original,
        user_preferences=preferences,
        user_goal=user_goal,
        count=count
    )
```

**Changes:**
1. Line 445 stays the same (get original recipe)
2. Add lines to fetch preferences and goal from `user_profile_repo`
3. Update call to `get_alternatives()` with new parameters

**Dependency Check:**
- `MealPlanServiceV2` already has `user_profile_repo`? **NO!**
- Need to add `IUserProfileRepository` to constructor

---

### File 2: MealPlanServiceV2 Constructor Update

**Current Constructor (Lines 36-55):**
```python
def __init__(
    self,
    meal_plan_repo: IMealPlanRepository,
    meal_log_repo: IMealLogRepository,
    recipe_repo: IRecipeRepository,
    inventory_service: IntelligentInventoryService
):
    self.meal_plan_repo = meal_plan_repo
    self.meal_log_repo = meal_log_repo
    self.recipe_repo = recipe_repo
    self.inventory_service = inventory_service
```

**New Constructor:**
```python
def __init__(
    self,
    meal_plan_repo: IMealPlanRepository,
    meal_log_repo: IMealLogRepository,
    recipe_repo: IRecipeRepository,
    inventory_service: IntelligentInventoryService,
    user_profile_repo: IUserProfileRepository
):
    """
    Initialize service with injected dependencies.

    Args:
        meal_plan_repo: Meal plan repository
        meal_log_repo: Meal log repository
        recipe_repo: Recipe repository
        inventory_service: Inventory service
        user_profile_repo: User profile repository
    """
    self.meal_plan_repo = meal_plan_repo
    self.meal_log_repo = meal_log_repo
    self.recipe_repo = recipe_repo
    self.inventory_service = inventory_service
    self.user_profile_repo = user_profile_repo
```

**Changes:**
1. Add `user_profile_repo: IUserProfileRepository` parameter
2. Assign to `self.user_profile_repo`

---

### File 3: dependencies.py Update

**Current (Lines 169-181):**
```python
def get_meal_plan_service_v2(
    meal_plan_repo: IMealPlanRepository = Depends(get_meal_plan_repository),
    meal_log_repo: IMealLogRepository = Depends(get_meal_log_repository),
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_service: IntelligentInventoryService = Depends(get_inventory_service)
) -> MealPlanServiceV2:

    return MealPlanServiceV2(
        meal_plan_repo=meal_plan_repo,
        meal_log_repo=meal_log_repo,
        recipe_repo=recipe_repo,
        inventory_service=inventory_service
    )
```

**New:**
```python
def get_meal_plan_service_v2(
    meal_plan_repo: IMealPlanRepository = Depends(get_meal_plan_repository),
    meal_log_repo: IMealLogRepository = Depends(get_meal_log_repository),
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_service: IntelligentInventoryService = Depends(get_inventory_service),
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> MealPlanServiceV2:
    """
    Get meal plan service with all repository dependencies.
    REFACTORED: Added user_profile_repo for get_alternatives_for_meal()
    """
    return MealPlanServiceV2(
        meal_plan_repo=meal_plan_repo,
        meal_log_repo=meal_log_repo,
        recipe_repo=recipe_repo,
        inventory_service=inventory_service,
        user_profile_repo=user_profile_repo
    )
```

**Changes:**
1. Add `user_profile_repo` parameter with Depends
2. Pass to MealPlanServiceV2 constructor

---

### File 4: RecipeRepository.get_alternatives() Signature Update

**Current Signature (Line 212-217):**
```python
def get_alternatives(
    self,
    original_recipe: Recipe,
    user_id: int,
    count: int
) -> List[dict]:
```

**New Signature:**
```python
def get_alternatives(
    self,
    original_recipe: Recipe,
    user_preferences: Optional[UserPreference],
    user_goal: Optional[UserGoal],
    count: int
) -> List[dict]:
    """
    Get alternative recipes similar to the given recipe.

    REFACTORED: Now receives user preferences and goal as parameters
    instead of querying them directly (architecture fix).
    Original: meal_plan_service.py:399-539

    Args:
        original_recipe: Original recipe object
        user_preferences: User preferences (from UserProfileRepository)
        user_goal: User goal (from UserProfileRepository)
        count: Number of alternatives to return

    Returns:
        List of alternative recipe dictionaries with scores
    """
```

**Changes:**
1. Remove `user_id: int` parameter
2. Add `user_preferences: Optional[UserPreference]` parameter
3. Add `user_goal: Optional[UserGoal]` parameter
4. Update docstring

---

### File 5: RecipeRepository.get_alternatives() Implementation

**Current Lines 234-235 (TO DELETE):**
```python
# Get user preferences and goal
preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
user_goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
```

**New (Replace lines 234-235):**
```python
# REFACTORED: Preferences and goal passed as parameters
# No longer querying user tables from recipe repository
preferences = user_preferences
goal = user_goal
```

**Changes:**
1. Delete DB queries (lines 234-235)
2. Use parameters instead
3. Rename variables to match rest of code (preferences, goal)

**Update variable references:**
- Line 248: `if preferences and preferences.dietary_type:` ✅ (already correct)
- Line 310: `if user_goal and recipe.goals:` → `if goal and recipe.goals:`
- Line 311: `if user_goal.goal_type.value in recipe.goals:` → `if goal.goal_type.value in recipe.goals:`

---

### File 6: RecipeRepository Imports Cleanup

**Current (Line 15):**
```python
from app.models.database import Recipe, RecipeIngredient, Item, UserPreference, UserGoal
```

**After Refactoring:**
```python
from app.models.database import Recipe, RecipeIngredient, Item, UserPreference, UserGoal
```

**Keep imports** because:
- `UserPreference` type hint in method signature
- `UserGoal` type hint in method signature
- NOT querying them, just receiving as parameters ✅

---

## Implementation Order

1. ✅ Update `MealPlanServiceV2.__init__()` - Add user_profile_repo parameter
2. ✅ Update `dependencies.py` - Inject user_profile_repo
3. ✅ Update `RecipeRepository.get_alternatives()` signature - Change parameters
4. ✅ Update `RecipeRepository.get_alternatives()` body - Remove DB queries, use parameters
5. ✅ Update `MealPlanServiceV2.get_alternatives_for_meal()` - Fetch user data, pass to repository
6. ✅ Test compilation

---

## Database Queries Before/After

### Before:
1. `SELECT * FROM recipes WHERE id = ?` (get original)
2. `SELECT * FROM user_preferences WHERE user_id = ?` ❌ (in RecipeRepository)
3. `SELECT * FROM user_goals WHERE user_id = ? AND is_active = TRUE` ❌ (in RecipeRepository)
4. `SELECT * FROM recipes WHERE id != ?` (get candidates)

**Total: 4 queries (2 architecture violations)**

### After:
1. `SELECT * FROM recipes WHERE id = ?` (get original)
2. `SELECT * FROM user_preferences WHERE user_id = ?` ✅ (in UserProfileRepository)
3. `SELECT * FROM user_goals WHERE user_id = ? AND is_active = TRUE` ✅ (in UserProfileRepository)
4. `SELECT * FROM recipes WHERE id != ?` (get candidates)

**Total: 4 queries (0 architecture violations)**

---

## Breaking Changes

### RecipeRepository.get_alternatives() Signature
**Before:**
```python
get_alternatives(original_recipe, user_id, count)
```

**After:**
```python
get_alternatives(original_recipe, user_preferences, user_goal, count)
```

**Impact:** Only called from `MealPlanServiceV2.get_alternatives_for_meal()` - no other callers

---

## Validation Checklist

- ✅ MealPlanServiceV2 has user_profile_repo injected
- ✅ RecipeRepository ONLY queries recipes table
- ✅ User data fetched from correct repository
- ✅ No breaking changes to API response
- ✅ Response structure unchanged
- ✅ Error handling preserved

---

## Files to Modify

1. `backend/app/services/meal_plan_service_v2.py` - Constructor + get_alternatives_for_meal()
2. `backend/app/dependencies.py` - get_meal_plan_service_v2()
3. `backend/app/repositories/recipe_repository.py` - get_alternatives() signature and body

**Total: 3 files**

---

Ready to implement?
