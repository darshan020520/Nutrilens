from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.api import auth, auth_v2, onboarding, onboarding_v2, recipes, recipes_v2, inventory, inventory_v2, meal_plan, meal_plan_v2, notifications, tracking, tracking_v2, websocket, dashboard, dashboard_v2, receipt, receipt_v2, orchestrator, nutrition_chat
from app.core.config import settings
from app.services.websocket_manager import websocket_manager
from app.core.events import event_bus
from app.core.mongodb import init_mongodb_collections, close_mongo_clients
from app.agents.graph_instance import initialize_nutrition_graph
from app.models.database import SessionLocal
from app.dependencies import initialize_event_publisher
from app.core.redis_client import close_redis_client
from app.core.llm_clients import get_openai_client, close_llm_clients
from app.core.exceptions import TokenBudgetExceeded, RateLimitExceeded, LLMServiceError
import asyncio
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize LLM clients (singleton pattern)
    await get_openai_client()
    print("✅ LLM clients initialized")

    # Startup: Initialize WebSocket Redis connection
    await websocket_manager.initialize_redis()
    print("✅ WebSocket manager initialized")

    # Startup: Initialize MongoDB collections and indexes
    try:
        init_mongodb_collections()
        print("✅ MongoDB initialized")
    except Exception as e:
        print(f"⚠️ MongoDB initialization failed: {e}")
        logging.error(f"MongoDB initialization error: {e}")

    # Startup: Initialize EventPublisher with observers
    db = SessionLocal()
    try:
        initialize_event_publisher(db)
        print("✅ EventPublisher initialized with observers")
    except Exception as e:
        print(f"⚠️ EventPublisher initialization failed: {e}")
        logging.error(f"EventPublisher initialization error: {e}")
    finally:
        db.close()

    # Startup: Initialize and compile LangGraph (singleton pattern)
    async with initialize_nutrition_graph():
        print("✅ LangGraph compiled and ready")

        yield  # Application runs here with compiled graph available

    # Shutdown: Close all connections gracefully
    await websocket_manager.close_all_connections()
    print("✅ WebSocket manager closed")

    # Shutdown: Close MongoDB clients
    close_mongo_clients()
    print("✅ MongoDB clients closed")

    # Shutdown: Close Redis client
    close_redis_client()
    print("✅ Redis client closed")

    # Shutdown: Close LLM clients
    await close_llm_clients()
    print("✅ LLM clients closed")

app = FastAPI(
    title="NutriLens API",
    description="AI-powered nutrition planning system",
    version="1.0.0",
    lifespan=lifespan 
)
logger = logging.getLogger(__name__)
# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers
@app.exception_handler(TokenBudgetExceeded)
async def token_budget_exceeded_handler(request: Request, exc: TokenBudgetExceeded):
    """Handle token budget exceeded - return 402 Payment Required"""
    return JSONResponse(
        status_code=402,
        content={
            "detail": exc.message,
            "used": exc.used,
            "limit": exc.limit,
            "error_type": "token_budget_exceeded"
        }
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit exceeded - return 429 Too Many Requests"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": exc.message,
            "retry_after": exc.retry_after,
            "error_type": "rate_limit_exceeded"
        },
        headers={"Retry-After": str(exc.retry_after)}
    )


@app.exception_handler(LLMServiceError)
async def llm_service_error_handler(request: Request, exc: LLMServiceError):
    """Handle LLM service errors - return 503 Service Unavailable"""
    return JSONResponse(
        status_code=503,
        content={
            "detail": exc.message,
            "error_type": "llm_service_error"
        }
    )


# Include routers
# app.include_router(auth.router, prefix="/api")
app.include_router(auth_v2.router, prefix="/api")  # V2 endpoint (clean architecture)
# app.include_router(onboarding.router, prefix="/api")
app.include_router(onboarding_v2.router, prefix="/api")  # V2 endpoint (clean architecture)
app.include_router(recipes.router, prefix="/api")
app.include_router(recipes_v2.router, prefix="/api")  # V2 endpoint (clean architecture)
# app.include_router(inventory.router, prefix="/api")
app.include_router(inventory_v2.router, prefix="/api")  # V2 endpoint (clean architecture)
app.include_router(meal_plan.router, prefix="/api")
app.include_router(meal_plan_v2.router_v2, prefix="/api")  # V2 endpoint (new architecture)
app.include_router(tracking.router, prefix="/api")
app.include_router(tracking_v2.router, prefix="/api")  # V2 endpoint (clean architecture)
app.include_router(websocket.router)
app.include_router(notifications.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(dashboard_v2.router, prefix="/api")  # V2 endpoint (clean architecture)
app.include_router(receipt.router, prefix="/api")
app.include_router(receipt_v2.router, prefix="/api")  # V2 endpoint (clean architecture)
app.include_router(orchestrator.router, prefix="/api")
app.include_router(nutrition_chat.router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""

    asyncio.create_task(event_bus.process_events())

    logger.info("Background tasks started")



@app.get("/")
def root():
    return {
        "name": "NutriLens API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "websocket_stats": websocket_manager.get_stats()
    }


