"""
Dashboard API Endpoints
Provides aggregated data for the Home Dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from app.services.consumption_services import ConsumptionService
from app.services.inventory_service import IntelligentInventoryService
from app.agents.tracking_agent import TrackingAgent


from app.models.database import (get_db,
    User, UserProfile, UserGoal, UserPath, MealPlan, 
    MealLog, UserInventory, Item
)
from app.services.auth import get_current_user_dependency as get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# ===== RESPONSE SCHEMAS =====

class MealsCardData(BaseModel):
    """Today's Meals Card"""
    meals_planned: int
    meals_consumed: int
    meals_skipped: int
    next_meal: Optional[str] = None
    next_meal_time: Optional[str] = None

class MacrosCardData(BaseModel):
    """Macros Progress Card"""
    calories_consumed: float
    calories_target: float
    calories_percentage: float
    protein_consumed: float
    protein_target: float
    protein_percentage: float
    carbs_consumed: float
    carbs_target: float
    carbs_percentage: float
    fat_consumed: float
    fat_target: float
    fat_percentage: float

class InventoryCardData(BaseModel):
    """Inventory Status Card"""
    expiring_soon_count: int
    low_stock_count: int
    out_of_stock_count: int
    total_items: int

class GoalCardData(BaseModel):
    """Goal Progress Card"""
    goal_type: str
    current_weight: float
    target_weight: float
    weight_change: float
    current_streak: int
    goal_progress_percentage: float

class DashboardSummary(BaseModel):
    """Complete Dashboard Summary"""
    meals_card: MealsCardData
    macros_card: MacrosCardData
    inventory_card: InventoryCardData
    goal_card: GoalCardData

class ActivityItem(BaseModel):
    """Recent Activity Item"""
    id: int
    type: str
    description: str
    timestamp: datetime
    icon: str

class RecentActivityResponse(BaseModel):
    """Recent Activity Feed"""
    activities: List[ActivityItem]
    total_count: int


# ===== HELPER FUNCTIONS =====

def calculate_streak(db: Session, user_id: int) -> int:
    """Calculate current streak of consecutive days with logged meals"""
    today = date.today()
    streak = 0
    
    for days_ago in range(30):  # Check last 30 days max
        check_date = today - timedelta(days=days_ago)
        
        # Check if user logged at least one meal on this day
        meals_logged = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == check_date,
                MealLog.consumed_datetime.isnot(None)
            )
        ).count()
        
        if meals_logged > 0:
            streak += 1
        else:
            break
    
    return streak


def find_next_meal(meal_logs: List[MealLog]) -> tuple:
    """Find next upcoming meal from today's logs"""
    now = datetime.now()
    
    upcoming = [
        m for m in meal_logs 
        if m.consumed_datetime is None 
        and not m.was_skipped 
        and m.planned_datetime > now
    ]
    
    if upcoming:
        upcoming.sort(key=lambda x: x.planned_datetime)
        next_meal = upcoming[0]
        return (
            next_meal.meal_type.capitalize(),
            next_meal.planned_datetime.strftime("%I:%M %p")
        )
    
    return (None, None)


# ===== ENDPOINTS =====

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete dashboard summary with all 4 card data
    
    Properly delegates to existing services with correct data mapping
    """
    try:
        user_id = current_user.id
        
        # Initialize services
        consumption_service = ConsumptionService(db)
        tracking_agent = TrackingAgent(db, user_id)
        
        # ===== 1. TODAY'S MEALS CARD =====
        today_result = consumption_service.get_today_summary(user_id)

        print("print todays meals", today_result)
        
        if not today_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get today's summary"
            )
        
        # Get today's meal logs for next meal calculation
        today = date.today()
        meal_logs_today = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == today
            )
        ).all()
        
        next_meal, next_meal_time = find_next_meal(meal_logs_today)
        
        meals_card = MealsCardData(
            meals_planned=today_result.get("meals_planned", 0),
            meals_consumed=today_result.get("meals_consumed", 0),
            meals_skipped=today_result.get("meals_skipped", 0),
            next_meal=next_meal,
            next_meal_time=next_meal_time
        )
        
        # ===== 2. MACROS PROGRESS CARD =====
        # Extract from today_result which has all the data
        total_macros = today_result.get("total_macros", {})
        targets = today_result.get("targets", {})
        
        # Calculate percentages safely
        def safe_percentage(consumed: float, target: float) -> float:
            return round((consumed / target * 100), 1) if target > 0 else 0
        
        macros_card = MacrosCardData(
            calories_consumed=round(today_result.get("total_calories", 0), 1),
            calories_target=round(targets.get("calories", 2000), 1),
            calories_percentage=safe_percentage(
                today_result.get("total_calories", 0),
                targets.get("calories", 2000)
            ),
            protein_consumed=round(total_macros.get("protein_g", 0), 1),
            protein_target=round(targets.get("protein_g", 150), 1),
            protein_percentage=safe_percentage(
                total_macros.get("protein_g", 0),
                targets.get("protein_g", 150)
            ),
            carbs_consumed=round(total_macros.get("carbs_g", 0), 1),
            carbs_target=round(targets.get("carbs_g", 200), 1),
            carbs_percentage=safe_percentage(
                total_macros.get("carbs_g", 0),
                targets.get("carbs_g", 200)
            ),
            fat_consumed=round(total_macros.get("fat_g", 0), 1),
            fat_target=round(targets.get("fat_g", 67), 1),
            fat_percentage=safe_percentage(
                total_macros.get("fat_g", 0),
                targets.get("fat_g", 67)
            )
        )
        
        # ===== 3. INVENTORY STATUS CARD =====
        # Use IntelligentInventoryService for accurate inventory counts
        inventory_service = IntelligentInventoryService(db)
        inventory_status = inventory_service.get_inventory_status(user_id)

        # Get expiring items count from inventory status
        expiring_count = len(inventory_status.expiring_soon)

        # Get low stock count from inventory status
        low_stock_count = len(inventory_status.low_stock)

        # Get out of stock count - items with quantity = 0
        out_of_stock = db.query(UserInventory).filter(
            and_(
                UserInventory.user_id == user_id,
                UserInventory.quantity_grams == 0
            )
        ).count()

        inventory_card = InventoryCardData(
            expiring_soon_count=expiring_count,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock,
            total_items=inventory_status.total_items
        )
        print("inventory_card", inventory_card)
        
        # ===== 4. GOAL PROGRESS CARD =====
        # Get user profile and goal
        user_profile = db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        user_goal = db.query(UserGoal).filter(
            UserGoal.user_id == user_id
        ).first()
        
        # Calculate streak
        current_streak = calculate_streak(db, user_id)
        
        # Extract goal data
        current_weight = user_profile.weight_kg if user_profile else 70.0
        target_weight = getattr(user_goal, 'target_weight', None) if user_goal else None
        if target_weight is None:
            target_weight = current_weight
        goal_type = user_goal.goal_type if user_goal else "maintain_weight"

        # Calculate progress
        weight_change = target_weight - current_weight
        
        # Progress percentage calculation
        if goal_type in ["lose_weight", "LOSE_WEIGHT", "fat_loss", "FAT_LOSS"]:
            # For weight loss: progress = how much already lost / how much to lose
            starting_weight = getattr(user_goal, 'starting_weight', current_weight) if user_goal else current_weight
            total_to_lose = starting_weight - target_weight
            already_lost = starting_weight - current_weight
            progress_pct = (already_lost / total_to_lose * 100) if total_to_lose > 0 else 0
        elif goal_type in ["gain_weight", "GAIN_WEIGHT", "muscle_gain", "MUSCLE_GAIN"]:
            # For weight gain: progress = how much already gained / how much to gain
            starting_weight = getattr(user_goal, 'starting_weight', current_weight) if user_goal else current_weight
            total_to_gain = target_weight - starting_weight
            already_gained = current_weight - starting_weight
            progress_pct = (already_gained / total_to_gain * 100) if total_to_gain > 0 else 0
        else:
            # Maintain weight
            progress_pct = 100.0 if abs(current_weight - target_weight) < 2 else 0
        
        goal_card = GoalCardData(
            goal_type=goal_type,
            current_weight=round(current_weight, 1),
            target_weight=round(target_weight, 1),
            weight_change=round(weight_change, 1),
            current_streak=current_streak,
            goal_progress_percentage=round(max(0, min(100, progress_pct)), 1)
        )
        
        # ===== RETURN COMPLETE SUMMARY =====
        return DashboardSummary(
            meals_card=meals_card,
            macros_card=macros_card,
            inventory_card=inventory_card,
            goal_card=goal_card
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating dashboard summary: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate dashboard summary: {str(e)}"
        )


@router.get("/recent-activity", response_model=RecentActivityResponse)
async def get_recent_activity(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recent activity feed
    
    Uses meal logs and meal plans to show recent activities
    """
    try:
        activities = []
        
        # Get recent meal logs (consumed and skipped)
        recent_meals = db.query(MealLog).filter(
            MealLog.user_id == current_user.id
        ).order_by(
            desc(MealLog.planned_datetime)
        ).limit(limit * 2).all() 
        
        print("recent meals", recent_meals) # Get more than needed
        
        for meal in recent_meals:
            print("recent meals", meal)
            if meal.consumed_datetime:
                activities.append(ActivityItem(
                    id=meal.id,
                    type="meal_logged",
                    description=f"{meal.meal_type.capitalize()} logged - {meal.recipe.title if meal.recipe else 'External meal'}",
                    timestamp=meal.consumed_datetime,
                    icon="🍽️"
                ))
            elif meal.was_skipped and meal.planned_datetime:
                activities.append(ActivityItem(
                    id=meal.id,
                    type="meal_skipped",
                    description=f"{meal.meal_type.capitalize()} skipped",
                    timestamp=meal.planned_datetime,
                    icon="⏭️"
                ))
        
        # Get recent meal plans
        recent_plans = db.query(MealPlan).filter(
            MealPlan.user_id == current_user.id
        ).order_by(
            desc(MealPlan.created_at)
        ).limit(2).all()
        
        for plan in recent_plans:
            activities.append(ActivityItem(
                id=plan.id,
                type="plan_generated",
                description=f"New meal plan generated for {plan.week_start_date.strftime('%b %d')}",
                timestamp=plan.created_at,
                icon="📋"
            ))
        
        # Sort all activities by timestamp
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Return only the requested limit
        activities = activities[:limit]
        
        return RecentActivityResponse(
            activities=activities,
            total_count=len(activities)
        )
        
    except Exception as e:
        logger.error(f"Error fetching recent activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent activity: {str(e)}"
        )