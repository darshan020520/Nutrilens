# Meal Plan Endpoints - Clean Architecture Refactoring Plan

## Current Problems

### 1. **DB Queries in Dependencies** ❌
- `get_user_meal_windows()` in dependencies.py has direct DB query
- Dependencies should ONLY wire components, not contain business logic

### 2. **DB Queries in Services** ❌
- `ConstraintBuilderService` has 4 direct DB queries (UserProfile, UserGoal, UserPath, UserPreference)
- `GroceryService` has direct DB queries (RecipeIngredient, Item, UserInventory)
- `MealPlanOptimizer` has direct DB queries
- Services should use repositories, NOT raw DB session

### 3. **Services Taking DB Session** ❌
- `ConstraintBuilderService(db)` - should take repositories
- `GroceryService(db)` - should take repositories
- `MealPlanOptimizer(db)` - should take repositories

---

## Minimal Refactoring Plan (NO OVER-ENGINEERING)

### **Phase 1: Create UserProfileRepository**

**What:** Single repository for all user profile data
**Why:** Currently 4 tables (UserProfile, UserGoal, UserPath, UserPreference) queried directly in services

**Files to Create:**
1. `backend/app/repositories/interfaces/user_profile_repository.py` - Interface
2. `backend/app/repositories/user_profile_repository.py` - Implementation

**Methods Needed:**
```python
class IUserProfileRepository:
    def get_profile(self, user_id: int) -> Optional[UserProfile]
    def get_active_goal(self, user_id: int) -> Optional[UserGoal]
    def get_path(self, user_id: int) -> Optional[UserPath]
    def get_preferences(self, user_id: int) -> Optional[UserPreference]
    def get_meal_windows(self, user_id: int) -> List[Dict]  # Returns meal_windows array
```

**Logic to Move:**
- From `constraint_builder_service.py:47-50` → repository methods
- From `dependencies.py:217-218` → `get_meal_windows()` method

---

### **Phase 2: Refactor ConstraintBuilderService**

**What:** Remove DB queries, use UserProfileRepository
**Why:** Services should not have direct DB access

**Changes:**
1. Change constructor: `__init__(self, db: Session)` → `__init__(self, user_profile_repo: IUserProfileRepository)`
2. Replace lines 47-50 (4 DB queries) with repository calls
3. NO LOGIC CHANGES - just swap DB queries for repository methods

**Before:**
```python
def __init__(self, db: Session):
    self.db = db

def build_constraints(self, user_id: int):
    profile = self.db.query(UserProfile).filter_by(user_id=user_id).first()
    goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
    path = self.db.query(UserPath).filter_by(user_id=user_id).first()
    preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
```

**After:**
```python
def __init__(self, user_profile_repo: IUserProfileRepository):
    self.user_profile_repo = user_profile_repo

def build_constraints(self, user_id: int):
    profile = self.user_profile_repo.get_profile(user_id)
    goal = self.user_profile_repo.get_active_goal(user_id)
    path = self.user_profile_repo.get_path(user_id)
    preferences = self.user_profile_repo.get_preferences(user_id)
```

---

### **Phase 3: Update Dependency Injection**

**What:** Wire UserProfileRepository into services
**Why:** Make dependencies.py actually do dependency injection correctly

**Changes in `dependencies.py`:**

1. **Add new dependency:**
```python
def get_user_profile_repository(db: Session = Depends(get_db)) -> IUserProfileRepository:
    return UserProfileRepository(db)
```

2. **Update constraint builder:**
```python
# BEFORE
def get_constraint_builder_service(db: Session = Depends(get_db)) -> ConstraintBuilderService:
    return ConstraintBuilderService(db)

# AFTER
def get_constraint_builder_service(
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> ConstraintBuilderService:
    return ConstraintBuilderService(user_profile_repo)
```

3. **Remove `get_user_meal_windows` function** - no longer needed (use repository directly)

---

### **Phase 4: Update /generate Endpoint**

**What:** Remove helper function call, use service/repository
**Why:** Keep endpoint clean

**Changes in `meal_plan_v2.py`:**

**Before:**
```python
meal_windows = await get_user_meal_windows(
    user_id=current_user.id,
    current_user=current_user
)
```

**After (Option A - via repository):**
```python
meal_windows = user_profile_repo.get_meal_windows(current_user.id)
```

**OR After (Option B - in orchestrator):**
Move this logic into orchestrator - orchestrator fetches meal windows internally

**Recommendation:** Option B - orchestrator should handle this

---

### **Phase 5: Update MealPlanOrchestrator (Optional)**

**What:** Orchestrator fetches meal_windows itself instead of receiving it as parameter
**Why:** Cleaner API - orchestrator knows what data it needs

**Before:**
```python
async def generate_weekly_meal_plan(
    self,
    user_id: int,
    start_date: datetime,
    constraints: OptimizationConstraints,
    current_inventory: Optional[Dict[int, float]],
    user_meal_windows: List[Dict]  # ❌ Passed from endpoint
):
```

**After:**
```python
def __init__(
    self,
    meal_plan_service: MealPlanServiceV2,
    optimizer: MealPlanOptimizer,
    grocery_service: GroceryService,
    user_profile_repo: IUserProfileRepository,  # ✅ Inject repository
    event_publisher: Optional[Any] = None
):

async def generate_weekly_meal_plan(
    self,
    user_id: int,
    start_date: datetime,
    constraints: OptimizationConstraints,
    current_inventory: Optional[Dict[int, float]]
    # ✅ No more user_meal_windows parameter
):
    # Fetch internally
    meal_windows = self.user_profile_repo.get_meal_windows(user_id)
```

**Update endpoint:**
```python
result = await orchestrator.generate_weekly_meal_plan(
    user_id=current_user.id,
    start_date=request.start_date or datetime.now(),
    constraints=constraints,
    current_inventory=None
    # ✅ No more meal_windows parameter
)
```

---

### **Phase 6: Clean Up /generate Endpoint**

**What:** Remove print statements and clean up
**Why:** Professional code

**Remove:**
- Line 55: `print("generating new meal plan")`
- Line 56: `print("current user id", current_user.id)`

---

## What We Are NOT Doing (To Avoid Over-Engineering)

❌ **NOT refactoring GroceryService** - leave for later
❌ **NOT refactoring MealPlanOptimizer** - too complex, leave for later
❌ **NOT creating separate repositories** for Recipe/Inventory (already exist)
❌ **NOT touching other endpoints** - they're already clean
❌ **NOT changing business logic** - only moving data access to repositories

---

## Summary of Changes

### Files to CREATE:
1. `backend/app/repositories/interfaces/user_profile_repository.py` (interface)
2. `backend/app/repositories/user_profile_repository.py` (implementation)

### Files to MODIFY:
1. `backend/app/services/constraint_builder_service.py` - use repository instead of DB
2. `backend/app/dependencies.py` - add repository, update injections, remove helper
3. `backend/app/orchestrators/meal_plan_orchestrator.py` - inject repository, fetch meal_windows internally
4. `backend/app/api/meal_plan_v2.py` - remove meal_windows call, remove print statements

### Files NOT TOUCHING:
- `grocery_service.py` - leave for Phase 2
- `final_meal_optimizer.py` - too complex, leave for Phase 2
- Other endpoints - already clean

---

## Implementation Order

1. ✅ Create UserProfileRepository (interface + implementation)
2. ✅ Refactor ConstraintBuilderService to use repository
3. ✅ Update dependencies.py
4. ✅ Update MealPlanOrchestrator (inject repository, fetch meal_windows)
5. ✅ Update /generate endpoint (remove helper call, remove prints)
6. ✅ Test the flow

---

## Zero Logic Changes Guarantee

- All business logic stays EXACTLY the same
- Only changing HOW data is fetched (repository instead of DB query)
- Same inputs, same outputs, same behavior
- Just better architecture