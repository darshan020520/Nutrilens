"""
Tracking API V2 - Clean Architecture Implementation

This module implements Phase 2 tracking endpoints using the layered architecture:
    API → Orchestrator → Services → Repositories → Database

Migrated from: backend/app/api/tracking.py (TrackingAgent-based implementation)

Active Endpoints (9):
1. POST /log-meal - Log meal consumption
2. POST /skip-meal - Skip a meal
3. GET /today - Today's consumption summary
4. GET /history - Historical consumption data
5. GET /inventory-status - Current inventory analytics
6. GET /expiring-items - Items expiring soon
7. GET /restock-list - Shopping recommendations
8. POST /estimate-external-meal - LLM nutrition estimation
9. POST /log-external-meal - Log external/restaurant meal

Architecture:
    This file (API Layer)
        ↓ Uses dependency injection
    MealLoggingOrchestrator (Workflow Coordination)
        ↓ Coordinates
    Services (Business Logic)
        ↓ Uses
    Repositories (Data Access)
        ↓ Queries
    Database Models
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime, date

# Auth and User
from app.models.database import User
from app.services.auth import get_current_user_dependency as get_current_user

# Dependencies (DI)
from app.dependencies import (
    get_tracking_orchestrator,
    get_external_meal_service,
    get_inventory_management_service,
    get_consumption_service_v2
)

# Orchestrator and Services
from app.orchestrators.meal_logging_orchestrator import MealLoggingOrchestrator
from app.services.external_meal_service import ExternalMealService
from app.services.inventory_management_service import InventoryManagementService
from app.services.consumption_service_v2 import ConsumptionServiceV2

# Request/Response Schemas
from app.schemas.tracking import (
    # Request schemas
    LogMealRequest,
    SkipMealRequest,
    ExternalMealEstimateRequest,
    LogExternalMealRequest,
    # Response schemas
    LogMealResponse,
    SkipMealResponse,
    TodaySummaryResponse,
    ConsumptionHistoryResponse,
    InventoryStatusResponse,
    ExpiringItemsResponse,
    RestockListResponse,
    ExternalMealEstimateResponse,
    LogExternalMealResponse,
    # Helper schemas
    MacroNutrients,
    InventoryChangeItem,
    InsightItem,
    RecommendationItem
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking/v2", tags=["Tracking V2"])


# ===== HELPER FUNCTIONS (copied from tracking.py for schema compatibility) =====

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


# ===== CORE MEAL TRACKING ENDPOINTS =====

@router.post("/log-meal", response_model=LogMealResponse)
async def log_meal(
    request: LogMealRequest,
    current_user: User = Depends(get_current_user),
    orchestrator: MealLoggingOrchestrator = Depends(get_tracking_orchestrator)
):
    """
    Log a planned meal consumption.

    Workflow:
    1. Validate meal log exists and belongs to user
    2. Mark meal as consumed
    3. Auto-deduct ingredients from inventory
    4. Update daily consumption totals
    5. Check inventory status
    6. Publish events and send notifications
    7. Return comprehensive response

    Source: backend/app/api/tracking.py:120-206
    Migrated to: Clean architecture with orchestrator pattern
    """
    try:
        logger.info(f"POST /tracking/v2/log-meal - User {current_user.id}, Meal {request.meal_log_id}")

        # Use orchestrator for full workflow
        result = await orchestrator.log_planned_meal(
            user_id=current_user.id,
            meal_log_id=request.meal_log_id,
            portion_multiplier=request.portion_multiplier,
            notes=request.notes
        )

        # Transform orchestrator response to match OLD API schema EXACTLY
        # OLD schema from tracking.py:179-191
        # Orchestrator wraps service result: result["meal_log"] contains the meal_tracking_service response
        meal_data = result["meal_log"]

        return LogMealResponse(
            success=True,
            meal_type=meal_data.get("meal_type", ""),
            recipe_name=meal_data.get("recipe", ""),  # Service returns "recipe" key, not "recipe_name"
            consumed_at=datetime.fromisoformat(meal_data.get("consumed_at")) if isinstance(meal_data.get("consumed_at"), str) else meal_data.get("consumed_at"),
            macros_consumed=format_macro_nutrients(meal_data.get("macros_consumed", {})),
            portion_multiplier=request.portion_multiplier,
            deducted_items=format_inventory_changes(meal_data.get("deducted_items", [])),
            daily_totals=meal_data.get("daily_totals", {}),  # Service returns "daily_totals" key
            remaining_targets=meal_data.get("daily_totals", {}).get("remaining_targets", {}),
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
    """
    Mark a planned meal as skipped.

    Workflow:
    1. Validate meal log exists and belongs to user
    2. Mark meal as skipped with reason
    3. Analyze skip patterns (frequency, meal types, etc.)
    4. Update daily summary
    5. Publish events
    6. Send notifications if patterns detected

    Source: backend/app/api/tracking.py:208-288
    Migrated to: Clean architecture with orchestrator pattern
    """
    try:
        logger.info(f"POST /tracking/v2/skip-meal - User {current_user.id}, Meal {request.meal_log_id}")

        # Use orchestrator for full workflow
        result = await orchestrator.skip_meal_workflow(
            user_id=current_user.id,
            meal_log_id=request.meal_log_id,
            skip_reason=request.reason  # Use 'reason' field from schema
        )

        # Transform orchestrator response to match OLD API schema EXACTLY
        # OLD schema from tracking.py:268-275
        # Orchestrator wraps service result: result["meal_log"] contains the skip service response
        skip_data = result["meal_log"]

        return SkipMealResponse(
            success=True,
            meal_type=skip_data.get("meal_type", ""),
            recipe_name=skip_data.get("recipe_name", ""),
            skip_reason=request.reason,
            adherence_impact=skip_data.get("adherence_impact", {}),  # Service returns this directly
            updated_adherence_rate=skip_data.get("updated_adherence_rate", 0.0)  # Service returns this directly
        )

    except ValueError as e:
        logger.error(f"Validation error skipping meal: {e}")
        # Match OLD API: "not found" errors should return 404, not 400
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
    """
    Get comprehensive summary for today's consumption.

    Includes:
    - All meals (planned, consumed, skipped, external)
    - Daily macro totals vs targets
    - Remaining calories and macros
    - Inventory status
    - Expiring items
    - Personalized recommendations

    Source: backend/app/api/tracking.py:474-531
    Migrated to: Clean architecture with orchestrator pattern
    """
    try:
        logger.info(f"GET /tracking/v2/today - User {current_user.id}")

        # Use orchestrator to aggregate daily overview
        result = await orchestrator.get_daily_overview(
            user_id=current_user.id,
            target_date=None  # Defaults to today
        )

        # Transform orchestrator response to match OLD API schema EXACTLY
        # OLD schema from tracking.py:507-520
        summary = result.get("daily_summary", {})
        return TodaySummaryResponse(
            date=result.get("date", datetime.utcnow().date().isoformat()),
            meals_planned=summary.get("meals_planned", 0),
            meals_consumed=summary.get("meals_consumed", 0),
            meals_skipped=summary.get("meals_skipped", 0),
            total_calories=summary.get("total_calories", 0),
            total_macros=format_macro_nutrients(summary.get("total_macros", {})),
            target_calories=summary.get("target_calories", 0),
            target_macros=format_macro_nutrients(summary.get("targets", {})),
            remaining_calories=summary.get("remaining_calories", 0),
            remaining_macros=format_macro_nutrients(summary.get("remaining_macros", {})),
            compliance_rate=summary.get("compliance_rate", 0),
            meal_details=summary.get("meals", [])
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
    """
    Get historical consumption data with trends and analytics.

    Query Parameters:
    - days: Number of days to retrieve (1-90, default: 7)

    Includes:
    - Daily consumption totals
    - Trend analysis (increasing/decreasing/stable)
    - Adherence rates
    - Macro distribution
    - Meal completion stats

    Source: backend/app/api/tracking.py:533-610
    Migrated to: Clean architecture with service pattern
    """
    try:
        logger.info(f"GET /tracking/v2/history - User {current_user.id}, Days {days}")

        # Use consumption service to get historical data
        result = await consumption_service.get_consumption_history(
            user_id=current_user.id,
            days=days
        )

        # Transform service response to match OLD API schema EXACTLY
        # Service returns: {period, daily_data (LIST), trends}
        # OLD expects: {period, statistics, history (LIST), trends}

        # daily_data is a LIST from repository, not a dict
        daily_data_list = result.get("daily_data", [])

        # Build history array matching OLD format
        history = []
        for daily_item in daily_data_list:
            history.append({
                "date": daily_item.get("date", ""),
                "meals": daily_item.get("meals", [])  # Will be populated if service called with include_details
            })

        # Build statistics from daily_data list
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
        # Match OLD API: "not found" errors should return 404, not 400
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting consumption history: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ===== INVENTORY MANAGEMENT ENDPOINTS =====

@router.get("/inventory-status", response_model=InventoryStatusResponse)
async def get_inventory_status(
    current_user: User = Depends(get_current_user),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service)
):
    """
    Get current inventory status with analytics.

    Includes:
    - Overall percentage stocked
    - Critical items (low/out of stock)
    - Well-stocked items
    - Category breakdown
    - Consumption-based recommendations

    Source: backend/app/api/tracking.py:683-737
    Migrated to: Clean architecture with service pattern
    """
    try:
        logger.info(f"GET /tracking/v2/inventory-status - User {current_user.id}")

        # Use inventory service for status calculation
        result = await inventory_service.calculate_inventory_status(
            user_id=current_user.id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to calculate inventory status"
            )

        # Transform service response to match OLD API schema EXACTLY
        # Service returns: overall_percentage, category_breakdown (complex objects)
        # OLD expects: overall_stock_level, items_by_category (simple counts)

        # Extract items_by_category from category_breakdown
        items_by_category = {}
        if result.get("category_breakdown"):
            for category, data in result["category_breakdown"].items():
                items_by_category[category] = data.get("total_items", 0)

        return InventoryStatusResponse(
            total_items=result.get("total_items_tracked", 0),
            items_by_category=items_by_category,
            overall_stock_level=result.get("overall_percentage", 0),
            low_stock_items=result.get("low_stock_items", []),
            critical_items=result.get("critical_items", []),
            expiring_soon=result.get("expiring_soon", []),
            overstocked_items=result.get("well_stocked", []),  # Service calls it "well_stocked"
            recommendations=result.get("recommendations", [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting inventory status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/expiring-items", response_model=ExpiringItemsResponse)
async def get_expiring_items(
    days: int = Query(default=3, ge=1, le=14, description="Days threshold for expiry warning (1-14)"),
    filter_mode: str = Query(default="both", regex="^(date_only|consumption_only|both)$",
                              description="Filter mode: date_only, consumption_only, or both"),
    current_user: User = Depends(get_current_user),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service)
):
    """
    Get items expiring soon with smart filtering.

    Query Parameters:
    - days: Days threshold for expiry warning (1-14, default: 3)
    - filter_mode: Filtering strategy
      * date_only: Check expiry date alone
      * consumption_only: Check if will be consumed before expiry
      * both: Combine both filters (default)

    Includes:
    - List of expiring items
    - Recipes using those ingredients
    - Recommendations for using items
    - Priority levels (urgent, soon, routine)

    Source: backend/app/api/tracking.py:739-798
    Migrated to: Clean architecture with service pattern
    """
    try:
        logger.info(f"GET /tracking/v2/expiring-items - User {current_user.id}, Days {days}, Mode {filter_mode}")

        # Use inventory service for expiry detection
        result = await inventory_service.check_expiring_items(
            user_id=current_user.id,
            filter_mode=filter_mode,
            days_threshold=days
        )

        # Transform service response to match OLD API schema EXACTLY
        # Service returns: {expiring_count, expiring_items, recommendations, summary: {urgent, high, medium}}
        # OLD expects: {total_expiring, urgent_count, high_priority_count, medium_priority_count, items, action_recommendations}

        summary = result.get("summary", {})

        return ExpiringItemsResponse(
            total_expiring=result.get("expiring_count", 0),
            urgent_count=summary.get("urgent", 0),
            high_priority_count=summary.get("high", 0),
            medium_priority_count=summary.get("medium", 0),
            items=result.get("expiring_items", []),
            action_recommendations=result.get("recommendations", [])
        )

    except ValueError as e:
        logger.error(f"Validation error getting expiring items: {e}")
        # Match OLD API: "not found" errors should return 404, not 400
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
    """
    Get intelligent shopping/restock recommendations.

    Analysis includes:
    - Upcoming planned meals (next 7 days)
    - Historical consumption patterns (last 30 days)
    - Current inventory levels
    - Seasonal/bulk buying opportunities

    Returns:
    - Prioritized restock list (urgent, soon, routine)
    - Quantity recommendations
    - Bulk buying suggestions
    - Cost estimates (if available)

    Source: backend/app/api/tracking.py:800-852
    Migrated to: Clean architecture with service pattern
    """
    try:
        logger.info(f"GET /tracking/v2/restock-list - User {current_user.id}")

        # Use inventory service for restock analysis
        result = await inventory_service.generate_restock_list(
            user_id=current_user.id
        )

        # Transform service response to match OLD API schema EXACTLY
        # Service returns: {restock_list: {urgent: [], soon: [], routine: []}, estimated_cost, shopping_strategy}
        # OLD expects: {urgent_items, soon_items, routine_items, estimated_total_cost, shopping_strategy}

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


# ===== EXTERNAL MEAL ENDPOINTS =====

@router.post("/estimate-external-meal", response_model=ExternalMealEstimateResponse)
async def estimate_external_meal(
    request: ExternalMealEstimateRequest,
    current_user: User = Depends(get_current_user),
    external_meal_service: ExternalMealService = Depends(get_external_meal_service)
):
    """
    Get LLM-based nutrition estimate for an external meal.

    Uses OpenAI to estimate macronutrients for restaurant meals,
    eating out, or meals without recipes.

    Request includes:
    - dish_name: Name of the dish (required)
    - portion_size: Portion description (required)
    - restaurant_name: Optional restaurant name for better estimation
    - cuisine_type: Optional cuisine type (e.g., "Indian", "Italian")

    Returns:
    - Estimated calories, protein, carbs, fat, fiber
    - Confidence score (low, medium, high)
    - Reasoning/explanation of estimation

    Note: This endpoint does NOT create any database entries.
    Use /log-external-meal to actually log the meal.

    Source: backend/app/api/tracking.py:854-904
    Migrated to: Clean architecture with service pattern
    """
    try:
        logger.info(f"POST /tracking/v2/estimate-external-meal - User {current_user.id}, Dish: {request.dish_name}")

        # Use external meal service for LLM estimation
        estimate = await external_meal_service.estimate_nutrition(
            dish_name=request.dish_name,
            portion_size=request.portion_size,
            restaurant_name=request.restaurant_name,
            cuisine_type=request.cuisine_type
        )

        return ExternalMealEstimateResponse(**estimate)

    except ValueError as e:
        logger.error(f"Validation error estimating external meal: {e}")
        # Match OLD API: "not found" errors should return 404, not 400
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
    """
    Log an external/restaurant meal.

    Can either:
    1. Replace a planned meal with external meal data
    2. Add a new external meal without replacing

    Workflow:
    1. Validate meal data (from estimate or manual entry)
    2. Create/update meal log
    3. Update daily consumption totals
    4. Check inventory status
    5. Get remaining meals for potential adjustment
    6. Publish events and send notifications

    Request includes:
    - meal_data: External meal nutrition data (required)
      * dish_name, portion_size, calories, protein_g, carbs_g, fat_g
      * Optional: restaurant_name, cuisine_type, fiber_g
    - meal_log_id_to_replace: Optional ID of planned meal to replace
    - meal_type: Required if not replacing (breakfast, lunch, dinner, snack)
    - notes: Optional notes about the meal

    Source: backend/app/api/tracking.py:907-1095
    Migrated to: Clean architecture with orchestrator pattern
    """
    try:
        logger.info(f"POST /tracking/v2/log-external-meal - User {current_user.id}, Dish: {request.meal_data.get('dish_name')}")

        # Use orchestrator for full external meal workflow
        result = await orchestrator.log_external_meal_workflow(
            user_id=current_user.id,
            meal_data=request.meal_data,
            meal_log_id_to_replace=request.meal_log_id_to_replace,
            meal_type=request.meal_type,
            notes=request.notes
        )

        # Transform orchestrator response to match OLD API schema EXACTLY
        # OLD schema from tracking.py:1061-1082 (flat structure)
        # Orchestrator now returns flat structure matching service response

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
        # Match OLD API: "not found" errors should return 404, not 400
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error logging external meal: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ===== HEALTH CHECK =====

@router.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.

    Returns:
        Dict with status and version info
    """
    return {
        "status": "healthy",
        "version": "v2",
        "architecture": "layered (API → Orchestrator → Services → Repositories)",
        "endpoints": 9
    }