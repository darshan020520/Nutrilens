import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from app.core.ist_datetime import today_ist

from app.models.database import User

from app.dependencies import (
    get_tracking_orchestrator,
    get_external_meal_service,
    get_inventory_management_service,
    get_consumption_service_v2,
    get_current_user
)

from app.orchestrators.meal_logging_orchestrator import MealLoggingOrchestrator
from app.services.external_meal_service import ExternalMealService
from app.services.inventory_management_service import InventoryManagementService
from app.services.consumption_service_v2 import ConsumptionServiceV2

from app.schemas.tracking import (
    LogMealRequest,
    SkipMealRequest,
    ExternalMealEstimateRequest,
    LogExternalMealRequest,
    LogMealResponse,
    SkipMealResponse,
    TodaySummaryResponse,
    ConsumptionHistoryResponse,
    ExpiringItemsResponse,
    RestockListResponse,
    ExternalMealEstimateResponse,
    LogExternalMealResponse,
    MacroNutrients,
    InventoryChangeItem,
    InsightItem,
    RecommendationItem
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking/v2", tags=["Tracking V2"])


def format_macro_nutrients(macros: dict) -> MacroNutrients:
    """Convert macro dict to MacroNutrients schema"""
    return MacroNutrients(
        calories=macros.get("calories", 0),
        protein_g=macros.get("protein_g", 0),
        carbs_g=macros.get("carbs_g", 0),
        fat_g=macros.get("fat_g", 0),
        fiber_g=macros.get("fiber_g", 0)
    )


def format_inventory_changes(changes: list) -> list:
    """Format inventory changes for response"""
    formatted = []
    for change in changes:
        formatted.append(InventoryChangeItem(
            item_name=change.get("item_name", ""),
            old_quantity=change.get("old_quantity", 0),
            new_quantity=change.get("new_quantity", 0),
            unit=change.get("unit", "g")
        ))
    return formatted


def format_insights(insights: list) -> list:
    """Format insights for response"""
    formatted = []
    for insight in insights:
        # Handle both string and dict formats
        if isinstance(insight, str):
            formatted.append(InsightItem(
                type="info",
                message=insight,
                priority="normal"
            ))
        else:
            formatted.append(InsightItem(
                type=insight.get("type", "info"),
                message=insight.get("message", ""),
                priority=insight.get("priority", "normal")
            ))
    return formatted


def format_recommendations(recommendations: list) -> list:
    """Format recommendations for response"""
    formatted = []
    for rec in recommendations:
        # Handle both string and dict formats
        if isinstance(rec, str):
            formatted.append(RecommendationItem(
                type="general",
                title="Recommendation",
                description=rec,
                action_url=None
            ))
        else:
            formatted.append(RecommendationItem(
                type=rec.get("type", "general"),
                title=rec.get("title", "Recommendation"),
                description=rec.get("description", ""),
                action_url=rec.get("action_url")
            ))
    return formatted


@router.post("/log-meal", response_model=LogMealResponse)
async def log_meal(
    request: LogMealRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: MealLoggingOrchestrator = Depends(get_tracking_orchestrator)
):
    try:
        logger.info(f"POST /tracking/v2/log-meal - User {current_user.id}, Meal {request.meal_log_id}")

        result = await orchestrator.log_planned_meal(
            user_id=current_user.id,
            meal_log_id=request.meal_log_id,
            portion_multiplier=request.portion_multiplier,
            notes=request.notes
        )

        meal_data = result["meal_log"]

        return LogMealResponse(
            success=True,
            meal_type=meal_data.get("meal_type", ""),
            recipe_name=meal_data.get("recipe", ""),  # Service returns "recipe" key, not "recipe_name"
            consumed_at=datetime.fromisoformat(meal_data.get("consumed_at")) if isinstance(meal_data.get("consumed_at"), str) else meal_data.get("consumed_at"),
            macros_consumed=format_macro_nutrients(meal_data.get("macros", {})),  # FIX: Service returns "macros" not "macros_consumed"
            portion_multiplier=request.portion_multiplier,
            deducted_items=format_inventory_changes(result.get("inventory_changes", [])),  # FIX: At orchestrator level, not in meal_data
            daily_totals=result.get("daily_summary", {}),  # FIX: Orchestrator returns "daily_summary" not "daily_totals"
            remaining_targets=result.get("daily_summary", {}).get("remaining_macros", {}),  # FIX: Use correct path and field name
            insights=format_insights(result.get("insights", [])),  # From orchestrator level
            recommendations=format_recommendations(result.get("recommendations", []))  # From orchestrator level
        )

    except ValueError as e:
        logger.error(f"Validation error logging meal: {e}")
        # Match OLD API: "not found" errors should return 404, not 400
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error logging meal: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/skip-meal", response_model=SkipMealResponse)
async def skip_meal(
    request: SkipMealRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: MealLoggingOrchestrator = Depends(get_tracking_orchestrator)
):
    try:
        logger.info(f"POST /tracking/v2/skip-meal - User {current_user.id}, Meal {request.meal_log_id}")

        result = await orchestrator.skip_meal_workflow(
            user_id=current_user.id,
            meal_log_id=request.meal_log_id,
            skip_reason=request.reason
        )

        skip_data = result["meal_log"]

        return SkipMealResponse(
            success=True,
            meal_type=skip_data.get("meal_type", ""),
            recipe_name=skip_data.get("recipe_name", ""),
            skip_reason=skip_data.get("reason"),
            adherence_impact=skip_data.get("adherence_impact", {}),
            updated_adherence_rate=skip_data.get("updated_adherence_rate", 0.0),
            skip_patterns=skip_data.get("skip_patterns", {}),
            insights=skip_data.get("insights", []),
            recommendations=skip_data.get("recommendations", [])
        )

    except ValueError as e:
        logger.error(f"Validation error skipping meal: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error skipping meal: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/today", response_model=TodaySummaryResponse)
async def get_today_summary(
    current_user: User = Depends(get_current_user),
    orchestrator: MealLoggingOrchestrator = Depends(get_tracking_orchestrator)
):
    try:
        logger.info(f"GET /tracking/v2/today - User {current_user.id}")
        result = await orchestrator.get_daily_overview(
            user_id=current_user.id,
            target_date=None
        )

        summary = result.get("daily_summary", {})

        total_macros = {
            "calories": summary.get("total_calories", 0),
            "protein_g": summary.get("total_protein_g", 0),
            "carbs_g": summary.get("total_carbs_g", 0),
            "fat_g": summary.get("total_fat_g", 0),
            "fiber_g": summary.get("total_fiber_g", 0)
        }
        target_macros = {
            "calories": summary.get("target_calories", 0),
            "protein_g": summary.get("target_protein_g", 0),
            "carbs_g": summary.get("target_carbs_g", 0),
            "fat_g": summary.get("target_fat_g", 0),
            "fiber_g": 0
        }
        remaining_macros = {
            "calories": summary.get("remaining_calories", 0),
            "protein_g": summary.get("remaining_protein_g", 0),
            "carbs_g": summary.get("remaining_carbs_g", 0),
            "fat_g": summary.get("remaining_fat_g", 0),
            "fiber_g": 0
        }

        return TodaySummaryResponse(
            date=result.get("date", today_ist().isoformat()),
            meals_planned=summary.get("meals_planned", 0),
            meals_consumed=summary.get("meals_consumed", 0),
            meals_skipped=summary.get("meals_skipped", 0),
            total_calories=summary.get("total_calories", 0),
            total_macros=format_macro_nutrients(total_macros),
            target_calories=summary.get("target_calories", 0),
            target_macros=format_macro_nutrients(target_macros),
            remaining_calories=summary.get("remaining_calories", 0),
            remaining_macros=format_macro_nutrients(remaining_macros),
            compliance_rate=round(summary.get("compliance_rate", 0) * 100, 1),  # Convert decimal to percentage
            meal_details=summary.get("meals", []),
            recommendations=summary.get("recommendations", [])
        )

    except Exception as e:
        logger.error(f"Error getting today's summary: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/history", response_model=ConsumptionHistoryResponse)
async def get_consumption_history(
    days: int = Query(default=7, ge=1, le=90, description="Number of days of history (1-90)"),
    current_user: User = Depends(get_current_user),
    consumption_service: ConsumptionServiceV2 = Depends(get_consumption_service_v2)
):

    try:
        logger.info(f"GET /tracking/v2/history - User {current_user.id}, Days {days}")


        result = await consumption_service.get_consumption_history(
            user_id=current_user.id,
            days=days,
            include_details=True
        )

        daily_data_list = result.get("daily_data", [])

        history = []
        for daily_item in daily_data_list:
            history.append({
                "date": daily_item.get("date", ""),
                "meals": daily_item.get("meals", [])
            })

        total_meals = sum(d.get("meals_planned", 0) for d in daily_data_list)
        logged_meals = sum(d.get("meals_consumed", 0) for d in daily_data_list)
        skipped_meals = sum(d.get("meals_skipped", 0) for d in daily_data_list)
        adherence_rate = (logged_meals / total_meals * 100) if total_meals > 0 else 0

        return ConsumptionHistoryResponse(
            period=result.get("period", {}),
            statistics={
                "total_meals": total_meals,
                "logged_meals": logged_meals,
                "skipped_meals": skipped_meals,
                "adherence_rate": round(adherence_rate, 1)
            },
            history=history,
            trends=result.get("trends", {})
        )

    except ValueError as e:
        logger.error(f"Validation error getting history: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting consumption history: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/expiring-items", response_model=ExpiringItemsResponse)
async def get_expiring_items(
    days: int = Query(default=3, ge=1, le=14, description="Days threshold for expiry warning (1-14)"),
    filter_mode: str = Query(default="date_only", regex="^(date_only|consumption_only|both)$",
                              description="Filter mode: date_only, consumption_only, or both"),
    current_user: User = Depends(get_current_user),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service)
):
    try:
        logger.info(f"GET /tracking/v2/expiring-items - User {current_user.id}, Days {days}, Mode {filter_mode}")

        result = await inventory_service.check_expiring_items(
            user_id=current_user.id,
            filter_mode=filter_mode,
            days_threshold=days
        )


        summary = result.get("summary", {})

        return ExpiringItemsResponse(
            total_expiring=result.get("expiring_count", 0),
            expired_count=summary.get("expired", 0),
            urgent_count=summary.get("urgent", 0),
            high_priority_count=summary.get("high", 0),
            medium_priority_count=summary.get("medium", 0),
            items=result.get("expiring_items", []),
            action_recommendations=result.get("recommendations", [])
        )

    except ValueError as e:
        logger.error(f"Validation error getting expiring items: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting expiring items: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/restock-list", response_model=RestockListResponse)
async def get_restock_list(
    current_user: User = Depends(get_current_user),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service)
):
    try:
        logger.info(f"GET /tracking/v2/restock-list - User {current_user.id}")

        result = await inventory_service.generate_restock_list(
            user_id=current_user.id
        )

        restock_list = result.get("restock_list", {})

        return RestockListResponse(
            total_items=result.get("total_items", 0),
            urgent_items=restock_list.get("urgent", []),
            soon_items=restock_list.get("soon", []),
            routine_items=restock_list.get("routine", []),
            estimated_total_cost=result.get("estimated_cost", 0),
            shopping_strategy=result.get("shopping_strategy", [])
        )

    except Exception as e:
        logger.error(f"Error generating restock list: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/estimate-external-meal", response_model=ExternalMealEstimateResponse)
async def estimate_external_meal(
    request: ExternalMealEstimateRequest,
    current_user: User = Depends(get_current_user),
    external_meal_service: ExternalMealService = Depends(get_external_meal_service)
):
    try:
        logger.info(f"POST /tracking/v2/estimate-external-meal - User {current_user.id}, Dish: {request.dish_name}")

        estimate = await external_meal_service.estimate_nutrition(
            user_id=current_user.id,
            dish_name=request.dish_name,
            portion_size=request.portion_size,
            restaurant_name=request.restaurant_name,
            cuisine_type=request.cuisine_type
        )

        return ExternalMealEstimateResponse(**estimate)

    except ValueError as e:
        logger.error(f"Validation error estimating external meal: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error estimating external meal: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/log-external-meal", response_model=LogExternalMealResponse)
async def log_external_meal(
    request: LogExternalMealRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: MealLoggingOrchestrator = Depends(get_tracking_orchestrator)
):
    try:
        logger.info(f"POST /tracking/v2/log-external-meal - User {current_user.id}, Dish: {request.dish_name}")

        meal_data = {
            "dish_name": request.dish_name,
            "portion_size": request.portion_size,
            "restaurant_name": request.restaurant_name,
            "cuisine_type": request.cuisine_type,
            "calories": request.calories,
            "protein_g": request.protein_g,
            "carbs_g": request.carbs_g,
            "fat_g": request.fat_g,
            "fiber_g": request.fiber_g
        }

        result = await orchestrator.log_external_meal_workflow(
            user_id=current_user.id,
            meal_data=meal_data,
            meal_log_id_to_replace=request.meal_log_id_to_replace,
            meal_type=request.meal_type,
            notes=request.notes
        )

        return LogExternalMealResponse(
            success=True,
            meal_log_id=result["meal_log_id"],
            meal_type=result["meal_type"],
            dish_name=result["dish_name"],
            restaurant_name=result.get("restaurant_name"),
            consumed_at=datetime.fromisoformat(result["consumed_at"]) if isinstance(result["consumed_at"], str) else result["consumed_at"],
            macros=MacroNutrients(**result["macros"]),
            replaced_meal=result.get("replaced_meal", False),
            original_recipe=result.get("original_recipe"),
            updated_daily_totals=result.get("updated_daily_totals", {}),
            remaining_calories=result.get("remaining_calories", 0),
            remaining_meals_today=result.get("remaining_meals_today"),
            insights=result.get("insights", []),
            recommendations=result.get("recommendations", [])
        )

    except ValueError as e:
        logger.error(f"Validation error logging external meal: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error logging external meal: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
