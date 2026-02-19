import logging
from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from app.models.database import MealLog, MealPlan

logger = logging.getLogger(__name__)


class ActivityRepository:
    def __init__(self, db: Session):
        self.db = db

    async def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:

        activities = []

        recent_meals = self.db.query(MealLog).options(
            joinedload(MealLog.recipe)
        ).filter(
            MealLog.user_id == user_id
        ).order_by(
            desc(MealLog.planned_datetime)
        ).limit(limit * 2).all()

        for meal in recent_meals:
            if meal.consumed_datetime:
                activities.append({
                    "id": meal.id,
                    "type": "meal_logged",
                    "description": f"{meal.meal_type.capitalize()} logged - {meal.recipe.title if meal.recipe else 'External meal'}",
                    "timestamp": meal.consumed_datetime,
                    "icon": "🍽️"
                })
            elif meal.was_skipped and meal.planned_datetime:
                activities.append({
                    "id": meal.id,
                    "type": "meal_skipped",
                    "description": f"{meal.meal_type.capitalize()} skipped",
                    "timestamp": meal.planned_datetime,
                    "icon": "⏭️"
                })

        recent_plans = self.db.query(MealPlan).filter(
            MealPlan.user_id == user_id
        ).order_by(
            desc(MealPlan.created_at)
        ).limit(2).all()

        for plan in recent_plans:
            activities.append({
                "id": plan.id,
                "type": "plan_generated",
                "description": f"New meal plan generated for {plan.week_start_date.strftime('%b %d')}",
                "timestamp": plan.created_at,
                "icon": "📋"
            })

        activities.sort(key=lambda x: x["timestamp"], reverse=True)

        return activities[:limit]
