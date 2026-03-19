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

    @abstractmethod
    async def get_by_id(self, meal_log_id: int, user_id: int) -> Optional[MealLog]:

        pass

    @abstractmethod
    async def get_all_for_user(
        self,
        user_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def create(self, meal_log: MealLog) -> MealLog:

        pass

    @abstractmethod
    async def update(self, meal_log: MealLog) -> MealLog:

        pass

    @abstractmethod
    async def delete(self, meal_log_id: int, user_id: int) -> bool:

        pass

    @abstractmethod
    async def get_by_date(
        self,
        user_id: int,
        target_date: date,
        active_plans_only: bool = False
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def get_by_date_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def get_todays_meals(self, user_id: int) -> List[MealLog]:

        pass

    @abstractmethod
    async def get_upcoming_meals(
        self,
        user_id: int,
        days: int = 7
    ) -> List[MealLog]:

        pass


    @abstractmethod
    async def get_consumed_meals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def get_skipped_meals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def get_pending_meals(
        self,
        user_id: int,
        target_date: date
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def get_external_meals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def get_meals_by_recipe(
        self,
        user_id: int,
        recipe_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:

        pass


    @abstractmethod
    async def mark_as_consumed(
        self,
        meal_log_id: int,
        user_id: int,
        consumed_at: datetime,
        portion_multiplier: float,
        notes: Optional[str] = None
    ) -> MealLog:

        pass

    @abstractmethod
    async def mark_as_skipped(
        self,
        meal_log_id: int,
        user_id: int,
        reason: Optional[str] = None
    ) -> MealLog:
 
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

        pass


    @abstractmethod
    async def count_meals_by_status(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> dict:
        pass

    @abstractmethod
    async def get_adherence_rate(
        self,
        user_id: int,
        days: int
    ) -> float:

        pass

    @abstractmethod
    async def get_meal_timing_patterns(
        self,
        user_id: int,
        days: int
    ) -> List[dict]:

        pass

    @abstractmethod
    async def get_skip_frequency_by_meal_type(
        self,
        user_id: int,
        days: int
    ) -> dict:

        pass

    @abstractmethod
    async def get_portion_multiplier_stats(
        self,
        user_id: int,
        days: int
    ) -> dict:

        pass

    @abstractmethod
    async def get_most_skipped_recipes(
        self,
        user_id: int,
        days: int,
        limit: int = 10
    ) -> List[Tuple[int, str, int, float]]:

        pass


    @abstractmethod
    async def bulk_create_meal_logs(
        self,
        meal_logs: List[MealLog]
    ) -> List[MealLog]:

        pass

    @abstractmethod
    async def bulk_delete_meal_logs(
        self,
        meal_log_ids: List[int],
        user_id: int
    ) -> int:

        pass

    @abstractmethod
    async def count_consumed_meals_in_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> int:
        """Count consumed meals in date range"""
        pass

    @abstractmethod
    async def count_consumed_meals_today(self, user_id: int) -> int:
        """Count consumed meals today"""
        pass