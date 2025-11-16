from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api import auth, onboarding, recipes, inventory, meal_plan, notifications, tracking, websocket, dashboard, receipt, orchestrator, nutrition_chat
from app.core.config import settings
from app.services.websocket_manager import websocket_manager
from app.core.events import event_bus
from app.core.mongodb import init_mongodb_collections, close_mongo_clients
from app.agents.graph_instance import initialize_nutrition_graph
import asyncio
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
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

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(recipes.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(meal_plan.router, prefix="/api")
app.include_router(tracking.router, prefix="/api")
app.include_router(websocket.router)
app.include_router(notifications.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(receipt.router, prefix="/api")
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


