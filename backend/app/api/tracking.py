# backend/app/api/tracking.py
"""
API endpoints for tracking and consumption logging
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.models.database import get_db, User
from app.services.consumption_services import ConsumptionService
from app.agents.tracking_agent import TrackingAgent
from app.services.auth import get_current_user

router = APIRouter(prefix="/tracking", tags=["Tracking"])

# Pydantic models for requests and responses

class MealLogRequest(BaseModel):
    """Request model for logging a meal"""
    meal_log_id: Optional[int] = Field(None, description="Existing meal log ID")
    recipe_id: Optional[int] = Field(None, description="Recipe ID for new log")
    meal_type: Optional[str] = Field(None, description="Meal type for new log")
    portion_multiplier: float = Field(1.0, ge=0.1, le=5.0, description="Portion size multiplier")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    external_calories: Optional[float] = Field(None, ge=0, le=5000, description="Calories for external meal")
    
    @validator('meal_type')
    def validate_meal_type(cls, v):
        if v and v not in ["breakfast", "lunch", "dinner", "snack"]:
            raise ValueError("Invalid meal type")
        return v
    
    @validator('meal_log_id')
    def validate_requirements(cls, v, values):
        if not v and not values.get('meal_type'):
            raise ValueError("Either meal_log_id or meal_type is required")
        return v

class SkipMealRequest(BaseModel):
    """Request model for skipping a meal"""
    meal_log_id: int = Field(..., description="Meal log ID to skip")
    reason: Optional[str] = Field(None, max_length=255, description="Reason for skipping")

class UpdatePortionRequest(BaseModel):
    """Request model for updating portion"""
    meal_log_id: int = Field(..., description="Meal log ID")
    new_portion_multiplier: float = Field(..., ge=0.1, le=5.0, description="New portion multiplier")

class ManualEntryRequest(BaseModel):
    """Request model for manual meal entry"""
    meal_type: str = Field(..., description="Type of meal")
    calories: float = Field(..., ge=0, le=5000, description="Calories consumed")
    protein_g: Optional[float] = Field(None, ge=0, description="Protein in grams")
    carbs_g: Optional[float] = Field(None, ge=0, description="Carbs in grams")
    fat_g: Optional[float] = Field(None, ge=0, description="Fat in grams")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")
    consumed_at: Optional[datetime] = Field(None, description="Time of consumption")

class ConsumptionResponse(BaseModel):
    """Response model for consumption logging"""
    success: bool
    meal_log_id: Optional[int]
    meal_type: Optional[str]
    recipe: Optional[str]
    consumed_at: Optional[str]
    portion: Optional[float]
    macros_consumed: Optional[Dict[str, float]]
    ingredients_deducted: Optional[List[Dict]]
    daily_progress: Optional[Dict[str, Any]]
    adherence_status: Optional[Dict[str, Any]]
    error: Optional[str]

class DailySummaryResponse(BaseModel):
    """Response model for daily summary"""
    success: bool
    date: str
    meals_planned: int
    meals_consumed: int
    meals_skipped: int
    meals_pending: int
    total_calories: float
    total_macros: Dict[str, float]
    meals: List[Dict[str, Any]]
    compliance_rate: float
    targets: Optional[Dict[str, float]]
    progress: Optional[Dict[str, float]]
    recommendations: List[str]
    hydration_reminder: str
    error: Optional[str]

class ConsumptionHistoryResponse(BaseModel):
    """Response model for consumption history"""
    success: bool
    history: Dict[str, Dict[str, Any]]
    statistics: Dict[str, Any]
    error: Optional[str]

class MealPatternsResponse(BaseModel):
    """Response model for meal patterns"""
    success: bool
    patterns: Dict[str, Any]
    insights: List[str]
    error: Optional[str]

# API Endpoints

@router.post("/log-meal", response_model=ConsumptionResponse)
async def log_meal(
    request: MealLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log a meal consumption with automatic inventory deduction
    
    - Either provide meal_log_id for planned meal or recipe_id + meal_type for new meal
    - Portion multiplier adjusts serving size (1.0 = normal, 0.5 = half, 2.0 = double)
    - External calories for meals eaten outside
    """
    service = ConsumptionService(db)
    
    result = service.log_meal(
        user_id=current_user.id,
        meal_log_id=request.meal_log_id,
        recipe_id=request.recipe_id,
        meal_type=request.meal_type,
        portion_multiplier=request.portion_multiplier,
        notes=request.notes,
        external_calories=request.external_calories
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to log meal")
        )
    
    return ConsumptionResponse(**result)

@router.post("/skip-meal")
async def skip_meal(
    request: SkipMealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a meal as skipped with optional reason
    
    - Helps track adherence patterns
    - Adjusts daily targets for remaining meals
    """
    service = ConsumptionService(db)
    
    result = service.skip_meal(
        user_id=current_user.id,
        meal_log_id=request.meal_log_id,
        reason=request.reason
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to skip meal")
        )
    
    return result

@router.put("/update-portion")
async def update_portion(
    request: UpdatePortionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update portion size for an already consumed meal
    
    - Adjusts inventory automatically
    - Learns from portion preferences
    """
    service = ConsumptionService(db)
    
    result = service.update_portion(
        user_id=current_user.id,
        meal_log_id=request.meal_log_id,
        new_portion_multiplier=request.new_portion_multiplier
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to update portion")
        )
    
    return result

@router.get("/today", response_model=DailySummaryResponse)
async def get_today_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get today's consumption summary
    
    - Shows all meals (consumed, skipped, pending)
    - Calculates total calories and macros
    - Provides progress against daily targets
    - Includes recommendations
    """
    service = ConsumptionService(db)
    
    result = service.get_today_summary(user_id=current_user.id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to get summary")
        )
    
    return DailySummaryResponse(**result)

@router.get("/history", response_model=ConsumptionHistoryResponse)
async def get_consumption_history(
    days: int = Query(7, ge=1, le=90, description="Number of days to retrieve"),
    include_details: bool = Query(False, description="Include meal details"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get consumption history for specified days
    
    - Default shows last 7 days
    - Can include detailed meal information
    - Provides statistics and trends
    """
    service = ConsumptionService(db)
    
    result = service.get_consumption_history(
        user_id=current_user.id,
        days=days,
        include_details=include_details
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to get history")
        )
    
    return ConsumptionHistoryResponse(**result)

@router.get("/patterns", response_model=MealPatternsResponse)
async def get_meal_patterns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze and get meal consumption patterns
    
    - Meal timing patterns
    - Skip frequencies
    - Portion preferences
    - Favorite recipes
    - Weekly patterns
    - Success factors
    """
    service = ConsumptionService(db)
    
    result = service.get_meal_patterns(user_id=current_user.id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to get patterns")
        )
    
    return MealPatternsResponse(**result)

@router.post("/manual-entry")
async def manual_meal_entry(
    request: ManualEntryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually log a meal with custom macros
    
    - For meals eaten outside or custom preparations
    - Specify calories and optionally macros
    """
    service = ConsumptionService(db)
    
    # Create external meal data
    external_meal = {
        "calories": request.calories,
        "protein_g": request.protein_g or 0,
        "carbs_g": request.carbs_g or 0,
        "fat_g": request.fat_g or 0,
        "logged_at": (request.consumed_at or datetime.utcnow()).isoformat()
    }
    
    result = service.log_meal(
        user_id=current_user.id,
        meal_type=request.meal_type,
        notes=request.notes,
        external_calories=request.calories
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to log manual entry")
        )
    
    return result

# Tracking Agent endpoints

@router.get("/agent/status")
async def get_tracking_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current tracking agent status
    
    - Daily consumption status
    - Current inventory levels
    - Active alerts
    - Consumption patterns
    """
    agent = TrackingAgent(db, current_user.id)
    
    return {
        "success": True,
        "state": agent.get_state()
    }

@router.post("/agent/check-expiry")
async def check_expiring_items(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check for items nearing expiry
    
    - Items expiring in next 3 days
    - Priority levels (high/medium)
    - Recommendations for usage
    """
    agent = TrackingAgent(db, current_user.id)
    
    result = agent.check_expiring_items()
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to check expiring items")
        )
    
    return result

@router.get("/agent/inventory-status")
async def get_inventory_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calculate overall inventory status
    
    - Overall percentage of required items
    - Category breakdown
    - Critical items needing restock
    - Well-stocked items
    """
    agent = TrackingAgent(db, current_user.id)
    
    result = agent.calculate_inventory_status()
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to calculate inventory status")
        )
    
    return result

@router.get("/agent/restock-list")
async def generate_restock_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate intelligent restock list
    
    - Urgent items (< 20% stock)
    - Soon needed items (< 50% stock)
    - Optional staples (< 70% stock)
    - Shopping strategy recommendations
    """
    agent = TrackingAgent(db, current_user.id)
    
    result = agent.generate_restock_list()
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to generate restock list")
        )
    
    return result

@router.post("/agent/process-receipt/{receipt_id}")
async def process_receipt_ocr(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process OCR results from receipt
    
    - Parse items from OCR text
    - Normalize to database items
    - Update processing status
    """
    agent = TrackingAgent(db, current_user.id)
    
    result = agent.process_receipt_ocr(receipt_id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to process receipt")
        )
    
    return result

@router.post("/agent/normalize-items")
async def normalize_ocr_items(
    items: List[Dict] = Body(..., description="OCR extracted items to normalize"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Normalize OCR extracted items to database items
    
    - Match items with confidence scores
    - Convert units to grams
    - Identify unmatched items
    """
    agent = TrackingAgent(db, current_user.id)
    
    result = agent.normalize_ocr_items(items)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to normalize items")
        )
    
    return result

# Real-time tracking endpoints

@router.get("/real-time/current-macros")
async def get_current_macros(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get real-time macro tracking for today
    
    - Current consumed macros
    - Remaining for the day
    - Next meal suggestions based on remaining
    """
    service = ConsumptionService(db)
    
    summary = service.get_today_summary(user_id=current_user.id)
    
    if not summary["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=summary.get("error", "Failed to get current macros")
        )
    
    # Extract macro information
    return {
        "success": True,
        "current": summary.get("total_macros", {}),
        "targets": summary.get("targets", {}),
        "progress": summary.get("progress", {}),
        "remaining": {
            "calories": summary["targets"]["calories"] - summary["total_calories"] if "targets" in summary else 0,
            "protein_g": summary["targets"]["protein_g"] - summary["total_macros"]["protein_g"] if "targets" in summary else 0,
            "carbs_g": summary["targets"]["carbs_g"] - summary["total_macros"]["carbs_g"] if "targets" in summary else 0,
            "fat_g": summary["targets"]["fat_g"] - summary["total_macros"]["fat_g"] if "targets" in summary else 0
        }
    }

@router.get("/real-time/next-meal-window")
async def get_next_meal_window(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get next meal window information
    
    - Next scheduled meal
    - Time until meal
    - Suggested recipe
    - Pre-meal preparation reminders
    """
    from app.models.database import MealLog, UserPath
    from datetime import datetime
    
    # Get user's meal windows
    user_path = db.query(UserPath).filter(
        UserPath.user_id == current_user.id
    ).first()
    
    if not user_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User path not configured"
        )
    
    # Get today's pending meals
    today = date.today()
    pending_meals = db.query(MealLog).filter(
        and_(
            MealLog.user_id == current_user.id,
            func.date(MealLog.planned_datetime) == today,
            MealLog.consumed_datetime.is_(None),
            MealLog.was_skipped.is_(False)
        )
    ).order_by(MealLog.planned_datetime).all()
    
    if not pending_meals:
        return {
            "success": True,
            "message": "No more meals scheduled for today",
            "next_meal": None
        }
    
    next_meal = pending_meals[0]
    time_until = (next_meal.planned_datetime - datetime.utcnow()).total_seconds() / 60  # in minutes
    
    response = {
        "success": True,
        "next_meal": {
            "id": next_meal.id,
            "meal_type": next_meal.meal_type,
            "scheduled_time": next_meal.planned_datetime.isoformat(),
            "time_until_minutes": max(0, time_until),
            "recipe": next_meal.recipe.title if next_meal.recipe else None
        }
    }
    
    # Add preparation reminders
    if 0 < time_until <= 30:
        response["reminder"] = "Time to start preparing your meal!"
    elif 30 < time_until <= 60:
        response["reminder"] = "Meal coming up in less than an hour"
    
    return response

@router.post("/real-time/quick-log/{meal_type}")
async def quick_log_meal(
    meal_type: str,
    portion: float = Query(1.0, ge=0.1, le=5.0, description="Portion multiplier"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Quick log the current or most recent meal of specified type
    
    - Automatically finds today's meal of that type
    - Logs consumption with specified portion
    """
    from app.models.database import MealLog
    
    # Find today's meal of specified type
    today = date.today()
    meal_log = db.query(MealLog).filter(
        and_(
            MealLog.user_id == current_user.id,
            func.date(MealLog.planned_datetime) == today,
            MealLog.meal_type == meal_type,
            MealLog.consumed_datetime.is_(None),
            MealLog.was_skipped.is_(False)
        )
    ).first()
    
    if not meal_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pending {meal_type} found for today"
        )
    
    service = ConsumptionService(db)
    
    result = service.log_meal(
        user_id=current_user.id,
        meal_log_id=meal_log.id,
        portion_multiplier=portion
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to quick log meal")
        )
    
    return result

# Analytics endpoints

@router.get("/analytics/weekly-summary")
async def get_weekly_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get weekly consumption analytics
    
    - Daily breakdown
    - Average compliance
    - Macro distribution
    - Improvement areas
    """
    service = ConsumptionService(db)
    
    # Get last 7 days history
    history = service.get_consumption_history(
        user_id=current_user.id,
        days=7,
        include_details=False
    )
    
    if not history["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=history.get("error", "Failed to get weekly summary")
        )
    
    # Calculate weekly metrics
    stats = history["statistics"]
    
    return {
        "success": True,
        "week_summary": {
            "compliance_rate": stats.get("overall_compliance", 0),
            "meals_consumed": stats.get("total_meals_consumed", 0),
            "meals_skipped": stats.get("total_meals_skipped", 0),
            "average_daily_calories": stats.get("average_daily_calories", 0),
            "trends": stats.get("trends", {}),
            "daily_breakdown": history["history"]
        },
        "recommendations": [
            "Maintain consistent meal timing for better results" if stats.get("overall_compliance", 0) < 80 else "Excellent compliance! Keep it up!",
            "Consider meal prep on weekends" if stats.get("total_meals_skipped", 0) > 5 else "Good meal adherence",
            "Review portion sizes if frequently adjusting" if stats.get("average_daily_calories", 0) > 2500 else "Calorie intake looks balanced"
        ]
    }

@router.get("/analytics/meal-success-rate")
async def get_meal_success_rate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get success rate by meal type
    
    - Breakfast, lunch, dinner, snack compliance
    - Best and worst performing meals
    - Recommendations for improvement
    """
    service = ConsumptionService(db)
    
    patterns = service.get_meal_patterns(user_id=current_user.id)
    
    if not patterns["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=patterns.get("error", "Failed to get meal success rates")
        )
    
    skip_patterns = patterns["patterns"].get("skip_patterns", {})
    
    success_rates = {}
    for meal_type, data in skip_patterns.items():
        success_rates[meal_type] = {
            "success_rate": 100 - data.get("skip_rate", 0),
            "total_meals": data.get("skip_rate", 0),
            "common_skip_reasons": data.get("common_reasons", {})
        }
    
    # Find best and worst
    if success_rates:
        best_meal = max(success_rates.items(), key=lambda x: x[1]["success_rate"])
        worst_meal = min(success_rates.items(), key=lambda x: x[1]["success_rate"])
        
        return {
            "success": True,
            "meal_success_rates": success_rates,
            "best_performing": {
                "meal_type": best_meal[0],
                "success_rate": best_meal[1]["success_rate"]
            },
            "needs_improvement": {
                "meal_type": worst_meal[0],
                "success_rate": worst_meal[1]["success_rate"]
            },
            "insights": patterns.get("insights", [])
        }
    
    return {
        "success": True,
        "message": "Not enough data for analysis"
    }