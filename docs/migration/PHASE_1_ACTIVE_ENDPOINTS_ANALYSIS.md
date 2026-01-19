# Phase 1 - Active Endpoints Analysis

**Analysis Date**: 2025-11-24
**Purpose**: Identify which endpoints are actually used by the frontend

---

## 🔍 Frontend Usage Analysis

### Methodology
Searched frontend codebase (`frontend/src`) for actual API calls to `/meal-plans/*` endpoints.

### Findings: Only **5 Endpoints** Are Currently Used!

---

## ✅ ACTIVE ENDPOINTS (5 total)

### 1. **POST /meal-plans/generate**
**Status**: ✅ MIGRATED to v2
**File**: `backend/app/api/meal_plan_v2.py`
**Frontend Usage**: `WeekView.tsx:141`
```typescript
const response = await api.post("/meal-plans/generate", {
  start_date: new Date().toISOString(),
});
```
**Priority**: CRITICAL (already migrated)

---

### 2. **GET /meal-plans/current/with-status** ⭐
**Status**: ❌ NOT MIGRATED
**Frontend Usage**: `WeekView.tsx:72`
```typescript
queryKey: ["meal-plan", "current"],
const response = await api.get("/meal-plans/current/with-status");
```
**Priority**: CRITICAL (main dashboard view)
**Complexity**: MEDIUM
**Service**: Uses `MealPlanService` + direct MealLog queries

---

### 3. **GET /meal-plans/{plan_id}/grocery-list** ⭐
**Status**: ❌ NOT MIGRATED
**Frontend Usage**: `WeekView.tsx:87`
```typescript
queryKey: ["meal-plan", weekPlan?.id, "grocery-list"],
const response = await api.get(`/meal-plans/${weekPlan.id}/grocery-list`);
```
**Priority**: HIGH (grocery list feature)
**Complexity**: LOW (GroceryService already exists!)
**Service**: Can use `GroceryService` we just created ✅

---

### 4. **POST /meal-plans/{plan_id}/swap-meal** ⭐
**Status**: ❌ NOT MIGRATED
**Frontend Usage**:
- `WeekView.tsx:161`
- `useMealPlan.ts:22`
```typescript
const response = await api.post(`/meal-plans/${weekPlan?.id}/swap-meal`, {
  day: dayIndex,
  meal_type: mealType,
  new_recipe_id: newRecipeId,
});
```
**Priority**: HIGH (user feature)
**Complexity**: MEDIUM
**Service**: Uses `MealPlanService.swap_meal()`

---

### 5. **GET /meal-plans/{plan_id}/alternatives/{recipe_id}** ⭐
**Status**: ❌ NOT MIGRATED
**Frontend Usage**: `useMealPlan.ts:10`
```typescript
queryKey: ["meal-plan", planId, "alternatives", recipeId, count],
const response = await api.get(`/meal-plans/${planId}/alternatives/${recipeId}?count=${count}`);
```
**Priority**: HIGH (required for swap meal)
**Complexity**: MEDIUM
**Service**: Uses `MealPlanService.get_alternatives_for_meal()`

---

## ❌ UNUSED ENDPOINTS (11 total)

These endpoints exist in `meal_plan.py` but are **NOT called by the frontend**:

1. **GET /meal-plans/current** - Similar to `/current/with-status`, not used
2. **GET /meal-plans/{plan_id}** - Not used (frontend uses /current/with-status)
3. **PUT /meal-plans/{plan_id}/adjust** - Not implemented in UI
4. **GET /meal-plans/{recipe_id}/alternatives** - Different signature, not used
5. **POST /meal-plans/log-meal** - Meal logging uses different endpoint
6. **GET /meal-plans/history/meals** - Not displayed in current UI
7. **POST /meal-plans/eating-out** - Not implemented in UI
8. **POST /meal-plans/meal-prep-suggestions** - Not implemented in UI
9. **POST /meal-plans/bulk-cooking-suggestions** - Not implemented in UI
10. **GET /meal-plans/shopping/reminders** - Not implemented in UI
11. **POST /meal-plans/optimize-inventory** - Not implemented in UI

---

## 🎯 REVISED MIGRATION STRATEGY

### Phase 1.1: Critical Active Endpoints (Week 2)
**Target: 4 endpoints** (excluding already-migrated `/generate`)

Migrate ONLY the endpoints that are actively used:

1. ✅ POST /meal-plans/generate (DONE)
2. GET /meal-plans/current/with-status
3. GET /meal-plans/{plan_id}/grocery-list
4. POST /meal-plans/{plan_id}/swap-meal
5. GET /meal-plans/{plan_id}/alternatives/{recipe_id}

**Timeline**: 1-2 sessions
**Risk**: LOW-MEDIUM (4 endpoints, all use existing services)

---

### Phase 1.2: Unused Endpoints (Deferred to Phase 6)
**Target: 11 endpoints**

**Decision**: ⏸️ **DEFER MIGRATION**

**Rationale**:
- These endpoints are not currently used by the frontend
- No user-facing features depend on them
- Migrating them now would be speculative work
- Focus on **actual user value** first

**When to migrate**:
- When frontend features are implemented that need them
- During Phase 6 (cleanup and remaining endpoints)
- If technical debt becomes an issue

---

## 📊 Revised Statistics

### Original Plan
- Total endpoints: 16
- Target for Phase 1: All 16 endpoints

### Revised Plan (Data-Driven)
- **Active endpoints**: 5 (31%)
- **Unused endpoints**: 11 (69%)
- **Target for Phase 1**: 5 active endpoints only

### Impact
- **Reduced scope**: 5 endpoints vs 16 endpoints (69% reduction!)
- **Faster completion**: ~2-3 days vs 2-3 weeks
- **Same user value**: 100% of used features migrated
- **Lower risk**: No speculative migrations

---

## 🚀 Next Steps (Session 3)

### Immediate Priorities

1. **GET /meal-plans/current/with-status** (CRITICAL)
   - Main dashboard data source
   - Need to extract MealLog status enrichment logic

2. **GET /meal-plans/{plan_id}/grocery-list** (HIGH)
   - Use existing `GroceryService` ✅
   - Quick win - service already exists

3. **POST /meal-plans/{plan_id}/swap-meal** (HIGH)
   - Uses `MealPlanService.swap_meal()`
   - Required for meal swapping feature

4. **GET /meal-plans/{plan_id}/alternatives/{recipe_id}** (HIGH)
   - Uses `MealPlanService.get_alternatives_for_meal()`
   - Required for meal swapping UI

---

## 🎯 Success Criteria

### Week 2 Target (Revised)
- **5/5 active endpoints migrated** (100% of used features)
- **Logic changes**: 0 (COPY-PASTE ONLY)
- **Side-by-side**: Both v1 and v2 functional
- **User impact**: Zero downtime, identical behavior

### Deferred Work
- **11 unused endpoints**: Document and defer to Phase 6
- **Rationale**: Focus on actual user value first
- **Technical debt**: Acceptable (old code still works)

---

## 📝 Frontend Files Using Meal Plan API

1. `frontend/src/app/dashboard/meals/components/WeekView.tsx`
   - Main meal plan display
   - Uses: `/current/with-status`, `/generate`, `/swap-meal`, `/grocery-list`

2. `frontend/src/app/dashboard/meals/hooks/useMealPlan.ts`
   - Custom hook for meal plan operations
   - Uses: `/alternatives/{recipe_id}`, `/swap-meal`

3. `frontend/src/app/dashboard/meals/components/TodayView.tsx`
   - Today's meals view
   - Invalidates queries on updates

4. `frontend/src/app/dashboard/meals/components/ExternalMealDialog.tsx`
   - External meal logging
   - Invalidates meal-plan queries

---

## 💡 Key Insights

1. **69% of endpoints are unused** - Major scope reduction opportunity
2. **All active endpoints use services** - Migration is straightforward
3. **GroceryService already exists** - One endpoint is a quick win
4. **Frontend is main source of truth** - Always check actual usage before migrating
5. **Speculative work is wasteful** - Migrate features that exist, not features that might exist

---

**Decision**: Proceed with **5 active endpoints only** in Phase 1.
**Defer**: 11 unused endpoints to Phase 6 (cleanup).
**Rationale**: Focus on user value, reduce scope, faster delivery.

---

**Next Session**: Migrate the 4 remaining active endpoints (excluding already-done `/generate`)
