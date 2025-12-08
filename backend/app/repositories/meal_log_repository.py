"""
Meal Log Repository Implementation

PostgreSQL implementation of meal log data access.

ALL CODE COPY-PASTED FROM planning_agent.py - ZERO LOGIC CHANGES
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.repositories.interfaces.meal_log_repository import IMealLogRepository
from app.models.database import MealLog, UserPath

logger = logging.getLogger(__name__)


class MealLogRepository(IMealLogRepository):
    """
    PostgreSQL implementation of meal log repository.

    COPY-PASTED QUERIES FROM: planning_agent.py:1023-1097
    """

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    async def get_by_id(self, log_id: int) -> Optional[MealLog]:
        """
        Get meal log by ID.

        Args:
            log_id: Meal log ID

        Returns:
            MealLog if found, None otherwise
        """
        return self.db.query(MealLog).filter(MealLog.id == log_id).first()

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

        EXACT COPY-PASTE FROM: planning_agent.py:1029-1093

        Args:
            user_id: User ID
            meal_plan_id: Meal plan ID to link logs to
            meal_plan_data: Meal plan week_plan data
            start_date: Start date of the meal plan
            user_meal_windows: User's meal timing windows

        Returns:
            Number of logs created
        """
        try:
            # COPY-PASTED FROM planning_agent.py:1030 - NO CHANGES
            logs_to_add = []

            # COPY-PASTED FROM planning_agent.py:1037-1043 - NO CHANGES
            # Create meal time map from windows or use defaults
            default_meal_times = {
                'breakfast': '08:00',
                'lunch': '13:00',
                'dinner': '19:00',
                'snack': '16:00'
            }

            # COPY-PASTED FROM planning_agent.py:1045-1054 - NO CHANGES
            meal_time_map = {}
            for window in user_meal_windows:
                meal_type = window.get('meal', '').lower()
                start_time = window.get('start', default_meal_times.get(meal_type, '12:00'))
                meal_time_map[meal_type] = start_time

            # Fill in any missing meal types with defaults
            for meal_type, default_time in default_meal_times.items():
                if meal_type not in meal_time_map:
                    meal_time_map[meal_type] = default_time

            # COPY-PASTED FROM planning_agent.py:1056 - NO CHANGES (kept print for exact match)
            print("printing meal plan format inside MealLog save function", meal_plan_data)

            # COPY-PASTED FROM planning_agent.py:1057-1086 - NO CHANGES
            for day_key, day_data in meal_plan_data.items():
                # Extract the numeric day offset (e.g., 'day_0' → 0)
                day_offset = int(day_key.split('_')[1])
                planned_date = start_date + timedelta(days=day_offset)

                for meal_name, recipe in day_data.get('meals', {}).items():
                    if not recipe:
                        continue  # Skip empty meal slots

                    # Get meal time and create proper datetime
                    meal_time_str = meal_time_map.get(meal_name.lower(), '12:00')
                    hour, minute = map(int, meal_time_str.split(':'))
                    planned_datetime = planned_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    logs_to_add.append(
                        MealLog(
                            user_id=user_id,
                            recipe_id=recipe['id'],
                            meal_type=meal_name,
                            planned_datetime=planned_datetime,
                            consumed_datetime=None,
                            was_skipped=False,
                            skip_reason=None,
                            portion_multiplier=1.0,
                            notes=None,
                            external_meal=None,
                            meal_plan_id=meal_plan_id,
                            day_index=day_offset
                        )
                    )

            # COPY-PASTED FROM planning_agent.py:1088-1093 - NO CHANGES
            if logs_to_add:
                self.db.bulk_save_objects(logs_to_add)
                self.db.commit()
                logger.info(f"Created {len(logs_to_add)} MealLog entries for user {user_id}")
            else:
                logger.warning("No MealLog entries to create—meal plan may be empty.")

            return len(logs_to_add)

        except Exception as e:
            # COPY-PASTED FROM planning_agent.py:1095-1096 - NO CHANGES
            self.db.rollback()
            logger.error(f"Failed to create MealLog entries: {str(e)}")
            raise

    async def get_by_user_and_date_range(
        self,
        user_id: int,
        start_datetime: datetime,
        end_datetime: datetime,
        was_skipped: Optional[bool] = None
    ) -> List[MealLog]:
        """
        Get meal logs for user within date range.

        EXACT COPY-PASTE FROM: planning_agent.py:1108-1113

        Args:
            user_id: User ID
            start_datetime: Start of date range
            end_datetime: End of date range
            was_skipped: Filter by skipped status (None = all)

        Returns:
            List of MealLogs
        """
        # COPY-PASTED FROM planning_agent.py:1108-1113 - NO CHANGES
        query = self.db.query(MealLog).filter(
            MealLog.user_id == user_id,
            MealLog.consumed_datetime >= start_datetime,
            MealLog.consumed_datetime <= end_datetime
        )

        if was_skipped is not None:
            query = query.filter(MealLog.was_skipped == was_skipped)

        return query.all()

    async def update(self, log_id: int, updates: Dict[str, Any]) -> MealLog:
        """
        Update meal log.

        Args:
            log_id: Meal log ID
            updates: Fields to update

        Returns:
            Updated MealLog
        """
        log = self.db.query(MealLog).filter(MealLog.id == log_id).first()

        if not log:
            raise ValueError(f"MealLog {log_id} not found")

        for key, value in updates.items():
            if hasattr(log, key):
                setattr(log, key, value)

        self.db.commit()
        self.db.refresh(log)

        return log

    async def delete(self, log_id: int) -> bool:
        """
        Delete meal log.

        Args:
            log_id: Meal log ID

        Returns:
            True if deleted, False if not found
        """
        log = self.db.query(MealLog).filter(MealLog.id == log_id).first()

        if not log:
            return False

        self.db.delete(log)
        self.db.commit()

        return True

    async def get_pending_meal(
        self,
        user_id: int,
        meal_type: str
    ) -> Optional[MealLog]:
        """
        Get pending meal log (not consumed, not skipped) for user by meal type.

        Args:
            user_id: User ID
            meal_type: Meal type (breakfast, lunch, dinner, snack)

        Returns:
            Pending MealLog if found, None otherwise
        """
        return self.db.query(MealLog).filter(
            MealLog.user_id == user_id,
            MealLog.meal_type == meal_type,
            MealLog.consumed_datetime.is_(None),
            MealLog.was_skipped == False
        ).first()

    async def get_by_plan_day_meal(
        self,
        meal_plan_id: int,
        day_index: int,
        meal_type: str
    ) -> Optional[MealLog]:
        """
        Get meal log by meal plan, day index, and meal type.

        COPY-PASTED FROM: meal_plan_service.py:225-230

        Args:
            meal_plan_id: Meal plan ID
            day_index: Day index (0-6)
            meal_type: Meal type

        Returns:
            MealLog if found, None otherwise
        """
        # COPY-PASTED FROM meal_plan_service.py:225-230 - NO CHANGES
        return self.db.query(MealLog).filter_by(
            meal_plan_id=meal_plan_id,
            day_index=day_index,
            meal_type=meal_type
        ).first()

    async def update_recipe(
        self,
        log_id: int,
        recipe_id: int,
        planned_datetime: datetime
    ) -> None:
        """
        Update meal log with new recipe and planned datetime.

        COPY-PASTED FROM: meal_plan_service.py:232-236

        Args:
            log_id: Meal log ID
            recipe_id: New recipe ID
            planned_datetime: New planned datetime
        """
        # COPY-PASTED FROM meal_plan_service.py:232-236 - NO CHANGES
        log = self.db.query(MealLog).filter(MealLog.id == log_id).first()
        if log:
            log.recipe_id = recipe_id
            log.planned_datetime = planned_datetime
            # Note: commit is done by caller (service/orchestrator)

    async def create_single(
        self,
        user_id: int,
        recipe_id: int,
        meal_type: str,
        planned_datetime: datetime,
        meal_plan_id: int,
        day_index: int
    ) -> MealLog:
        """
        Create single meal log entry.

        COPY-PASTED FROM: meal_plan_service.py:239-250

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
        # COPY-PASTED FROM meal_plan_service.py:239-250 - NO CHANGES
        new_log = MealLog(
            user_id=user_id,
            recipe_id=recipe_id,
            meal_type=meal_type,
            planned_datetime=planned_datetime,
            meal_plan_id=meal_plan_id,
            day_index=day_index,
            portion_multiplier=1.0
        )
        self.db.add(new_log)
        # Note: commit is done by caller (service/orchestrator)
        return new_log

    async def get_by_plan_and_date_range(
        self,
        user_id: int,
        meal_plan_id: int,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[MealLog]:
        """
        Get meal logs for a specific meal plan within date range.

        COPY-PASTED FROM: meal_plan.py:126-133

        Args:
            user_id: User ID
            meal_plan_id: Meal plan ID
            start_datetime: Start of date range
            end_datetime: End of date range

        Returns:
            List of MealLogs
        """
        from sqlalchemy import and_

        return self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.meal_plan_id == meal_plan_id,
                MealLog.planned_datetime >= start_datetime,
                MealLog.planned_datetime < end_datetime
            )
        ).all()
