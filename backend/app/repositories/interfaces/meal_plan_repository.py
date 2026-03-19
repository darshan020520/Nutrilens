"""
Meal Plan Repository Interface

Defines contract for meal plan data access.

COPY-PASTED QUERIES FROM:
- planning_agent.py:988-1021 (_save_meal_plan)
- meal_plan_service.py (various queries)
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime


class IMealPlanRepository(ABC):
    """
    Interface for meal plan data access.

    All database queries for MealPlan model go through this interface.
    """

    @abstractmethod
    async def get_by_id(self, plan_id: int) -> Optional[Any]:
        """
        Get meal plan by ID.

        Args:
            plan_id: Meal plan ID

        Returns:
            MealPlan if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_active_plan(self, user_id: int) -> Optional[Any]:
        """
        Get active meal plan for user.

        Args:
            user_id: User ID

        Returns:
            Active MealPlan if exists, None otherwise
        """
        pass

    @abstractmethod
    async def deactivate_active_plans(self, user_id: int) -> None:
        """
        Deactivate all active plans for user.

        COPY-PASTED FROM: planning_agent.py:992-995

        Args:
            user_id: User ID
        """
        pass

    @abstractmethod
    async def create(
        self,
        user_id: int,
        week_start_date: datetime,
        plan_data: Dict,
        grocery_list: Dict,
        total_calories: float,
        avg_macros: Dict,
        is_active: bool = True
    ) -> Any:
        """
        Create new meal plan.

        COPY-PASTED FROM: planning_agent.py:1000-1016

        Args:
            user_id: User ID
            week_start_date: Start date of the plan
            plan_data: Weekly plan data (JSON)
            grocery_list: Grocery list data (JSON)
            total_calories: Total calories for the week
            avg_macros: Average macros (JSON)
            is_active: Whether plan is active

        Returns:
            Created MealPlan
        """
        pass

    @abstractmethod
    async def update(self, plan_id: int, updates: Dict[str, Any]) -> Any:
        """
        Update meal plan.

        Args:
            plan_id: Meal plan ID
            updates: Fields to update

        Returns:
            Updated MealPlan
        """
        pass

    @abstractmethod
    async def delete(self, plan_id: int) -> bool:
        """
        Delete meal plan.

        Args:
            plan_id: Meal plan ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def get_all_for_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0
    ) -> List[Any]:
        """
        Get all meal plans for user with pagination.

        Args:
            user_id: User ID
            limit: Maximum number of plans to return
            offset: Number of plans to skip

        Returns:
            List of MealPlans
        """
        pass

    @abstractmethod
    async def commit(self) -> None:
        """
        Commit current database transaction.

        Used for explicit transaction control.
        """
        pass
