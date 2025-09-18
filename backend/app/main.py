from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, onboarding, recipes, inventory, meal_plan  # Add inventory
from app.core.config import settings
from app.api.websocket_tracking import router as websocket_router
from app.services.notification_service import NotificationService
from app.core.events import event_bus
import asyncio
import logging

app = FastAPI(
    title="NutriLens API",
    description="AI-powered nutrition planning system",
    version="1.0.0"
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
app.include_router(websocket_router, prefix="/api")  # Add this line

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