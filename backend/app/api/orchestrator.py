# backend/app/api/orchestrator.py
"""
Orchestrator API Router for WhatsApp Agent Integration

Provides simplified endpoints for WhatsApp orchestrator.
WhatsApp agent passes user_id directly (no JWT auth needed for these endpoints).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel

from app.models.database import get_db, User, MealLog, MealPlan
from app.agents.tracking_agent import TrackingAgent
from app.services.consumption_services import ConsumptionService
from app.services.llm_nutrition_estimator import estimate_nutrition_with_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


# ===== REQUEST SCHEMAS =====

class LogMealRequest(BaseModel):
    """Log a planned meal"""
    user_id: int
    meal_log_id: int
    portion_multiplier: Optional[float] = 1.0


class EstimateExternalMealRequest(BaseModel):
    """Estimate external meal nutrition"""
    user_id: int
    meal_type: str
    dish_name: str
    portion_size: str
    restaurant_name: Optional[str] = None
    cuisine_type: Optional[str] = None


class LogExternalMealRequest(BaseModel):
    """Log confirmed external meal"""
    user_id: int
    meal_type: str
    dish_name: str
    portion_size: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: Optional[float] = 0
    restaurant_name: Optional[str] = None
    cuisine_type: Optional[str] = None


@router.get("/planned-meal")
async def get_planned_meal(
    user_id: int = Query(..., description="User ID from WhatsApp"),
    meal_type: str = Query(..., description="breakfast|lunch|dinner|snack"),
    db: Session = Depends(get_db)
):
    """
    Get specific planned meal for user by meal type.

    WhatsApp agent calls this with user_id and meal_type to get meal details.

    Query Parameters:
        user_id: NutriLens user ID
        meal_type: breakfast | lunch | dinner | snack

    Returns:
        meal_log_id, meal_name, macros for user confirmation
    """
    try:
        today = date.today()

        # Get active meal plan
        active_plan = db.query(MealPlan).filter(
            and_(
                MealPlan.user_id == user_id,
                MealPlan.is_active == True
            )
        ).first()

        if not active_plan:
            return {
                "success": False,
                "error": "no_active_plan",
                "message": "No active meal plan found"
            }

        # Get meal log for this meal type today
        meal_log = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.meal_plan_id == active_plan.id,
                MealLog.meal_type == meal_type.lower(),
                func.date(MealLog.planned_datetime) == today
            )
        ).first()

        if not meal_log:
            return {
                "success": False,
                "error": "meal_not_found",
                "message": f"No {meal_type} planned for today"
            }

        # Check if already logged
        if meal_log.consumed_datetime:
            return {
                "success": False,
                "error": "already_logged",
                "message": f"{meal_type.capitalize()} already logged"
            }

        # Check if skipped
        if meal_log.was_skipped:
            return {
                "success": False,
                "error": "already_skipped",
                "message": f"{meal_type.capitalize()} was skipped"
            }

        # Get meal details
        meal_name = "Unknown Meal"
        macros = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

        if meal_log.recipe:
            meal_name = meal_log.recipe.title
            recipe_macros = meal_log.recipe.macros_per_serving or {}
            portion = meal_log.portion_multiplier or 1.0

            macros = {
                "calories": round(recipe_macros.get("calories", 0) * portion, 1),
                "protein": round(recipe_macros.get("protein_g", 0) * portion, 1),
                "carbs": round(recipe_macros.get("carbs_g", 0) * portion, 1),
                "fat": round(recipe_macros.get("fat_g", 0) * portion, 1)
            }
        elif meal_log.external_meal:
            meal_name = meal_log.external_meal.get("dish_name", "External Meal")
            macros = {
                "calories": round(meal_log.external_meal.get("calories", 0), 1),
                "protein": round(meal_log.external_meal.get("protein_g", 0), 1),
                "carbs": round(meal_log.external_meal.get("carbs_g", 0), 1),
                "fat": round(meal_log.external_meal.get("fat_g", 0), 1)
            }

        return {
            "success": True,
            "meal_log_id": meal_log.id,
            "meal_type": meal_log.meal_type,
            "meal_name": meal_name,
            "calories": macros["calories"],
            "protein": macros["protein"],
            "carbs": macros["carbs"],
            "fat": macros["fat"]
        }

    except Exception as e:
        logger.error(f"Error getting planned meal: {str(e)}")
        return {
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }


@router.post("/log-meal")
async def log_meal(
    request: LogMealRequest,
    db: Session = Depends(get_db)
):
    """
    Log a planned meal as consumed.

    Uses existing TrackingAgent.log_meal_consumption() - no duplication.
    """
    try:
        tracking_agent = TrackingAgent(db, request.user_id)

        result = await tracking_agent.log_meal_consumption(
            meal_log_id=request.meal_log_id,
            portion_multiplier=request.portion_multiplier
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "failed"),
                "message": result.get("error", "Failed to log meal")
            }

        # Get updated daily summary
        consumption_service = ConsumptionService(db)
        daily_summary = consumption_service.get_today_summary(request.user_id)

        return {
            "success": True,
            "meal_log_id": request.meal_log_id,
            "calories_remaining": daily_summary.get("remaining_calories", 0),
            "message": "Meal logged successfully"
        }

    except Exception as e:
        logger.error(f"Error logging meal: {str(e)}")
        db.rollback()
        return {
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }


@router.post("/estimate-external-meal")
async def estimate_external_meal(
    request: EstimateExternalMealRequest,
    db: Session = Depends(get_db)
):
    """
    Estimate nutrition for external meal - for user confirmation.

    Uses existing estimate_nutrition_with_llm() - does NOT create meal log.
    """
    try:
        # Use existing LLM estimation function
        estimation = estimate_nutrition_with_llm(
            dish_name=request.dish_name,
            portion_size=request.portion_size,
            restaurant_name=request.restaurant_name,
            cuisine_type=request.cuisine_type,
            api_key=settings.openai_api_key
        )

        return {
            "success": True,
            "dish_name": estimation["dish_name"],
            "portion_size": estimation["portion_size"],
            "estimated_macros": {
                "calories": round(estimation["calories"], 1),
                "protein": round(estimation["protein_g"], 1),
                "carbs": round(estimation["carbs_g"], 1),
                "fat": round(estimation["fat_g"], 1),
                "fiber": round(estimation.get("fiber_g", 0), 1)
            },
            "confidence": estimation["confidence"],
            "reasoning": estimation["reasoning"]
        }

    except Exception as e:
        logger.error(f"Error estimating external meal: {str(e)}")
        return {
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }


@router.post("/log-external-meal")
async def log_external_meal(
    request: LogExternalMealRequest,
    db: Session = Depends(get_db)
):
    """
    Log confirmed external meal after user approves estimation.

    Creates new meal log with confirmed macro data.
    """
    try:
        consumed_at = datetime.utcnow()
        today = date.today()

        logger.info(f"[LOG_EXTERNAL_MEAL] User: {request.user_id}, Meal Type: {request.meal_type}, Dish: {request.dish_name}")

        # Build external_meal JSON data (confirmed by user)
        external_meal_data = {
            "dish_name": request.dish_name,
            "portion_size": request.portion_size,
            "restaurant_name": request.restaurant_name,
            "cuisine_type": request.cuisine_type,
            "calories": request.calories,
            "protein_g": request.protein_g,
            "carbs_g": request.carbs_g,
            "fat_g": request.fat_g,
            "fiber_g": request.fiber_g,
            "logged_at": consumed_at.isoformat()
        }

        # Check if there's a pending planned meal for this meal_type today
        active_plan = db.query(MealPlan).filter(
            and_(
                MealPlan.user_id == request.user_id,
                MealPlan.is_active == True
            )
        ).first()

        logger.info(f"[LOG_EXTERNAL_MEAL] Active meal plan: {active_plan.id if active_plan else 'None'}")

        existing_pending_meal = None
        if active_plan:
            existing_pending_meal = db.query(MealLog).filter(
                and_(
                    MealLog.user_id == request.user_id,
                    MealLog.meal_plan_id == active_plan.id,
                    MealLog.meal_type == request.meal_type.lower(),
                    func.date(MealLog.planned_datetime) == today,
                    MealLog.consumed_datetime.is_(None),
                    MealLog.was_skipped == False
                )
            ).first()

        logger.info(f"[LOG_EXTERNAL_MEAL] Existing pending {request.meal_type}: {existing_pending_meal.id if existing_pending_meal else 'None'}")

        if existing_pending_meal:
            # REPLACE the pending planned meal
            logger.info(f"[LOG_EXTERNAL_MEAL] REPLACING meal_log_id: {existing_pending_meal.id}")
            existing_pending_meal.consumed_datetime = consumed_at
            existing_pending_meal.external_meal = external_meal_data
            existing_pending_meal.recipe_id = None  # Clear recipe link
            meal_log = existing_pending_meal
        else:
            # CREATE new external meal log
            logger.info(f"[LOG_EXTERNAL_MEAL] CREATING new external meal log")
            meal_log = MealLog(
                user_id=request.user_id,
                recipe_id=None,
                meal_type=request.meal_type.lower(),
                planned_datetime=consumed_at,
                consumed_datetime=consumed_at,
                was_skipped=False,
                meal_plan_id=None,
                day_index=None,
                external_meal=external_meal_data
            )
            db.add(meal_log)

        db.commit()
        db.refresh(meal_log)

        logger.info(f"[LOG_EXTERNAL_MEAL] Final meal_log_id: {meal_log.id}, Action: {'REPLACED' if existing_pending_meal else 'CREATED'}")

        # Get updated daily summary
        consumption_service = ConsumptionService(db)
        daily_summary = consumption_service.get_today_summary(request.user_id)

        return {
            "success": True,
            "meal_log_id": meal_log.id,
            "calories_remaining": daily_summary.get("remaining_calories", 0),
            "message": "External meal logged successfully"
        }

    except Exception as e:
        logger.error(f"Error logging external meal: {str(e)}")
        db.rollback()
        return {
            "success": False,
            "error": "internal_error",
            "message": str(e)
        }
