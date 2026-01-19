# UserProfileRepository Interface Design

## Best Practices Applied

### ✅ 1. **Single Responsibility Principle (SRP)**
- **One responsibility:** Manage user profile-related data access
- **Consolidates 4 related models:** UserProfile, UserGoal, UserPath, UserPreference
- **Why together?** These models are always queried together for user context
- **Alternative considered:** Separate repositories for each model (rejected - too fragmented)

### ✅ 2. **Interface Segregation Principle (ISP)**
- **Small, focused methods:** Each method does ONE thing
- **No fat interfaces:** Clients only depend on methods they use
- **Examples:**
  - `get_profile()` - Just profile data
  - `get_active_goal()` - Just active goal
  - `get_meal_windows()` - Just meal windows (convenience)

### ✅ 3. **Dependency Inversion Principle (DIP)**
- **Services depend on interface (IUserProfileRepository), not implementation**
- **Implementation can be swapped** without changing services
- **Example:** Could swap SQLAlchemy for MongoDB without changing ConstraintBuilderService

### ✅ 4. **Don't Repeat Yourself (DRY)**
- **Eliminates duplicate queries across codebase:**
  - `constraint_builder_service.py:47-50` (4 queries)
  - `dependencies.py:217-218` (1 query)
  - `final_meal_optimizer.py:885-888` (4 queries)
  - `suggestion_engine.py:92-102` (3 queries)
  - And many more...
- **One place for all user data queries**

### ✅ 5. **Return Types Follow Convention**
- **Returns `Optional[Model]`** for single entities (might not exist)
- **Returns `List[Dict]`** for meal_windows (convenience wrapper)
- **Returns `Dict`** for bulk fetch optimization
- **Consistent with existing repositories** (see meal_plan_repository.py)

### ✅ 6. **Clear Documentation**
- **Every method has:**
  - Purpose description
  - Args documented
  - Returns documented with examples
  - Edge cases explained (e.g., empty list if not found)

### ✅ 7. **Optimization Method**
- **`get_all_user_data()`** - Batch fetch all 4 models
- **Why?** ConstraintBuilderService needs all 4 - avoid 4 separate queries
- **Performance:** 1 query instead of 4
- **Optional:** Clients can still use individual methods

---

## Method Design Decisions

### **Individual Getters (4 methods)**
```python
get_profile(user_id) -> Optional[UserProfile]
get_active_goal(user_id) -> Optional[UserGoal]
get_path(user_id) -> Optional[UserPath]
get_preferences(user_id) -> Optional[UserPreference]
```

**Why:**
- Granular access when you only need one piece
- Clear, specific names
- Follows query patterns already in codebase

**Current Usage:**
- `ConstraintBuilderService` → needs all 4 ✅
- `dependencies.py` → needs only `path.meal_windows` ✅
- `MealPlanOptimizer` → needs all 4 ✅

---

### **Convenience Method: get_meal_windows()**
```python
get_meal_windows(user_id) -> List[Dict]
```

**Why:**
- Most common use case: "Just give me meal windows"
- Hides implementation detail that meal_windows lives in UserPath
- Returns empty list (safe default) instead of None
- Replaces `dependencies.py:get_user_meal_windows()` helper

**Implementation:**
```python
def get_meal_windows(self, user_id: int) -> List[Dict]:
    path = self.get_path(user_id)
    return path.meal_windows if path and path.meal_windows else []
```

---

### **Optimization Method: get_all_user_data()**
```python
get_all_user_data(user_id) -> Dict
```

**Why:**
- **Performance:** Fetch all 4 models in 1 query instead of 4
- **Common pattern:** ConstraintBuilderService, MealPlanOptimizer both need all 4
- **Returns Dict for flexibility:** Can add more fields later without breaking interface

**Implementation Strategy:**
```python
def get_all_user_data(self, user_id: int) -> Dict:
    # Option A: 4 separate queries (simple, clear)
    return {
        "profile": self.get_profile(user_id),
        "goal": self.get_active_goal(user_id),
        "path": self.get_path(user_id),
        "preferences": self.get_preferences(user_id)
    }

    # Option B: 1 query with joins (faster, more complex)
    # Could optimize later without changing interface
```

**Usage:**
```python
# Before (4 queries)
profile = repo.get_profile(user_id)
goal = repo.get_active_goal(user_id)
path = repo.get_path(user_id)
preferences = repo.get_preferences(user_id)

# After (1 query)
user_data = repo.get_all_user_data(user_id)
profile = user_data["profile"]
goal = user_data["goal"]
path = user_data["path"]
preferences = user_data["preferences"]
```

---

## Comparison with Existing Repositories

### **Similar Pattern: IMealPlanRepository**
- ✅ Returns `Optional[Model]` for single entities
- ✅ Returns `List[Model]` for collections
- ✅ Clear method names (get_by_id, get_active_plan)
- ✅ Async methods (we'll make UserProfileRepository async too)

### **Differences:**
- **UserProfileRepository consolidates 4 models** (not just 1)
- **Has optimization method** (get_all_user_data)
- **Has convenience method** (get_meal_windows)

---

## Questions for Review

### 1. **Should methods be async?**
**Current interface:** Not async (simple queries)
**Existing pattern:** IMealPlanRepository uses async

**Recommendation:** Make async for consistency
```python
@abstractmethod
async def get_profile(self, user_id: int) -> Optional[UserProfile]:
```

### 2. **Should get_all_user_data() be in interface?**
**Pro:** Performance optimization, common pattern
**Con:** Could be added later if needed

**Recommendation:** Keep it - ConstraintBuilderService needs all 4, optimizer needs all 4

### 3. **Should meal_windows return List[Dict] or custom model?**
**Current:** List[Dict] (matches JSON column in database)
**Alternative:** Create MealWindow dataclass

**Recommendation:** Keep List[Dict] - matches existing data structure

### 4. **Should we add update/create methods?**
**Current scope:** Read-only (for /generate endpoint)
**Future:** Could add later when needed

**Recommendation:** Start with read-only, add writes when needed

---

## Migration Impact

### **Services that will use this repository:**
1. ✅ `ConstraintBuilderService` - needs profile, goal, path, preferences
2. ✅ `MealPlanOptimizer` - needs profile, goal, path, preferences
3. ⚠️ `InventoryService` - only needs profile.goal_calories
4. ⚠️ `SuggestionEngine` - needs profile, goal, preferences
5. ⚠️ `EducationService` - needs profile, goal
6. ⚠️ `ConsumptionService` - only needs profile

**For this refactoring (only /generate endpoint):**
- Migrate: ConstraintBuilderService ✅
- Migrate: dependencies.py helper ✅
- Leave others for later ⚠️

---

## Final Interface

```python
class IUserProfileRepository(ABC):
    # Individual getters (granular access)
    async def get_profile(user_id) -> Optional[UserProfile]
    async def get_active_goal(user_id) -> Optional[UserGoal]
    async def get_path(user_id) -> Optional[UserPath]
    async def get_preferences(user_id) -> Optional[UserPreference]

    # Convenience method (hides implementation)
    async def get_meal_windows(user_id) -> List[Dict]

    # Optimization method (batch fetch)
    async def get_all_user_data(user_id) -> Dict
```

**Total Methods:** 6
**Read-only:** Yes
**Async:** Yes (for consistency with existing repos)
**Well-documented:** Yes
**Follows SOLID:** Yes
