"""
Dependency Injection Configuration

Provides FastAPI dependencies for repositories, services, and orchestrators.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.models.database import get_db, UserPath

# Phase 1: Meal Planning (existing dependencies)
from app.repositories.meal_plan_repository import MealPlanRepository
from app.repositories.meal_log_repository import MealLogRepository
from app.repositories.recipe_repository import RecipeRepository
from app.repositories.interfaces.meal_plan_repository import IMealPlanRepository
from app.repositories.interfaces.meal_log_repository import IMealLogRepository
from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.services.meal_plan_service_v2 import MealPlanServiceV2
from app.services.inventory_service import IntelligentInventoryService
from app.services.final_meal_optimizer import MealPlanOptimizer
from app.services.grocery_service import GroceryService
from app.services.constraint_builder_service import ConstraintBuilderService
from app.orchestrators.meal_plan_orchestrator import MealPlanOrchestrator
from app.events.event_publisher import EventPublisher

# Phase 2: Tracking (new dependencies)
from app.repositories.interfaces import (
    ITrackingRepository,
    IInventoryRepository,
    IConsumptionAnalyticsRepository
)
from app.repositories import (
    TrackingRepository,
    InventoryRepository,
    ConsumptionAnalyticsRepository
)
from app.services.meal_tracking_service import MealTrackingService
from app.services.external_meal_service import ExternalMealService
from app.services.inventory_management_service import InventoryManagementService
from app.services.consumption_service_v2 import ConsumptionServiceV2
from app.services.notification_service import NotificationService
from app.orchestrators.meal_logging_orchestrator import MealLoggingOrchestrator
from app.events.meal_events import MealEventPublisher

# Phase 3: Dashboard (new dependencies)
from app.repositories.activity_repository import ActivityRepository
from app.orchestrators.dashboard_orchestrator import DashboardOrchestrator

# Phase 5: Auth (new dependencies)
from app.repositories.auth_repository import AuthRepository
from app.repositories.interfaces.auth_repository import IAuthRepository

# Phase 6: Onboarding (new dependencies)
from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository

# Phase 8: Receipt (new dependencies)
from app.repositories.receipt_repository import ReceiptRepository
from app.repositories.interfaces.receipt_repository import IReceiptRepository


# ===== Repository Dependencies =====

def get_meal_plan_repository(db: Session = Depends(get_db)) -> IMealPlanRepository:
    """
    Provide meal plan repository.

    Args:
        db: Database session

    Returns:
        Meal plan repository implementation
    """
    return MealPlanRepository(db)


def get_meal_log_repository(db: Session = Depends(get_db)) -> IMealLogRepository:
    """
    Provide meal log repository.

    Args:
        db: Database session

    Returns:
        Meal log repository implementation
    """
    return MealLogRepository(db)


def get_recipe_repository(db: Session = Depends(get_db)) -> IRecipeRepository:
    """
    Provide recipe repository.

    Args:
        db: Database session

    Returns:
        Recipe repository implementation
    """
    return RecipeRepository(db)


# ===== Service Dependencies =====

def get_inventory_service(db: Session = Depends(get_db)) -> IntelligentInventoryService:
    """
    Provide inventory service.

    Args:
        db: Database session

    Returns:
        Inventory service
    """
    return IntelligentInventoryService(db)


def get_meal_plan_optimizer(db: Session = Depends(get_db)) -> MealPlanOptimizer:
    """
    Provide meal plan optimizer.

    Args:
        db: Database session

    Returns:
        Meal plan optimizer
    """
    return MealPlanOptimizer(db)


def get_grocery_service(db: Session = Depends(get_db)) -> GroceryService:
    """
    Provide grocery service.

    Args:
        db: Database session

    Returns:
        Grocery service
    """
    return GroceryService(db)


def get_constraint_builder_service(db: Session = Depends(get_db)) -> ConstraintBuilderService:
    """
    Provide constraint builder service.

    Args:
        db: Database session

    Returns:
        Constraint builder service
    """
    return ConstraintBuilderService(db)


def get_meal_plan_service_v2(
    meal_plan_repo: IMealPlanRepository = Depends(get_meal_plan_repository),
    meal_log_repo: IMealLogRepository = Depends(get_meal_log_repository),
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_service: IntelligentInventoryService = Depends(get_inventory_service)
) -> MealPlanServiceV2:
    """
    Provide meal plan service V2 with injected dependencies.

    Args:
        meal_plan_repo: Meal plan repository
        meal_log_repo: Meal log repository
        recipe_repo: Recipe repository
        inventory_service: Inventory service

    Returns:
        Meal plan service V2
    """
    return MealPlanServiceV2(
        meal_plan_repo=meal_plan_repo,
        meal_log_repo=meal_log_repo,
        recipe_repo=recipe_repo,
        inventory_service=inventory_service
    )


# ===== Event Dependencies =====

# Singleton event publisher (shared across app)
_event_publisher = None


def get_event_publisher() -> EventPublisher:
    """
    Provide event publisher singleton.

    Returns:
        Event publisher instance
    """
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = EventPublisher()
    return _event_publisher


# ===== Orchestrator Dependencies =====

def get_meal_plan_orchestrator(
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    optimizer: MealPlanOptimizer = Depends(get_meal_plan_optimizer),
    grocery_service: GroceryService = Depends(get_grocery_service),
    event_publisher: EventPublisher = Depends(get_event_publisher)
) -> MealPlanOrchestrator:
    """
    Provide meal plan orchestrator with all dependencies.

    Args:
        meal_plan_service: Meal plan service
        optimizer: Meal plan optimizer
        grocery_service: Grocery service
        event_publisher: Event publisher

    Returns:
        Meal plan orchestrator
    """
    return MealPlanOrchestrator(
        meal_plan_service=meal_plan_service,
        optimizer=optimizer,
        grocery_service=grocery_service,
        event_publisher=event_publisher
    )


# ===== Helper Dependencies =====

def get_user_meal_windows(
    user_id: int,
    db: Session = Depends(get_db)
) -> list:
    """
    Get user's meal timing windows.

    COPY-PASTED FROM: planning_agent.py:1034-1035

    Args:
        user_id: User ID
        db: Database session

    Returns:
        List of meal windows
    """
    # COPY-PASTED FROM planning_agent.py:1034-1035 - NO CHANGES
    user_path = db.query(UserPath).filter_by(user_id=user_id).first()
    meal_windows = user_path.meal_windows if user_path and user_path.meal_windows else []

    return meal_windows


# ===== Phase 2: Tracking Dependencies =====

# Repository Dependencies (Phase 2)

def get_tracking_repository(db: Session = Depends(get_db)) -> ITrackingRepository:
    """
    Provide tracking repository for Phase 2.

    Args:
        db: Database session

    Returns:
        Tracking repository implementation
    """
    return TrackingRepository(db)


def get_inventory_repository(db: Session = Depends(get_db)) -> IInventoryRepository:
    """
    Provide inventory repository for Phase 2.

    Args:
        db: Database session

    Returns:
        Inventory repository implementation
    """
    return InventoryRepository(db)


def get_consumption_analytics_repository(
    db: Session = Depends(get_db)
) -> IConsumptionAnalyticsRepository:
    """
    Provide consumption analytics repository for Phase 2.

    Args:
        db: Database session

    Returns:
        Consumption analytics repository implementation
    """
    return ConsumptionAnalyticsRepository(db)


# Service Dependencies (Phase 2)

def get_notification_service() -> NotificationService:
    """
    Provide notification service.

    Returns:
        Notification service instance

    Note:
        NotificationService is stateless, so we create a new instance per request.
        In production, you might want to use a singleton pattern with connection pooling.
    """
    return NotificationService()


def get_meal_tracking_service(
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
    notification_service: NotificationService = Depends(get_notification_service)
) -> MealTrackingService:
    """
    Provide meal tracking service with injected dependencies.

    Args:
        tracking_repo: Tracking repository
        inventory_repo: Inventory repository
        analytics_repo: Analytics repository
        notification_service: Notification service

    Returns:
        Meal tracking service instance
    """
    return MealTrackingService(
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        analytics_repo=analytics_repo,
        notification_service=notification_service
    )


def get_external_meal_service(
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository)
) -> ExternalMealService:
    """
    Provide external meal service with injected dependencies.

    Args:
        tracking_repo: Tracking repository
        analytics_repo: Analytics repository

    Returns:
        External meal service instance
    """
    return ExternalMealService(
        tracking_repo=tracking_repo,
        analytics_repo=analytics_repo
    )


def get_inventory_management_service(
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    db: Session = Depends(get_db)
) -> InventoryManagementService:
    """
    Provide inventory management service with injected dependencies.

    Args:
        inventory_repo: Inventory repository
        tracking_repo: Tracking repository
        db: Database session (required by service for complex queries)

    Returns:
        Inventory management service instance
    """
    return InventoryManagementService(
        inventory_repo=inventory_repo,
        tracking_repo=tracking_repo,
        db=db
    )


def get_consumption_service_v2(
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
    db: Session = Depends(get_db)
) -> ConsumptionServiceV2:
    """
    Provide consumption service V2 with injected dependencies.

    Args:
        tracking_repo: Tracking repository
        inventory_repo: Inventory repository
        analytics_repo: Analytics repository
        db: Database session (for backward compatibility)

    Returns:
        Consumption service V2 instance
    """
    return ConsumptionServiceV2(
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        analytics_repo=analytics_repo,
        db=db
    )


# Event Publisher Dependencies (Phase 2)

# Singleton meal event publisher (shared across app)
_meal_event_publisher = None


def get_meal_event_publisher() -> MealEventPublisher:
    """
    Provide meal event publisher singleton.

    Returns:
        Meal event publisher instance

    Note:
        WebSocket manager and event bus are optional dependencies.
        They can be injected here when those systems are implemented.
    """
    global _meal_event_publisher
    if _meal_event_publisher is None:
        # TODO: Inject WebSocket manager and event bus when available
        _meal_event_publisher = MealEventPublisher(
            websocket_manager=None,  # Placeholder
            event_bus=None  # Placeholder
        )
    return _meal_event_publisher


# Orchestrator Dependencies (Phase 2)

def get_meal_logging_orchestrator(
    meal_tracking_service: MealTrackingService = Depends(get_meal_tracking_service),
    external_meal_service: ExternalMealService = Depends(get_external_meal_service),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service),
    consumption_service: ConsumptionServiceV2 = Depends(get_consumption_service_v2),
    notification_service: NotificationService = Depends(get_notification_service),
    event_publisher: MealEventPublisher = Depends(get_meal_event_publisher),
    db: Session = Depends(get_db)
) -> MealLoggingOrchestrator:
    """
    Provide meal logging orchestrator with all dependencies.

    This is the top-level orchestrator that coordinates all services
    for meal logging workflows in Phase 2.

    Args:
        meal_tracking_service: Meal tracking service
        external_meal_service: External meal service
        inventory_service: Inventory management service
        consumption_service: Consumption service V2
        notification_service: Notification service
        event_publisher: Meal event publisher
        db: Database session (for transaction management)

    Returns:
        Meal logging orchestrator instance
    """
    return MealLoggingOrchestrator(
        meal_tracking_service=meal_tracking_service,
        external_meal_service=external_meal_service,
        inventory_service=inventory_service,
        consumption_service=consumption_service,
        notification_service=notification_service,
        event_publisher=event_publisher,
        db=db
    )


# Convenience Dependencies (Phase 2)

def get_tracking_orchestrator(
    orchestrator: MealLoggingOrchestrator = Depends(get_meal_logging_orchestrator)
) -> MealLoggingOrchestrator:
    """
    Convenience dependency for endpoints that need the meal logging orchestrator.

    This is the primary dependency that Phase 2 endpoints should use.

    Args:
        orchestrator: Orchestrator instance

    Returns:
        Meal logging orchestrator instance

    Usage in endpoints:
        @router.post("/log-meal")
        async def log_meal(
            orchestrator: MealLoggingOrchestrator = Depends(get_tracking_orchestrator),
            ...
        ):
            return await orchestrator.log_planned_meal(...)
    """
    return orchestrator


# ===== Phase 3: Dashboard Dependencies =====

# Repository Dependencies (Phase 3)

def get_activity_repository(db: Session = Depends(get_db)) -> ActivityRepository:
    """
    Provide activity repository for Phase 3.

    Args:
        db: Database session

    Returns:
        Activity repository implementation
    """
    return ActivityRepository(db)


# Orchestrator Dependencies (Phase 3)

def get_dashboard_orchestrator(
    consumption_service: ConsumptionServiceV2 = Depends(get_consumption_service_v2),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service),
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    activity_repo: ActivityRepository = Depends(get_activity_repository),
    db: Session = Depends(get_db)
) -> DashboardOrchestrator:
    """
    Provide dashboard orchestrator with all dependencies.

    This orchestrator coordinates existing services from Phase 1 & 2
    to build dashboard summary data.

    Args:
        consumption_service: Consumption service V2 (from Phase 2)
        inventory_service: Inventory management service (from Phase 2)
        meal_plan_service: Meal plan service V2 (from Phase 1)
        activity_repo: Activity repository (new in Phase 3)
        db: Database session (for direct queries)

    Returns:
        Dashboard orchestrator instance

    Usage in endpoints:
        @router.get("/summary")
        async def get_dashboard_summary(
            orchestrator: DashboardOrchestrator = Depends(get_dashboard_orchestrator),
            ...
        ):
            return await orchestrator.get_dashboard_summary(...)
    """
    return DashboardOrchestrator(
        consumption_service=consumption_service,
        inventory_service=inventory_service,
        meal_plan_service=meal_plan_service,
        activity_repo=activity_repo,
        db=db
    )


# ===== Phase 5: Auth Dependencies =====

# Repository Dependencies (Phase 5)

def get_auth_repository(db: Session = Depends(get_db)) -> IAuthRepository:
    """
    Provide auth repository for Phase 5.

    Args:
        db: Database session

    Returns:
        Auth repository implementation

    Usage in endpoints:
        @router.post("/register")
        async def register(
            auth_repo: AuthRepository = Depends(get_auth_repository),
            ...
        ):
            existing_user = auth_repo.get_by_email(email)
            ...
    """
    return AuthRepository(db)


# ===== Phase 6: Onboarding Dependencies =====

# Repository Dependencies (Phase 6)

def get_onboarding_repository(db: Session = Depends(get_db)) -> IOnboardingRepository:
    """
    Provide onboarding repository for Phase 6.

    Args:
        db: Database session

    Returns:
        Onboarding repository implementation

    Usage in endpoints:
        @router.post("/basic-info")
        async def submit_basic_info(
            onboarding_repo: OnboardingRepository = Depends(get_onboarding_repository),
            ...
        ):
            onboarding_repo.update_user_onboarding_step(user_id, updates)
            ...
    """
    return OnboardingRepository(db)


# ===== Phase 8: Receipt Dependencies =====

# Repository Dependencies (Phase 8)

def get_receipt_repository(db: Session = Depends(get_db)) -> IReceiptRepository:
    """
    Provide receipt repository for Phase 8.

    Args:
        db: Database session

    Returns:
        Receipt repository implementation

    Usage in endpoints:
        @router.post("/upload")
        async def upload_receipt(
            receipt_repo: ReceiptRepository = Depends(get_receipt_repository),
            ...
        ):
            receipt_scan = receipt_repo.create_receipt_scan(user_id, s3_url)
            ...
    """
    return ReceiptRepository(db)
