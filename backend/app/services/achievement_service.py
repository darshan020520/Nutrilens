import logging
from typing import List, Dict
from datetime import datetime, timedelta, date

from app.repositories.interfaces.tracking_repository import ITrackingRepository
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

class AchievementService:

    def __init__(
        self,
        tracking_repo: ITrackingRepository,
        user_profile_repo: IUserProfileRepository
    ):
        self.tracking_repo = tracking_repo
        self.user_profile_repo = user_profile_repo
        self.redis = get_redis_client()

    async def check_achievements(
        self,
        user_id: int,
        daily_totals: Dict
    ) -> List[Dict]:

        achievements = []
        today = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            streak_achievement = await self._check_streak(user_id, today)
            if streak_achievement:
                achievements.append(streak_achievement)

            daily_achievement = await self._check_daily_completion(user_id, today)
            if daily_achievement:
                achievements.append(daily_achievement)

            nutrition_achievement = await self._check_nutrition_target(
                user_id, daily_totals, today
            )
            if nutrition_achievement:
                achievements.append(nutrition_achievement)

        except Exception as e:
            logger.error(f"Error checking achievements for user {user_id}: {e}")

        return achievements

    async def _check_streak(self, user_id: int, today: str) -> Dict | None:

        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        recent_logs = await self.tracking_repo.count_consumed_meals_in_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )

        if recent_logs >= 21:
            streak_days = recent_logs // 3

            if streak_days >= 30:
                achievement_type = "streak_30day"
                message = "Incredible! 30-day meal streak - habit mastery achieved!"
            elif streak_days >= 14:
                achievement_type = "streak_14day"
                message = "Amazing! 14-day meal streak - you're on fire!"
            elif streak_days >= 7:
                achievement_type = "streak_7day"
                message = "7-day meal logging streak! Building lasting habits!"
            else:
                return None

            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if await self.redis.exists(dedup_key):
                return None

            await self.redis.setex(dedup_key, 86400, "1")

            return {"type": achievement_type, "message": message}

        return None

    async def _check_daily_completion(self, user_id: int, today: str) -> Dict | None:
        """Check if user logged 3+ meals today"""

        consumed_count = await self.tracking_repo.count_consumed_meals_today(user_id)

        if consumed_count >= 3:
            achievement_type = "daily_completion"

            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if await self.redis.exists(dedup_key):
                return None

            await self.redis.setex(dedup_key, 86400, "1")

            return {
                "type": achievement_type,
                "message": "Perfect day! All meals logged - crushing your goals!"
            }

        return None

    async def _check_nutrition_target(
        self, user_id: int, daily_totals: Dict, today: str
    ) -> Dict | None:
        """Check if user hit protein target"""

        protein_consumed = daily_totals.get("protein_g", 0)

        goal = await self.user_profile_repo.get_active_goal(user_id)
        # UserGoal stores macros in macro_targets JSON, not as direct attributes
        protein_target = 50  # default
        if goal and goal.macro_targets:
            protein_target = goal.macro_targets.get("protein_g", 50)

        if protein_consumed >= protein_target:
            achievement_type = "nutrition_target"

            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if await self.redis.exists(dedup_key):
                return None

            await self.redis.setex(dedup_key, 86400, "1")

            return {
                "type": achievement_type,
                "message": f"Protein goal achieved! Hit {int(protein_consumed)}g target!"
            }

        return None
