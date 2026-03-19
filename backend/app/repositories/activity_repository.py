import asyncio
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select, desc

from app.models.database import MealLog, MealPlan
from app.core.ist_datetime import now_ist_naive

logger = logging.getLogger(__name__)


class ActivityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> Dict[str, Any]:

        activities = []
        now = now_ist_naive()
        fetch_n = limit * 3

        consumed_result, skipped_result, plans_result = await asyncio.gather(
            self.db.execute(
                select(MealLog)
                .options(joinedload(MealLog.recipe))
                .where(MealLog.user_id == user_id, MealLog.consumed_datetime.isnot(None))
                .order_by(desc(MealLog.consumed_datetime))
                .limit(fetch_n)
            ),
            self.db.execute(
                select(MealLog)
                .where(
                    MealLog.user_id == user_id,
                    MealLog.was_skipped == True,
                    MealLog.planned_datetime <= now
                )
                .order_by(desc(MealLog.planned_datetime))
                .limit(fetch_n)
            ),
            self.db.execute(
                select(MealPlan)
                .where(MealPlan.user_id == user_id)
                .order_by(desc(MealPlan.created_at))
                .limit(3)
            ),
        )

        consumed_meals = consumed_result.unique().scalars().all()
        skipped_meals = skipped_result.unique().scalars().all()
        recent_plans = plans_result.unique().scalars().all()

        for meal in consumed_meals:
            if meal.recipe:
                name = meal.recipe.title
            elif meal.external_meal:
                name = meal.external_meal.get("dish_name", "External meal")
            else:
                name = "External meal"

            activities.append({
                "id": f"meal-{meal.id}",
                "type": "meal_logged",
                "description": f"{meal.meal_type.capitalize()} logged - {name}",
                "timestamp": meal.consumed_datetime,
                "icon": "🍽️"
            })

        for meal in skipped_meals:
            activities.append({
                "id": f"meal-{meal.id}",
                "type": "meal_skipped",
                "description": f"{meal.meal_type.capitalize()} skipped",
                "timestamp": meal.planned_datetime,
                "icon": "⏭️"
            })

        for plan in recent_plans:
            activities.append({
                "id": f"plan-{plan.id}",
                "type": "plan_generated",
                "description": f"New meal plan generated for {plan.week_start_date.strftime('%b %d')}",
                "timestamp": plan.created_at,
                "icon": "📋"
            })

        activities.sort(key=lambda x: x["timestamp"], reverse=True)

        total_count = len(activities)

        return {
            "activities": activities[:limit],
            "total_count": total_count
        }
