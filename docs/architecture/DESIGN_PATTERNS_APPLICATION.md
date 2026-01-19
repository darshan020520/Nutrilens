# Design Patterns in NutriLens Architecture

**Date**: 2025-11-24
**Purpose**: Document which design patterns are used and where

---

## Design Patterns Overview

We use **8 key design patterns** in the target architecture:

1. **Repository Pattern** - Data access abstraction
2. **Dependency Injection Pattern** - Loose coupling
3. **Strategy Pattern** - Interchangeable algorithms
4. **Factory Pattern** - Object creation
5. **Facade Pattern** - Simplified interface
6. **Observer Pattern** - Event-driven communication
7. **Unit of Work Pattern** - Transaction management
8. **DTO Pattern** - Data transfer between layers

---

## 1. Repository Pattern

**Purpose**: Abstract data access logic from business logic

**Location**: `backend/app/repositories/`

### Problem It Solves
```python
# BAD: Service directly queries database
class MealPlanService:
    def __init__(self, db: Session):
        self.db = db

    def get_active_plan(self, user_id: int):
        # Business logic mixed with database queries
        return self.db.query(MealPlan).filter(
            MealPlan.user_id == user_id,
            MealPlan.is_active == True
        ).first()
```

### Implementation

```python
# ===== Repository Interface =====
# backend/app/repositories/interfaces/meal_plan_repository.py
from abc import ABC, abstractmethod

class IMealPlanRepository(ABC):
    """Repository interface - defines contract."""

    @abstractmethod
    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """Get active meal plan for user."""
        pass

    @abstractmethod
    async def create(self, meal_plan: MealPlan) -> MealPlan:
        """Create meal plan."""
        pass

    @abstractmethod
    async def update(self, meal_plan: MealPlan) -> MealPlan:
        """Update meal plan."""
        pass


# ===== Concrete Repository =====
# backend/app/repositories/meal_plan_repository.py
class MealPlanRepository(IMealPlanRepository):
    """PostgreSQL implementation of meal plan repository."""

    def __init__(self, db: Session):
        self.db = db

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """Encapsulates database query."""
        db_plan = self.db.query(MealPlanORM).filter(
            MealPlanORM.user_id == user_id,
            MealPlanORM.is_active == True
        ).first()

        if not db_plan:
            return None

        # Convert ORM to domain model
        return MealPlan.from_orm(db_plan)

    async def create(self, meal_plan: MealPlan) -> MealPlan:
        """Encapsulates database insert."""
        db_meal_plan = MealPlanORM(
            user_id=meal_plan.user_id,
            week_start_date=meal_plan.week_start_date,
            plan_data=meal_plan.plan_data,
            grocery_list=meal_plan.grocery_list,
            total_calories=meal_plan.total_calories,
            is_active=meal_plan.is_active
        )

        self.db.add(db_meal_plan)
        self.db.commit()
        self.db.refresh(db_meal_plan)

        return MealPlan.from_orm(db_meal_plan)

    async def update(self, meal_plan: MealPlan) -> MealPlan:
        """Encapsulates database update."""
        db_plan = self.db.query(MealPlanORM).filter_by(id=meal_plan.id).first()

        if not db_plan:
            raise ValueError(f"MealPlan {meal_plan.id} not found")

        db_plan.plan_data = meal_plan.plan_data
        db_plan.grocery_list = meal_plan.grocery_list
        db_plan.total_calories = meal_plan.total_calories

        self.db.commit()
        self.db.refresh(db_plan)

        return MealPlan.from_orm(db_plan)


# ===== Service Uses Repository =====
# backend/app/services/meal_plan_service.py
class MealPlanService:
    """Service only contains business logic."""

    def __init__(self, meal_plan_repo: IMealPlanRepository):
        self.meal_plan_repo = meal_plan_repo  # Depends on interface

    async def get_or_create_active_plan(self, user_id: int) -> MealPlan:
        """Business logic - NO database queries."""
        plan = await self.meal_plan_repo.get_active_plan(user_id)

        if not plan:
            # Business rule: Create default plan
            plan = MealPlan(
                user_id=user_id,
                week_start_date=datetime.now(),
                is_active=True
            )
            plan = await self.meal_plan_repo.create(plan)

        return plan
```

### Benefits
✅ Service can be tested without database
✅ Can swap PostgreSQL for MongoDB without changing service
✅ Queries are centralized (no duplication)
✅ Clear separation: business logic vs data access

---

## 2. Dependency Injection Pattern

**Purpose**: Provide dependencies from outside rather than creating them internally

**Location**: `backend/app/dependencies.py`, FastAPI `Depends()`

### Problem It Solves
```python
# BAD: Service creates its own dependencies
class MealPlanService:
    def __init__(self):
        self.db = Session()  # Creates own database connection
        self.meal_plan_repo = MealPlanRepository(self.db)  # Creates own repo
        # Hard to test, tightly coupled
```

### Implementation

```python
# ===== Dependency Provider =====
# backend/app/dependencies.py
from fastapi import Depends
from sqlalchemy.orm import Session

def get_db() -> Session:
    """Provides database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_meal_plan_repository(
    db: Session = Depends(get_db)
) -> IMealPlanRepository:
    """Provides meal plan repository."""
    return MealPlanRepository(db)

def get_meal_plan_service(
    meal_plan_repo: IMealPlanRepository = Depends(get_meal_plan_repository)
) -> MealPlanService:
    """Provides meal plan service with injected repository."""
    return MealPlanService(meal_plan_repo)

def get_meal_plan_orchestrator(
    meal_plan_service: MealPlanService = Depends(get_meal_plan_service),
    optimization_service: OptimizationService = Depends(get_optimization_service),
    grocery_service: GroceryService = Depends(get_grocery_service),
    meal_logging_service: MealLoggingService = Depends(get_meal_logging_service)
) -> MealPlanOrchestrator:
    """Provides orchestrator with all injected services."""
    return MealPlanOrchestrator(
        meal_plan_service=meal_plan_service,
        optimization_service=optimization_service,
        grocery_service=grocery_service,
        meal_logging_service=meal_logging_service
    )


# ===== API Uses Dependency Injection =====
# backend/app/api/meal_plan.py
@router.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan(
    request: GeneratePlanRequest,
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """
    Dependency Injection in action:
    - orchestrator is injected (not created)
    - All its dependencies are injected recursively
    """
    meal_plan = await orchestrator.generate_weekly_meal_plan(
        user_id=current_user.id,
        start_date=request.start_date,
        preferences=request.preferences
    )
    return MealPlanResponse.from_domain(meal_plan)


# ===== Testing with Dependency Injection =====
# backend/tests/api/test_meal_plan.py
def test_generate_meal_plan():
    """Override dependencies for testing."""

    # Create mock dependencies
    mock_orchestrator = Mock(MealPlanOrchestrator)
    mock_orchestrator.generate_weekly_meal_plan.return_value = MealPlan(...)

    # Override dependency
    app.dependency_overrides[get_meal_plan_orchestrator] = lambda: mock_orchestrator

    # Test API
    response = client.post("/meal-plans/generate", json={...})

    assert response.status_code == 200
    mock_orchestrator.generate_weekly_meal_plan.assert_called_once()
```

### Benefits
✅ Easy to test (inject mocks)
✅ Loose coupling (no hardcoded dependencies)
✅ Easy to swap implementations
✅ FastAPI handles dependency creation automatically

---

## 3. Strategy Pattern

**Purpose**: Define a family of algorithms, encapsulate each one, and make them interchangeable

**Location**: `backend/app/services/strategies/`

### Problem It Solves
```python
# BAD: Service has multiple if-else for different algorithms
class OptimizationService:
    def optimize(self, goal_type: str, ...):
        if goal_type == "muscle_gain":
            # Muscle gain optimization logic
        elif goal_type == "fat_loss":
            # Fat loss optimization logic
        elif goal_type == "body_recomp":
            # Body recomp optimization logic
        # Adding new goal type = modifying this method
```

### Implementation

```python
# ===== Strategy Interface =====
# backend/app/services/strategies/optimization_strategy.py
from abc import ABC, abstractmethod

class OptimizationStrategy(ABC):
    """Strategy interface for meal plan optimization."""

    @abstractmethod
    def optimize(
        self,
        user_profile: UserProfile,
        recipes: List[Recipe],
        constraints: Dict
    ) -> List[Recipe]:
        """Optimize recipe selection based on strategy."""
        pass


# ===== Concrete Strategies =====
# backend/app/services/strategies/muscle_gain_strategy.py
class MuscleGainOptimizationStrategy(OptimizationStrategy):
    """Optimization strategy for muscle gain goal."""

    def optimize(self, user_profile, recipes, constraints):
        """
        Muscle gain optimization:
        - Higher protein (1.6-2.2g per kg bodyweight)
        - Calorie surplus (200-500 calories)
        - Focus on resistance training days
        """
        target_protein = user_profile.weight_kg * 2.0
        target_calories = user_profile.tdee + 300

        # Filter recipes by protein-rich criteria
        high_protein_recipes = [
            r for r in recipes
            if r.macros_per_serving.get('protein_g', 0) > 30
        ]

        # Select recipes to hit targets
        selected = self._select_recipes_for_targets(
            recipes=high_protein_recipes,
            target_calories=target_calories,
            target_protein=target_protein
        )

        return selected


# backend/app/services/strategies/fat_loss_strategy.py
class FatLossOptimizationStrategy(OptimizationStrategy):
    """Optimization strategy for fat loss goal."""

    def optimize(self, user_profile, recipes, constraints):
        """
        Fat loss optimization:
        - Moderate protein (1.6g per kg)
        - Calorie deficit (300-500 calories)
        - High volume, low calorie meals
        """
        target_protein = user_profile.weight_kg * 1.6
        target_calories = user_profile.tdee - 400

        # Filter recipes by low-calorie, high-volume
        low_cal_recipes = [
            r for r in recipes
            if r.macros_per_serving.get('calories', 0) < 400
            and r.tags and 'high_volume' in r.tags
        ]

        selected = self._select_recipes_for_targets(
            recipes=low_cal_recipes,
            target_calories=target_calories,
            target_protein=target_protein
        )

        return selected


# backend/app/services/strategies/body_recomp_strategy.py
class BodyRecompOptimizationStrategy(OptimizationStrategy):
    """Optimization strategy for body recomposition."""

    def optimize(self, user_profile, recipes, constraints):
        """
        Body recomp optimization:
        - High protein (2.0g per kg)
        - Maintenance calories
        - Nutrient timing (carbs around workouts)
        """
        target_protein = user_profile.weight_kg * 2.0
        target_calories = user_profile.tdee

        # Balance of protein, moderate carbs, moderate fats
        balanced_recipes = [
            r for r in recipes
            if 25 <= r.macros_per_serving.get('protein_g', 0) <= 40
        ]

        selected = self._select_recipes_for_targets(
            recipes=balanced_recipes,
            target_calories=target_calories,
            target_protein=target_protein
        )

        return selected


# ===== Strategy Factory =====
# backend/app/services/strategies/optimization_factory.py
class OptimizationStrategyFactory:
    """Factory to get appropriate optimization strategy."""

    def __init__(self):
        self._strategies = {
            "muscle_gain": MuscleGainOptimizationStrategy(),
            "fat_loss": FatLossOptimizationStrategy(),
            "body_recomp": BodyRecompOptimizationStrategy(),
            "maintenance": MaintenanceOptimizationStrategy(),
            "endurance": EnduranceOptimizationStrategy()
        }

    def get_strategy(self, goal_type: str) -> OptimizationStrategy:
        """Get strategy for goal type."""
        strategy = self._strategies.get(goal_type)
        if not strategy:
            raise ValueError(f"Unknown goal type: {goal_type}")
        return strategy


# ===== Service Uses Strategy =====
# backend/app/services/optimization_service.py
class OptimizationService:
    """Service uses strategy pattern for optimization."""

    def __init__(
        self,
        recipe_repo: IRecipeRepository,
        strategy_factory: OptimizationStrategyFactory
    ):
        self.recipe_repo = recipe_repo
        self.strategy_factory = strategy_factory

    async def optimize(
        self,
        user_profile: UserProfile,
        user_goal: UserGoal,
        constraints: Dict
    ) -> List[Recipe]:
        """
        Optimize meal plan using appropriate strategy.
        NO if-else needed!
        """
        # Get all available recipes
        recipes = await self.recipe_repo.get_all_for_user(
            dietary_type=user_profile.dietary_type,
            allergies=user_profile.allergies
        )

        # Get strategy for user's goal
        strategy = self.strategy_factory.get_strategy(user_goal.goal_type)

        # Use strategy to optimize
        optimized_recipes = strategy.optimize(
            user_profile=user_profile,
            recipes=recipes,
            constraints=constraints
        )

        return optimized_recipes
```

### Adding New Strategy (Extension)
```python
# NEW FILE: backend/app/services/strategies/keto_strategy.py
class KetoOptimizationStrategy(OptimizationStrategy):
    """Optimization for keto diet."""

    def optimize(self, user_profile, recipes, constraints):
        """
        Keto optimization:
        - Very high fat (70% of calories)
        - Very low carbs (<50g per day)
        - Moderate protein
        """
        # Implementation
        pass

# ONLY add to factory (one line):
self._strategies["keto"] = KetoOptimizationStrategy()
```

### Benefits
✅ Add new goal types without modifying service
✅ Each strategy is isolated and testable
✅ Easy to swap strategies at runtime
✅ Follows Open/Closed Principle

---

## 4. Factory Pattern

**Purpose**: Create objects without specifying exact class

**Location**: Various `*_factory.py` files

### Implementation

```python
# ===== Factory for Repositories =====
# backend/app/repositories/factory.py
class RepositoryFactory:
    """Factory to create repositories with caching."""

    def __init__(self, db: Session, cache: Optional[Redis] = None):
        self.db = db
        self.cache = cache

    def create_meal_plan_repository(self) -> IMealPlanRepository:
        """Create meal plan repository with optional caching."""
        base_repo = MealPlanRepository(self.db)

        if self.cache:
            # Wrap with caching decorator
            return CachedMealPlanRepository(self.cache, base_repo)

        return base_repo

    def create_user_repository(self) -> IUserRepository:
        """Create user repository."""
        return UserRepository(self.db)


# ===== Factory for Services =====
# backend/app/services/factory.py
class ServiceFactory:
    """Factory to create services with all dependencies."""

    def __init__(self, repo_factory: RepositoryFactory):
        self.repo_factory = repo_factory

    def create_meal_plan_service(self) -> MealPlanService:
        """Create meal plan service with repository."""
        meal_plan_repo = self.repo_factory.create_meal_plan_repository()
        return MealPlanService(meal_plan_repo)

    def create_optimization_service(self) -> OptimizationService:
        """Create optimization service with dependencies."""
        recipe_repo = self.repo_factory.create_recipe_repository()
        strategy_factory = OptimizationStrategyFactory()
        return OptimizationService(recipe_repo, strategy_factory)
```

### Benefits
✅ Centralized object creation
✅ Easy to add caching/logging/monitoring
✅ Can switch between implementations easily

---

## 5. Facade Pattern

**Purpose**: Provide simplified interface to complex subsystem

**Location**: Orchestrators act as facades

### Implementation

```python
# ===== Complex Subsystem =====
# Multiple services with complex interactions

# ===== Facade (Orchestrator) =====
# backend/app/orchestrators/meal_plan_orchestrator.py
class MealPlanOrchestrator:
    """
    Facade Pattern: Simplifies complex meal plan generation workflow
    Hides complexity of coordinating multiple services
    """

    def __init__(
        self,
        user_service: UserService,
        optimization_service: OptimizationService,
        grocery_service: GroceryService,
        meal_plan_service: MealPlanService,
        meal_logging_service: MealLoggingService,
        notification_service: NotificationService,
        event_publisher: EventPublisher
    ):
        # Many dependencies - complex subsystem
        self.user_service = user_service
        self.optimization_service = optimization_service
        self.grocery_service = grocery_service
        self.meal_plan_service = meal_plan_service
        self.meal_logging_service = meal_logging_service
        self.notification_service = notification_service
        self.event_publisher = event_publisher

    async def generate_weekly_meal_plan(
        self,
        user_id: int,
        start_date: datetime,
        preferences: Dict
    ) -> MealPlan:
        """
        Simplified interface: One method to do everything
        Hides 7-step complex workflow
        """
        # Step 1: Get user data
        user_profile = await self.user_service.get_profile(user_id)
        user_goal = await self.user_service.get_goal(user_id)
        inventory = await self.user_service.get_inventory_summary(user_id)

        # Step 2: Optimize
        optimized_plan = await self.optimization_service.optimize(
            user_profile=user_profile,
            user_goal=user_goal,
            inventory=inventory,
            preferences=preferences
        )

        # Step 3: Calculate groceries
        grocery_list = await self.grocery_service.calculate_for_plan(
            plan=optimized_plan,
            current_inventory=inventory
        )

        # Step 4: Save plan
        saved_plan = await self.meal_plan_service.create_meal_plan(
            user_id=user_id,
            plan_data=optimized_plan,
            grocery_list=grocery_list
        )

        # Step 5: Create logs
        await self.meal_logging_service.create_logs_for_plan(
            user_id=user_id,
            meal_plan_id=saved_plan.id,
            plan_data=optimized_plan
        )

        # Step 6: Send notification
        await self.notification_service.send_plan_ready_notification(
            user_id=user_id,
            meal_plan=saved_plan
        )

        # Step 7: Publish event
        await self.event_publisher.publish(
            "meal_plan.generated",
            {"user_id": user_id, "plan_id": saved_plan.id}
        )

        return saved_plan


# ===== API Uses Facade (Simple Interface) =====
# backend/app/api/meal_plan.py
@router.post("/generate")
async def generate_meal_plan(
    request: GeneratePlanRequest,
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """
    API only calls ONE method - complex workflow is hidden
    """
    meal_plan = await orchestrator.generate_weekly_meal_plan(
        user_id=current_user.id,
        start_date=request.start_date,
        preferences=request.preferences
    )
    return MealPlanResponse.from_domain(meal_plan)
```

### Benefits
✅ API doesn't know about complex 7-step workflow
✅ Easy to change workflow without affecting API
✅ Centralizes complex coordination logic

---

## 6. Observer Pattern (Event-Driven)

**Purpose**: Define one-to-many dependency so when one object changes state, all dependents are notified

**Location**: `backend/app/events/`

### Implementation

```python
# ===== Event Classes =====
# backend/app/events/meal_plan_events.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MealPlanGeneratedEvent:
    """Event published when meal plan is generated."""
    user_id: int
    meal_plan_id: int
    generated_at: datetime
    plan_data: Dict


@dataclass
class MealLoggedEvent:
    """Event published when meal is logged."""
    user_id: int
    meal_log_id: int
    meal_type: str
    calories: float
    logged_at: datetime


# ===== Event Publisher (Subject) =====
# backend/app/events/event_publisher.py
class EventPublisher:
    """Publishes events to subscribers (Observer pattern)."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, event_data: Any):
        """Publish event to all subscribers."""
        handlers = self._subscribers.get(event_type, [])

        for handler in handlers:
            try:
                await handler(event_data)
            except Exception as e:
                logger.error(f"Event handler failed: {e}")


# ===== Event Handlers (Observers) =====
# backend/app/events/handlers/notification_handler.py
class NotificationEventHandler:
    """Observer that handles notification events."""

    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    async def handle_meal_plan_generated(self, event: MealPlanGeneratedEvent):
        """React to meal plan generation."""
        await self.notification_service.send_notification(
            user_id=event.user_id,
            title="Meal Plan Ready!",
            message=f"Your meal plan for the week is ready."
        )

    async def handle_meal_logged(self, event: MealLoggedEvent):
        """React to meal logging."""
        # Check if user hit daily goals
        # Send congratulations notification if goals met
        pass


# backend/app/events/handlers/analytics_handler.py
class AnalyticsEventHandler:
    """Observer that tracks analytics."""

    def __init__(self, analytics_service: AnalyticsService):
        self.analytics_service = analytics_service

    async def handle_meal_plan_generated(self, event: MealPlanGeneratedEvent):
        """Track meal plan generation."""
        await self.analytics_service.track_event(
            event_name="meal_plan_generated",
            user_id=event.user_id,
            properties={"plan_id": event.meal_plan_id}
        )

    async def handle_meal_logged(self, event: MealLoggedEvent):
        """Track meal logging."""
        await self.analytics_service.track_event(
            event_name="meal_logged",
            user_id=event.user_id,
            properties={"calories": event.calories}
        )


# ===== Registration (Setup Observers) =====
# backend/app/events/setup.py
def setup_event_handlers(
    publisher: EventPublisher,
    notification_service: NotificationService,
    analytics_service: AnalyticsService
):
    """Register all event handlers."""

    # Notification handler
    notification_handler = NotificationEventHandler(notification_service)
    publisher.subscribe("meal_plan.generated", notification_handler.handle_meal_plan_generated)
    publisher.subscribe("meal.logged", notification_handler.handle_meal_logged)

    # Analytics handler
    analytics_handler = AnalyticsEventHandler(analytics_service)
    publisher.subscribe("meal_plan.generated", analytics_handler.handle_meal_plan_generated)
    publisher.subscribe("meal.logged", analytics_handler.handle_meal_logged)


# ===== Usage in Orchestrator =====
# backend/app/orchestrators/meal_plan_orchestrator.py
class MealPlanOrchestrator:
    def __init__(self, ..., event_publisher: EventPublisher):
        self.event_publisher = event_publisher

    async def generate_weekly_meal_plan(self, ...):
        # Generate plan
        saved_plan = await self.meal_plan_service.create(...)

        # Publish event (observers will react)
        await self.event_publisher.publish(
            "meal_plan.generated",
            MealPlanGeneratedEvent(
                user_id=user_id,
                meal_plan_id=saved_plan.id,
                generated_at=datetime.now(),
                plan_data=saved_plan.plan_data
            )
        )

        return saved_plan
```

### Benefits
✅ Loose coupling (orchestrator doesn't know about notification/analytics)
✅ Easy to add new handlers without modifying orchestrator
✅ Event-driven architecture for microservices

---

## 7. Unit of Work Pattern

**Purpose**: Maintain list of objects affected by business transaction and coordinate changes

**Location**: `backend/app/repositories/unit_of_work.py`

### Implementation

```python
# ===== Unit of Work =====
# backend/app/repositories/unit_of_work.py
class UnitOfWork:
    """
    Unit of Work Pattern: Manages transaction boundaries
    Ensures all changes succeed or fail together
    """

    def __init__(self, db: Session):
        self.db = db
        self._meal_plan_repo = None
        self._meal_log_repo = None
        self._inventory_repo = None

    @property
    def meal_plan_repo(self) -> IMealPlanRepository:
        """Lazy load meal plan repository."""
        if self._meal_plan_repo is None:
            self._meal_plan_repo = MealPlanRepository(self.db)
        return self._meal_plan_repo

    @property
    def meal_log_repo(self) -> IMealLogRepository:
        """Lazy load meal log repository."""
        if self._meal_log_repo is None:
            self._meal_log_repo = MealLogRepository(self.db)
        return self._meal_log_repo

    @property
    def inventory_repo(self) -> IInventoryRepository:
        """Lazy load inventory repository."""
        if self._inventory_repo is None:
            self._inventory_repo = InventoryRepository(self.db)
        return self._inventory_repo

    async def commit(self):
        """Commit all changes."""
        self.db.commit()

    async def rollback(self):
        """Rollback all changes."""
        self.db.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.db.close()


# ===== Usage in Orchestrator =====
# backend/app/orchestrators/tracking_orchestrator.py
class TrackingOrchestrator:
    """Uses Unit of Work for transaction management."""

    async def log_meal_with_inventory_deduction(
        self,
        user_id: int,
        meal_log_id: int,
        portion_multiplier: float
    ):
        """
        Log meal and deduct inventory in single transaction.
        If either fails, both are rolled back.
        """
        # Create Unit of Work (transaction scope)
        uow = UnitOfWork(get_db())

        try:
            # Operation 1: Update meal log
            meal_log = await uow.meal_log_repo.get_by_id(meal_log_id)
            meal_log.consumed_datetime = datetime.now()
            meal_log.portion_multiplier = portion_multiplier
            await uow.meal_log_repo.update(meal_log)

            # Operation 2: Deduct inventory
            for ingredient in meal_log.recipe.ingredients:
                quantity_to_deduct = ingredient.quantity_grams * portion_multiplier
                await uow.inventory_repo.deduct(
                    user_id=user_id,
                    item_id=ingredient.item_id,
                    quantity=quantity_to_deduct
                )

            # Both operations succeed - commit transaction
            await uow.commit()

        except Exception as e:
            # Any operation fails - rollback transaction
            await uow.rollback()
            raise
```

### Benefits
✅ Atomic operations (all-or-nothing)
✅ Transaction management in one place
✅ Easy to track what's changed

---

## 8. DTO (Data Transfer Object) Pattern

**Purpose**: Transfer data between layers without exposing domain models

**Location**: `backend/app/schemas/` and `backend/app/dtos/`

### Implementation

```python
# ===== Domain Model (Internal) =====
# backend/app/domain/meal_plan.py
@dataclass
class MealPlan:
    """Domain model - internal representation."""
    id: Optional[int]
    user_id: int
    week_start_date: datetime
    plan_data: Dict
    grocery_list: Dict
    total_calories: float
    is_active: bool
    created_at: Optional[datetime]


# ===== ORM Model (Database) =====
# backend/app/models/database.py
class MealPlanORM(Base):
    """ORM model - database representation."""
    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    week_start_date = Column(DateTime)
    plan_data = Column(JSON)
    grocery_list = Column(JSON)
    total_calories = Column(Float)
    is_active = Column(Boolean)
    created_at = Column(DateTime)


# ===== Request DTO (API Input) =====
# backend/app/schemas/meal_plan.py
class GeneratePlanRequest(BaseModel):
    """DTO for API request - validation."""
    start_date: Optional[datetime] = None
    preferences: Dict = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-11-24T00:00:00",
                "preferences": {
                    "dietary_type": "vegetarian",
                    "max_prep_time": 30
                }
            }
        }


# ===== Response DTO (API Output) =====
# backend/app/schemas/meal_plan.py
class MealPlanResponse(BaseModel):
    """DTO for API response - presentation."""
    id: int
    week_start_date: str  # String for JSON serialization
    plan_data: Dict
    grocery_list: Dict
    total_calories: float
    is_active: bool

    @classmethod
    def from_domain(cls, meal_plan: MealPlan) -> "MealPlanResponse":
        """Convert domain model to response DTO."""
        return cls(
            id=meal_plan.id,
            week_start_date=meal_plan.week_start_date.isoformat(),
            plan_data=meal_plan.plan_data,
            grocery_list=meal_plan.grocery_list,
            total_calories=meal_plan.total_calories,
            is_active=meal_plan.is_active
        )


# ===== API Uses DTOs =====
# backend/app/api/meal_plan.py
@router.post("/generate", response_model=MealPlanResponse)
async def generate_meal_plan(
    request: GeneratePlanRequest,  # Request DTO (input validation)
    orchestrator: MealPlanOrchestrator = Depends(get_meal_plan_orchestrator),
    current_user: User = Depends(get_current_user)
):
    # Get domain model from orchestrator
    meal_plan = await orchestrator.generate_weekly_meal_plan(
        user_id=current_user.id,
        start_date=request.start_date,
        preferences=request.preferences
    )

    # Convert domain model to response DTO
    return MealPlanResponse.from_domain(meal_plan)
```

### Benefits
✅ API doesn't expose database structure
✅ Validation at API boundary
✅ Can change domain model without breaking API
✅ Clean separation of concerns

---

## Summary: Design Patterns in Architecture

| Pattern | Where Used | Purpose |
|---------|------------|---------|
| **Repository** | `repositories/` | Abstract data access |
| **Dependency Injection** | `dependencies.py`, FastAPI | Loose coupling |
| **Strategy** | `services/strategies/` | Interchangeable algorithms |
| **Factory** | `*_factory.py` | Object creation |
| **Facade** | Orchestrators | Simplify complex workflows |
| **Observer** | `events/` | Event-driven communication |
| **Unit of Work** | `unit_of_work.py` | Transaction management |
| **DTO** | `schemas/`, `dtos/` | Data transfer between layers |

---

## Pattern Interactions

```
API Request (DTO)
    ↓
Dependency Injection provides Orchestrator
    ↓
Orchestrator (Facade) coordinates
    ↓
Service uses Strategy for algorithm
    ↓
Service uses Repository (from Factory)
    ↓
Repository uses Unit of Work for transaction
    ↓
Domain Model converted to Response DTO
    ↓
Observer publishes events
```

All patterns work together to create maintainable, testable architecture.
