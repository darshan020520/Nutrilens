import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.repositories.interfaces.meal_log_repository import IMealLogRepository
from app.models.database import MealLog, MealPlan, UserPath

logger = logging.getLogger(__name__)


class MealLogRepository(IMealLogRepository):
    def __init__(self, db: Session):
        self.db = db

    async def get_by_id(self, log_id: int) -> Optional[MealLog]:
        return self.db.query(MealLog).filter(MealLog.id == log_id).first()

    async def create_bulk(
        self,
        user_id: int,
        meal_plan_id: int,
        meal_plan_data: Dict,
        start_date: datetime,
        user_meal_windows: List[Dict]
    ) -> int:
        try:
            logs_to_add = []

            default_meal_times = {
                'breakfast': '08:00',
                'lunch': '13:00',
                'dinner': '19:00',
                'snack': '16:00'
            }

            meal_time_map = {}
            for window in user_meal_windows:
                meal_type = window.get('meal', '').lower()
                start_time = window.get('start', default_meal_times.get(meal_type, '12:00'))
                meal_time_map[meal_type] = start_time

            for meal_type, default_time in default_meal_times.items():
                if meal_type not in meal_time_map:
                    meal_time_map[meal_type] = default_time

            print("printing meal plan format inside MealLog save function", meal_plan_data)

            for day_key, day_data in meal_plan_data.items():
                day_offset = int(day_key.split('_')[1])
                planned_date = start_date + timedelta(days=day_offset)

                for meal_name, recipe in day_data.get('meals', {}).items():
                    if not recipe:
                        continue

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

            if logs_to_add:
                self.db.bulk_save_objects(logs_to_add)
                self.db.commit()
                logger.info(f"Created {len(logs_to_add)} MealLog entries for user {user_id}")
            else:
                logger.warning("No MealLog entries to create—meal plan may be empty.")

            return len(logs_to_add)

        except Exception as e:
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
        query = self.db.query(MealLog).filter(
            MealLog.user_id == user_id,
            MealLog.consumed_datetime >= start_datetime,
            MealLog.consumed_datetime <= end_datetime
        )

        if was_skipped is not None:
            query = query.filter(MealLog.was_skipped == was_skipped)

        return query.all()

    async def update(self, log_id: int, updates: Dict[str, Any]) -> MealLog:
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
        return new_log

    async def get_by_plan_and_date_range(
        self,
        user_id: int,
        meal_plan_id: int,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[MealLog]:
        from sqlalchemy import and_

        return self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.meal_plan_id == meal_plan_id,
                MealLog.planned_datetime >= start_datetime,
                MealLog.planned_datetime < end_datetime
            )
        ).all()

    async def get_upcoming_meals_for_today(
        self,
        user_id: int,
        current_datetime: datetime
    ) -> List[MealLog]:
        from sqlalchemy import and_, func, or_

        today = current_datetime.date()

        # Query all unconsumed meals for today (grace window applied in service layer)
        return self.db.query(MealLog).outerjoin(
            MealPlan, MealLog.meal_plan_id == MealPlan.id
        ).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.planned_datetime) == today,
                MealLog.consumed_datetime.is_(None),
                MealLog.was_skipped == False,
                MealLog.was_missed == False,
                or_(MealLog.meal_plan_id.is_(None), MealPlan.is_active.is_(True))
            )
        ).order_by(MealLog.planned_datetime).all()

    async def delete_future_orphan_logs(
        self,
        user_id: int,
        cutoff_datetime: datetime
    ) -> int:
        inactive_plan_ids = self.db.query(MealPlan.id).filter(
            MealPlan.user_id == user_id,
            MealPlan.is_active == False
        ).subquery()

        deleted = self.db.query(MealLog).filter(
            MealLog.meal_plan_id.in_(inactive_plan_ids),
            MealLog.planned_datetime >= cutoff_datetime,
            MealLog.consumed_datetime.is_(None),
            MealLog.was_skipped == False
        ).delete(synchronize_session=False)

        self.db.commit()
        return deleted

    async def get_upcoming_meals_in_time_window(
        self,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> List[MealLog]:
        
        from app.models.database import User

        return self.db.query(MealLog).options(
            joinedload(MealLog.recipe),
            joinedload(MealLog.user)
        ).join(
            User, MealLog.user_id == User.id
        ).filter(
            and_(
                MealLog.planned_datetime >= start_datetime,
                MealLog.planned_datetime <= end_datetime,
                MealLog.consumed_datetime.is_(None),
                MealLog.was_skipped == False,
                MealLog.was_missed == False,
                User.is_active == True
            )
        ).all()


