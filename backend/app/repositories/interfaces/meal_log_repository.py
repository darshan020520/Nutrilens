"""
Meal Log Repository Interface

Defines contract for meal log data access.

COPY-PASTED QUERIES FROM:
- planning_agent.py:1023-1097 (_create_meal_logs)
- tracking_agent.py (various meal log queries)
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime


class IMealLogRepository(ABC):
    """
    Interface for meal log data access.

    All database queries for MealLog model go through this interface.
    """

    @abstractmethod
    async def get_by_id(self, log_id: int) -> Optional[Any]:
        """
        Get meal log by ID.

        Args:
            log_id: Meal log ID

        Returns:
            MealLog if found, None otherwise
        """
        pass

    @abstractmethod
    async def create_bulk(
        self,
        user_id: int,
        meal_plan_id: int,
        meal_plan_data: Dict,
        start_date: datetime,
        user_meal_windows: List[Dict]
    ) -> int:
        """
        Create multiple meal logs for a meal plan.

        COPY-PASTED FROM: planning_agent.py:1023-1097

        Args:
            user_id: User ID
            meal_plan_id: Meal plan ID to link logs to
            meal_plan_data: Meal plan week_plan data
            start_date: Start date of the meal plan
            user_meal_windows: User's meal timing windows

        Returns:
            Number of logs created
        """
        pass

    @abstractmethod
    async def get_by_user_and_date_range(
        self,
        user_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        was_skipped: Optional[bool] = None
    ) -> List[Any]:
        """
        Get meal logs for user within date range.

        COPY-PASTED FROM: planning_agent.py:1108-1113

        Args:
            user_id: User ID
            start_datetime: Start of date range
            end_datetime: End of date range
            was_skipped: Filter by skipped status (None = all)

        Returns:
            List of MealLogs
        """
        pass

    @abstractmethod
    async def update(self, log_id: int, updates: Dict[str, Any]) -> Any:
        """
        Update meal log.

        Args:
            log_id: Meal log ID
            updates: Fields to update

        Returns:
            Updated MealLog
        """
        pass

    @abstractmethod
    async def delete(self, log_id: int) -> bool:
        """
        Delete meal log.

        Args:
            log_id: Meal log ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def get_pending_meal(
        self,
        user_id: int,
        meal_type: str
    ) -> Optional[Any]:
        """
        Get pending meal log (not consumed, not skipped) for user by meal type.

        Args:
            user_id: User ID
            meal_type: Meal type (breakfast, lunch, dinner, snack)

        Returns:
            Pending MealLog if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_plan_day_meal(
        self,
        meal_plan_id: int,
        day_index: int,
        meal_type: str
    ) -> Optional[Any]:
        """
        Get meal log by meal plan, day index, and meal type.

        Args:
            meal_plan_id: Meal plan ID
            day_index: Day index (0-6)
            meal_type: Meal type

        Returns:
            MealLog if found, None otherwise
        """
        pass

    @abstractmethod
    async def update_recipe(
        self,
        log_id: int,
        recipe_id: int,
        planned_datetime: datetime
    ) -> None:
        """
        Update meal log with new recipe and planned datetime.

        Args:
            log_id: Meal log ID
            recipe_id: New recipe ID
            planned_datetime: New planned datetime
        """
        pass

    @abstractmethod
    async def create_single(
        self,
        user_id: int,
        recipe_id: int,
        meal_type: str,
        planned_datetime: datetime,
        meal_plan_id: int,
        day_index: int
    ) -> Any:
        """
        Create single meal log entry.

        Args:
            user_id: User ID
            recipe_id: Recipe ID
            meal_type: Meal type
            planned_datetime: Planned datetime
            meal_plan_id: Meal plan ID
            day_index: Day index

        Returns:
            Created MealLog
        """
        pass

    @abstractmethod
    async def get_by_plan_and_date_range(
        self,
        user_id: int,
        meal_plan_id: int,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[Any]:
        """
        Get meal logs for a specific meal plan within date range.

        Used for status enrichment in meal plan views.
        Source: meal_plan.py:116-133

        Args:
            user_id: User ID
            meal_plan_id: Meal plan ID
            start_datetime: Start of date range
            end_datetime: End of date range

        Returns:
            List of MealLogs
        """
        pass

    @abstractmethod
    async def get_upcoming_meals_for_today(
        self,
        user_id: int,
        current_datetime: datetime
    ) -> List[Any]:
        """
        Get upcoming meals for today (not consumed, not skipped, planned after current time).

        Domain operation for finding next meals to consume.
        Used by: MealPlanServiceV2.get_next_meal()
        Replaces: dashboard_orchestrator.py:220-233 (direct query)

        Args:
            user_id: User ID
            current_datetime: Current datetime to compare against

        Returns:
            List of MealLog entities ordered by planned_datetime
        """
        pass

    @abstractmethod
    async def delete_future_orphan_logs(
        self,
        user_id: int,
        cutoff_datetime: datetime
    ) -> int:
        """
        Delete unresolved meal logs from inactive plans that are scheduled
        on or after cutoff_datetime.

        "Unresolved" = consumed_datetime IS NULL AND was_skipped = False.
        These are phantom future slots left behind when the user generated a
        new plan before finishing the previous one. Past unresolved rows
        (genuine misses) are intentionally preserved for history accuracy.

        Args:
            user_id: User ID
            cutoff_datetime: Delete orphan logs with planned_datetime >= this value.
                             Should be now_ist_naive() captured just before
                             deactivating the old plans.

        Returns:
            Number of logs deleted
        """
        pass

    @abstractmethod
    async def get_upcoming_meals_in_time_window(
        self,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[Any]:
        """
        Get upcoming meals in a specific time window for meal reminders.

        Returns meals that:
        - Are planned between start_datetime and end_datetime
        - Have not been consumed (consumed_datetime is None)
        - Have not been skipped (was_skipped = False)

        Uses joinedload for user and recipe to prevent N+1 queries.
        Only returns meals for active users.

        Used by: NotificationWorker for 30-minute meal reminders

        Args:
            start_datetime: Start of time window
            end_datetime: End of time window

        Returns:
            List of MealLog entities with user and recipe eagerly loaded
        """
        pass
