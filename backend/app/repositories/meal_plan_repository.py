"""
Meal Plan Repository Implementation

PostgreSQL implementation of meal plan data access.

ALL CODE COPY-PASTED FROM planning_agent.py - ZERO LOGIC CHANGES
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.interfaces.meal_plan_repository import IMealPlanRepository
from app.models.database import MealPlan
from app.schemas.meal_plan import MealPlanResponse

logger = logging.getLogger(__name__)


class MealPlanRepository(IMealPlanRepository):
    """
    PostgreSQL implementation of meal plan repository.

    COPY-PASTED QUERIES FROM: planning_agent.py:988-1021
    """

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    async def get_by_id(self, plan_id: int) -> Optional[MealPlan]:
        """
        Get meal plan by ID.

        Args:
            plan_id: Meal plan ID

        Returns:
            MealPlan if found, None otherwise
        """
        return self.db.query(MealPlan).filter(MealPlan.id == plan_id).first()

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        """
        Get active meal plan for user.

        Args:
            user_id: User ID

        Returns:
            Active MealPlan if exists, None otherwise
        """
        return self.db.query(MealPlan).filter_by(
            user_id=user_id,
            is_active=True
        ).first()

    async def deactivate_active_plans(self, user_id: int) -> None:
        """
        Deactivate all active plans for user.

        EXACT COPY-PASTE FROM: planning_agent.py:992-995

        Args:
            user_id: User ID
        """
        # COPY-PASTED FROM planning_agent.py:992-995 - NO CHANGES
        self.db.query(MealPlan).filter_by(
            user_id=user_id,
            is_active=True
        ).update({'is_active': False})
        # Note: commit is done by caller (service/orchestrator)

    async def create(
        self,
        user_id: int,
        week_start_date: datetime,
        plan_data: Dict,
        grocery_list: Dict,
        total_calories: float,
        avg_macros: Dict,
        is_active: bool = True
    ) -> MealPlanResponse:
        """
        Create new meal plan.

        EXACT COPY-PASTE FROM: planning_agent.py:1000-1016

        Args:
            user_id: User ID
            week_start_date: Start date of the plan
            plan_data: Weekly plan data (JSON)
            grocery_list: Grocery list data (JSON)
            total_calories: Total calories for the week
            avg_macros: Average macros (JSON)
            is_active: Whether plan is active

        Returns:
            Created MealPlan as MealPlanResponse
        """
        try:
            # COPY-PASTED FROM planning_agent.py:1000-1008 - NO CHANGES
            new_plan = MealPlan(
                user_id=user_id,
                week_start_date=week_start_date,
                plan_data=plan_data,
                grocery_list=grocery_list,
                total_calories=total_calories,
                avg_macros=avg_macros,
                is_active=is_active
            )

            # COPY-PASTED FROM planning_agent.py:1010 - NO CHANGES
            new_plan.updated_at = datetime.now()

            # COPY-PASTED FROM planning_agent.py:1013-1014 - NO CHANGES
            self.db.add(new_plan)
            self.db.commit()

            # COPY-PASTED FROM planning_agent.py:1016 - NO CHANGES
            return MealPlanResponse.model_validate(new_plan)

        except Exception as e:
            # COPY-PASTED FROM planning_agent.py:1019-1021 - NO CHANGES
            self.db.rollback()
            logger.error(f"Error saving meal plan: {str(e)}")
            raise

    async def update(self, plan_id: int, updates: Dict[str, Any]) -> MealPlan:
        """
        Update meal plan.

        Args:
            plan_id: Meal plan ID
            updates: Fields to update

        Returns:
            Updated MealPlan
        """
        plan = self.db.query(MealPlan).filter(MealPlan.id == plan_id).first()

        if not plan:
            raise ValueError(f"MealPlan {plan_id} not found")

        for key, value in updates.items():
            if hasattr(plan, key):
                setattr(plan, key, value)

        plan.updated_at = datetime.now()
        self.db.commit()
        self.db.refresh(plan)

        return plan

    async def delete(self, plan_id: int) -> bool:
        """
        Delete meal plan.

        Args:
            plan_id: Meal plan ID

        Returns:
            True if deleted, False if not found
        """
        plan = self.db.query(MealPlan).filter(MealPlan.id == plan_id).first()

        if not plan:
            return False

        self.db.delete(plan)
        self.db.commit()

        return True

    async def get_all_for_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> List[MealPlan]:
        """
        Get all meal plans for user with pagination.

        Args:
            user_id: User ID
            limit: Maximum number of plans to return
            offset: Number of plans to skip

        Returns:
            List of MealPlans
        """
        return self.db.query(MealPlan).filter(
            MealPlan.user_id == user_id
        ).order_by(
            MealPlan.week_start_date.desc()
        ).limit(limit).offset(offset).all()

    async def commit(self) -> None:
        """
        Commit current database transaction.

        Used for explicit transaction control.
        """
        self.db.commit()
