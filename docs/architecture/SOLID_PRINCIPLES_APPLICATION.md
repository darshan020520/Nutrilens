# SOLID Principles in NutriLens Architecture

**Date**: 2025-11-24
**Purpose**: Document how SOLID principles are applied in the target architecture

---

## Overview of SOLID

1. **S**ingle Responsibility Principle
2. **O**pen/Closed Principle
3. **L**iskov Substitution Principle
4. **I**nterface Segregation Principle
5. **D**ependency Inversion Principle

---

## 1. Single Responsibility Principle (SRP)

**Definition**: A class should have only one reason to change.

### Current Violations

#### Example 1: PlanningAgent (Multiple Responsibilities)
```python
# backend/app/agents/planning_agent.py
class PlanningAgent:
    def generate_weekly_meal_plan(self, **kwargs):
        # Responsibility 1: Optimization
        meal_plan = self.optimizer.optimize(...)

        # Responsibility 2: Grocery calculation
        grocery_list = self.calculate_grocery_list(...)

        # Responsibility 3: Database persistence
        saved_plan = self._save_meal_plan(meal_plan)

        # Responsibility 4: Logging
        self._create_meal_logs(...)

        # Responsibility 5: WebSocket broadcasting
        self._broadcast_plan_update(...)
```

**Reasons to change**:
1. Optimization algorithm changes
2. Grocery calculation logic changes
3. Database schema changes
4. Logging format changes
5. WebSocket protocol changes

#### Example 2: API Endpoint with Business Logic
```python
# backend/app/api/tracking.py:907-1095
@router.post("/log-external-meal")
async def log_external_meal(request, current_user, db):
    # Responsibility 1: HTTP handling
    # Responsibility 2: Data validation
    # Responsibility 3: Database queries
    # Responsibility 4: Business logic (replace vs create)
    # Responsibility 5: Response formatting
```

### Target Implementation (SRP Applied)

#### Separated into Single-Responsibility Classes

```python
# ===== API Layer: HTTP Handling ONLY =====
# backend/app/api/meal_plan.py
@router.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan(
    request: GeneratePlanRequest,
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """
    Single Responsibility: HTTP request/response handling
    Reason to change: API contract changes
    """
    meal_plan = await orchestrator.generate_weekly_meal_plan(
        user_id=current_user.id,
        start_date=request.start_date,
        preferences=request.preferences
    )
    return MealPlanResponse.from_domain(meal_plan)


# ===== Orchestrator: Workflow Coordination ONLY =====
# backend/app/orchestrators/meal_plan_orchestrator.py
class MealPlanOrchestrator:
    """
    Single Responsibility: Coordinate meal plan generation workflow
    Reason to change: Workflow steps change
    """

    def __init__(
        self,
        optimization_service: OptimizationService,
        grocery_service: GroceryService,
        meal_plan_service: MealPlanService,
        meal_logging_service: MealLoggingService
    ):
        self.optimization_service = optimization_service
        self.grocery_service = grocery_service
        self.meal_plan_service = meal_plan_service
        self.meal_logging_service = meal_logging_service

    async def generate_weekly_meal_plan(self, user_id, start_date, preferences):
        """Coordinates services - no business logic."""
        optimized_plan = await self.optimization_service.optimize(...)
        grocery_list = await self.grocery_service.calculate(...)
        saved_plan = await self.meal_plan_service.create(...)
        await self.meal_logging_service.create_logs(...)
        return saved_plan


# ===== Service: Optimization Logic ONLY =====
# backend/app/services/optimization_service.py
class OptimizationService:
    """
    Single Responsibility: Meal plan optimization logic
    Reason to change: Optimization algorithm changes
    """

    def __init__(self, recipe_repo: RecipeRepository, user_repo: UserRepository):
        self.recipe_repo = recipe_repo
        self.user_repo = user_repo

    async def optimize(self, user_profile, user_goal, inventory, preferences):
        """Optimizes meal plan based on constraints."""
        # ONLY optimization logic, NO database access


# ===== Service: Grocery Calculation ONLY =====
# backend/app/services/grocery_service.py
class GroceryService:
    """
    Single Responsibility: Calculate grocery lists
    Reason to change: Grocery calculation logic changes
    """

    def __init__(self, inventory_repo: InventoryRepository):
        self.inventory_repo = inventory_repo

    async def calculate_for_plan(self, plan, current_inventory):
        """Calculates what to buy based on plan and inventory."""
        # ONLY grocery logic, NO database access


# ===== Service: Meal Plan Business Rules ONLY =====
# backend/app/services/meal_plan_service.py
class MealPlanService:
    """
    Single Responsibility: Meal plan business rules
    Reason to change: Meal plan business rules change
    """

    def __init__(self, meal_plan_repo: MealPlanRepository):
        self.meal_plan_repo = meal_plan_repo

    async def create_meal_plan(self, user_id, plan_data, grocery_list):
        """Applies business rules and delegates persistence."""
        # ONLY business rules, NO database access
        await self.meal_plan_repo.deactivate_active_plans(user_id)
        meal_plan = MealPlan(...)  # Business logic
        return await self.meal_plan_repo.create(meal_plan)


# ===== Repository: Database Access ONLY =====
# backend/app/repositories/meal_plan_repository.py
class MealPlanRepository:
    """
    Single Responsibility: Meal plan data access
    Reason to change: Database schema changes
    """

    def __init__(self, db: Session):
        self.db = db

    async def create(self, meal_plan: MealPlan):
        """Saves to database."""
        # ONLY database operations
        db_meal_plan = MealPlanORM(**meal_plan.dict())
        self.db.add(db_meal_plan)
        self.db.commit()
        return MealPlan.from_orm(db_meal_plan)

    async def deactivate_active_plans(self, user_id: int):
        """Deactivates active plans."""
        # ONLY database operations
        self.db.query(MealPlanORM).filter(...).update({'is_active': False})
        self.db.commit()
```

### SRP Benefits
✅ Each class has ONE reason to change
✅ Easy to test in isolation
✅ Easy to understand
✅ Easy to maintain
✅ Can change optimization without touching database code

---

## 2. Open/Closed Principle (OCP)

**Definition**: Software entities should be open for extension but closed for modification.

### Current Violations

```python
# backend/app/services/meal_plan_service.py
class MealPlanService:
    def calculate_macros(self, recipe_id: int):
        recipe = self.db.query(Recipe).filter_by(id=recipe_id).first()

        # If we want to add a new macro calculation method, we modify this class
        if recipe.dietary_type == "vegan":
            return self._calculate_vegan_macros(recipe)
        elif recipe.dietary_type == "keto":
            return self._calculate_keto_macros(recipe)
        # Adding new dietary type = modifying this class (violates OCP)
```

### Target Implementation (OCP Applied)

#### Using Strategy Pattern

```python
# ===== Abstract Strategy =====
# backend/app/services/macro_calculators/base.py
from abc import ABC, abstractmethod

class MacroCalculatorStrategy(ABC):
    """
    Open for extension: Create new strategies
    Closed for modification: Don't change existing strategies
    """

    @abstractmethod
    def calculate(self, recipe: Recipe) -> Dict[str, float]:
        """Calculate macros for a recipe."""
        pass


# ===== Concrete Strategies (Extensions) =====
# backend/app/services/macro_calculators/standard.py
class StandardMacroCalculator(MacroCalculatorStrategy):
    """Standard macro calculation."""

    def calculate(self, recipe: Recipe) -> Dict[str, float]:
        # Standard calculation logic
        return {"calories": ..., "protein": ..., "carbs": ..., "fat": ...}


# backend/app/services/macro_calculators/vegan.py
class VeganMacroCalculator(MacroCalculatorStrategy):
    """Vegan-specific macro calculation."""

    def calculate(self, recipe: Recipe) -> Dict[str, float]:
        # Vegan-specific adjustments
        return {"calories": ..., "protein": ..., "carbs": ..., "fat": ...}


# backend/app/services/macro_calculators/keto.py
class KetoMacroCalculator(MacroCalculatorStrategy):
    """Keto-specific macro calculation."""

    def calculate(self, recipe: Recipe) -> Dict[str, float]:
        # Keto-specific adjustments
        return {"calories": ..., "protein": ..., "carbs": ..., "fat": ...}


# ===== Context (Uses Strategy) =====
# backend/app/services/meal_plan_service.py
class MealPlanService:
    """
    Closed for modification: Don't need to change this when adding new dietary types
    Open for extension: Add new MacroCalculatorStrategy subclasses
    """

    def __init__(
        self,
        meal_plan_repo: MealPlanRepository,
        macro_calculator_factory: MacroCalculatorFactory
    ):
        self.meal_plan_repo = meal_plan_repo
        self.macro_calculator_factory = macro_calculator_factory

    def calculate_macros(self, recipe: Recipe) -> Dict[str, float]:
        """Calculate macros using appropriate strategy."""
        calculator = self.macro_calculator_factory.get_calculator(recipe.dietary_type)
        return calculator.calculate(recipe)


# ===== Factory =====
# backend/app/services/macro_calculators/factory.py
class MacroCalculatorFactory:
    """Factory to get appropriate calculator."""

    def __init__(self):
        self._calculators = {
            "standard": StandardMacroCalculator(),
            "vegan": VeganMacroCalculator(),
            "keto": KetoMacroCalculator(),
            # Add new dietary type here without modifying MealPlanService
        }

    def get_calculator(self, dietary_type: str) -> MacroCalculatorStrategy:
        return self._calculators.get(dietary_type, self._calculators["standard"])
```

#### Adding New Dietary Type (Extension)

```python
# NEW FILE: backend/app/services/macro_calculators/paleo.py
class PaleoMacroCalculator(MacroCalculatorStrategy):
    """Paleo-specific macro calculation."""

    def calculate(self, recipe: Recipe) -> Dict[str, float]:
        # Paleo-specific adjustments
        return {"calories": ..., "protein": ..., "carbs": ..., "fat": ...}


# ONLY modify factory registration (one line):
# backend/app/services/macro_calculators/factory.py
self._calculators = {
    "standard": StandardMacroCalculator(),
    "vegan": VeganMacroCalculator(),
    "keto": KetoMacroCalculator(),
    "paleo": PaleoMacroCalculator(),  # NEW
}
```

### OCP Benefits
✅ Add new dietary types without modifying existing code
✅ Existing strategies don't break when adding new ones
✅ Easy to test each strategy independently

---

## 3. Liskov Substitution Principle (LSP)

**Definition**: Objects of a superclass should be replaceable with objects of a subclass without breaking the application.

### Current Violations

```python
# backend/app/repositories/meal_plan_repository.py (hypothetical bad example)
class BaseMealPlanRepository:
    def get_active_plan(self, user_id: int) -> MealPlan:
        """Get active meal plan."""
        pass

class SqlMealPlanRepository(BaseMealPlanRepository):
    def get_active_plan(self, user_id: int) -> MealPlan:
        """Returns MealPlan from SQL."""
        return self.db.query(MealPlan).filter(...).first()

class CachedMealPlanRepository(BaseMealPlanRepository):
    def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """Returns MealPlan or None if cache miss."""
        # VIOLATION: Returns Optional[MealPlan] instead of MealPlan
        # Breaks contract - callers expect MealPlan, not Optional
        return self.cache.get(f"meal_plan:{user_id}")
```

### Target Implementation (LSP Applied)

```python
# ===== Base Repository (Contract) =====
# backend/app/repositories/base_meal_plan_repository.py
from abc import ABC, abstractmethod

class BaseMealPlanRepository(ABC):
    """
    LSP: All subclasses must honor this contract
    """

    @abstractmethod
    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """
        Get active meal plan for user.

        Returns:
            MealPlan if exists, None otherwise (contract is clear)
        """
        pass

    @abstractmethod
    async def create(self, meal_plan: MealPlan) -> MealPlan:
        """
        Create meal plan.

        Args:
            meal_plan: Valid MealPlan object

        Returns:
            Created MealPlan with ID populated

        Raises:
            ValueError: If meal_plan is invalid
        """
        pass


# ===== SQL Implementation =====
# backend/app/repositories/sql_meal_plan_repository.py
class SqlMealPlanRepository(BaseMealPlanRepository):
    """SQL implementation - honors base contract."""

    def __init__(self, db: Session):
        self.db = db

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """Returns Optional[MealPlan] as per contract."""
        db_plan = self.db.query(MealPlanORM).filter(
            MealPlanORM.user_id == user_id,
            MealPlanORM.is_active == True
        ).first()
        return MealPlan.from_orm(db_plan) if db_plan else None

    async def create(self, meal_plan: MealPlan) -> MealPlan:
        """Returns MealPlan with ID as per contract."""
        if not meal_plan.user_id:
            raise ValueError("user_id is required")  # Honors contract

        db_meal_plan = MealPlanORM(**meal_plan.dict())
        self.db.add(db_meal_plan)
        self.db.commit()
        self.db.refresh(db_meal_plan)
        return MealPlan.from_orm(db_meal_plan)


# ===== Cached Implementation =====
# backend/app/repositories/cached_meal_plan_repository.py
class CachedMealPlanRepository(BaseMealPlanRepository):
    """Cached implementation - honors base contract."""

    def __init__(self, cache: Redis, fallback_repo: BaseMealPlanRepository):
        self.cache = cache
        self.fallback_repo = fallback_repo

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """
        Returns Optional[MealPlan] as per contract.
        LSP: Caller can use this anywhere SqlMealPlanRepository is used.
        """
        # Try cache
        cached = self.cache.get(f"meal_plan:{user_id}")
        if cached:
            return MealPlan.from_json(cached)

        # Fallback to SQL
        meal_plan = await self.fallback_repo.get_active_plan(user_id)

        # Cache it
        if meal_plan:
            self.cache.set(f"meal_plan:{user_id}", meal_plan.to_json())

        return meal_plan  # Honors contract: Optional[MealPlan]

    async def create(self, meal_plan: MealPlan) -> MealPlan:
        """Honors contract exactly like SQL implementation."""
        if not meal_plan.user_id:
            raise ValueError("user_id is required")

        # Create via fallback
        created = await self.fallback_repo.create(meal_plan)

        # Invalidate cache
        self.cache.delete(f"meal_plan:{meal_plan.user_id}")

        return created  # Honors contract: returns MealPlan


# ===== Service (Doesn't care which implementation) =====
# backend/app/services/meal_plan_service.py
class MealPlanService:
    """
    LSP in action: Works with ANY BaseMealPlanRepository subclass
    """

    def __init__(self, meal_plan_repo: BaseMealPlanRepository):
        # Can be SqlMealPlanRepository OR CachedMealPlanRepository
        # Service doesn't care - both honor the contract
        self.meal_plan_repo = meal_plan_repo

    async def get_or_create_plan(self, user_id: int) -> MealPlan:
        """Works with any repository implementation."""
        plan = await self.meal_plan_repo.get_active_plan(user_id)

        if not plan:
            # Both implementations return MealPlan - LSP satisfied
            plan = await self.meal_plan_repo.create(
                MealPlan(user_id=user_id, ...)
            )

        return plan
```

### LSP Benefits
✅ Can swap SQL for Cached without breaking MealPlanService
✅ Can add new repository implementations (MongoDB, Redis) without changing services
✅ Testing is easy - use in-memory repository

---

## 4. Interface Segregation Principle (ISP)

**Definition**: Clients should not be forced to depend on interfaces they don't use.

### Current Violations

```python
# backend/app/repositories/mega_repository.py (BAD)
class MegaMealPlanRepository:
    """
    ISP Violation: Too many methods in one interface
    Forces clients to depend on methods they don't need
    """

    def get_active_plan(self, user_id: int): pass
    def create(self, meal_plan): pass
    def update(self, meal_plan): pass
    def delete(self, plan_id): pass
    def get_all_plans(self, user_id): pass
    def get_plans_by_date_range(self, user_id, start, end): pass
    def get_grocery_list(self, plan_id): pass
    def calculate_total_calories(self, plan_id): pass
    def optimize_plan(self, plan_id): pass
    def send_notification(self, plan_id): pass  # Why is this here?
    def generate_pdf(self, plan_id): pass       # Why is this here?
    def share_on_social(self, plan_id): pass    # Why is this here?
```

**Problem**: A service that only needs to create meal plans must implement ALL methods.

### Target Implementation (ISP Applied)

#### Segregated Interfaces

```python
# ===== Read Interface =====
# backend/app/repositories/interfaces/meal_plan_reader.py
class IMealPlanReader(ABC):
    """
    ISP: Small, focused interface for reading meal plans
    Only clients that need to read depend on this
    """

    @abstractmethod
    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        pass

    @abstractmethod
    async def get_by_id(self, plan_id: int) -> Optional[MealPlan]:
        pass


# ===== Write Interface =====
# backend/app/repositories/interfaces/meal_plan_writer.py
class IMealPlanWriter(ABC):
    """
    ISP: Small, focused interface for writing meal plans
    Only clients that need to write depend on this
    """

    @abstractmethod
    async def create(self, meal_plan: MealPlan) -> MealPlan:
        pass

    @abstractmethod
    async def update(self, meal_plan: MealPlan) -> MealPlan:
        pass

    @abstractmethod
    async def deactivate_active_plans(self, user_id: int):
        pass


# ===== Query Interface =====
# backend/app/repositories/interfaces/meal_plan_query.py
class IMealPlanQuery(ABC):
    """
    ISP: Small, focused interface for complex queries
    Only clients that need queries depend on this
    """

    @abstractmethod
    async def get_plans_by_date_range(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[MealPlan]:
        pass

    @abstractmethod
    async def get_all_plans(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[MealPlan]:
        pass


# ===== Repository Implements Multiple Small Interfaces =====
# backend/app/repositories/meal_plan_repository.py
class MealPlanRepository(IMealPlanReader, IMealPlanWriter, IMealPlanQuery):
    """
    Implements all interfaces, but clients depend only on what they need
    """

    def __init__(self, db: Session):
        self.db = db

    # IMealPlanReader methods
    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        # Implementation

    async def get_by_id(self, plan_id: int) -> Optional[MealPlan]:
        # Implementation

    # IMealPlanWriter methods
    async def create(self, meal_plan: MealPlan) -> MealPlan:
        # Implementation

    async def update(self, meal_plan: MealPlan) -> MealPlan:
        # Implementation

    async def deactivate_active_plans(self, user_id: int):
        # Implementation

    # IMealPlanQuery methods
    async def get_plans_by_date_range(self, ...) -> List[MealPlan]:
        # Implementation

    async def get_all_plans(self, user_id: int, limit: int) -> List[MealPlan]:
        # Implementation


# ===== Services Depend Only On What They Need =====

# Service that only reads
class MealPlanDisplayService:
    """
    ISP: Depends only on IMealPlanReader
    Doesn't need to know about writing or complex queries
    """

    def __init__(self, reader: IMealPlanReader):
        self.reader = reader  # Small interface

    async def display_current_plan(self, user_id: int):
        plan = await self.reader.get_active_plan(user_id)
        return format_for_display(plan)


# Service that only writes
class MealPlanCreationService:
    """
    ISP: Depends only on IMealPlanWriter
    Doesn't need to know about reading or querying
    """

    def __init__(self, writer: IMealPlanWriter):
        self.writer = writer  # Small interface

    async def create_new_plan(self, meal_plan: MealPlan) -> MealPlan:
        await self.writer.deactivate_active_plans(meal_plan.user_id)
        return await self.writer.create(meal_plan)


# Service that needs both
class MealPlanHistoryService:
    """
    ISP: Depends on IMealPlanReader and IMealPlanQuery
    Doesn't need writing capability
    """

    def __init__(self, reader: IMealPlanReader, query: IMealPlanQuery):
        self.reader = reader
        self.query = query  # Small interfaces

    async def get_history(self, user_id: int) -> List[MealPlan]:
        return await self.query.get_all_plans(user_id, limit=10)
```

### ISP Benefits
✅ Services only depend on methods they actually use
✅ Easy to test - mock only what's needed
✅ Clear separation of read/write concerns (CQRS-like)
✅ Can swap implementations easily

---

## 5. Dependency Inversion Principle (DIP)

**Definition**: High-level modules should not depend on low-level modules. Both should depend on abstractions.

### Current Violations

```python
# backend/app/services/meal_plan_service.py (CURRENT - BAD)
from app.models.database import MealPlan as MealPlanORM  # Depends on concrete ORM

class MealPlanService:
    """
    DIP Violation: High-level service depends on low-level ORM
    """

    def __init__(self, db: Session):
        self.db = db  # Depends on concrete SQLAlchemy Session

    def get_active_plan(self, user_id: int):
        # Directly uses ORM model (low-level detail)
        return self.db.query(MealPlanORM).filter(
            MealPlanORM.user_id == user_id,
            MealPlanORM.is_active == True
        ).first()
```

**Dependency Graph** (BAD):
```
MealPlanService (high-level)
        ↓ depends on
SQLAlchemy Session (low-level)
        ↓ depends on
MealPlanORM (low-level)
        ↓ depends on
PostgreSQL (low-level)
```

### Target Implementation (DIP Applied)

```python
# ===== Abstraction (Interface) =====
# backend/app/repositories/interfaces/meal_plan_repository.py
from abc import ABC, abstractmethod

class IMealPlanRepository(ABC):
    """
    DIP: Abstraction that both high-level and low-level depend on
    """

    @abstractmethod
    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        pass

    @abstractmethod
    async def create(self, meal_plan: MealPlan) -> MealPlan:
        pass


# ===== High-Level Module (Service) =====
# backend/app/services/meal_plan_service.py
class MealPlanService:
    """
    DIP: Depends on abstraction (IMealPlanRepository), not concrete implementation
    """

    def __init__(self, meal_plan_repo: IMealPlanRepository):
        # Depends on interface, not concrete class
        self.meal_plan_repo = meal_plan_repo

    async def get_or_create_active_plan(self, user_id: int) -> MealPlan:
        """High-level business logic - doesn't know about database."""
        plan = await self.meal_plan_repo.get_active_plan(user_id)

        if not plan:
            plan = MealPlan(user_id=user_id, ...)
            plan = await self.meal_plan_repo.create(plan)

        return plan


# ===== Low-Level Module (Repository) =====
# backend/app/repositories/sql_meal_plan_repository.py
class SqlMealPlanRepository(IMealPlanRepository):
    """
    DIP: Depends on same abstraction (IMealPlanRepository)
    """

    def __init__(self, db: Session):
        self.db = db

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """Low-level database details."""
        db_plan = self.db.query(MealPlanORM).filter(
            MealPlanORM.user_id == user_id,
            MealPlanORM.is_active == True
        ).first()
        return MealPlan.from_orm(db_plan) if db_plan else None

    async def create(self, meal_plan: MealPlan) -> MealPlan:
        """Low-level database details."""
        db_meal_plan = MealPlanORM(**meal_plan.dict())
        self.db.add(db_meal_plan)
        self.db.commit()
        self.db.refresh(db_meal_plan)
        return MealPlan.from_orm(db_meal_plan)


# ===== Dependency Injection =====
# backend/app/dependencies.py
def get_meal_plan_repository(db: Session = Depends(get_db)) -> IMealPlanRepository:
    """Factory function for dependency injection."""
    # Can return any implementation of IMealPlanRepository
    return SqlMealPlanRepository(db)
    # Or: return CachedMealPlanRepository(cache, SqlMealPlanRepository(db))
    # Or: return MongoMealPlanRepository(mongo_client)

def get_meal_plan_service(
    repo: IMealPlanRepository = Depends(get_meal_plan_repository)
) -> MealPlanService:
    """Service with injected repository."""
    return MealPlanService(repo)


# ===== API Layer =====
# backend/app/api/meal_plan.py
@router.get("/current")
async def get_current_meal_plan(
    current_user: User = Depends(get_current_user),
    service: MealPlanService = Depends(get_meal_plan_service)  # DIP: Injected
):
    """API doesn't know or care about database implementation."""
    plan = await service.get_or_create_active_plan(current_user.id)
    return MealPlanResponse.from_domain(plan)
```

**Dependency Graph** (GOOD):
```
           IMealPlanRepository (abstraction)
                    ↑      ↑
        ┌───────────┘      └───────────┐
        │                              │
MealPlanService                SqlMealPlanRepository
(high-level)                   (low-level)

Both depend on abstraction, not each other
```

### DIP Benefits with Testing

```python
# ===== Testing with DIP =====
# backend/tests/services/test_meal_plan_service.py
class InMemoryMealPlanRepository(IMealPlanRepository):
    """Test double - implements same interface."""

    def __init__(self):
        self.plans = {}

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        return self.plans.get(user_id)

    async def create(self, meal_plan: MealPlan) -> MealPlan:
        meal_plan.id = len(self.plans) + 1
        self.plans[meal_plan.user_id] = meal_plan
        return meal_plan


def test_get_or_create_active_plan():
    """Test service with in-memory repository - no database needed."""

    # Arrange: Use in-memory repository (DIP allows this!)
    repo = InMemoryMealPlanRepository()
    service = MealPlanService(repo)

    # Act
    plan = await service.get_or_create_active_plan(user_id=123)

    # Assert
    assert plan.user_id == 123
    assert plan.id is not None
```

### DIP Benefits
✅ High-level services don't depend on low-level database details
✅ Can swap PostgreSQL for MongoDB without changing services
✅ Easy to test with fake/mock repositories
✅ Clear separation between business logic and infrastructure

---

## Summary: SOLID Principles Application

| Principle | Where Applied | Benefit |
|-----------|---------------|---------|
| **SRP** | API, Orchestrator, Service, Repository layers | Each class has one reason to change |
| **OCP** | Strategy pattern for calculators, extensible services | Add features without modifying existing code |
| **LSP** | Repository implementations, service interfaces | Can swap implementations without breaking code |
| **ISP** | Segregated repository interfaces (Reader, Writer, Query) | Services depend only on what they need |
| **DIP** | Service depends on repository interface, not concrete class | Can swap database/cache without changing services |

---

## Architecture Layers and SOLID

```
┌─────────────────────────────────────────────┐
│  API Layer                                  │  SRP: HTTP handling only
│  - Validates requests                       │  DIP: Depends on orchestrator interface
│  - Calls orchestrator                       │
│  - Formats responses                        │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Orchestration Layer                        │  SRP: Workflow coordination only
│  - Coordinates services                     │  DIP: Depends on service interfaces
│  - Transaction management                   │  OCP: Extensible workflows
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Service Layer                              │  SRP: Business logic only
│  - Business rules                           │  DIP: Depends on repository interfaces
│  - Domain logic                             │  ISP: Small, focused services
│  - NO database access                       │  OCP: Extensible via strategies
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Repository Layer                           │  SRP: Data access only
│  - Database queries                         │  LSP: Swappable implementations
│  - ORM usage                                │  ISP: Segregated interfaces
│  - Caching                                  │
└─────────────────────────────────────────────┘
```

All five SOLID principles work together to create a maintainable, testable, and extensible architecture.
