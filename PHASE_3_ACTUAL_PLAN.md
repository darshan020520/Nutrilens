# PHASE 3: DASHBOARD ENDPOINTS MIGRATION

**Date**: 2025-12-02
**Status**: READY TO START

---

## Why Dashboard is Phase 3

According to the **original migration plan** (SYSTEMATIC_MIGRATION_APPROACH.md):

✅ **Phase 0**: Infrastructure - COMPLETE
✅ **Phase 1**: Meal Plan Endpoints (5 endpoints) - COMPLETE
✅ **Phase 2**: Meal Logging/Tracking (9 endpoints) - COMPLETE
⏳ **Phase 3**: Dashboard (2 endpoints) - **NEXT**

---

## Frontend Usage Analysis

The frontend actively uses **2 dashboard endpoints**:

### 1. GET `/dashboard/summary`
**Used In**: `frontend/src/app/dashboard/hooks/useDashboard.ts`
**Purpose**: Main dashboard summary data
**Status**: ❌ NOT MIGRATED

### 2. GET `/dashboard/recent-activity`
**Used In**: `frontend/src/app/dashboard/hooks/useDashboard.ts`
**Purpose**: Recent activity feed
**Status**: ❌ NOT MIGRATED

---

## Current Implementation

**File**: `backend/app/api/dashboard.py`

Let me check what these endpoints currently do:

### GET `/dashboard/summary`
- Line count: ~176 lines in API file
- Uses: TrackingAgent, MealPlanService
- Returns: Comprehensive dashboard data

### GET `/dashboard/recent-activity`
- Uses: Direct DB queries
- Returns: Activity feed

---

## Migration Plan

### Step 1: Create DashboardOrchestrator
```python
class DashboardOrchestrator:
    """
    Orchestrates dashboard data aggregation.

    Coordinates:
    - Meal plan status (MealPlanServiceV2)
    - Today's tracking (ConsumptionServiceV2)
    - Inventory status (InventoryManagementService)
    - Recent activity (ActivityRepository - NEW)
    """
```

### Step 2: Create ActivityRepository (NEW)
```python
class ActivityRepository:
    """Handle recent activity queries."""

    async def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Activity]:
        # Replace direct DB queries with repository pattern
```

### Step 3: Create `/dashboard/v2/` endpoints
- GET `/dashboard/v2/summary`
- GET `/dashboard/v2/recent-activity`

### Step 4: Test side-by-side with v1

### Step 5: Frontend cutover

---

## Estimated Effort

**Based on previous phases:**
- Phase 1 (5 endpoints): ~2-3 sessions
- Phase 2 (9 endpoints): ~3-4 sessions
- Phase 3 (2 endpoints): **~1-2 sessions** (less complex)

**Why less effort?**
- Only 2 endpoints
- Can reuse existing services (MealPlanServiceV2, ConsumptionServiceV2, InventoryManagementService)
- Orchestrator mainly aggregates existing data

---

## After Phase 3

Following the original plan, remaining phases are:

⏳ **Phase 4**: Receipt Processing (4 endpoints) - Check frontend usage first
⏳ **Phase 5**: WhatsApp Consolidation (4 endpoints) - Check frontend usage first
⏳ **Phase 6**: Remaining Endpoints (~39 endpoints) - Only migrate if used by frontend

**Principle**: Continue the data-driven approach - only migrate endpoints actually used by the frontend.

---

## Ready to Start?

Phase 3 is:
- ✅ Well-scoped (2 endpoints)
- ✅ Frontend-critical (both used actively)
- ✅ Can reuse existing infrastructure
- ✅ Follows original migration plan

**Shall we begin Phase 3: Dashboard Endpoints?**
