"""
Tracking Repository Implementation

Implements data access operations for meal logs and tracking functionality.
Extracted from TrackingAgent to follow clean repository pattern.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, case

from app.repositories.interfaces.tracking_repository import ITrackingRepository
from app.models.database import MealLog, Recipe, User

logger = logging.getLogger(__name__)


class TrackingRepository(ITrackingRepository):
    """
    Repository for tracking data access operations.

    All meal log database queries are implemented here.
    NO business logic - only data access.
    """

    def __init__(self, db: Session):
        """
        Initialize tracking repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # =========================================================================
    # BASIC CRUD OPERATIONS
    # =========================================================================

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[MealLog]:
        """
        Get all meal logs with pagination (across all users).

        Note: This method is required by IRepository interface.
        For user-specific logs, use get_all_for_user() instead.

        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip

        Returns:
            List of meal logs ordered by ID
        """
        try:
            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe),
                joinedload(MealLog.user)
            ).order_by(
                MealLog.id
            ).limit(limit).offset(offset).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting all meal logs: {e}")
            raise

    async def get_by_id(
        self,
        meal_log_id: int,
        user_id: int
    ) -> Optional[MealLog]:
        """
        Get meal log by ID with user validation.

        Source: backend/app/agents/tracking_agent.py:229-233 (pattern)

        Args:
            meal_log_id: ID of the meal log
            user_id: User ID for ownership validation

        Returns:
            MealLog if found and belongs to user, None otherwise
        """
        try:
            meal_log = self.db.query(MealLog).options(
                joinedload(MealLog.recipe),
                joinedload(MealLog.user)
            ).filter(
                and_(
                    MealLog.id == meal_log_id,
                    MealLog.user_id == user_id
                )
            ).first()

            return meal_log

        except Exception as e:
            logger.error(f"Error getting meal log {meal_log_id}: {e}")
            raise

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
        try:
            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                MealLog.user_id == user_id
            ).order_by(
                MealLog.planned_datetime.desc()
            ).limit(limit).offset(offset).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting meal logs for user {user_id}: {e}")
            raise

    async def create(self, meal_log: MealLog) -> MealLog:
        """
        Create new meal log.

        Args:
            meal_log: MealLog entity to create

        Returns:
            Created meal log with ID populated
        """
        try:
            self.db.add(meal_log)
            self.db.commit()
            self.db.refresh(meal_log)

            logger.info(f"Created meal log {meal_log.id} for user {meal_log.user_id}")
            return meal_log

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating meal log: {e}")
            raise

    async def update(self, meal_log: MealLog) -> MealLog:
        """
        Update existing meal log.

        Args:
            meal_log: MealLog entity to update (must have ID)

        Returns:
            Updated meal log
        """
        try:
            self.db.commit()
            self.db.refresh(meal_log)

            logger.info(f"Updated meal log {meal_log.id}")
            return meal_log

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating meal log {meal_log.id}: {e}")
            raise

    async def delete(self, meal_log_id: int, user_id: int) -> bool:
        """
        Delete meal log by ID with user validation.

        Args:
            meal_log_id: ID of meal log to delete
            user_id: User ID for ownership validation

        Returns:
            True if deleted, False if not found or unauthorized
        """
        try:
            result = self.db.query(MealLog).filter(
                and_(
                    MealLog.id == meal_log_id,
                    MealLog.user_id == user_id
                )
            ).delete()

            self.db.commit()

            if result > 0:
                logger.info(f"Deleted meal log {meal_log_id}")
                return True
            else:
                logger.warning(f"Meal log {meal_log_id} not found for deletion")
                return False

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting meal log {meal_log_id}: {e}")
            raise

    # =========================================================================
    # DATE-BASED QUERIES
    # =========================================================================

    async def get_by_date(
        self,
        user_id: int,
        target_date: date
    ) -> List[MealLog]:
        """
        Get all meal logs for a specific date.

        Source: backend/app/agents/tracking_agent.py:830-841 (pattern)

        Args:
            user_id: User ID
            target_date: Date to query

        Returns:
            List of meal logs for that date, ordered by planned_datetime
        """
        try:
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).order_by(
                MealLog.planned_datetime
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting meal logs for date {target_date}: {e}")
            raise

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
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).order_by(
                MealLog.planned_datetime
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting meal logs for range {start_date} to {end_date}: {e}")
            raise

    async def get_todays_meals(self, user_id: int) -> List[MealLog]:
        """
        Get all meal logs for today.

        Args:
            user_id: User ID

        Returns:
            List of today's meal logs, ordered by planned_datetime
        """
        today = datetime.utcnow().date()
        return await self.get_by_date(user_id, today)

    async def get_upcoming_meals(
        self,
        user_id: int,
        days: int = 7
    ) -> List[MealLog]:
        """
        Get upcoming meal logs (future planned meals).

        Source: backend/app/agents/tracking_agent.py:830-841

        Args:
            user_id: User ID
            days: Number of days ahead to look (default 7)

        Returns:
            List of future meal logs, ordered by planned_datetime
        """
        try:
            now = datetime.utcnow()
            until_date = now + timedelta(days=days)

            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= now,
                    MealLog.planned_datetime <= until_date,
                    MealLog.was_skipped == False,
                    MealLog.consumed_datetime.is_(None)
                )
            ).order_by(
                MealLog.planned_datetime
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting upcoming meals for user {user_id}: {e}")
            raise

    # =========================================================================
    # STATUS-BASED QUERIES
    # =========================================================================

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
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime,
                    MealLog.consumed_datetime.isnot(None)
                )
            ).order_by(
                MealLog.consumed_datetime
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting consumed meals: {e}")
            raise

    async def get_skipped_meals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[MealLog]:
        """
        Get meals that have been skipped (was_skipped = True).

        Source: backend/app/agents/tracking_agent.py:627-680 (pattern)

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of skipped meal logs
        """
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime,
                    MealLog.was_skipped == True
                )
            ).order_by(
                MealLog.planned_datetime
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting skipped meals: {e}")
            raise

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
        try:
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())

            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime,
                    MealLog.consumed_datetime.is_(None),
                    MealLog.was_skipped == False
                )
            ).order_by(
                MealLog.planned_datetime
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting pending meals: {e}")
            raise

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
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            meal_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime,
                    MealLog.external_meal.isnot(None)
                )
            ).order_by(
                MealLog.consumed_datetime.desc()
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting external meals: {e}")
            raise

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
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            meal_logs = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.recipe_id == recipe_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).order_by(
                MealLog.planned_datetime
            ).all()

            return meal_logs

        except Exception as e:
            logger.error(f"Error getting meals for recipe {recipe_id}: {e}")
            raise

    # =========================================================================
    # MEAL LOGGING OPERATIONS
    # =========================================================================

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

        Source: backend/app/api/tracking.py:155-176

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
        try:
            meal_log = await self.get_by_id(meal_log_id, user_id)

            if not meal_log:
                raise ValueError(f"Meal log {meal_log_id} not found")

            if meal_log.consumed_datetime is not None:
                raise ValueError("This meal has already been logged")

            if meal_log.was_skipped:
                raise ValueError("Cannot log a meal that has been skipped")

            # Update fields
            meal_log.consumed_datetime = consumed_at
            meal_log.portion_multiplier = portion_multiplier
            if notes:
                meal_log.notes = notes

            self.db.commit()
            self.db.refresh(meal_log)

            logger.info(f"Marked meal log {meal_log_id} as consumed")
            return meal_log

        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error marking meal as consumed: {e}")
            raise

    async def mark_as_skipped(
        self,
        meal_log_id: int,
        user_id: int,
        reason: Optional[str] = None
    ) -> MealLog:
        """
        Mark meal log as skipped.

        Source: backend/app/agents/tracking_agent.py:627-680

        Args:
            meal_log_id: ID of meal log
            user_id: User ID for validation
            reason: Optional skip reason

        Returns:
            Updated meal log

        Raises:
            ValueError: If meal log not found or already consumed/skipped
        """
        try:
            meal_log = await self.get_by_id(meal_log_id, user_id)

            if not meal_log:
                raise ValueError(f"Meal log {meal_log_id} not found")

            if meal_log.was_skipped:
                raise ValueError("This meal is already marked as skipped")

            if meal_log.consumed_datetime is not None:
                raise ValueError("Cannot skip a meal that has already been logged")

            # Update fields
            meal_log.was_skipped = True
            meal_log.skip_reason = reason

            self.db.commit()
            self.db.refresh(meal_log)

            logger.info(f"Marked meal log {meal_log_id} as skipped")
            return meal_log

        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error marking meal as skipped: {e}")
            raise

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

        Source: backend/app/api/tracking.py:988-1010

        Args:
            user_id: User ID
            meal_type: Meal type (breakfast, lunch, dinner, snack)
            consumed_at: When the meal was consumed
            external_meal_data: Nutrition data as dict
            notes: Optional notes

        Returns:
            Created meal log
        """
        try:
            meal_log = MealLog(
                user_id=user_id,
                recipe_id=None,  # No recipe for external meal
                meal_type=meal_type,
                planned_datetime=consumed_at,
                consumed_datetime=consumed_at,
                was_skipped=False,
                meal_plan_id=None,
                day_index=None,
                external_meal=external_meal_data,
                notes=notes
            )

            self.db.add(meal_log)
            self.db.commit()
            self.db.refresh(meal_log)

            logger.info(f"Created external meal log {meal_log.id} for user {user_id}")
            return meal_log

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating external meal log: {e}")
            raise

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

        Source: backend/app/api/tracking.py:954-985

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
        try:
            meal_log = await self.get_by_id(meal_log_id, user_id)

            if not meal_log:
                raise ValueError(f"Meal log {meal_log_id} not found")

            if meal_log.consumed_datetime:
                raise ValueError("This meal has already been logged")

            # Replace with external meal
            meal_log.consumed_datetime = consumed_at
            meal_log.external_meal = external_meal_data
            meal_log.recipe_id = None  # Clear recipe link
            if notes:
                meal_log.notes = notes

            self.db.commit()
            self.db.refresh(meal_log)

            logger.info(f"Replaced planned meal {meal_log_id} with external meal")
            return meal_log

        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error replacing planned meal with external: {e}")
            raise

    # =========================================================================
    # ANALYTICS QUERIES
    # =========================================================================

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
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # Get all meals in range
            total = self.db.query(func.count(MealLog.id)).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).scalar()

            # Count consumed
            consumed = self.db.query(func.count(MealLog.id)).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime,
                    MealLog.consumed_datetime.isnot(None)
                )
            ).scalar()

            # Count skipped
            skipped = self.db.query(func.count(MealLog.id)).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime,
                    MealLog.was_skipped == True
                )
            ).scalar()

            # Pending = total - consumed - skipped
            pending = total - consumed - skipped

            return {
                "total": total or 0,
                "consumed": consumed or 0,
                "skipped": skipped or 0,
                "pending": pending or 0
            }

        except Exception as e:
            logger.error(f"Error counting meals by status: {e}")
            raise

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
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            counts = await self.count_meals_by_status(user_id, start_date, end_date)

            total_actionable = counts["consumed"] + counts["skipped"]

            if total_actionable == 0:
                return 1.0  # No meals to judge adherence

            adherence = counts["consumed"] / total_actionable
            return round(adherence, 3)

        except Exception as e:
            logger.error(f"Error calculating adherence rate: {e}")
            raise

    async def get_meal_timing_patterns(
        self,
        user_id: int,
        days: int
    ) -> List[dict]:
        """
        Get average consumption times by meal type.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            List of dicts with timing patterns per meal type
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # Get consumed meals with timing
            consumed_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime.isnot(None),
                    MealLog.consumed_datetime >= start_datetime,
                    MealLog.consumed_datetime <= end_datetime
                )
            ).all()

            # Group by meal type
            timing_by_type = {}

            for meal in consumed_meals:
                meal_type = meal.meal_type
                if meal_type not in timing_by_type:
                    timing_by_type[meal_type] = []

                # Extract time portion
                consumed_time = meal.consumed_datetime.time()
                timing_by_type[meal_type].append(consumed_time)

            # Calculate averages
            patterns = []
            for meal_type, times in timing_by_type.items():
                if times:
                    # Convert times to minutes since midnight for averaging
                    minutes_list = [t.hour * 60 + t.minute for t in times]
                    avg_minutes = sum(minutes_list) / len(minutes_list)

                    # Convert back to time
                    avg_hour = int(avg_minutes // 60)
                    avg_minute = int(avg_minutes % 60)
                    avg_time = f"{avg_hour:02d}:{avg_minute:02d}"

                    # Calculate skip rate for this meal type
                    total_planned = self.db.query(func.count(MealLog.id)).filter(
                        and_(
                            MealLog.user_id == user_id,
                            MealLog.meal_type == meal_type,
                            MealLog.planned_datetime >= start_datetime,
                            MealLog.planned_datetime <= end_datetime
                        )
                    ).scalar()

                    skipped = self.db.query(func.count(MealLog.id)).filter(
                        and_(
                            MealLog.user_id == user_id,
                            MealLog.meal_type == meal_type,
                            MealLog.was_skipped == True,
                            MealLog.planned_datetime >= start_datetime,
                            MealLog.planned_datetime <= end_datetime
                        )
                    ).scalar()

                    skip_rate = (skipped / total_planned) if total_planned > 0 else 0.0

                    patterns.append({
                        "meal_type": meal_type,
                        "average_time": avg_time,
                        "count": len(times),
                        "skip_rate": round(skip_rate, 3)
                    })

            return patterns

        except Exception as e:
            logger.error(f"Error getting meal timing patterns: {e}")
            raise

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
            Dict mapping meal type to skip rate
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # Get all meal types
            meal_types = self.db.query(MealLog.meal_type).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).distinct().all()

            skip_rates = {}

            for (meal_type,) in meal_types:
                total = self.db.query(func.count(MealLog.id)).filter(
                    and_(
                        MealLog.user_id == user_id,
                        MealLog.meal_type == meal_type,
                        MealLog.planned_datetime >= start_datetime,
                        MealLog.planned_datetime <= end_datetime
                    )
                ).scalar()

                skipped = self.db.query(func.count(MealLog.id)).filter(
                    and_(
                        MealLog.user_id == user_id,
                        MealLog.meal_type == meal_type,
                        MealLog.was_skipped == True,
                        MealLog.planned_datetime >= start_datetime,
                        MealLog.planned_datetime <= end_datetime
                    )
                ).scalar()

                skip_rate = (skipped / total) if total > 0 else 0.0
                skip_rates[meal_type] = round(skip_rate, 3)

            return skip_rates

        except Exception as e:
            logger.error(f"Error getting skip frequency: {e}")
            raise

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
            Dict with portion statistics
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # Get all consumed meals with portions
            consumed_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime.isnot(None),
                    MealLog.consumed_datetime >= start_datetime,
                    MealLog.consumed_datetime <= end_datetime
                )
            ).all()

            if not consumed_meals:
                return {
                    "average": 1.0,
                    "median": 1.0,
                    "min": 1.0,
                    "max": 1.0,
                    "by_meal_type": {}
                }

            # Overall stats
            portions = [m.portion_multiplier for m in consumed_meals]
            portions.sort()

            median_idx = len(portions) // 2
            median = portions[median_idx] if portions else 1.0

            stats = {
                "average": round(sum(portions) / len(portions), 2),
                "median": round(median, 2),
                "min": round(min(portions), 2),
                "max": round(max(portions), 2),
                "by_meal_type": {}
            }

            # By meal type
            by_type = {}
            for meal in consumed_meals:
                meal_type = meal.meal_type
                if meal_type not in by_type:
                    by_type[meal_type] = []
                by_type[meal_type].append(meal.portion_multiplier)

            for meal_type, type_portions in by_type.items():
                stats["by_meal_type"][meal_type] = round(
                    sum(type_portions) / len(type_portions), 2
                )

            return stats

        except Exception as e:
            logger.error(f"Error getting portion stats: {e}")
            raise

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
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # Query to get skip counts per recipe
            results = self.db.query(
                MealLog.recipe_id,
                Recipe.title,
                func.count(MealLog.id).label('total_count'),
                func.sum(case((MealLog.was_skipped == True, 1), else_=0)).label('skip_count')
            ).join(
                Recipe, MealLog.recipe_id == Recipe.id
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.recipe_id.isnot(None),
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).group_by(
                MealLog.recipe_id,
                Recipe.title
            ).all()

            # Calculate skip rates
            skip_data = []
            for recipe_id, recipe_name, total_count, skip_count in results:
                if total_count > 0:
                    skip_rate = skip_count / total_count
                    skip_data.append((recipe_id, recipe_name, skip_count, skip_rate))

            # Sort by skip rate (highest first)
            skip_data.sort(key=lambda x: x[3], reverse=True)

            return skip_data[:limit]

        except Exception as e:
            logger.error(f"Error getting most skipped recipes: {e}")
            raise

    # =========================================================================
    # BULK OPERATIONS
    # =========================================================================

    async def bulk_create_meal_logs(
        self,
        meal_logs: List[MealLog]
    ) -> List[MealLog]:
        """
        Create multiple meal logs in one transaction.

        Args:
            meal_logs: List of MealLog entities to create

        Returns:
            List of created meal logs with IDs
        """
        try:
            self.db.add_all(meal_logs)
            self.db.commit()

            for meal_log in meal_logs:
                self.db.refresh(meal_log)

            logger.info(f"Bulk created {len(meal_logs)} meal logs")
            return meal_logs

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk creating meal logs: {e}")
            raise

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
        try:
            result = self.db.query(MealLog).filter(
                and_(
                    MealLog.id.in_(meal_log_ids),
                    MealLog.user_id == user_id
                )
            ).delete(synchronize_session=False)

            self.db.commit()

            logger.info(f"Bulk deleted {result} meal logs")
            return result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk deleting meal logs: {e}")
            raise

    async def count_consumed_meals_in_range(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> int:
        """Count consumed meals in date range"""
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            count = self.db.query(func.count(MealLog.id)).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime >= start_datetime,
                    MealLog.consumed_datetime <= end_datetime,
                    MealLog.consumed_datetime.isnot(None)
                )
            ).scalar()

            return count or 0

        except Exception as e:
            logger.error(f"Error counting consumed meals in range: {e}")
            raise

    async def count_consumed_meals_today(self, user_id: int) -> int:
        """Count consumed meals today"""
        try:
            today = datetime.utcnow().date()

            count = self.db.query(func.count(MealLog.id)).filter(
                and_(
                    MealLog.user_id == user_id,
                    func.date(MealLog.consumed_datetime) == today,
                    MealLog.consumed_datetime.isnot(None)
                )
            ).scalar()

            return count or 0

        except Exception as e:
            logger.error(f"Error counting consumed meals today: {e}")
            raise