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

            daily_achievement = await self._check_daily_completion(user_id, today, daily_totals)
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
        """
        Count consecutive days from today going backwards where at least one
        meal was consumed. Always fires (even streak=1) to encourage the user.
        Dedup prevents more than one notification per day.
        """
        today_date = date.today()
        # Look back up to 60 days — enough for any realistic streak
        start_date = today_date - timedelta(days=60)

        consumed_meals = await self.tracking_repo.get_consumed_meals(
            user_id=user_id,
            start_date=start_date,
            end_date=today_date
        )

        # Distinct dates that had at least one consumed meal
        dates_with_meals = {
            m.consumed_datetime.date()
            for m in consumed_meals
            if m.consumed_datetime
        }

        # Count consecutive days backwards from today
        streak = 0
        current = today_date
        while current in dates_with_meals:
            streak += 1
            current -= timedelta(days=1)

        # Don't fire before the first meal of the day is logged
        if streak == 0:
            return None

        dedup_key = f"achievement_sent:{user_id}:streak:{today}"
        if await self.redis.exists(dedup_key):
            return None

        await self.redis.setex(dedup_key, 86400, "1")

        if streak == 1:
            message = "Day 1! Every great streak starts here — keep it going!"
        elif streak < 7:
            message = f"{streak}-day streak! You're building a solid habit!"
        elif streak < 14:
            message = f"One week down! {streak}-day streak — you're on fire!"
        elif streak < 30:
            message = f"Incredible dedication! {streak}-day streak and still going strong!"
        else:
            message = f"Unstoppable! {streak}-day streak — you're a nutrition champion!"

        return {
            "type": "current_streak",
            "name": f"{streak}-Day Streak",
            "description": f"{streak} consecutive days of meal logging",
            "message": message,
        }

    async def _check_daily_completion(
        self, user_id: int, today: str, daily_totals: Dict
    ) -> Dict | None:
        """
        Fire when the user has consumed all meals scheduled for today.
        Uses meals_planned / meals_consumed from daily_totals (sourced from
        ConsumptionAnalyticsRepository.get_today_summary via consumption service).
        """
        meals_planned = daily_totals.get("meals_planned", 0)
        meals_consumed = daily_totals.get("meals_consumed", 0)

        if meals_planned > 0 and meals_consumed >= meals_planned:
            achievement_type = "daily_completion"

            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if await self.redis.exists(dedup_key):
                return None

            await self.redis.setex(dedup_key, 86400, "1")

            return {
                "type": achievement_type,
                "name": "All Meals Logged!",
                "description": f"Completed all {meals_planned} scheduled meals today",
                "message": f"Perfect day! All {meals_planned} meals logged — crushing your goals!",
            }

        return None

    async def _check_nutrition_target(
        self, user_id: int, daily_totals: Dict, today: str
    ) -> Dict | None:
        """
        Fire when the user has consumed at least 80% of their daily calorie target.
        Target is taken from daily_totals (sourced from UserGoal.macro_targets /
        UserProfile.goal_calories via consumption service) with a DB fallback.
        """
        calories_consumed = daily_totals.get("total_calories", 0)

        # Primary: target passed through from consumption service (already from DB)
        target_calories = daily_totals.get("target_calories", 0)

        # DB fallback if not present in daily_totals
        if not target_calories:
            goal = await self.user_profile_repo.get_active_goal(user_id)
            profile = await self.user_profile_repo.get_profile(user_id)
            if goal and goal.macro_targets and profile and profile.goal_calories:
                target_calories = profile.goal_calories
            else:
                target_calories = 2000  # safe fallback

        if target_calories > 0 and calories_consumed >= target_calories * 0.8:
            achievement_type = "nutrition_target"

            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if await self.redis.exists(dedup_key):
                return None

            await self.redis.setex(dedup_key, 86400, "1")

            percentage = round(calories_consumed / target_calories * 100)
            return {
                "type": achievement_type,
                "name": "Nutrition Target Hit!",
                "description": f"Reached {percentage}% of daily calorie goal",
                "message": (
                    f"Great work! You've hit {percentage}% of your "
                    f"{int(target_calories)} kcal daily target!"
                ),
            }

        return None
