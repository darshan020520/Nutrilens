from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, onboarding, recipes, inventory  # Add inventory
from app.core.config import settings

app = FastAPI(
    title="NutriLens API",
    description="AI-powered nutrition planning system",
    version="1.0.0"
)

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
app.include_router(inventory.router, prefix="/api")  # Add this line

@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    from app.services.data_seeder import DataSeeder
    from app.models.database import get_db
    
    # Auto-seed data if empty
    db = next(get_db())
    seeder = DataSeeder(db)
    seeder.seed_all()
    db.close()

@app.get("/")
def root():
    return {
        "name": "NutriLens API",
        "version": "1.0.0",
        "status": "operational"
    }