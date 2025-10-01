# backend/app/api/tracking.py
"""
Complete Tracking API Router for NutriLens AI
Handles meal logging, inventory management, and consumption analytics
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.models.database import get_db, User, MealLog
from app.services.auth import get_current_user_dependency as get_current_user
from app.agents.tracking_agent import TrackingAgent
from app.services.consumption_services import ConsumptionService
from app.schemas.tracking import (
    # Request schemas
    LogMealRequest,
    SkipMealRequest,
    BulkInventoryUpdateRequest,
    ManualFoodEntryRequest,
    # Response schemas
    LogMealResponse,
    SkipMealResponse,
    TodaySummaryResponse,
    ConsumptionHistoryResponse,
    ConsumptionPatternsResponse,
    InventoryStatusResponse,
    ExpiringItemsResponse,
    RestockListResponse,
    BulkInventoryUpdateResponse,
    ManualFoodEntryResponse,
    MacroNutrients,
    InventoryChangeItem,
    InsightItem,
    RecommendationItem
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracking", tags=["Tracking"])


# ===== HELPER FUNCTIONS =====

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
        formatted.append(RecommendationItem(
            type=rec.get("type", "general"),
            title=rec.get("title", ""),
            description=rec.get("description", ""),
            action_url=rec.get("action_url")
        ))
    return formatted


# ===== POST ENDPOINTS (ACTIONS) =====

@router.post("/log-meal", response_model=LogMealResponse)
async def log_meal(
    request: LogMealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log a meal consumption from the meal plan
    
    This endpoint:
    1. Marks the meal as consumed
    2. Automatically deducts ingredients from inventory
    3. Updates daily consumption totals
    4. Checks for achievements
    5. Broadcasts WebSocket updates (if connected)
    6. Queues notifications (if applicable)
    
    Returns comprehensive meal logging details with insights and recommendations.
    """
    try:
        # Initialize tracking agent
        tracking_agent = TrackingAgent(db, current_user.id)
        
        # Verify meal_log exists and belongs to user
        meal_log = db.query(MealLog).filter(
            MealLog.id == request.meal_log_id,
            MealLog.user_id == current_user.id
        ).first()
        
        if not meal_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meal log {request.meal_log_id} not found"
            )
        
        if meal_log.consumed_datetime is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This meal has already been logged"
            )
        
        # Log the meal via tracking agent
        result = await tracking_agent.log_meal_consumption(
            meal_log_id=request.meal_log_id,
            portion_multiplier=request.portion_multiplier
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to log meal")
            )
        
        # Update notes if provided
        if request.notes:
            meal_log.notes = request.notes
            db.commit()
        
        # Format response
        response = LogMealResponse(
            success=True,
            meal_type=result["meal_type"],
            recipe_name=result["recipe"],
            consumed_at=datetime.fromisoformat(result["consumed_at"]),
            macros_consumed=format_macro_nutrients(result.get("macros_consumed", {})),
            portion_multiplier=request.portion_multiplier,
            deducted_items=format_inventory_changes(result.get("deducted_items", [])),
            daily_totals=result.get("daily_totals", {}),
            remaining_targets=result.get("daily_totals", {}).get("remaining_targets", {}),
            insights=format_insights(result.get("insights", [])),
            recommendations=format_recommendations(result.get("recommendations", []))
        )
        
        logger.info(f"User {current_user.id} logged meal {request.meal_log_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging meal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log meal: {str(e)}"
        )


@router.post("/skip-meal", response_model=SkipMealResponse)
async def skip_meal(
    request: SkipMealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a planned meal as skipped
    
    This endpoint:
    1. Records the meal skip with optional reason
    2. Updates adherence statistics
    3. Analyzes skip patterns
    4. Provides recommendations to improve adherence
    
    Returns skip confirmation with adherence impact analysis.
    """
    try:
        # Initialize tracking agent
        tracking_agent = TrackingAgent(db, current_user.id)
        
        # Verify meal_log exists and belongs to user
        meal_log = db.query(MealLog).filter(
            MealLog.id == request.meal_log_id,
            MealLog.user_id == current_user.id
        ).first()
        
        if not meal_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meal log {request.meal_log_id} not found"
            )
        
        if meal_log.was_skipped:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This meal is already marked as skipped"
            )
        
        if meal_log.consumed_datetime is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot skip a meal that has already been logged"
            )
        
        # Skip the meal via tracking agent
        result = tracking_agent.track_skipped_meals(
            meal_log_id=request.meal_log_id,
            reason=request.reason
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to skip meal")
            )
        
        # Format response
        response = SkipMealResponse(
            success=True,
            meal_type=result.get("meal_type", ""),
            recipe_name=result.get("recipe_name", ""),
            skip_reason=request.reason,
            adherence_impact=result.get("adherence_impact", {}),
            updated_adherence_rate=result.get("updated_adherence_rate", 0.0)
        )
        
        logger.info(f"User {current_user.id} skipped meal {request.meal_log_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error skipping meal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to skip meal: {str(e)}"
        )


@router.post("/update-inventory", response_model=BulkInventoryUpdateResponse)
async def update_inventory(
    request: BulkInventoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk update inventory items (add, deduct, or set quantities)
    
    This endpoint:
    1. Normalizes item names using AI
    2. Validates quantities and operations
    3. Performs bulk updates
    4. Identifies items that failed
    5. Provides inventory recommendations
    6. Broadcasts WebSocket updates
    
    Returns detailed update results with success/failure breakdown.
    """
    try:
        # Initialize tracking agent
        tracking_agent = TrackingAgent(db, current_user.id)
        
        # Convert request items to inventory changes format
        inventory_changes = []
        for item in request.items:
            inventory_changes.append({
                "item_name": item.item_name,
                "quantity_grams": item.quantity_grams,
                "operation": item.operation.value,
                "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None
            })
        
        # Update inventory via tracking agent
        result = tracking_agent.update_inventory(inventory_changes)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update inventory")
            )
        
        # Format response
        response = BulkInventoryUpdateResponse(
            success=True,
            total_items=len(request.items),
            successful_updates=result.get("successful_updates", 0),
            failed_updates=result.get("failed_updates", 0),
            updated_items=format_inventory_changes(result.get("updated_items", [])),
            failed_items=result.get("failed_items", []),
            inventory_recommendations=result.get("recommendations", []),
            insights=result.get("insights", [])
        )
        
        logger.info(f"User {current_user.id} updated {len(request.items)} inventory items")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating inventory: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update inventory: {str(e)}"
        )


@router.post("/manual-entry", response_model=ManualFoodEntryResponse)
async def manual_food_entry(
    request: ManualFoodEntryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Log a manually entered food item (not from meal plan)
    
    This endpoint:
    1. Normalizes the food name using AI
    2. Parses quantity and unit
    3. Estimates macros from database or API
    4. Updates daily consumption totals
    5. Provides confidence score
    
    Useful for logging restaurant meals, snacks, or off-plan items.
    """
    try:
        # Initialize services
        tracking_agent = TrackingAgent(db, current_user.id)
        consumption_service = ConsumptionService(db)
        
        # Parse and normalize food item
        # This would call the item normalizer service
        from app.services.item_normalizer import IntelligentItemNormalizer
        normalizer = IntelligentItemNormalizer(db)
        
        normalized_result = normalizer.normalize_item(
            text_input=f"{request.quantity} {request.food_name}"
        )
        
        if not normalized_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not normalize food item"
            )
        
        normalized_item = normalized_result["normalized_items"][0]
        
        # Estimate macros (you would implement macro estimation logic here)
        # For now, using placeholder values
        estimated_macros = {
            "calories": 200,  # Would calculate based on item and quantity
            "protein_g": 15,
            "carbs_g": 20,
            "fat_g": 8,
            "fiber_g": 2
        }
        
        # Create a manual meal log entry
        from app.models.database import MealLog
        manual_log = MealLog(
            user_id=current_user.id,
            recipe_id=None,  # No recipe for manual entry
            meal_type=request.meal_type.value,
            planned_datetime=request.consumed_at,
            consumed_datetime=request.consumed_at,
            was_skipped=False,
            notes=request.notes,
            external_meal={
                "food_name": request.food_name,
                "normalized_name": normalized_item["canonical_name"],
                "quantity": request.quantity,
                "macros": estimated_macros
            }
        )
        
        db.add(manual_log)
        db.commit()
        
        # Update daily totals
        today_summary = consumption_service.get_today_summary(current_user.id)
        
        # Format response
        response = ManualFoodEntryResponse(
            success=True,
            food_name=request.food_name,
            normalized_name=normalized_item["canonical_name"],
            quantity_parsed=request.quantity,
            estimated_macros=format_macro_nutrients(estimated_macros),
            confidence_score=normalized_item.get("confidence", 0.8),
            meal_type=request.meal_type.value,
            consumed_at=request.consumed_at,
            updated_daily_totals=today_summary,
            recommendations=[
                "Consider adding this to your meal plan for better tracking",
                "Log portion sizes accurately for better insights"
            ]
        )
        
        logger.info(f"User {current_user.id} logged manual food entry: {request.food_name}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error with manual food entry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log manual food: {str(e)}"
        )


# ===== GET ENDPOINTS (QUERIES) =====

@router.get("/today", response_model=TodaySummaryResponse)
async def get_today_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get today's complete consumption summary
    
    Returns:
    - Meals planned, consumed, and skipped
    - Total calories and macros consumed
    - Remaining targets
    - Compliance rate
    - Detailed meal breakdown
    """
    try:
        # Initialize consumption service
        consumption_service = ConsumptionService(db)
        
        # Get today's summary
        result = consumption_service.get_today_summary(current_user.id)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch today's summary"
            )
        
        summary = result["summary"]
        
        # Format response
        response = TodaySummaryResponse(
            date=summary.get("date", datetime.utcnow().date().isoformat()),
            meals_planned=summary.get("meals_planned", 0),
            meals_consumed=summary.get("meals_consumed", 0),
            meals_skipped=summary.get("meals_skipped", 0),
            total_calories=summary.get("total_calories", 0),
            total_macros=format_macro_nutrients(summary.get("total_macros", {})),
            target_calories=summary.get("target_calories", 0),
            target_macros=format_macro_nutrients(summary.get("target_macros", {})),
            remaining_calories=summary.get("remaining_calories", 0),
            remaining_macros=format_macro_nutrients(summary.get("remaining_macros", {})),
            compliance_rate=summary.get("compliance_rate", 0),
            meal_details=summary.get("meal_details", [])
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching today's summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch summary: {str(e)}"
        )


@router.get("/history", response_model=ConsumptionHistoryResponse)
async def get_consumption_history(
    days: int = Query(7, ge=1, le=90, description="Number of days to retrieve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get historical consumption data
    
    Query Parameters:
    - days: Number of days of history (1-90, default 7)
    
    Returns consumption history with daily summaries and trends.
    """
    try:
        # Initialize consumption service
        consumption_service = ConsumptionService(db)
        
        # Get consumption history
        result = consumption_service.get_consumption_history(
            user_id=current_user.id,
            days=days
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch consumption history"
            )
        
        history = result["history"]
        
        # Format response
        response = ConsumptionHistoryResponse(
            period_days=days,
            start_date=history.get("start_date", ""),
            end_date=history.get("end_date", ""),
            total_meals_logged=history.get("total_meals_logged", 0),
            total_meals_skipped=history.get("total_meals_skipped", 0),
            average_compliance=history.get("average_compliance", 0),
            daily_summaries=history.get("daily_summaries", []),
            trends=history.get("trends", {})
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching consumption history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )


@router.get("/patterns", response_model=ConsumptionPatternsResponse)
async def get_consumption_patterns(
    days: int = Query(7, ge=7, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get consumption pattern analysis and insights
    
    Query Parameters:
    - days: Number of days to analyze (7-90, default 7)
    
    Returns:
    - Meal timing patterns
    - Skip frequency analysis
    - Portion preferences
    - Adherence trends
    - Personalized insights and recommendations
    """
    try:
        # Initialize consumption service
        consumption_service = ConsumptionService(db)
        
        # Get consumption analytics
        result = consumption_service.generate_consumption_analytics(
            user_id=current_user.id,
            days=days
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to generate consumption patterns"
            )
        
        analytics = result["analytics"]
        
        # Format meal timing patterns
        timing_patterns = []
        for pattern in analytics.get("meal_timing_patterns", []):
            timing_patterns.append({
                "meal_type": pattern["meal_type"],
                "average_time": pattern["average_time"],
                "frequency": pattern["frequency"],
                "skip_rate": pattern.get("skip_rate", 0)
            })
        
        # Format response
        response = ConsumptionPatternsResponse(
            analysis_period_days=days,
            meal_timing_patterns=timing_patterns,
            skip_frequency=analytics.get("skip_frequency", {}),
            portion_preferences=analytics.get("portion_preferences", {}),
            adherence_by_day=analytics.get("adherence_by_day", {}),
            adherence_by_meal=analytics.get("adherence_by_meal", {}),
            insights=analytics.get("insights", []),
            recommendations=analytics.get("recommendations", [])
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing consumption patterns: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze patterns: {str(e)}"
        )


@router.get("/inventory-status", response_model=InventoryStatusResponse)
async def get_inventory_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current inventory status with analytics
    
    Returns:
    - Total items count
    - Items by category
    - Overall stock level
    - Low stock and critical items
    - Expiring items
    - Overstocked items
    - Intelligent recommendations
    """
    try:
        # Initialize tracking agent
        tracking_agent = TrackingAgent(db, current_user.id)
        
        # Get inventory status
        result = tracking_agent.calculate_inventory_status()
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to calculate inventory status"
            )
        
        status_data = result["status"]
        
        # Format response
        response = InventoryStatusResponse(
            total_items=status_data.get("total_items", 0),
            items_by_category=status_data.get("items_by_category", {}),
            overall_stock_level=status_data.get("overall_stock_percentage", 0),
            low_stock_items=status_data.get("low_stock_items", []),
            critical_items=status_data.get("critical_items", []),
            expiring_soon=status_data.get("expiring_soon", []),
            overstocked_items=status_data.get("overstocked_items", []),
            recommendations=status_data.get("recommendations", [])
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching inventory status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch inventory status: {str(e)}"
        )


@router.get("/expiring-items", response_model=ExpiringItemsResponse)
async def get_expiring_items(
    days: int = Query(3, ge=1, le=14, description="Days threshold for expiry"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get items expiring within specified days with recipe suggestions
    
    Query Parameters:
    - days: Expiry threshold in days (1-14, default 3)
    
    Returns items expiring soon with:
    - Expiry urgency levels
    - Recipe suggestions to use them
    - Action recommendations
    """
    try:
        # Initialize tracking agent
        tracking_agent = TrackingAgent(db, current_user.id)
        
        # Get expiring items
        result = tracking_agent.check_expiring_items(days)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to check expiring items"
            )
        
        expiry_data = result["expiring_items"]
        
        # Format response
        response = ExpiringItemsResponse(
            total_expiring=expiry_data.get("total_count", 0),
            urgent_count=expiry_data.get("urgent_count", 0),
            high_priority_count=expiry_data.get("high_priority_count", 0),
            medium_priority_count=expiry_data.get("medium_priority_count", 0),
            items=expiry_data.get("items", []),
            action_recommendations=expiry_data.get("recommendations", [])
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching expiring items: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch expiring items: {str(e)}"
        )


@router.get("/restock-list", response_model=RestockListResponse)
async def get_restock_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get intelligent shopping/restock recommendations
    
    Returns:
    - Items that are low or out of stock
    - Priority levels (urgent, soon, routine)
    - Usage frequency data
    - Days until depletion estimates
    - Shopping strategy recommendations
    """
    try:
        # Initialize tracking agent
        tracking_agent = TrackingAgent(db, current_user.id)
        
        # Generate restock list
        result = tracking_agent.generate_restock_list()
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to generate restock list"
            )
        
        restock_data = result["restock_list"]
        
        # Format response
        response = RestockListResponse(
            total_items=restock_data.get("total_items", 0),
            urgent_items=restock_data.get("urgent", []),
            soon_items=restock_data.get("soon", []),
            routine_items=restock_data.get("routine", []),
            estimated_total_cost=restock_data.get("estimated_cost"),
            shopping_strategy=restock_data.get("shopping_strategy", [])
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating restock list: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate restock list: {str(e)}"
        )