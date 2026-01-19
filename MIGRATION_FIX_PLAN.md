# MIGRATION FIX PLAN - SYSTEMATIC CORRECTION
**Date**: 2025-11-28
**Status**: ACTIVE EXECUTION
**Goal**: Fix all issues identified in audit with ZERO tolerance for mistakes

---

## EXECUTION PRINCIPLES

### NON-NEGOTIABLE RULES
1. ✅ **READ THE OLD CODE FIRST** - Understand exact behavior before changing anything
2. ✅ **PRESERVE EXACT SCHEMAS** - Response structures must match OLD implementation byte-for-byte
3. ✅ **NO ASSUMPTIONS** - Verify every single field, every single endpoint
4. ✅ **TEST BEFORE CLAIMING DONE** - If not tested, it's not done
5. ✅ **ONE ISSUE AT A TIME** - Complete one fix fully before moving to next

---

## CRITICAL ISSUES TO FIX (Priority Order)

### PRIORITY 1: Schema Mismatches (BREAKING CHANGES)

#### Issue 1.1: POST `/tracking/v2/log-meal` Response Schema
**Status**: 🔴 CRITICAL - Breaking frontend

**Current (WRONG):**
```python
LogMealResponse(
    message="Meal logged successfully",
    meal_log=result["meal_log"],
    inventory_changes=result.get(...),
    daily_summary=result["daily_summary"],
    inventory_status=result.get(...),
    insights=result.get(...),
    recommendations=result.get(...)
)
```

**Required (OLD schema from tracking.py:128-140):**
```python
LogMealResponse(
    success=True,
    meal_type=result["meal_type"],
    recipe_name=result["recipe"],
    consumed_at=datetime.fromisoformat(...),
    macros_consumed=MacroNutrients(...),
    portion_multiplier=request.portion_multiplier,
    deducted_items=List[InventoryChangeItem],
    daily_totals=Dict[str, Any],
    remaining_targets=Dict[str, float],
    insights=List[InsightItem],
    recommendations=List[RecommendationItem]
)
```

**Fix Steps:**
1. Read tracking.py:128-140 (OLD schema definition)
2. Read tracking.py:162-191 (OLD response construction)
3. Update tracking_v2.py to construct IDENTICAL response
4. Update orchestrator to return data in OLD format
5. Test response matches OLD exactly

**Files to Modify:**
- `backend/app/api/tracking_v2.py` (lines 82-130)
- `backend/app/orchestrators/meal_logging_orchestrator.py` (return format)

---

#### Issue 1.2: POST `/tracking/v2/skip-meal` Request Schema
**Status**: 🟡 MINOR - Field name mismatch

**Current (WRONG):** `skip_reason` field
**Required (OLD):** `reason` field

**Fix Steps:**
1. Read tracking.py:208-220 (OLD request schema)
2. Update SkipMealRequest schema
3. Update orchestrator to use `reason` not `skip_reason`

**Files to Modify:**
- `backend/app/schemas/tracking.py` (SkipMealRequest)
- `backend/app/api/tracking_v2.py` (parameter name)

---

#### Issue 1.3: GET `/tracking/v2/today` Response Schema
**Status**: 🔴 CRITICAL - Breaking frontend

**Current (WRONG):** Nested structure with `daily_summary`, `inventory_status`
**Required (OLD from tracking.py:474-531):** Flat structure

**Fix Steps:**
1. Read tracking.py:474-531 (OLD endpoint implementation)
2. Read TodaySummaryResponse schema definition
3. Flatten the nested response to match OLD
4. Test response structure matches

**Files to Modify:**
- `backend/app/api/tracking_v2.py` (lines 206-250)

---

### PRIORITY 2: Architecture Violations

#### Issue 2.1: Direct DB Access in API Layer
**Status**: 🟡 MEDIUM - Violates clean architecture

**Location:** `backend/app/api/meal_plan_v2.py:126`
**Problem:**
```python
# COPY-PASTED FROM meal_plan.py:116-143 - NO CHANGES
meal_logs = db.query(MealLog).filter(...)  # ← Should be in repository
```

**Fix Steps:**
1. Create `MealLogRepository.get_for_status_enrichment()` method
2. Move query logic to repository
3. Update meal_plan_v2.py to call repository instead
4. Remove direct DB access

**Files to Modify:**
- `backend/app/repositories/meal_log_repository.py` (add method)
- `backend/app/api/meal_plan_v2.py` (remove DB query)

---

#### Issue 2.2: ConsumptionServiceV2 Direct DB Access
**Status**: 🟡 MEDIUM - Backward compatibility trade-off

**Location:** `backend/app/services/consumption_service_v2.py:192, 518`

**Fix Steps:**
1. Create RecipeRepository if needed
2. Create UserRepository if needed
3. Update ConsumptionServiceV2 to use repositories only
4. Remove `self.db` parameter (breaking change - need migration strategy)

**Files to Modify:**
- `backend/app/services/consumption_service_v2.py`
- Potentially new repository files

---

### PRIORITY 3: Missing Endpoints

#### Issue 3.1: POST `/tracking/update-inventory` - NOT MIGRATED
**Status**: 🔴 HIGH - Critical inventory feature

**Fix Steps:**
1. Read tracking.py:612-681 (OLD implementation)
2. Create endpoint in tracking_v2.py
3. Use InventoryManagementService
4. Test bulk inventory update

---

#### Issue 3.2: POST `/tracking/manual-entry` - NOT MIGRATED
**Status**: 🟡 MEDIUM - Manual food logging

**Fix Steps:**
1. Read tracking.py:1097-1203 (OLD implementation)
2. Determine if goes to ExternalMealService or MealTrackingService
3. Create endpoint in tracking_v2.py
4. Test manual entry flow

---

#### Issue 3.3: GET `/tracking/patterns` - NOT MIGRATED
**Status**: 🟡 MEDIUM - Analytics feature

**Fix Steps:**
1. Read tracking.py:533-610 (OLD implementation)
2. Use ConsumptionServiceV2.generate_consumption_analytics()
3. Create endpoint in tracking_v2.py
4. Test patterns response

---

## EXECUTION STRATEGY

### Phase A: Fix Schema Mismatches (2-3 hours)
**Goal:** Make v2 responses match v1 exactly

1. ✅ Read OLD tracking.py thoroughly
2. ✅ Document exact schema expectations
3. ✅ Update tracking_v2.py response construction
4. ✅ Test each endpoint response matches OLD

### Phase B: Fix Architecture Violations (1-2 hours)
**Goal:** Remove direct DB access

1. ✅ Create missing repository methods
2. ✅ Update services to use repositories only
3. ✅ Validate no DB queries in wrong layers

### Phase C: Add Missing Endpoints (2-3 hours)
**Goal:** Feature parity with v1

1. ✅ Migrate 3 missing Phase 2 endpoints
2. ✅ Test all endpoints work
3. ✅ Verify frontend compatibility

### Phase D: Validation (1 hour)
**Goal:** Prove everything works

1. ✅ Start FastAPI server
2. ✅ Test all v2 endpoints
3. ✅ Compare responses to v1
4. ✅ Run frontend to verify no breaks

---

## VALIDATION CHECKLIST

After each fix:
- [ ] OLD code read and understood
- [ ] Change implements EXACT old behavior
- [ ] Response schema matches OLD byte-for-byte
- [ ] No new architecture violations
- [ ] Endpoint tested manually
- [ ] No hallucinations or assumptions

---

## CURRENT STATUS: READY TO EXECUTE

**Next Action:** Start with Priority 1, Issue 1.1 - Fix /log-meal response schema

---

_This is not a plan to discuss. This is a plan to EXECUTE._