"""
Dashboard API Endpoints V2 - Clean Architecture

Provides aggregated data for the Home Dashboard.

MIGRATED FROM: dashboard.py
USES: Clean architecture with DashboardOrchestrator
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.models.database import get_db, User
from app.services.auth import get_current_user_dependency as get_current_user
from app.orchestrators.dashboard_orchestrator import DashboardOrchestrator
from app.dependencies import get_dashboard_orchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard/v2", tags=["dashboard-v2"])


# ===== RESPONSE SCHEMAS (IDENTICAL TO V1) =====

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


# ===== ENDPOINTS =====

@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    orchestrator: DashboardOrchestrator = Depends(get_dashboard_orchestrator)
):
    """
    Get complete dashboard summary with all 4 card data.

    SOURCE: dashboard.py:140-316
    MIGRATED TO: Clean architecture with DashboardOrchestrator

    Returns:
        DashboardSummary with:
        - meals_card: Today's meal status
        - macros_card: Macro nutrient progress
        - inventory_card: Inventory status counts
        - goal_card: Goal progress and streak
    """
    try:
        logger.info(f"GET /dashboard/v2/summary - User {current_user.id}")

        # Orchestrator coordinates all services and returns aggregated data
        summary = await orchestrator.get_dashboard_summary(current_user.id)

        return DashboardSummary(**summary)

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
    limit: int = Query(default=5, ge=1, le=50, description="Maximum number of activities to return"),
    current_user: User = Depends(get_current_user),
    orchestrator: DashboardOrchestrator = Depends(get_dashboard_orchestrator)
):
    """
    Get recent activity feed.

    SOURCE: dashboard.py:319-393
    MIGRATED TO: Clean architecture with ActivityRepository

    Args:
        limit: Maximum number of activities (1-50, default 5)

    Returns:
        RecentActivityResponse with activities list and count
    """
    try:
        logger.info(f"GET /dashboard/v2/recent-activity - User {current_user.id}, limit={limit}")

        # Orchestrator uses ActivityRepository to get aggregated activity
        activity = await orchestrator.get_recent_activity(
            user_id=current_user.id,
            limit=limit
        )

        return RecentActivityResponse(**activity)

    except Exception as e:
        logger.error(f"Error fetching recent activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent activity: {str(e)}"
        )