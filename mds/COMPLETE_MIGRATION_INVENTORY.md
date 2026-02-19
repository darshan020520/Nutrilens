# COMPLETE BACKEND MIGRATION INVENTORY

**Date**: 2025-12-02
**Status**: PARTIAL MIGRATION

---

## MIGRATED TO CLEAN ARCHITECTURE ✅

### Phase 1: Meal Planning (5 endpoints)
**File**: `backend/app/api/meal_plan_v2.py`
- POST `/generate`
- GET `/current/with-status`
- GET `/{plan_id}/grocery-list`
- POST `/{plan_id}/swap-meal`
- GET `/{plan_id}/alternatives/{recipe_id}`

### Phase 2: Tracking (9 endpoints)
**File**: `backend/app/api/tracking_v2.py`
- GET `/today`
- POST `/log-meal`
- POST `/skip-meal`
- GET `/history`
- GET `/inventory-status`
- GET `/expiring-items`
- GET `/restock-list`
- POST `/estimate-external-meal`
- POST `/log-external-meal`

**Total Migrated**: **14 endpoints** ✅

---

## NOT YET MIGRATED (OLD AGENT PATTERN) ❌

### 1. Recipes API (6 endpoints)
**File**: `backend/app/api/recipes.py`
- Pattern: Uses services/repositories (already clean?)
- Needs verification

### 2. Nutrition API (17 endpoints)
**File**: `backend/app/api/nutrition.py`
- Pattern: **Uses Agent pattern** (32 agent references)
- Status: ❌ **NEEDS MIGRATION**

### 3. Inventory API (8 endpoints)
**File**: `backend/app/api/inventory.py`
- Pattern: Uses services/repositories (already clean?)
- Needs verification

### 4. Dashboard API (2 endpoints)
**File**: `backend/app/api/dashboard.py`
- Pattern: Uses some agent references (2 mentions)
- Needs verification

### 5. Onboarding API (5 endpoints)
**File**: `backend/app/api/onboarding.py`
- Pattern: Uses services/repositories (already clean?)
- Needs verification

### 6. Receipt API (4 endpoints)
**File**: `backend/app/api/receipt.py`
- Pattern: Microservice integration
- Needs verification

### 7. Meal Dashboard API (4 endpoints)
**File**: `backend/app/api/meal_dashboard.py`
- Pattern: Uses services/repositories (already clean?)
- Needs verification

### 8. Orchestrator API (4 endpoints)
**File**: `backend/app/api/orchestrator.py`
- Pattern: Uses orchestrators (7 references)
- Needs verification

### 9. Nutrition Chat API (4 endpoints)
**File**: `backend/app/api/nutrition_chat.py`
- Pattern: Uses agent (5 references)
- Status: ❌ **NEEDS MIGRATION**

**Total Not Migrated**: **54 endpoints** ❌

---

## OLD AGENT-BASED ENDPOINTS (BEING REPLACED)

### 10. Old Meal Plan API (16 endpoints)
**File**: `backend/app/api/meal_plan.py`
- Status: Being replaced by `meal_plan_v2.py`
- Action: Deprecate after v2 testing

### 11. Old Tracking API (12 endpoints)
**File**: `backend/app/api/tracking.py`
- Status: Being replaced by `tracking_v2.py`
- Action: Deprecate after v2 testing

---

## SUMMARY

| Category | Count | Status |
|----------|-------|--------|
| **Migrated to Clean Architecture** | 14 | ✅ COMPLETE |
| **Old endpoints being replaced** | 28 | 🔄 Deprecate after v2 testing |
| **Not yet examined** | 54 | ❌ NEEDS ANALYSIS |
| **Total Backend Endpoints** | **96** | **15% migrated** |

---

## CRITICAL FINDING

**Only 15% of the backend has been migrated to clean architecture!**

The remaining 54 endpoints across 9 API modules need to be:
1. **Analyzed** - Check if they use Agent pattern
2. **Prioritized** - Identify which ones frontend uses
3. **Migrated** - Convert to Repository → Service → Orchestrator pattern

---

## NEXT STEPS - PHASE 3 OPTIONS

### Option A: Analyze Remaining APIs
Systematically check each of the 9 API modules to:
- Identify which use Agent pattern
- Identify which endpoints frontend uses
- Create migration plan

### Option B: Mark Current Work Complete
Consider Phases 1 & 2 complete for now:
- 14/14 frontend-critical endpoints migrated
- Can proceed with testing these
- Plan remaining migration as separate effort

### Option C: Continue Full Migration
Immediately start migrating the next critical module (likely Nutrition API with 17 endpoints)

---

## RECOMMENDATION

**Option A: Complete Analysis First**

Before continuing migration, we need to:
1. Verify which of the 54 endpoints actually use old Agent pattern
2. Search frontend to see which are actively used
3. Prioritize based on frontend usage + code quality

This ensures we're not migrating dead code or code that's already clean.