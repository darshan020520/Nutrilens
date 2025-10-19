from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api import auth, onboarding, recipes, inventory, meal_plan, notifications, tracking, websocket, dashboard, receipt
from app.core.config import settings
from app.services.websocket_manager import websocket_manager
from app.core.events import event_bus
import asyncio
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize WebSocket Redis connection
    await websocket_manager.initialize_redis()
    print("✅ WebSocket manager initialized")
    
    yield
    
    # Shutdown: Close all connections gracefully
    await websocket_manager.close_all_connections()
    print("✅ WebSocket manager closed")

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


