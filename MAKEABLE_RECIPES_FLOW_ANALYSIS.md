# Makeable Recipes Flow - Complete Analysis

## Issue Summary

**PROBLEM FOUND:** The backend returns a different structure than what the frontend expects!

### Frontend Expects:
```typescript
{
  count: number,
  fully_makeable: Recipe[],      // ❌ NOT PROVIDED by backend
  partially_makeable: Recipe[]   // ❌ NOT PROVIDED by backend
}
```

### Backend Actually Returns:
```python
{
  "count": len(recipes),
  "recipes": recipes,           # ✅ Single flat list
  "message": "..."
}
```

---

## Detailed Flow Analysis

### 1. Frontend Call Chain

**Component:** `frontend/src/app/dashboard/inventory/components/MakeableRecipes.tsx`
```typescript
// Line 18-21
import { useMakeableRecipes } from "../hooks/useInventory";

export default function MakeableRecipes() {
  const { data, isLoading, error } = useMakeableRecipes(20);

  // Line 55 - Destructures expected structure
  const { fully_makeable, partially_makeable, count } = data;
  //       ^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^
  //       These keys don't exist in backend response!
```

**Hook:** `frontend/src/app/dashboard/inventory/hooks/useInventory.ts`
```typescript
// Lines 123-132
export function useMakeableRecipes(limit: number = 10) {
  return useQuery({
    queryKey: ["inventory", "makeable-recipes", limit],
    queryFn: async () => {
      const response = await api.get(`/inventory/makeable-recipes?limit=${limit}`);
      return response.data;  // Returns backend response as-is
    },
    staleTime: 5 * 60 * 1000,
  });
}
```

**Expected Type:** `frontend/src/app/dashboard/inventory/types.ts`
```typescript
// Lines 141-148
export interface MakeableRecipe {
  recipe_id: number;
  name: string;
  can_make: boolean;
  missing_ingredients: string[];
  available_ingredients: string[];
  estimated_servings: number;
}
```

---

### 2. Backend API Endpoint

**Endpoint:** `backend/app/api/inventory.py`
```python
# Lines 244-258
@router.get("/makeable-recipes")
def get_makeable_recipes(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recipes user can make with current inventory"""
    service = IntelligentInventoryService(db)
    recipes = service.get_makeable_recipes(current_user.id, limit)

    return {
        "count": len(recipes),
        "recipes": recipes,  # ❌ Should be split into fully_makeable and partially_makeable
        "message": f"You can make {len(recipes)} recipes with your current inventory"
    }
```

---

### 3. Backend Service Logic

**Service:** `backend/app/services/inventory_service.py`

**Main Function:** `get_makeable_recipes()` (Lines 664-698)
```python
def get_makeable_recipes(self, user_id: int, limit: int = 10) -> List[Dict]:
    """
    Find all recipes the user can make with current inventory
    This is crucial for AI meal planning
    """
    # Get all recipes
    all_recipes = self.db.query(Recipe).all()
    makeable = []

    for recipe in all_recipes:
        availability = self.check_recipe_availability(user_id, recipe.id)

        if availability['can_make']:
            # ✅ Fully makeable
            makeable.append({
                'recipe_id': recipe.id,
                'title': recipe.title,
                'prep_time': recipe.prep_time_min,
                'goals': recipe.goals,
                'macros': recipe.macros_per_serving
            })
        elif availability['coverage_percentage'] >= 80:
            # ⚠️ Partially makeable (80%+ coverage)
            makeable.append({
                'recipe_id': recipe.id,
                'title': recipe.title,
                'prep_time': recipe.prep_time_min,
                'goals': recipe.goals,
                'macros': recipe.macros_per_serving,
                'note': f"Missing: {', '.join([m['item'] for m in availability['missing_items'][:2]])}"
            })

    # Sort by prep time
    makeable.sort(key=lambda x: x.get('prep_time', 999))

    return makeable[:limit]  # ❌ Returns flat list, not categorized
```

**Helper Function:** `check_recipe_availability()` (Lines 597-662)
```python
def check_recipe_availability(self, user_id: int, recipe_id: int) -> Dict:
    """
    Check if user has ingredients for a recipe
    Returns detailed availability report for AI planning
    """
    recipe = self.db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        return {'available': False, 'reason': 'Recipe not found'}

    ingredients = self.db.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id == recipe_id
    ).all()

    availability = {
        'recipe': recipe.title,
        'can_make': True,                    # ✅ Boolean flag
        'missing_items': [],                 # ✅ List of missing
        'insufficient_items': [],            # ✅ List of insufficient
        'available_items': [],               # ✅ List of available
        'coverage_percentage': 0             # ✅ Percentage (0-100)
    }

    total_ingredients = 0
    available_count = 0

    for ingredient in ingredients:
        if ingredient.is_optional:
            continue  # ✅ Skips optional ingredients

        total_ingredients += 1

        # Check inventory
        inventory_item = self.db.query(UserInventory).filter(
            and_(
                UserInventory.user_id == user_id,
                UserInventory.item_id == ingredient.item_id
            )
        ).first()

        item = self.db.query(Item).filter(Item.id == ingredient.item_id).first()

        if not inventory_item:
            # ❌ Item not in inventory
            availability['missing_items'].append({
                'item': item.canonical_name,
                'required': ingredient.quantity_grams
            })
            availability['can_make'] = False
        elif inventory_item.quantity_grams < ingredient.quantity_grams:
            # ⚠️ Item insufficient quantity
            availability['insufficient_items'].append({
                'item': item.canonical_name,
                'required': ingredient.quantity_grams,
                'available': inventory_item.quantity_grams,
                'shortage': ingredient.quantity_grams - inventory_item.quantity_grams
            })
            availability['can_make'] = False
        else:
            # ✅ Item available with sufficient quantity
            availability['available_items'].append({
                'item': item.canonical_name,
                'required': ingredient.quantity_grams,
                'available': inventory_item.quantity_grams
            })
            available_count += 1

    # Calculate coverage percentage
    availability['coverage_percentage'] = (
        (available_count / total_ingredients * 100)
        if total_ingredients > 0 else 0
    )

    return availability
```

---

## Issues Identified

### 🔴 Issue 1: Response Structure Mismatch

**Backend returns:**
```json
{
  "count": 10,
  "recipes": [
    {
      "recipe_id": 1,
      "title": "Chicken Salad",
      "prep_time": 15,
      "goals": ["fat_loss"],
      "macros": {...}
    },
    ...
  ],
  "message": "You can make 10 recipes..."
}
```

**Frontend expects:**
```json
{
  "count": 10,
  "fully_makeable": [
    {
      "recipe_id": 1,
      "recipe_name": "Chicken Salad",      // ❌ Key mismatch: "title" vs "recipe_name"
      "prep_time_minutes": 15,              // ❌ Key mismatch: "prep_time" vs "prep_time_minutes"
      "description": "...",                 // ❌ Missing
      "available_ingredients": 5,           // ❌ Missing
      "total_ingredients": 5,               // ❌ Missing
      "available_ingredient_names": [...],  // ❌ Missing
      "servings": 2,                        // ❌ Missing
      "match_percentage": 100               // ❌ Missing
    }
  ],
  "partially_makeable": [
    {
      "recipe_id": 2,
      "recipe_name": "Pasta",
      "match_percentage": 80,               // ❌ Missing
      "missing_ingredient_names": [...]     // ❌ Missing
    }
  ]
}
```

---

### 🔴 Issue 2: Missing Fields in Backend Response

The backend service returns:
```python
{
    'recipe_id': recipe.id,
    'title': recipe.title,              # ❌ Should be "recipe_name"
    'prep_time': recipe.prep_time_min,  # ❌ Should be "prep_time_minutes"
    'goals': recipe.goals,
    'macros': recipe.macros_per_serving
}
```

But frontend needs:
```typescript
{
  recipe_id: number;
  recipe_name: string;                        // ❌ Missing
  description: string;                        // ❌ Missing
  prep_time_minutes: number;                  // ❌ Missing
  servings: number;                           // ❌ Missing
  available_ingredients: number;              // ❌ Missing
  total_ingredients: number;                  // ❌ Missing
  available_ingredient_names: string[];       // ❌ Missing
  missing_ingredient_names?: string[];        // ❌ Missing
  match_percentage: number;                   // ❌ Missing
}
```

---

### 🔴 Issue 3: No Categorization

Backend returns a **flat list** with mixed fully/partially makeable recipes.

Frontend expects **two separate arrays**:
- `fully_makeable`: Recipes with 100% ingredient match
- `partially_makeable`: Recipes with 80-99% ingredient match

---

### 🔴 Issue 4: Logic Issues in Service

**Problem 1:** Partially makeable threshold is hardcoded to 80%
```python
elif availability['coverage_percentage'] >= 80:
    # Hardcoded 80% - should be configurable
```

**Problem 2:** Missing data from `check_recipe_availability()` is not used
```python
# check_recipe_availability returns:
{
    'missing_items': [...],      # ✅ Available
    'insufficient_items': [...], # ✅ Available
    'available_items': [...]     # ✅ Available
}

# But get_makeable_recipes only uses:
if availability['can_make']:  # Just boolean, doesn't extract item names
```

**Problem 3:** No sorting by match percentage
```python
# Currently sorts by prep_time only
makeable.sort(key=lambda x: x.get('prep_time', 999))

# Should also consider:
# - coverage_percentage (prioritize higher matches)
# - user's dietary goals
# - recipe difficulty
```

---

## Required Fixes

### Fix 1: Update Backend Response Structure

**File:** `backend/app/api/inventory.py`

**Current Code (Lines 244-258):**
```python
@router.get("/makeable-recipes")
def get_makeable_recipes(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recipes user can make with current inventory"""
    service = IntelligentInventoryService(db)
    recipes = service.get_makeable_recipes(current_user.id, limit)

    return {
        "count": len(recipes),
        "recipes": recipes,
        "message": f"You can make {len(recipes)} recipes with your current inventory"
    }
```

**Required Change:**
```python
@router.get("/makeable-recipes")
def get_makeable_recipes(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recipes user can make with current inventory"""
    service = IntelligentInventoryService(db)
    result = service.get_makeable_recipes(current_user.id, limit)

    # Service should now return: {fully_makeable: [...], partially_makeable: [...]}
    return {
        "count": len(result['fully_makeable']) + len(result['partially_makeable']),
        "fully_makeable": result['fully_makeable'],
        "partially_makeable": result['partially_makeable']
    }
```

---

### Fix 2: Update Service to Return Categorized Results

**File:** `backend/app/services/inventory_service.py`

**Current Code (Lines 664-698):**
```python
def get_makeable_recipes(self, user_id: int, limit: int = 10) -> List[Dict]:
    """Find all recipes the user can make with current inventory"""
    all_recipes = self.db.query(Recipe).all()
    makeable = []

    for recipe in all_recipes:
        availability = self.check_recipe_availability(user_id, recipe.id)

        if availability['can_make']:
            makeable.append({
                'recipe_id': recipe.id,
                'title': recipe.title,
                'prep_time': recipe.prep_time_min,
                'goals': recipe.goals,
                'macros': recipe.macros_per_serving
            })
        elif availability['coverage_percentage'] >= 80:
            makeable.append({
                'recipe_id': recipe.id,
                'title': recipe.title,
                'prep_time': recipe.prep_time_min,
                'goals': recipe.goals,
                'macros': recipe.macros_per_serving,
                'note': f"Missing: {', '.join([m['item'] for m in availability['missing_items'][:2]])}"
            })

    makeable.sort(key=lambda x: x.get('prep_time', 999))
    return makeable[:limit]
```

**Required Change:**
```python
def get_makeable_recipes(self, user_id: int, limit: int = 10) -> Dict[str, List[Dict]]:
    """
    Find all recipes the user can make with current inventory
    Returns categorized recipes: fully_makeable and partially_makeable
    """
    all_recipes = self.db.query(Recipe).all()
    fully_makeable = []
    partially_makeable = []

    for recipe in all_recipes:
        availability = self.check_recipe_availability(user_id, recipe.id)

        # Extract ingredient names
        available_names = [item['item'] for item in availability['available_items']]
        missing_names = [item['item'] for item in availability['missing_items']]
        missing_names.extend([item['item'] for item in availability['insufficient_items']])

        total_ingredients = len(availability['available_items']) + len(missing_names)
        match_percentage = availability['coverage_percentage']

        recipe_data = {
            'recipe_id': recipe.id,
            'recipe_name': recipe.title,  # ✅ Fixed key name
            'description': recipe.description,  # ✅ Added
            'prep_time_minutes': recipe.prep_time_min,  # ✅ Fixed key name
            'servings': recipe.servings,  # ✅ Added
            'available_ingredients': len(available_names),  # ✅ Added
            'total_ingredients': total_ingredients,  # ✅ Added
            'available_ingredient_names': available_names,  # ✅ Added
            'match_percentage': round(match_percentage, 1),  # ✅ Added
            'macros': recipe.macros_per_serving,
            'goals': recipe.goals
        }

        if availability['can_make']:
            # 100% match - fully makeable
            fully_makeable.append(recipe_data)
        elif match_percentage >= 80:
            # 80-99% match - partially makeable
            recipe_data['missing_ingredient_names'] = missing_names  # ✅ Added
            partially_makeable.append(recipe_data)

    # Sort fully_makeable by prep time
    fully_makeable.sort(key=lambda x: x.get('prep_time_minutes', 999))

    # Sort partially_makeable by match percentage (highest first), then prep time
    partially_makeable.sort(
        key=lambda x: (-x.get('match_percentage', 0), x.get('prep_time_minutes', 999))
    )

    return {
        'fully_makeable': fully_makeable[:limit],
        'partially_makeable': partially_makeable[:limit]
    }
```

---

### Fix 3: Add Configuration for Partial Match Threshold

**Optional Enhancement:** Make the 80% threshold configurable

```python
def get_makeable_recipes(
    self,
    user_id: int,
    limit: int = 10,
    partial_match_threshold: float = 80.0  # ✅ Configurable
) -> Dict[str, List[Dict]]:
    """
    Find all recipes the user can make with current inventory

    Args:
        user_id: User ID
        limit: Max recipes per category
        partial_match_threshold: Minimum % to consider partially makeable (default: 80%)
    """
    # ... code ...

    elif match_percentage >= partial_match_threshold:  # ✅ Use parameter
        recipe_data['missing_ingredient_names'] = missing_names
        partially_makeable.append(recipe_data)
```

---

## Testing Checklist

After implementing fixes, verify:

### ✅ Backend Service Tests
- [ ] `check_recipe_availability()` returns correct structure
- [ ] `get_makeable_recipes()` categorizes recipes correctly
- [ ] 100% match recipes go to `fully_makeable`
- [ ] 80-99% match recipes go to `partially_makeable`
- [ ] <80% match recipes are excluded
- [ ] All required fields are present in response
- [ ] Ingredient names are correctly extracted
- [ ] Match percentage is calculated correctly

### ✅ API Endpoint Tests
- [ ] `/inventory/makeable-recipes` returns correct structure
- [ ] Response has `fully_makeable` and `partially_makeable` keys
- [ ] `count` field is sum of both arrays
- [ ] Limit parameter works correctly

### ✅ Frontend Tests
- [ ] Component renders without errors
- [ ] Fully makeable recipes display correctly
- [ ] Partially makeable recipes display correctly
- [ ] Missing ingredients show up for partial matches
- [ ] Progress bars show correct percentages
- [ ] Empty states work when no recipes available

### ✅ Integration Tests
- [ ] Add items to inventory
- [ ] Verify makeable recipes update correctly
- [ ] Remove items from inventory
- [ ] Verify recipes move from fully → partially → gone
- [ ] Check with recipes having optional ingredients

---

## Summary

### Current Status: ❌ NOT WORKING

**Root Cause:** Backend and frontend have mismatched data contracts

**Impact:**
- Frontend will show empty state or crash
- Users can't see recipes they can make
- Feature is completely broken

**Severity:** HIGH - This is a core feature for meal planning

### After Fixes: ✅ WILL WORK

**Changes Required:**
1. Update `get_makeable_recipes()` service to return categorized dict
2. Update API endpoint to return correct structure
3. Ensure all required fields are included
4. Add proper sorting logic

**Estimated Fix Time:** 1-2 hours
**Testing Time:** 30 minutes

---

## Next Steps

1. ✅ Implement Fix 1: Update service function
2. ✅ Implement Fix 2: Update API endpoint
3. ✅ Test with sample data
4. ✅ Verify frontend renders correctly
5. ✅ Add unit tests for the service
6. ✅ Document the fixed API contract
