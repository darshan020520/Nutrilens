import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.models.database import MealLog, MealPlan
from app.core.ist_datetime import now_ist_naive

logger = logging.getLogger(__name__)


class ActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    async def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> Dict[str, Any]:

        activities = []
        now = now_ist_naive()
        fetch_n = limit * 3

        # --- Consumed meals ordered by when they were actually eaten ---
        consumed_meals = self.db.query(MealLog).options(
            joinedload(MealLog.recipe)
        ).filter(
            MealLog.user_id == user_id,
            MealLog.consumed_datetime.isnot(None)
        ).order_by(
            desc(MealLog.consumed_datetime)
        ).limit(fetch_n).all()

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

        # --- Skipped meals — only past ones, ordered by when they were planned ---
        skipped_meals = self.db.query(MealLog).filter(
            MealLog.user_id == user_id,
            MealLog.was_skipped == True,
            MealLog.planned_datetime <= now
        ).order_by(
            desc(MealLog.planned_datetime)
        ).limit(fetch_n).all()

        for meal in skipped_meals:
            activities.append({
                "id": f"meal-{meal.id}",
                "type": "meal_skipped",
                "description": f"{meal.meal_type.capitalize()} skipped",
                "timestamp": meal.planned_datetime,
                "icon": "⏭️"
            })

        # --- Recent meal plans ---
        recent_plans = self.db.query(MealPlan).filter(
            MealPlan.user_id == user_id
        ).order_by(
            desc(MealPlan.created_at)
        ).limit(3).all()

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
