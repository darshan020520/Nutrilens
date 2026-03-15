"""
Dependency Injection Configuration

Provides FastAPI dependencies for repositories, services, and orchestrators.
"""

import logging
from app.core.llm_orchestrator import LLMOrchestrator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.database import get_db, User
from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.repositories.interfaces.meal_plan_repository import IMealPlanRepository
from app.repositories.interfaces.meal_log_repository import IMealLogRepository
from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.repositories.interfaces import (
    ITrackingRepository,
    IInventoryRepository,
    IConsumptionAnalyticsRepository,
    IUserProfileRepository
)

from app.repositories.meal_plan_repository import MealPlanRepository
from app.repositories.meal_log_repository import MealLogRepository
from app.repositories.recipe_repository import RecipeRepository

from app.services.meal_plan_service_v2 import MealPlanServiceV2
from app.services.intelligent_inventory_service_v2 import IntelligentInventoryServiceV2
from app.services.final_meal_optimizer import MealPlanOptimizer
from app.services.grocery_service import GroceryService
from app.services.constraint_builder_service import ConstraintBuilderService
from app.orchestrators.meal_plan_orchestrator import MealPlanOrchestrator
from app.infrastructure.events.event_publisher import EventPublisher


from app.repositories import (
    TrackingRepository,
    InventoryRepository,
    ConsumptionAnalyticsRepository,
    UserProfileRepository
)
from app.services.meal_tracking_service import MealTrackingService
from app.services.external_meal_service import ExternalMealService
from app.services.inventory_management_service import InventoryManagementService
from app.services.consumption_service_v2 import ConsumptionServiceV2
from app.orchestrators.meal_logging_orchestrator import MealLoggingOrchestrator
from app.repositories.activity_repository import ActivityRepository
from app.orchestrators.dashboard_orchestrator import DashboardOrchestrator

from app.repositories.auth_repository import AuthRepository
from app.repositories.interfaces.auth_repository import IAuthRepository
from app.services.auth import AuthService
from fastapi.security import OAuth2PasswordBearer

from app.repositories.onboarding_repository import OnboardingRepository
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository
from app.services.onboarding import OnboardingService
from app.repositories.receipt_repository import ReceiptRepository
from app.repositories.interfaces.receipt_repository import IReceiptRepository
from app.infrastructure.normalization.factory import create_normalizer
from app.infrastructure.normalization.batch.batch_normalizer import BatchNormalizer
from app.infrastructure.normalization.repositories.item_repository import ItemRepository
from app.services.receipt_processing_service import ReceiptProcessingService
from app.services.s3_service import S3Service
from app.infrastructure.events.event_publisher import EventPublisher
from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter
from app.core.llm_orchestrator import LLMOrchestrator
from app.infrastructure.prompts import MongoPromptRegistry
from app.core.mongodb import get_mongo_async_client
from app.core.token_governor import RedisTokenGovernor
from app.infrastructure.normalization.adapters.openai_llm_adapter import OpenAILLMAdapter


from app.core.llm_clients import get_openai_client


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_auth_repository(db: Session = Depends(get_db)) -> IAuthRepository:
    return AuthRepository(db)


def get_auth_service(
    auth_repo: IAuthRepository = Depends(get_auth_repository)
) -> AuthService:
    return AuthService(auth_repo=auth_repo)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:

    user = auth_service.get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


def get_onboarding_repository(db: Session = Depends(get_db)) -> IOnboardingRepository:
    return OnboardingRepository(db)


async def get_onboarding_service(
    onboarding_repo: IOnboardingRepository = Depends(get_onboarding_repository)
) -> OnboardingService:
    llm_orchestrator = await get_llm_orchestrator()
    return OnboardingService(onboarding_repo=onboarding_repo, llm_orchestrator=llm_orchestrator)


def get_receipt_repository(db: Session = Depends(get_db)) -> IReceiptRepository:
    return ReceiptRepository(db)


_s3_service = None


def get_s3_service():
    """
    Get singleton S3Service instance.

    Creates S3Service once on first call and reuses it for all subsequent calls.
    Thread-safe: boto3 client is created once, avoiding concurrent creation issues.

    Returns:
        S3Service for S3 operations
    """
    global _s3_service
    if _s3_service is None:
        from app.services.s3_service import S3Service
        _s3_service = S3Service(
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            region=settings.s3_region,
            bucket_name=settings.s3_bucket
        )
    return _s3_service


def get_meal_plan_repository(db: Session = Depends(get_db)) -> IMealPlanRepository:

    return MealPlanRepository(db)


def get_meal_log_repository(db: Session = Depends(get_db)) -> IMealLogRepository:

    return MealLogRepository(db)


def get_recipe_repository(db: Session = Depends(get_db)) -> IRecipeRepository:

    return RecipeRepository(db)


def get_user_profile_repository(db: Session = Depends(get_db)) -> IUserProfileRepository:
    """Get user profile repository instance"""
    return UserProfileRepository(db)


def get_constraint_builder_service(
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> ConstraintBuilderService:
    """Get constraint builder service with repository dependency"""
    return ConstraintBuilderService(user_profile_repo)


def get_meal_plan_service_v2(
    meal_plan_repo: IMealPlanRepository = Depends(get_meal_plan_repository),
    meal_log_repo: IMealLogRepository = Depends(get_meal_log_repository),
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    # inventory_service: IntelligentInventoryService = Depends(get_inventory_service),
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> MealPlanServiceV2:
    """
    Get meal plan service with all repository dependencies.
    REFACTORED: Added user_profile_repo for get_alternatives_for_meal()
    """
    return MealPlanServiceV2(
        meal_plan_repo=meal_plan_repo,
        meal_log_repo=meal_log_repo,
        recipe_repo=recipe_repo,
        # inventory_service=inventory_service,
        user_profile_repo=user_profile_repo
    )


_event_publisher = None


def get_event_publisher() -> EventPublisher:

    global _event_publisher
    if _event_publisher is None:
        _event_publisher = EventPublisher()
    return _event_publisher


def get_inventory_repository(db: Session = Depends(get_db)) -> IInventoryRepository:

    return InventoryRepository(db)


def get_meal_plan_optimizer(
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> MealPlanOptimizer:
    """
    Get meal plan optimizer instance with repository dependencies.

    REFACTORED: Now injects repositories instead of raw DB session.
    """
    return MealPlanOptimizer(
        recipe_repo=recipe_repo,
        inventory_repo=inventory_repo,
        user_profile_repo=user_profile_repo
    )

def get_grocery_service(
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository)
) -> GroceryService:
    """
    Get grocery service instance with repository dependencies.
    REFACTORED: Now injects repositories instead of raw DB session.
    """
    return GroceryService(
        recipe_repo=recipe_repo,
        inventory_repo=inventory_repo
    )

def get_meal_plan_orchestrator(
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    optimizer: MealPlanOptimizer = Depends(get_meal_plan_optimizer),
    grocery_service: GroceryService = Depends(get_grocery_service),
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository),
    event_publisher: EventPublisher = Depends(get_event_publisher)
) -> MealPlanOrchestrator:

    return MealPlanOrchestrator(
        meal_plan_service=meal_plan_service,
        optimizer=optimizer,
        grocery_service=grocery_service,
        user_profile_repo=user_profile_repo,
        event_publisher=event_publisher
    )


def get_tracking_repository(db: Session = Depends(get_db)) -> ITrackingRepository:

    return TrackingRepository(db)


def get_inventory_repository(db: Session = Depends(get_db)) -> IInventoryRepository:

    return InventoryRepository(db)





def get_meal_plan_optimizer(
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository)
) -> MealPlanOptimizer:
    """
    Get meal plan optimizer instance with repository dependencies.

    REFACTORED: Now injects repositories instead of raw DB session.
    """
    return MealPlanOptimizer(
        recipe_repo=recipe_repo,
        inventory_repo=inventory_repo,
        user_profile_repo=user_profile_repo
    )


def get_item_repository(db: Session = Depends(get_db)) -> ItemRepository:
    """
    Create ItemRepository instance for infrastructure layer access.

    NOTE: This creates a new instance per request. The ItemRepository
    inside the normalizer factory is a singleton, but this allows
    the service layer to have direct access to Item queries when needed.
    """
    redis_client = get_redis_client()

    cache_adapter = RedisCacheAdapter(redis_client=redis_client)

    return ItemRepository(db=db, cache_adapter=cache_adapter)


async def get_intelligent_inventory_service_v2(
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    item_repo: ItemRepository = Depends(get_item_repository),
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository),
    meal_plan_repo: IMealPlanRepository = Depends(get_meal_plan_repository),
    db: Session = Depends(get_db)
) -> IntelligentInventoryServiceV2:


    redis_client = get_redis_client()

    # Create adapters with singleton clients (lightweight wrappers)
    llm_orchestrator = await get_llm_orchestrator()
    embedding_adapter = await get_openai_embedding_adapter()

    # Create normalizer per-request (stateless wrapper around singletons)
    normalizer = await create_normalizer(
        db=db,
        redis_client=redis_client,
        llm_orchestrator=llm_orchestrator,
        embedding_adapter=embedding_adapter,
        item_repo=item_repo
    )

    return IntelligentInventoryServiceV2(
        inventory_repo=inventory_repo,
        recipe_repo=recipe_repo,
        normalizer=normalizer,
        item_repo=item_repo,
        db=db,
        llm_orchestrator=llm_orchestrator,
        embedding_adapter=embedding_adapter,
        user_profile_repo=user_profile_repo,
        meal_plan_repo=meal_plan_repo
    )


def get_receipt_processing_service(
    receipt_repo: IReceiptRepository = Depends(get_receipt_repository),
    s3_service: S3Service = Depends(get_s3_service),
    inventory_service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
) -> ReceiptProcessingService:
    """Get receipt processing service with all dependencies"""
    return ReceiptProcessingService(
        receipt_repo=receipt_repo,
        s3_service=s3_service,
        inventory_service=inventory_service,
        scanner_url=settings.receipt_scanner_url
    )


def get_consumption_analytics_repository(
    db: Session = Depends(get_db)
) -> IConsumptionAnalyticsRepository:

    return ConsumptionAnalyticsRepository(db)


# ============================================================================
# USER CONTEXT DEPENDENCY (for LangGraph nutrition bot)
# ============================================================================

def get_user_context(
    user_id: int,
    user_profile_repo: IUserProfileRepository = Depends(get_user_profile_repository),
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    recipe_repo: IRecipeRepository = Depends(get_recipe_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
    onboarding_service: OnboardingService = Depends(get_onboarding_service)
):
    """
    Get UserContext instance with all repository dependencies.

    Used by LangGraph nutrition bot to inject dependencies via context_schema.

    Args:
        user_id: The user ID to build context for
        All other args are injected via Depends

    Returns:
        UserContext instance with all dependencies
    """
    from app.agents.nutrition_context import UserContext

    return UserContext(
        user_id=user_id,
        user_profile_repo=user_profile_repo,
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        recipe_repo=recipe_repo,
        analytics_repo=analytics_repo,
        onboarding_service=onboarding_service
    )

def get_meal_tracking_service(
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
) -> MealTrackingService:

    return MealTrackingService(
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        analytics_repo=analytics_repo
    )



def get_prompt_registry():
    """
    Get MongoDB-based prompt registry.

    Stateless wrapper around singleton MongoDB client.
    Created per-request (lightweight, no connection overhead).

    Returns:
        IPromptRegistry: MongoDB prompt registry instance
    """

    client = get_mongo_async_client()
    return MongoPromptRegistry(
        client=client,
        database=settings.mongodb_db,
        collection="llm_prompts"
    )


def get_token_governor():
    """
    Get Redis-based token governor.

    Stateless wrapper around singleton Redis client.
    Created per-request (lightweight, no connection overhead).

    Returns:
        ITokenGovernor: Redis token governor instance
    """
    

    return RedisTokenGovernor(ttl=86400)  # 24-hour budget window


async def get_llm_adapter():
    """
    Get OpenAI LLM adapter.

    Stateless wrapper around singleton OpenAI client.
    Created per-request (lightweight, no connection overhead).

    Returns:
        ILLMAdapter: OpenAI adapter instance
    """

    openai_client = await get_openai_client()
    return OpenAILLMAdapter(client=openai_client)


async def get_llm_orchestrator():
    """
    Get LLM Orchestrator - the single entry point for all LLM calls.

    Wires together:
    - PromptRegistry (MongoDB) - fetches and renders prompts
    - TokenGovernor (Redis) - manages token budgets
    - LLMAdapter (OpenAI) - executes LLM calls

    Created per-request (all components are stateless wrappers).

    Usage in routes:
        @router.post("/normalize")
        async def normalize_item(
            orchestrator: LLMOrchestrator = Depends(get_llm_orchestrator)
        ):
            result = await orchestrator.run(
                user_id=user.id,
                slug="verify_match",
                variables={"user_text": "red capsicum", "candidates": "[...]"},
                response_model=VerifyMatchResult
            )

    Returns:
        LLMOrchestrator: Fully wired orchestrator instance
    """

    registry = get_prompt_registry()
    governor = get_token_governor()
    adapter = await get_llm_adapter()

    return LLMOrchestrator(
        registry=registry,
        governor=governor,
        adapter=adapter
    )




async def get_inventory_management_service(
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    db: Session = Depends(get_db),
    llm_orchestrator: LLMOrchestrator = Depends(get_llm_orchestrator)
) -> InventoryManagementService:

    return InventoryManagementService(
        inventory_repo=inventory_repo,
        tracking_repo=tracking_repo,
        db=db,
        llm_orchestrator=llm_orchestrator
    )


async def get_consumption_service_v2(
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
    db: Session = Depends(get_db),
    llm_orchestrator: LLMOrchestrator = Depends(get_llm_orchestrator)
) -> ConsumptionServiceV2:

    return ConsumptionServiceV2(
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        analytics_repo=analytics_repo,
        db=db,
        llm_orchestrator=llm_orchestrator
    )




def get_activity_repository(db: Session = Depends(get_db)) -> ActivityRepository:
    return ActivityRepository(db)




def get_dashboard_orchestrator(
    consumption_service: ConsumptionServiceV2 = Depends(get_consumption_service_v2),
    inventory_service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2),
    meal_plan_service: MealPlanServiceV2 = Depends(get_meal_plan_service_v2),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    activity_repo: ActivityRepository = Depends(get_activity_repository)
) -> DashboardOrchestrator:

    return DashboardOrchestrator(
        consumption_service=consumption_service,
        inventory_service=inventory_service,
        meal_plan_service=meal_plan_service,
        onboarding_service=onboarding_service,
        activity_repo=activity_repo
    )


_event_publisher = None
_websocket_observer = None
_notification_observer = None


def create_achievement_service(db: Session):
    """
    Factory function to create AchievementService.
    Used at STARTUP - does NOT use Depends().

    Args:
        db: Database session (created manually at startup)

    Returns:
        AchievementService instance
    """
    from app.services.achievement_service import AchievementService

    tracking_repo = TrackingRepository(db)
    user_profile_repo = UserProfileRepository(db)

    return AchievementService(
        tracking_repo=tracking_repo,
        user_profile_repo=user_profile_repo
    )


def create_notification_observer():
    """
    Factory function to create NotificationObserver.
    Used at STARTUP - does NOT use Depends().

    Injects SessionLocal (the factory class, not an instance) so the observer
    can open a fresh session per handler call instead of holding a stale one.

    Returns:
        NotificationObserver instance with session factory injected
    """
    from app.infrastructure.observers.notification_observer import NotificationObserver
    from app.models.database import SessionLocal

    return NotificationObserver(session_factory=SessionLocal)


def create_websocket_observer():
    """
    Factory function to create WebSocketObserver.
    Used at STARTUP - does NOT use Depends().

    Returns:
        WebSocketObserver instance
    """
    from app.infrastructure.observers.websocket_observer import WebSocketObserver
    from app.services.websocket_manager import websocket_manager

    return WebSocketObserver(websocket_manager)


def initialize_event_publisher():
    """
    Initialize EventPublisher with observers attached.
    Called ONCE at startup in main.py lifespan event.

    Returns:
        EventPublisher singleton with observers attached
    """
    global _event_publisher, _websocket_observer, _notification_observer

    if _event_publisher is None:
        _event_publisher = EventPublisher()

        # _websocket_observer = create_websocket_observer()  # WebSocket disabled
        _notification_observer = create_notification_observer()

        # _event_publisher.attach(_websocket_observer)  # WebSocket disabled
        _event_publisher.attach(_notification_observer)

        logger.info("EventPublisher initialized with 1 observer attached (WebSocket disabled)")

    return _event_publisher


def get_event_publisher():
    """
    Get EventPublisher singleton.
    Called from route handlers via Depends().

    Returns:
        EventPublisher singleton

    Raises:
        RuntimeError: If EventPublisher not initialized at startup
    """
    global _event_publisher
    if _event_publisher is None:
        raise RuntimeError(
            "EventPublisher not initialized. "
            "Call initialize_event_publisher() at startup."
        )
    return _event_publisher


# ============================================================================
# LLM ADAPTER DEPENDENCIES
# ============================================================================

async def get_openai_mini_adapter():
    """
    Get OpenAILLMAdapter configured for gpt-4o-mini model.

    Used by:
    - Normalizer (item matching, structure extraction, unit conversion)
    - Receipt processing

    Returns:
        ILLMAdapter: Lightweight adapter wrapping singleton OpenAI client
    """
    from app.infrastructure.normalization.adapters.openai_llm_adapter import OpenAILLMAdapter
    from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter

    redis_client = get_redis_client()  # Singleton Redis
    cache_adapter = RedisCacheAdapter(redis_client=redis_client)

    return OpenAILLMAdapter(
        cache_adapter=cache_adapter,
        model="gpt-4o-mini"
    )


async def get_openai_4o_adapter():
    """
    Get OpenAILLMAdapter configured for gpt-4o model.

    Used by:
    - Nutrition estimation (higher accuracy for macro calculations)

    Returns:
        ILLMAdapter: Lightweight adapter wrapping singleton OpenAI client
    """
    from app.infrastructure.normalization.adapters.openai_llm_adapter import OpenAILLMAdapter
    from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter

    redis_client = get_redis_client()
    cache_adapter = RedisCacheAdapter(redis_client=redis_client)

    return OpenAILLMAdapter(
        cache_adapter=cache_adapter,
        model="gpt-4o"
    )


async def get_openai_structured_adapter():
    """
    Get OpenAILLMAdapter configured for gpt-4o-2024-08-06 model.

    Used by:
    - Recipe generation (structured outputs)
    - Ingredient processing

    Returns:
        ILLMAdapter: Lightweight adapter wrapping singleton OpenAI client
    """
    from app.infrastructure.normalization.adapters.openai_llm_adapter import OpenAILLMAdapter
    from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter

    redis_client = get_redis_client()
    cache_adapter = RedisCacheAdapter(redis_client=redis_client)

    return OpenAILLMAdapter(
        cache_adapter=cache_adapter,
        model="gpt-4o-2024-08-06"
    )


async def get_openai_embedding_adapter():
    """Get EmbeddingAdapter configured for OpenAI text-embedding-3-small"""
    from app.core.llm_clients import get_openai_client
    from app.services.openai_embedding_service import OpenAIEmbeddingService
    from app.infrastructure.normalization.adapters.embedding_adapter import EmbeddingAdapter
    from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter

    openai_client = await get_openai_client()  # Singleton client
    redis_client = get_redis_client()
    cache_adapter = RedisCacheAdapter(redis_client=redis_client)

    # Create embedding service with singleton client
    embedding_service = OpenAIEmbeddingService(
        client=openai_client,
        model="text-embedding-3-small"
    )

    # Wrap with caching adapter
    return EmbeddingAdapter(
        embedding_service=embedding_service,
        cache_adapter=cache_adapter
    )



# ============================================================================
# LLM ORCHESTRATOR DEPENDENCIES (New Clean Architecture)
# ============================================================================


async def get_external_meal_service(
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
    llm_orchestrator: LLMOrchestrator = Depends(get_llm_orchestrator)
) -> ExternalMealService:

    return ExternalMealService(
        tracking_repo=tracking_repo,
        analytics_repo=analytics_repo,
        llm_orchestrator=llm_orchestrator
    )


def get_meal_logging_orchestrator(
    meal_tracking_service: MealTrackingService = Depends(get_meal_tracking_service),
    external_meal_service: ExternalMealService = Depends(get_external_meal_service),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service),
    consumption_service: ConsumptionServiceV2 = Depends(get_consumption_service_v2),
    event_publisher: EventPublisher = Depends(get_event_publisher),
    db: Session = Depends(get_db)
) -> MealLoggingOrchestrator:
    """Get meal logging orchestrator with all dependencies including new EventPublisher"""
    return MealLoggingOrchestrator(
        meal_tracking_service=meal_tracking_service,
        external_meal_service=external_meal_service,
        inventory_service=inventory_service,
        consumption_service=consumption_service,
        event_publisher=event_publisher,
        db=db
    )

def get_tracking_orchestrator(
    orchestrator: MealLoggingOrchestrator = Depends(get_meal_logging_orchestrator)
) -> MealLoggingOrchestrator:

    return orchestrator


# ============================================================================
# WHATSAPP CONTEXT BUILDER (for background tasks, no FastAPI Depends)
# ============================================================================

async def build_whatsapp_context(user_id: int, db: Session):
    """
    Build WhatsAppContextSchema for background processing.

    Called from the WhatsApp webhook background task where FastAPI's
    Depends() is not available. Creates all dependencies manually
    using the provided DB session.

    Args:
        user_id: User ID to build context for
        db: SQLAlchemy session (created manually in background task)

    Returns:
        WhatsAppContextSchema with all dependencies wired
    """
    from app.agents.whatsapp_graph import WhatsAppContextSchema
    from app.agents.nutrition_context import UserContext

    # Repositories
    user_profile_repo = UserProfileRepository(db)
    tracking_repo = TrackingRepository(db)
    inventory_repo = InventoryRepository(db)
    recipe_repo = RecipeRepository(db)
    analytics_repo = ConsumptionAnalyticsRepository(db)
    onboarding_repo = OnboardingRepository(db)

    # LLM Orchestrator (async - uses singleton OpenAI client)
    llm_orchestrator = await get_llm_orchestrator()

    # Services
    onboarding_service = OnboardingService(onboarding_repo=onboarding_repo)
    meal_tracking_service = MealTrackingService(
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        analytics_repo=analytics_repo
    )
    inventory_management_service = InventoryManagementService(
        inventory_repo=inventory_repo,
        tracking_repo=tracking_repo,
        db=db,
        llm_orchestrator=llm_orchestrator
    )
    consumption_service = ConsumptionServiceV2(
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        analytics_repo=analytics_repo,
        db=db,
        llm_orchestrator=llm_orchestrator
    )

    external_meal_service = ExternalMealService(
        tracking_repo=tracking_repo,
        analytics_repo=analytics_repo,
        llm_orchestrator=llm_orchestrator
    )

    event_publisher = get_event_publisher()

    meal_orchestrator = MealLoggingOrchestrator(
        meal_tracking_service=meal_tracking_service,
        external_meal_service=external_meal_service,
        inventory_service=inventory_management_service,
        consumption_service=consumption_service,
        event_publisher=event_publisher,
        db=db
    )

    # UserContext (shared read-only data access layer)
    user_context = UserContext(
        user_id=user_id,
        user_profile_repo=user_profile_repo,
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        recipe_repo=recipe_repo,
        analytics_repo=analytics_repo,
        onboarding_service=onboarding_service
    )

    # Token governor and prompt registry (stateless wrappers)
    governor = get_token_governor()
    prompt_registry = get_prompt_registry()

    return WhatsAppContextSchema(
        user_context=user_context,
        governor=governor,
        prompt_registry=prompt_registry,
        meal_orchestrator=meal_orchestrator,
        external_meal_service=external_meal_service
    )