# Systematic Migration Approach

**Date**: 2025-11-24
**Purpose**: Step-by-step approach to migrate from current architecture to target architecture

---

## Overview

We have analyzed **77+ endpoints** across **11 API files**. This document provides a systematic, manageable approach to restructure them all.

---

## Migration Strategy: Vertical Slice Approach

Instead of migrating layer-by-layer (which breaks everything), we migrate **one feature at a time** (vertical slice):

```
❌ BAD: Horizontal (Layer by Layer)
   Step 1: Migrate ALL repositories (breaks everything)
   Step 2: Migrate ALL services (still broken)
   Step 3: Migrate ALL APIs (finally works)

✅ GOOD: Vertical (Feature by Feature)
   Step 1: Migrate Meal Plan Generation (works alongside old code)
   Step 2: Migrate Meal Logging (works alongside old code)
   Step 3: Migrate Inventory Management (works alongside old code)
   ...old and new coexist, incremental progress
```

---

## Phase 0: Preparation (Week 1)

### 0.1 Set Up New Structure

Create directory structure for target architecture:

```bash
backend/
├── app/
│   ├── api/                    # Existing (keep)
│   ├── orchestrators/          # NEW
│   │   ├── __init__.py
│   │   ├── meal_plan_orchestrator.py
│   │   ├── tracking_orchestrator.py
│   │   ├── dashboard_orchestrator.py
│   │   └── receipt_orchestrator.py
│   ├── services/               # Existing (refactor)
│   │   ├── strategies/         # NEW (for Strategy pattern)
│   │   └── ...
│   ├── repositories/           # NEW
│   │   ├── __init__.py
│   │   ├── interfaces/         # NEW
│   │   │   ├── __init__.py
│   │   │   ├── meal_plan_repository.py
│   │   │   ├── meal_log_repository.py
│   │   │   └── ...
│   │   ├── meal_plan_repository.py
│   │   ├── meal_log_repository.py
│   │   └── ...
│   ├── domain/                 # Existing (Wave 1 value objects)
│   │   └── user/
│   │       └── value_objects.py  # BMI, BMR, TDEE
│   ├── dtos/                   # NEW (separate from schemas)
│   │   ├── __init__.py
│   │   ├── meal_plan_dto.py
│   │   └── ...
│   ├── clients/                # NEW (for microservices)
│   │   ├── __init__.py
│   │   ├── receipt_scanner_client.py
│   │   └── ...
│   ├── events/                 # NEW (for Observer pattern)
│   │   ├── __init__.py
│   │   ├── event_publisher.py
│   │   ├── events.py
│   │   └── handlers/
│   └── dependencies.py         # Existing (enhance with DI)
```

### 0.2 Create Base Classes

```python
# backend/app/repositories/interfaces/base_repository.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')

class IRepository(ABC, Generic[T]):
    """Base repository interface."""

    @abstractmethod
    async def get_by_id(self, id: int) -> Optional[T]:
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        pass

    @abstractmethod
    async def delete(self, id: int) -> bool:
        pass


# backend/app/orchestrators/base_orchestrator.py
class BaseOrchestrator:
    """Base orchestrator with common functionality."""

    def __init__(self, event_publisher: Optional[EventPublisher] = None):
        self.event_publisher = event_publisher

    async def publish_event(self, event_type: str, event_data: Any):
        """Publish event if publisher is available."""
        if self.event_publisher:
            await self.event_publisher.publish(event_type, event_data)
```

---

## Phase 1: Meal Plan Generation (Week 2-3)

**Goal**: Migrate most complex endpoint first as a reference implementation

### Step 1.1: Create Repository Layer

```python
# backend/app/repositories/interfaces/meal_plan_repository.py
class IMealPlanRepository(ABC):
    """Interface for meal plan data access."""

    @abstractmethod
    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        pass

    @abstractmethod
    async def create(self, meal_plan: MealPlan) -> MealPlan:
        pass

    @abstractmethod
    async def deactivate_active_plans(self, user_id: int):
        pass


# backend/app/repositories/meal_plan_repository.py
class MealPlanRepository(IMealPlanRepository):
    """PostgreSQL implementation."""

    def __init__(self, db: Session):
        self.db = db

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        db_plan = self.db.query(MealPlanORM).filter(
            MealPlanORM.user_id == user_id,
            MealPlanORM.is_active == True
        ).first()
        return MealPlan.from_orm(db_plan) if db_plan else None

    async def create(self, meal_plan: MealPlan) -> MealPlan:
        # Implementation
        pass

    async def deactivate_active_plans(self, user_id: int):
        # Implementation
        pass
```

### Step 1.2: Refactor Service to Use Repository

```python
# backend/app/services/meal_plan_service_v2.py (new version)
class MealPlanServiceV2:
    """Refactored service using repository."""

    def __init__(self, meal_plan_repo: IMealPlanRepository):
        self.meal_plan_repo = meal_plan_repo

    async def create_meal_plan(
        self,
        user_id: int,
        plan_data: Dict,
        grocery_list: Dict
    ) -> MealPlan:
        """Business logic only, NO DB access."""
        await self.meal_plan_repo.deactivate_active_plans(user_id)

        meal_plan = MealPlan(
            user_id=user_id,
            plan_data=plan_data,
            grocery_list=grocery_list,
            # Business rules...
        )

        return await self.meal_plan_repo.create(meal_plan)
```

### Step 1.3: Create Orchestrator

```python
# backend/app/orchestrators/meal_plan_orchestrator.py
class MealPlanOrchestrator(BaseOrchestrator):
    """Orchestrator for meal plan workflows."""

    def __init__(
        self,
        meal_plan_service: MealPlanServiceV2,
        optimization_service: OptimizationService,
        grocery_service: GroceryService,
        meal_logging_service: MealLoggingService,
        event_publisher: Optional[EventPublisher] = None
    ):
        super().__init__(event_publisher)
        self.meal_plan_service = meal_plan_service
        self.optimization_service = optimization_service
        self.grocery_service = grocery_service
        self.meal_logging_service = meal_logging_service

    async def generate_weekly_meal_plan(
        self,
        user_id: int,
        start_date: datetime,
        preferences: Dict
    ) -> MealPlan:
        """Coordinate meal plan generation."""
        # Implementation from design patterns doc
        pass
```

### Step 1.4: Create New API Endpoint (Side by Side)

```python
# backend/app/api/meal_plan_v2.py (NEW router, runs alongside old)
from fastapi import APIRouter

router_v2 = APIRouter(prefix="/meal-plans/v2", tags=["meal-plans-v2"])

@router_v2.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan(
    request: GeneratePlanRequest,
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """New implementation using orchestrator."""
    meal_plan = await orchestrator.generate_weekly_meal_plan(
        user_id=current_user.id,
        start_date=request.start_date,
        preferences=request.preferences
    )
    return MealPlanResponse.from_domain(meal_plan)


# backend/app/main.py
# Include both routers
app.include_router(meal_plan.router)      # Old
app.include_router(meal_plan_v2.router_v2)  # New
```

### Step 1.5: Test and Compare

```python
# backend/tests/api/test_meal_plan_v2.py
@pytest.mark.integration
def test_generate_meal_plan_v2_matches_v1():
    """Ensure new implementation produces same results as old."""

    # Call old endpoint
    old_response = client.post("/meal-plans/generate", json={
        "start_date": "2025-11-24",
        "preferences": {}
    })

    # Call new endpoint
    new_response = client.post("/meal-plans/v2/generate", json={
        "start_date": "2025-11-24",
        "preferences": {}
    })

    # Compare results (should be identical)
    assert old_response.json()["total_calories"] == new_response.json()["total_calories"]
    assert len(old_response.json()["plan_data"]["week_plan"]) == len(new_response.json()["plan_data"]["week_plan"])
```

### Step 1.6: Gradual Cutover

```python
# backend/app/api/meal_plan.py (update old endpoint)
@router.post("/generate")
async def generate_meal_plan(
    request: GeneratePlanRequest,
    use_new_implementation: bool = Query(False),  # Feature flag
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate meal plan with optional new implementation."""

    if use_new_implementation:
        # Use new orchestrator
        orchestrator = get_meal_plan_orchestrator(db)
        return await generate_meal_plan_v2(request, orchestrator, current_user)

    # Old implementation (fallback)
    agent = PlanningAgent(db)
    # ...existing code
```

### Step 1.7: Complete Cutover

After 1-2 weeks of testing with feature flag:

```python
# backend/app/api/meal_plan.py
@router.post("/generate")
async def generate_meal_plan(
    request: GeneratePlanRequest,
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """Generate meal plan (refactored)."""
    # Old implementation deleted
    # Only new implementation remains
    meal_plan = await orchestrator.generate_weekly_meal_plan(...)
    return MealPlanResponse.from_domain(meal_plan)
```

---

## Phase 2: Meal Logging (Week 4-5)

Apply same approach to tracking endpoints:

### Priority Order
1. `POST /tracking/log-meal` (uses TrackingOrchestrator)
2. `POST /tracking/log-external-meal` (has 188 lines in API)
3. `GET /tracking/today` (uses ConsumptionService)

### Steps (Same as Phase 1)
1. Create MealLogRepository
2. Refactor ConsumptionService to use repository
3. Create TrackingOrchestrator
4. Create `/tracking/v2/*` endpoints
5. Test side-by-side
6. Gradual cutover
7. Delete old code

---

## Phase 3: Dashboard (Week 6)

### Steps
1. Create DashboardOrchestrator (176 lines from API moves here)
2. Extract helper functions to services
3. Use existing services via dependency injection
4. Create `/dashboard/v2/summary`
5. Test and cutover

---

## Phase 4: Receipt Processing (Week 7)

### Steps
1. Create IReceiptScannerClient interface
2. Implement HttpReceiptScannerClient with retry/circuit breaker
3. Create ReceiptOrchestrator (175 lines from API moves here)
4. Create `/receipt/v2/upload`
5. Test and cutover

---

## Phase 5: Consolidate WhatsApp Endpoints (Week 8)

### Steps
1. Delete `orchestrator.py` (duplicate code)
2. Make WhatsApp agent call main API directly
3. Remove 188 lines of duplicate logic

---

## Phase 6: Remaining Endpoints (Week 9-12)

Group by domain and apply same pattern:

### Week 9: Inventory Endpoints
- `/inventory/add-items`
- `/inventory/items`
- `/inventory/status`

### Week 10: Onboarding Endpoints
- `/onboarding/basic-info`
- `/onboarding/goal-selection`
- `/onboarding/path-selection`

### Week 11: Nutrition Chat Endpoints
- Already well-structured, minor refactoring

### Week 12: Cleanup
- Delete all old code
- Remove feature flags
- Update documentation

---

## Tracking Progress

### Progress Dashboard

```python
# Track migration status
ENDPOINTS_STATUS = {
    "meal_plan": {
        "POST /generate": "✅ Migrated",
        "GET /current": "✅ Migrated",
        "GET /current/with-status": "🔄 In Progress",
        "POST /{plan_id}/swap-meal": "⏳ Pending",
        # ...
    },
    "tracking": {
        "POST /log-meal": "🔄 In Progress",
        "POST /log-external-meal": "⏳ Pending",
        # ...
    },
    # ...
}
```

### Migration Checklist (Per Endpoint)

```markdown
## Endpoint: POST /meal-plans/generate

- [x] Create repository interface (IMealPlanRepository)
- [x] Implement repository (MealPlanRepository)
- [x] Refactor service to use repository (MealPlanServiceV2)
- [x] Create orchestrator (MealPlanOrchestrator)
- [x] Create new API endpoint (/v2/generate)
- [x] Write comparison tests (v1 vs v2)
- [x] Deploy with feature flag
- [x] Monitor in production (1 week)
- [x] Enable feature flag for all users
- [x] Cut over to new implementation
- [x] Delete old code
- [x] Update documentation
```

---

## Testing Strategy

### 1. Unit Tests (Per Layer)

```python
# Test repository (mock database)
def test_meal_plan_repository_create():
    mock_db = Mock(Session)
    repo = MealPlanRepository(mock_db)
    # Test repository logic

# Test service (mock repository)
def test_meal_plan_service_create():
    mock_repo = Mock(IMealPlanRepository)
    service = MealPlanServiceV2(mock_repo)
    # Test business logic

# Test orchestrator (mock services)
def test_meal_plan_orchestrator_generate():
    mock_service = Mock(MealPlanServiceV2)
    orchestrator = MealPlanOrchestrator(mock_service, ...)
    # Test coordination logic
```

### 2. Integration Tests (Real Database)

```python
@pytest.mark.integration
def test_meal_plan_generation_end_to_end():
    """Test with real database, real services."""
    response = client.post("/meal-plans/v2/generate", json={...})
    assert response.status_code == 200

    # Verify database state
    db_plan = db.query(MealPlan).filter(...).first()
    assert db_plan is not None
```

### 3. Comparison Tests (Behavior Preservation)

```python
def test_new_matches_old():
    """Ensure new implementation behaves like old."""
    old_result = call_old_endpoint()
    new_result = call_new_endpoint()

    assert old_result["total_calories"] == new_result["total_calories"]
    assert old_result["plan_data"] == new_result["plan_data"]
```

### 4. Load Tests

```python
# locustfile.py
class MealPlanUser(HttpUser):
    @task
    def generate_meal_plan_v2(self):
        self.client.post("/meal-plans/v2/generate", json={...})

# Run: locust -f locustfile.py --users 100 --spawn-rate 10
```

---

## Rollback Plan

### If New Implementation Fails

```python
# Instant rollback via feature flag
@router.post("/generate")
async def generate_meal_plan(
    use_new_implementation: bool = Query(settings.USE_NEW_MEAL_PLAN_IMPL),
    ...
):
    if use_new_implementation:
        # New implementation
        pass
    else:
        # Old implementation (kept as backup)
        pass

# In settings.py or environment variable
USE_NEW_MEAL_PLAN_IMPL = False  # Rollback by setting to False
```

### Rollback Steps
1. Set feature flag to `False`
2. Redeploy
3. Fix issues in new implementation
4. Test thoroughly
5. Re-enable feature flag

---

## Success Metrics

### Per Phase

- [ ] All tests pass (unit, integration, comparison)
- [ ] New endpoint performance ≤ old endpoint performance
- [ ] Zero production errors for 1 week
- [ ] Code coverage ≥ 80%
- [ ] Documentation updated

### Overall (End of Migration)

- [ ] **Zero code duplication** (grocery calculation in ONE place)
- [ ] **All services use repositories** (no `self.db.query()` in services)
- [ ] **All APIs use orchestrators** (no business logic in API)
- [ ] **All microservices use clients** (no direct httpx in API)
- [ ] **77+ endpoints migrated**
- [ ] **Test coverage ≥ 80%**
- [ ] **Documentation complete**

---

## Timeline Summary

| Phase | Duration | Endpoints | Status |
|-------|----------|-----------|--------|
| Phase 0: Preparation | 1 week | - | ⏳ Not Started |
| Phase 1: Meal Plan Generation | 2 weeks | 16 endpoints | ⏳ Not Started |
| Phase 2: Meal Logging | 2 weeks | 12 endpoints | ⏳ Not Started |
| Phase 3: Dashboard | 1 week | 2 endpoints | ⏳ Not Started |
| Phase 4: Receipt Processing | 1 week | 4 endpoints | ⏳ Not Started |
| Phase 5: WhatsApp Consolidation | 1 week | 4 endpoints | ⏳ Not Started |
| Phase 6: Remaining Endpoints | 4 weeks | 39 endpoints | ⏳ Not Started |
| **Total** | **12 weeks** | **77 endpoints** | |

---

## How to Use This Approach

### Week by Week

1. **Week 1**: Set up structure, create base classes
2. **Week 2**: Start Phase 1 - Meal Plan repositories and services
3. **Week 3**: Complete Phase 1 - Test and cutover
4. **Week 4**: Start Phase 2 - Tracking repositories and services
5. **Week 5**: Complete Phase 2 - Test and cutover
6. **Week 6**: Phase 3 - Dashboard
7. **Week 7**: Phase 4 - Receipt Processing
8. **Week 8**: Phase 5 - WhatsApp Consolidation
9. **Week 9-12**: Phase 6 - Remaining endpoints

### Daily Workflow

```bash
# 1. Create new branch
git checkout -b migrate/meal-plan-generation

# 2. Create repository
touch backend/app/repositories/meal_plan_repository.py
# Implement...

# 3. Create service v2
touch backend/app/services/meal_plan_service_v2.py
# Implement...

# 4. Create orchestrator
touch backend/app/orchestrators/meal_plan_orchestrator.py
# Implement...

# 5. Create new API endpoint
touch backend/app/api/meal_plan_v2.py
# Implement...

# 6. Write tests
touch backend/tests/api/test_meal_plan_v2.py
pytest backend/tests/api/test_meal_plan_v2.py

# 7. Run comparison tests
pytest backend/tests/api/test_meal_plan_comparison.py

# 8. Commit and PR
git add .
git commit -m "Migrate meal plan generation to new architecture"
git push origin migrate/meal-plan-generation

# 9. Review, test in staging, deploy to production with feature flag

# 10. Monitor for 1 week, then complete cutover
```

---

## Key Principles

1. **Incremental**: One feature at a time
2. **Side-by-side**: Old and new coexist
3. **Tested**: Compare behavior before cutover
4. **Safe**: Feature flags for instant rollback
5. **Measurable**: Track progress with checklist
6. **Documented**: Update docs as you go

This approach ensures you **never break production** while making steady progress toward the target architecture.
