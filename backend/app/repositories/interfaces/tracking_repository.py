"""
Tracking Repository Interface

Defines data access operations for meal logs and tracking functionality.
All tracking-related database queries should go through this interface.
"""

from abc import abstractmethod
from datetime import datetime, date
from typing import Optional, List, Tuple
from app.repositories.interfaces.base_repository import IRepository
from app.models.database import MealLog


class ITrackingRepository(IRepository[MealLog]):
    """
    Interface for tracking data access operations.

    Responsibilities:
    - CRUD operations for meal logs
    - Date-based queries for consumption history
    - Status-based queries (consumed, skipped, pending)
    - Analytics queries for adherence and patterns
    - Meal logging operations (mark consumed, skipped)

    This is a DATA ACCESS layer - NO business logic here.
    """

    # =========================================================================
    # BASIC CRUD OPERATIONS (extend base repository)
    # =========================================================================

    @abstractmethod
    async def get_by_id(self, meal_log_id: int, user_id: int) -> Optional[MealLog]:
        """
        Get meal log by ID with user validation.

        Args:
            meal_log_id: ID of the meal log
            user_id: User ID for ownership validation

        Returns:
            MealLog if found and belongs to user, None otherwise
        """
        pass

    @abstractmethod
    async def get_all_for_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[MealLog]:
        """
        Get all meal logs for a user with pagination.

        Args:
            user_id: User ID
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of meal logs ordered by planned_datetime DESC
        """
        pass

    @abstractmethod
    async def create(self, meal_log: MealLog) -> MealLog:
        """
        Create new meal log.

        Args:
            meal_log: MealLog entity to create

        Returns:
            Created meal log with ID populated
        """
        pass

    @abstractmethod
    async def update(self, meal_log: MealLog) -> MealLog:
        """
        Update existing meal log.

        Args:
            meal_log: MealLog entity to update (must have ID)

        Returns:
            Updated meal log
        """
        pass

    @abstractmethod
    async def delete(self, meal_log_id: int, user_id: int) -> bool:
        """
        Delete meal log by ID with user validation.

        Args:
            meal_log_id: ID of meal log to delete
            user_id: User ID for ownership validation

        Returns:
            True if deleted, False if not found or unauthorized
        """
        pass

    # =========================================================================
    # DATE-BASED QUERIES
    # =========================================================================

    @abstractmethod
    async def get_by_date(
        self,
        user_id: int,
        target_date: date
    ) -> List[MealLog]:
        """
        Get all meal logs for a specific date.

        Args:
            user_id: User ID
            target_date: Date to query

        Returns:
            List of meal logs for that date, ordered by planned_datetime
        """
        pass

    @abstractmethod
    async def get_by_date_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:
        """
        Get meal logs within a date range (inclusive).

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of meal logs within range, ordered by planned_datetime
        """
        pass

    @abstractmethod
    async def get_todays_meals(self, user_id: int) -> List[MealLog]:
        """
        Get all meal logs for today.

        Args:
            user_id: User ID

        Returns:
            List of today's meal logs, ordered by planned_datetime
        """
        pass

    @abstractmethod
    async def get_upcoming_meals(
        self,
        user_id: int,
        days: int = 7
    ) -> List[MealLog]:
        """
        Get upcoming meal logs (future planned meals).

        Args:
            user_id: User ID
            days: Number of days ahead to look (default 7)

        Returns:
            List of future meal logs, ordered by planned_datetime
        """
        pass

    # =========================================================================
    # STATUS-BASED QUERIES
    # =========================================================================

    @abstractmethod
    async def get_consumed_meals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:
        """
        Get meals that have been consumed (consumed_datetime is not null).

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of consumed meal logs
        """
        pass

    @abstractmethod
    async def get_skipped_meals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:
        """
        Get meals that have been skipped (was_skipped = True).

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of skipped meal logs
        """
        pass

    @abstractmethod
    async def get_pending_meals(
        self,
        user_id: int,
        target_date: date
    ) -> List[MealLog]:
        """
        Get meals that are pending (not consumed and not skipped).

        Args:
            user_id: User ID
            target_date: Date to check

        Returns:
            List of pending meal logs for that date
        """
        pass

    @abstractmethod
    async def get_external_meals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:
        """
        Get external meals (meals with external_meal JSON data).

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of external meal logs
        """
        pass

    @abstractmethod
    async def get_meals_by_recipe(
        self,
        user_id: int,
        recipe_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:
        """
        Get meal logs for a specific recipe.

        Args:
            user_id: User ID
            recipe_id: Recipe ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of meal logs for that recipe
        """
        pass

    # =========================================================================
    # MEAL LOGGING OPERATIONS
    # =========================================================================

    @abstractmethod
    async def mark_as_consumed(
        self,
        meal_log_id: int,
        user_id: int,
        consumed_at: datetime,
        portion_multiplier: float,
        notes: Optional[str] = None
    ) -> MealLog:
        """
        Mark meal log as consumed.

        Updates:
        - consumed_datetime
        - portion_multiplier
        - notes (if provided)

        Args:
            meal_log_id: ID of meal log
            user_id: User ID for validation
            consumed_at: Timestamp when consumed
            portion_multiplier: Portion size multiplier
            notes: Optional consumption notes

        Returns:
            Updated meal log

        Raises:
            ValueError: If meal log not found or already consumed/skipped
        """
        pass

    @abstractmethod
    async def mark_as_skipped(
        self,
        meal_log_id: int,
        user_id: int,
        reason: Optional[str] = None
    ) -> MealLog:
        """
        Mark meal log as skipped.

        Updates:
        - was_skipped = True
        - skip_reason (if provided)

        Args:
            meal_log_id: ID of meal log
            user_id: User ID for validation
            reason: Optional skip reason

        Returns:
            Updated meal log

        Raises:
            ValueError: If meal log not found or already consumed/skipped
        """
        pass

    @abstractmethod
    async def create_external_meal_log(
        self,
        user_id: int,
        meal_type: str,
        consumed_at: datetime,
        external_meal_data: dict,
        notes: Optional[str] = None
    ) -> MealLog:
        """
        Create a new meal log for an external meal (restaurant, eating out).

        Creates meal log with:
        - recipe_id = None
        - consumed_datetime = consumed_at
        - external_meal = external_meal_data (JSON)
        - planned_datetime = consumed_at
        - was_skipped = False

        Args:
            user_id: User ID
            meal_type: Meal type (breakfast, lunch, dinner, snack)
            consumed_at: When the meal was consumed
            external_meal_data: Nutrition data as dict
            notes: Optional notes

        Returns:
            Created meal log
        """
        pass

    @abstractmethod
    async def replace_planned_with_external(
        self,
        meal_log_id: int,
        user_id: int,
        consumed_at: datetime,
        external_meal_data: dict,
        notes: Optional[str] = None
    ) -> MealLog:
        """
        Replace a planned meal with an external meal.

        Updates existing meal log:
        - recipe_id = None (clear recipe link)
        - consumed_datetime = consumed_at
        - external_meal = external_meal_data
        - notes (if provided)

        Args:
            meal_log_id: ID of planned meal to replace
            user_id: User ID for validation
            consumed_at: When external meal was consumed
            external_meal_data: Nutrition data as dict
            notes: Optional notes

        Returns:
            Updated meal log

        Raises:
            ValueError: If meal log not found or already consumed
        """
        pass

    # =========================================================================
    # ANALYTICS QUERIES
    # =========================================================================

    @abstractmethod
    async def count_meals_by_status(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> dict:
        """
        Count meals by status (consumed, skipped, pending).

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Dict with counts: {
                "total": 21,
                "consumed": 15,
                "skipped": 3,
                "pending": 3
            }
        """
        pass

    @abstractmethod
    async def get_adherence_rate(
        self,
        user_id: int,
        days: int
    ) -> float:
        """
        Calculate adherence rate (consumed / total planned meals).

        Adherence = consumed_meals / (consumed_meals + skipped_meals)

        Args:
            user_id: User ID
            days: Number of days to look back

        Returns:
            Adherence rate as float (0.0 to 1.0)
            Returns 1.0 if no meals logged
        """
        pass

    @abstractmethod
    async def get_meal_timing_patterns(
        self,
        user_id: int,
        days: int
    ) -> List[dict]:
        """
        Get average consumption times by meal type.

        Analyzes consumed meals to find typical timing patterns.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            List of dicts: [
                {
                    "meal_type": "breakfast",
                    "average_time": "08:30",
                    "count": 15,
                    "skip_rate": 0.1
                },
                ...
            ]
        """
        pass

    @abstractmethod
    async def get_skip_frequency_by_meal_type(
        self,
        user_id: int,
        days: int
    ) -> dict:
        """
        Get skip frequency for each meal type.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict mapping meal type to skip rate: {
                "breakfast": 0.15,
                "lunch": 0.05,
                "dinner": 0.08,
                "snack": 0.20
            }
        """
        pass

    @abstractmethod
    async def get_portion_multiplier_stats(
        self,
        user_id: int,
        days: int
    ) -> dict:
        """
        Get portion size statistics.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with stats: {
                "average": 1.05,
                "median": 1.0,
                "min": 0.5,
                "max": 1.5,
                "by_meal_type": {
                    "breakfast": 0.9,
                    "lunch": 1.1,
                    ...
                }
            }
        """
        pass

    @abstractmethod
    async def get_most_skipped_recipes(
        self,
        user_id: int,
        days: int,
        limit: int = 10
    ) -> List[Tuple[int, str, int, float]]:
        """
        Get recipes with highest skip rates.

        Args:
            user_id: User ID
            days: Number of days to analyze
            limit: Maximum number of recipes to return

        Returns:
            List of tuples: (recipe_id, recipe_name, skip_count, skip_rate)
            Example: [(5, "Oatmeal", 8, 0.4), ...]
        """
        pass

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    @abstractmethod
    async def bulk_create_meal_logs(
        self,
        meal_logs: List[MealLog]
    ) -> List[MealLog]:
        """
        Create multiple meal logs in one transaction.

        Used when generating meal plans with multiple days/meals.

        Args:
            meal_logs: List of MealLog entities to create

        Returns:
            List of created meal logs with IDs
        """
        pass

    @abstractmethod
    async def bulk_delete_meal_logs(
        self,
        meal_log_ids: List[int],
        user_id: int
    ) -> int:
        """
        Delete multiple meal logs in one transaction.

        Args:
            meal_log_ids: List of meal log IDs to delete
            user_id: User ID for validation

        Returns:
            Number of meal logs deleted
        """
        pass