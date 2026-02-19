# GroceryService - Complete Refactoring Plan

## Current State Analysis

### Database Operations Found in `grocery_service.py`:

1. **RecipeIngredient** - Line 75-77 (BATCH QUERY)
   ```python
   recipe_ingredients = (
       self.db.query(RecipeIngredient)
       .filter(RecipeIngredient.recipe_id.in_(recipe_ids))
       .all()
   )
   ```

2. **Item** - Line 85 (BATCH QUERY)
   ```python
   items_map = {
       item.id: item
       for item in self.db.query(Item).filter(Item.id.in_(item_ids)).all()
   }
   ```

3. **UserInventory** - Lines 92-94 (BATCH QUERY)
   ```python
   inventory_map = {
       inv.item_id: inv.quantity_grams
       for inv in self.db.query(UserInventory)
       .filter(UserInventory.user_id == user_id, UserInventory.item_id.in_(item_ids))
       .all()
   }
   ```

### Existing Repository Coverage

✅ **IRecipeRepository** - HAS BATCH METHOD
- `get_ingredients_for_recipes(recipe_ids)` ✅ (Added during optimizer refactoring)
- Returns: `Dict[int, List[RecipeIngredient]]`
- **Can replace lines 75-77 directly!**

❌ **IInventoryRepository** - MISSING BATCH METHOD
- Has: `get_all_for_user(user_id)` - Returns ALL inventory for user
- Missing: `get_by_item_ids(user_id, item_ids)` - Returns inventory filtered by item IDs
- **Need to add new method**

❌ **No Item Repository Interface**
- Item queries are in `infrastructure/normalization/repositories/item_repository.py`
- This is NOT part of clean architecture (it's in infrastructure layer)
- Items are simple lookups - can batch fetch directly from RecipeIngredient relationships
- **Solution: Use eager loading on RecipeIngredient.item relationship**

---

## Critical Finding: NO ITEM REPOSITORY IN CLEAN ARCHITECTURE

### Issue: Items are NOT in Repository Layer

**Current state:**
- `ItemRepository` exists in `infrastructure/normalization/repositories/`
- This is for OCR normalization (vector search, caching)
- NOT part of the clean architecture (API → Orchestrator → Service → Repository → DB)

**Solutions:**

**Option 1: Use Eager Loading (RECOMMENDED)**
- When fetching RecipeIngredient, eager load the Item relationship
- No need for separate Item query

**Before:**
```python
# Line 75-77: Fetch ingredients
recipe_ingredients = self.db.query(RecipeIngredient).filter(...).all()

# Line 82-86: Fetch items separately
item_ids = list({ri.item_id for ri in recipe_ingredients})
items_map = {item.id: item for item in self.db.query(Item).filter(Item.id.in_(item_ids)).all()}
```

**After:**
```python
# Fetch ingredients WITH items eager loaded
all_ingredients_map = await self.recipe_repo.get_ingredients_for_recipes(recipe_ids)
# RecipeIngredient.item is already loaded via joinedload in repository!

# No separate Item query needed!
```

**Option 2: Create IItemRepository Interface**
- Add new interface `IItemRepository` with `get_by_ids(item_ids)` method
- More overhead, but cleaner separation
- **NOT RECOMMENDED** - adds complexity for simple lookups

---

## Refactoring Strategy

### Phase 1: Add Missing Method to IInventoryRepository ✅

Need to add to `IInventoryRepository`:

```python
@abstractmethod
async def get_by_item_ids(
    self,
    user_id: int,
    item_ids: List[int]
) -> Dict[int, UserInventory]:
    """
    BATCH OPERATION: Get inventory for multiple items in ONE query.

    Solves N+1 query problem - instead of N queries (one per item),
    this does 1 query using WHERE item_id IN (...).

    Args:
        user_id: User ID
        item_ids: List of item IDs to fetch inventory for

    Returns:
        Dict mapping item_id to UserInventory:
        {
            5: UserInventory(item_id=5, quantity_grams=500, ...),
            12: UserInventory(item_id=12, quantity_grams=200, ...),
            ...
        }

        If user has no inventory for an item, it won't be in the dict.
        Returns empty dict if item_ids is empty or None.
    """
    pass
```

### Phase 2: Refactor GroceryService Constructor ✅

**Before:**
```python
def __init__(self, db: Session):
    self.db = db
```

**After:**
```python
def __init__(
    self,
    recipe_repo: IRecipeRepository,
    inventory_repo: IInventoryRepository
):
    self.recipe_repo = recipe_repo
    self.inventory_repo = inventory_repo
```

### Phase 3: Update `calculate_for_plan()` Method ✅

#### Replace 1: RecipeIngredient Query (Lines 75-77)

**Before:**
```python
recipe_ingredients = (
    self.db.query(RecipeIngredient)
    .filter(RecipeIngredient.recipe_id.in_(recipe_ids))
    .all()
)
```

**After:**
```python
# Batch fetch all ingredients for all recipes
all_ingredients_map = await self.recipe_repo.get_ingredients_for_recipes(recipe_ids)

# Flatten to list (original code expects a list)
recipe_ingredients = [
    ing
    for ingredients in all_ingredients_map.values()
    for ing in ingredients
]
```

#### Replace 2: Item Query (Lines 82-86) - REMOVE ENTIRELY

**Before:**
```python
item_ids = list({ri.item_id for ri in recipe_ingredients})
items_map = {
    item.id: item
    for item in self.db.query(Item).filter(Item.id.in_(item_ids)).all()
}
```

**After:**
```python
# NO QUERY NEEDED!
# RecipeIngredient.item is already eager-loaded via joinedload in repository
# Access item directly via: recipe_ingredient.item
```

**Update lines 103-110 to use eager-loaded relationship:**
```python
# Before
if ri.item_id not in grocery_list:
    item = items_map.get(ri.item_id)
    grocery_list[ri.item_id] = {
        "item_id": ri.item_id,
        "item_name": item.canonical_name if item else f"Item {ri.item_id}",
        "category": self._normalize_category(item.category if item else "other"),
        "unit": item.unit if item else "g",
        ...
    }

# After
if ri.item_id not in grocery_list:
    item = ri.item  # Access eager-loaded relationship
    grocery_list[ri.item_id] = {
        "item_id": ri.item_id,
        "item_name": item.canonical_name if item else f"Item {ri.item_id}",
        "category": self._normalize_category(item.category if item else "other"),
        "unit": item.unit if item else "g",
        ...
    }
```

#### Replace 3: UserInventory Query (Lines 92-94)

**Before:**
```python
inventory_map = {
    inv.item_id: inv.quantity_grams
    for inv in self.db.query(UserInventory)
    .filter(UserInventory.user_id == user_id, UserInventory.item_id.in_(item_ids))
    .all()
}
```

**After:**
```python
# Collect item IDs from recipe ingredients
item_ids = list({ri.item_id for ri in recipe_ingredients if ri.item_id})

# Batch fetch inventory
inventory_records = await self.inventory_repo.get_by_item_ids(user_id, item_ids)

# Convert to map (item_id -> quantity_grams)
inventory_map = {
    item_id: inv.quantity_grams
    for item_id, inv in inventory_records.items()
}
```

### Phase 4: Make `calculate_for_plan()` Async ✅

Since we're using `await` for repository calls, the method must be async:

```python
async def calculate_for_plan(self, meal_plan: Dict, user_id: int) -> Dict[str, Any]:
    """
    Build a grocery list from a meal plan.

    REFACTORED: Now uses repositories instead of direct DB queries.
    Original: planning_agent.py:265-362
    """
```

### Phase 5: Update Callers ✅

**File:** `backend/app/orchestrators/meal_plan_orchestrator.py`

**Line 104** - Add `await`:
```python
# Before
meal_plan['grocery_list'] = self.grocery_service.calculate_for_plan(
    meal_plan['week_plan'],
    user_id
)

# After
meal_plan['grocery_list'] = await self.grocery_service.calculate_for_plan(
    meal_plan['week_plan'],
    user_id
)
```

### Phase 6: Update dependencies.py ✅

**Before:**
```python
# GroceryService might not even be in dependencies.py
# It's created directly in orchestrator
```

**After:**
```python
def get_grocery_service(
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository)
) -> GroceryService:
    """
    Get grocery service instance with repository dependencies.
    REFACTORED: Now injects repositories instead of raw DB session.
    """
    return GroceryService(
        recipe_repo=recipe_repo,
        inventory_repo=inventory_repo
    )
```

**Update orchestrator dependency:**
```python
# Before
def get_meal_plan_orchestrator(
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    optimizer: MealPlanOptimizer = Depends(get_meal_plan_optimizer),
    grocery_service: GroceryService = ???,  # How is this created?
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> MealPlanOrchestrator:
    ...

# After
def get_meal_plan_orchestrator(
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    optimizer: MealPlanOptimizer = Depends(get_meal_plan_optimizer),
    grocery_service: GroceryService = Depends(get_grocery_service),  # ✅ Now injected
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> MealPlanOrchestrator:
    ...
```

---

## Files to Modify

### 1. IInventoryRepository (Interface)
**File:** `backend/app/repositories/interfaces/inventory_repository.py`

**Add method:**
- `get_by_item_ids(user_id, item_ids)` - Batch fetch inventory by item IDs

**Location:** Add after line 115 (after `get_all_inventory_for_item`)

### 2. InventoryRepository (Implementation)
**File:** `backend/app/repositories/inventory_repository.py`

**Implement:**
- `get_by_item_ids()` method

### 3. GroceryService
**File:** `backend/app/services/grocery_service.py`

**Changes:**
- Update `__init__()` to take repositories instead of db
- Make `calculate_for_plan()` async
- Update line 75-77: Use `recipe_repo.get_ingredients_for_recipes()`
- Delete lines 82-86: Remove Item query (use eager loading)
- Update lines 92-94: Use `inventory_repo.get_by_item_ids()`
- Update lines 103-110: Use `ri.item` instead of `items_map.get(ri.item_id)`
- Remove `from sqlalchemy.orm import Session` import
- Remove `from app.models.database import RecipeIngredient, Item, UserInventory` imports

### 4. MealPlanOrchestrator
**File:** `backend/app/orchestrators/meal_plan_orchestrator.py`

**Update:**
- Line 104: Add `await` to `self.grocery_service.calculate_for_plan()`

### 5. dependencies.py
**File:** `backend/app/dependencies.py`

**Add:**
- `get_grocery_service()` function to inject repositories

**Update:**
- `get_meal_plan_orchestrator()` to inject `GroceryService` via Depends

---

## Breaking Changes

### GroceryService.calculate_for_plan() is now async

**Before:**
```python
grocery_list = self.grocery_service.calculate_for_plan(meal_plan, user_id)
```

**After:**
```python
grocery_list = await self.grocery_service.calculate_for_plan(meal_plan, user_id)
```

**Impact:** All callers need to use `await`

**Current caller:** `meal_plan_orchestrator.py:104`

---

## Critical Validation Checklist

### ✅ MUST NOT BREAK:
1. Grocery list structure (items, categorized, total_items, items_to_buy, estimated_cost)
2. Categorization logic (_categorize_grocery_list, _normalize_category)
3. Quantity calculations (to_buy = needed - available)
4. Empty plan handling (return valid empty response)
5. Error handling (return valid empty response on exception)

### ✅ RETURN TYPE CONFIRMATION:
```python
# MUST ALWAYS RETURN THIS STRUCTURE:
{
    "items": Dict[str, Dict],  # {item_id: {item_name, category, unit, quantity_needed, quantity_available, to_buy}}
    "categorized": Dict[str, List[Dict]],  # {category: [items]}
    "total_items": int,
    "items_to_buy": int,
    "estimated_cost": Optional[float]
}
```

### ✅ EAGER LOADING VERIFICATION:
- Check that `IRecipeRepository.get_ingredients_for_recipes()` uses `joinedload(RecipeIngredient.item)`
- If NOT, add it to the implementation

**File:** `backend/app/repositories/recipe_repository.py`

**Check line ~200 (get_ingredients_for_recipes implementation):**
```python
# MUST HAVE THIS:
ingredients = self.db.query(RecipeIngredient).options(
    joinedload(RecipeIngredient.item)  # ✅ This loads Item relationship
).filter(
    RecipeIngredient.recipe_id.in_(recipe_ids)
).all()
```

---

## Performance Improvements

### Before:
- 3 database queries (already batch queries, no N+1 problem)
- Direct DB session dependency

### After:
- 2 database queries (removed Item query via eager loading)
- Repository pattern with dependency injection
- Same performance, better architecture

---

## Implementation Order

1. ✅ Check `RecipeRepository.get_ingredients_for_recipes()` for eager loading
2. ✅ Add `get_by_item_ids()` to IInventoryRepository interface
3. ✅ Implement `get_by_item_ids()` in InventoryRepository
4. ✅ Refactor GroceryService constructor
5. ✅ Make `calculate_for_plan()` async
6. ✅ Replace RecipeIngredient query with repository call
7. ✅ Remove Item query (use eager loading)
8. ✅ Replace UserInventory query with repository call
9. ✅ Update orchestrator to await calculate_for_plan()
10. ✅ Add `get_grocery_service()` to dependencies.py
11. ✅ Update `get_meal_plan_orchestrator()` to inject GroceryService
12. ✅ Test the flow

---

## Next Action

Should I proceed with:
1. Checking `RecipeRepository.get_ingredients_for_recipes()` for eager loading first?
2. Or start with adding `get_by_item_ids()` to IInventoryRepository?

What would you prefer?