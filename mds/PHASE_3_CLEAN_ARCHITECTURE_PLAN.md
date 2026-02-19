# PHASE 3: DASHBOARD ENDPOINTS - CLEAN ARCHITECTURE MIGRATION

**Date**: 2025-12-02
**Status**: READY TO START

---

## Migration Approach: REUSE EXISTING INFRASTRUCTURE ✅

**Key Insight**: Dashboard endpoints are **aggregators** - they just combine data from services we've already built!

### Existing Clean Architecture Services We Can Reuse

✅ **ConsumptionServiceV2** (`consumption_service_v2.py`)
- `get_daily_summary()` - Returns today's meals, macros, targets
- Already used by `/tracking/v2/today`

✅ **InventoryManagementService** (`inventory_management_service.py`)
- `calculate_inventory_status()` - Returns inventory counts
- Already used by `/tracking/v2/inventory-status`

✅ **MealPlanServiceV2** (`meal_plan_service_v2.py`)
- `get_active_plan()` - Returns current meal plan
- Already used by `/meal-plans/v2/current/with-status`

### What We Need to Build (Minimal!)

❌ **NEW: ActivityRepository** - For recent activity queries
❌ **NEW: DashboardOrchestrator** - Coordinates existing services

---

## Current vs Clean Architecture

### Current Implementation (dashboard.py)

```python
@router.get("/summary")
async def get_dashboard_summary(
    current_user: User,
    db: Session
):
    # ❌ OLD: Direct service instantiation
    consumption_service = ConsumptionService(db)  # OLD service
    tracking_agent = TrackingAgent(db, user_id)   # Agent pattern

    # ❌ OLD: Direct DB queries
    meal_logs_today = db.query(MealLog).filter(...)

    # ❌ OLD: Helper functions scattered in API file
    next_meal, next_meal_time = find_next_meal(meal_logs_today)
    streak = calculate_streak(db, user_id)
```

### Clean Architecture (dashboard_v2.py)

```python
@router.get("/v2/summary")
async def get_dashboard_summary(
    current_user: User,
    orchestrator: DashboardOrchestrator = Depends(get_dashboard_orchestrator)
):
    # ✅ NEW: Dependency injection
    # ✅ NEW: Orchestrator coordinates everything
    summary = await orchestrator.get_dashboard_summary(current_user.id)
    return DashboardSummary(**summary)
```

---

## Implementation Plan

### Step 1: Create ActivityRepository (NEW)

**File**: `backend/app/repositories/activity_repository.py`

```python
class ActivityRepository:
    """
    Repository for user activity tracking.

    Consolidates activity from:
    - Meal logs (logged, skipped)
    - Meal plan generation
    - Inventory updates
    - Recipe swaps
    """

    async def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get recent activity for user.

        Returns chronological list of activities from:
        - MealLog (consumed_datetime for logged meals)
        - MealLog (updated_at for skipped meals)
        - MealPlan (created_at for new plans)
        """
        # Query and aggregate from different tables
        # Replace direct DB queries from dashboard.py:240-280
```

**Reuses existing patterns from:**
- `MealLogRepository` - Query patterns
- `MealPlanRepository` - Join patterns

---

### Step 2: Create DashboardOrchestrator (NEW)

**File**: `backend/app/orchestrators/dashboard_orchestrator.py`

```python
class DashboardOrchestrator(BaseOrchestrator):
    """
    Orchestrates dashboard data aggregation.

    Coordinates:
    - ConsumptionServiceV2 (today's summary, macros)
    - InventoryManagementService (inventory status)
    - MealPlanServiceV2 (current plan)
    - ActivityRepository (recent activity)
    - UserGoalRepository (goal tracking)
    """

    def __init__(
        self,
        consumption_service: ConsumptionServiceV2,
        inventory_service: InventoryManagementService,
        meal_plan_service: MealPlanServiceV2,
        activity_repo: ActivityRepository,
        db: Session
    ):
        # Dependency injection - all clean services!

    async def get_dashboard_summary(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Aggregate dashboard data from clean services.

        Returns:
        {
            "meals_card": {...},      # From ConsumptionServiceV2
            "macros_card": {...},     # From ConsumptionServiceV2
            "inventory_card": {...},  # From InventoryManagementService
            "goal_card": {...}        # From DB + streak calculation
        }
        """
        # Step 1: Get today's summary (meals + macros)
        today_summary = await self.consumption_service.get_daily_summary(
            user_id=user_id,
            target_date=date.today()
        )

        # Step 2: Get inventory status
        inventory_status = await self.inventory_service.calculate_inventory_status(
            user_id=user_id
        )

        # Step 3: Get current meal plan (for next meal)
        current_plan = await self.meal_plan_service.get_active_plan(user_id)

        # Step 4: Calculate next meal from plan
        next_meal_info = self._calculate_next_meal(current_plan)

        # Step 5: Get goal progress
        goal_data = await self._get_goal_progress(user_id)

        # Step 6: Aggregate into dashboard cards
        return {
            "meals_card": {
                "meals_planned": today_summary.get("meals_planned", 0),
                "meals_consumed": today_summary.get("meals_consumed", 0),
                "meals_skipped": today_summary.get("meals_skipped", 0),
                "next_meal": next_meal_info["meal_type"],
                "next_meal_time": next_meal_info["time"]
            },
            "macros_card": self._build_macros_card(today_summary),
            "inventory_card": self._build_inventory_card(inventory_status),
            "goal_card": goal_data
        }

    async def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get recent activity feed."""
        activities = await self.activity_repo.get_recent_activity(
            user_id=user_id,
            limit=limit
        )

        return {
            "activities": activities,
            "total_count": len(activities)
        }
```

**Reuses orchestrator pattern from:**
- `MealPlanOrchestrator` - Structure and event publishing
- `MealLoggingOrchestrator` - Service coordination

---

### Step 3: Create API Endpoints (NEW)

**File**: `backend/app/api/dashboard_v2.py`

```python
router = APIRouter(prefix="/dashboard/v2", tags=["dashboard-v2"])

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    orchestrator: DashboardOrchestrator = Depends(get_dashboard_orchestrator)
):
    """
    Get complete dashboard summary.

    Source: backend/app/api/dashboard.py:140-238
    Migrated to: Clean architecture with orchestrator pattern
    """
    logger.info(f"GET /dashboard/v2/summary - User {current_user.id}")

    summary = await orchestrator.get_dashboard_summary(current_user.id)
    return DashboardSummary(**summary)


@router.get("/recent-activity", response_model=RecentActivityResponse)
async def get_recent_activity(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    orchestrator: DashboardOrchestrator = Depends(get_dashboard_orchestrator)
):
    """
    Get recent activity feed.

    Source: backend/app/api/dashboard.py:240-280
    Migrated to: Clean architecture with repository pattern
    """
    logger.info(f"GET /dashboard/v2/recent-activity - User {current_user.id}")

    activity = await orchestrator.get_recent_activity(
        user_id=current_user.id,
        limit=limit
    )
    return RecentActivityResponse(**activity)
```

---

### Step 4: Dependency Injection

**File**: `backend/app/dependencies.py` (add)

```python
def get_dashboard_orchestrator(
    consumption_service: ConsumptionServiceV2 = Depends(get_consumption_service_v2),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service),
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    activity_repo: ActivityRepository = Depends(get_activity_repository),
    db: Session = Depends(get_db)
) -> DashboardOrchestrator:
    """Provide DashboardOrchestrator instance."""
    return DashboardOrchestrator(
        consumption_service=consumption_service,
        inventory_service=inventory_service,
        meal_plan_service=meal_plan_service,
        activity_repo=activity_repo,
        db=db
    )
```

**Reuses dependency injection from:**
- `get_tracking_orchestrator`
- `get_meal_plan_orchestrator`

---

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│   API Layer: dashboard_v2.py            │
│   - GET /v2/summary                     │
│   - GET /v2/recent-activity             │
└──────────────┬──────────────────────────┘
               │ Depends()
               ▼
┌─────────────────────────────────────────┐
│   Orchestrator: DashboardOrchestrator   │
│   - Coordinates multiple services       │
│   - Aggregates data                     │
│   - Transforms to response format       │
└───┬──────┬──────┬──────┬────────────────┘
    │      │      │      │
    ▼      ▼      ▼      ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│Consump│ │Invent│ │MealPl│ │Activity  │
│tion   │ │ory   │ │an    │ │Repo      │
│Service│ │Mgmt  │ │Service│ │(NEW)     │
│V2     │ │Service│ │V2    │ │          │
│(EXIST)│ │(EXIST)│ │(EXIST)│ │          │
└───────┘ └───────┘ └───────┘ └──────────┘
```

**✅ Maintains clean architecture:**
- API → Orchestrator → Services → Repositories → DB
- No direct DB access in API
- No Agent pattern
- Full dependency injection

---

## What Makes This Clean

### ✅ Follows Existing Patterns

1. **Orchestrator Pattern** ← Same as MealLoggingOrchestrator
2. **Service Reuse** ← Uses services from Phase 1 & 2
3. **Repository Pattern** ← ActivityRepository follows same pattern
4. **Dependency Injection** ← Same DI pattern throughout
5. **No Duplication** ← Reuses existing infrastructure

### ✅ Minimal New Code

**New files needed**: Only 3!
1. `ActivityRepository` (~100 lines)
2. `DashboardOrchestrator` (~200 lines)
3. `dashboard_v2.py` (~100 lines)

**Total**: ~400 lines (vs 280 lines in current dashboard.py)

**Why more lines?** Proper separation of concerns, but uses existing services!

---

## Testing Strategy

### Unit Tests
- `test_activity_repository.py` - Repository pattern tests
- `test_dashboard_orchestrator.py` - Orchestrator logic tests

### Integration Tests
- `test_dashboard_v2_api.py` - Endpoint tests
- Compare v1 vs v2 responses

### Validation
- GET `/dashboard/summary` vs `/dashboard/v2/summary`
- GET `/dashboard/recent-activity` vs `/dashboard/v2/recent-activity`

---

## Estimated Effort

**Based on previous phases:**
- ActivityRepository: ~30 minutes (simple queries)
- DashboardOrchestrator: ~1 hour (mostly aggregation of existing services)
- API endpoints: ~30 minutes (thin layer)
- Testing: ~1 hour

**Total**: ~3 hours (1 session)

**Why so fast?** We're just wiring together services we already built!

---

## Ready to Start

**Phase 3 is perfectly positioned:**
- ✅ All required services already exist (from Phase 1 & 2)
- ✅ Clear orchestrator pattern to follow
- ✅ Minimal new code required
- ✅ Clean architecture maintained

**Shall we begin?**
