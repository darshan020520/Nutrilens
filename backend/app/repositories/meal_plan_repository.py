import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.repositories.interfaces.meal_plan_repository import IMealPlanRepository
from app.models.database import MealPlan
from app.schemas.meal_plan import MealPlanResponse
from app.core.ist_datetime import today_ist, start_of_day_naive, end_of_day_naive

logger = logging.getLogger(__name__)


class MealPlanRepository(IMealPlanRepository):

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, plan_id: int) -> Optional[MealPlan]:
        result = await self.db.execute(select(MealPlan).where(MealPlan.id == plan_id))
        return result.scalars().first()

    async def get_active_plan(self, user_id: int) -> Optional[MealPlan]:
        today = today_ist()
        active_window_start = start_of_day_naive(today - timedelta(days=6))
        active_window_end = end_of_day_naive(today)

        result = await self.db.execute(
            select(MealPlan)
            .where(
                MealPlan.user_id == user_id,
                MealPlan.is_active == True,
                MealPlan.week_start_date >= active_window_start,
                MealPlan.week_start_date <= active_window_end
            )
            .order_by(MealPlan.week_start_date.desc(), MealPlan.id.desc())
        )
        return result.scalars().first()

    async def deactivate_active_plans(self, user_id: int) -> None:
        await self.db.execute(
            update(MealPlan)
            .where(MealPlan.user_id == user_id, MealPlan.is_active == True)
            .values(is_active=False)
        )
        # commit is done by caller

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
        try:
            new_plan = MealPlan(
                user_id=user_id,
                week_start_date=week_start_date,
                plan_data=plan_data,
                grocery_list=grocery_list,
                total_calories=total_calories,
                avg_macros=avg_macros,
                is_active=is_active
            )

            new_plan.updated_at = datetime.now()

            self.db.add(new_plan)
            await self.db.commit()

            return MealPlanResponse.model_validate(new_plan)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error saving meal plan: {str(e)}")
            raise

    async def update(self, plan_id: int, updates: Dict[str, Any]) -> MealPlan:
        result = await self.db.execute(select(MealPlan).where(MealPlan.id == plan_id))
        plan = result.scalars().first()

        if not plan:
            raise ValueError(f"MealPlan {plan_id} not found")

        for key, value in updates.items():
            if hasattr(plan, key):
                setattr(plan, key, value)

        plan.updated_at = datetime.now()
        await self.db.commit()
        await self.db.refresh(plan)

        return plan

    async def delete(self, plan_id: int) -> bool:
        result = await self.db.execute(select(MealPlan).where(MealPlan.id == plan_id))
        plan = result.scalars().first()

        if not plan:
            return False

        await self.db.delete(plan)
        await self.db.commit()

        return True

    async def get_all_for_user(self, user_id: int, limit: int = 10, offset: int = 0) -> List[MealPlan]:
        result = await self.db.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .order_by(MealPlan.week_start_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.unique().scalars().all()

    async def commit(self) -> None:
        await self.db.commit()
