"""
AchievementService - Check user achievements with Redis deduplication

Service for checking user achievements:
- Streak achievements (7-day, 14-day, 30-day)
- Daily completion (3 meals logged)
- Nutrition targets (protein goal)
- Redis deduplication (send each achievement once per day)
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta, date

from app.repositories.interfaces.tracking_repository import ITrackingRepository
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class AchievementService:
    """Service for checking user achievements"""

    def __init__(
        self,
        tracking_repo: ITrackingRepository,
        user_profile_repo: IUserProfileRepository
    ):
        """
        Args:
            tracking_repo: Repository for meal logs
            user_profile_repo: Repository for user preferences/goals
        """
        self.tracking_repo = tracking_repo
        self.user_profile_repo = user_profile_repo
        self.redis = get_redis_client()

    async def check_achievements(
        self,
        user_id: int,
        daily_totals: Dict
    ) -> List[Dict]:
        """
        Check all achievements for user.

        Args:
            user_id: User ID
            daily_totals: Today's nutrition totals

        Returns:
            List of achievements: [{"type": "streak_7day", "message": "..."}]
        """
        achievements = []
        today = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Check streak achievements
            streak_achievement = await self._check_streak(user_id, today)
            if streak_achievement:
                achievements.append(streak_achievement)

            # Check daily completion
            daily_achievement = await self._check_daily_completion(user_id, today)
            if daily_achievement:
                achievements.append(daily_achievement)

            # Check nutrition target
            nutrition_achievement = await self._check_nutrition_target(
                user_id, daily_totals, today
            )
            if nutrition_achievement:
                achievements.append(nutrition_achievement)

        except Exception as e:
            logger.error(f"Error checking achievements for user {user_id}: {e}")

        return achievements

    async def _check_streak(self, user_id: int, today: str) -> Dict | None:
        """Check streak achievements (7-day, 14-day, 30-day)"""

        # Count consumed meals in last 7 days
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        recent_logs = await self.tracking_repo.count_consumed_meals_in_range(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )

        if recent_logs >= 21:  # 3 meals * 7 days
            streak_days = recent_logs // 3

            # Determine achievement type
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

            # Check Redis deduplication
            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if self.redis.exists(dedup_key):
                return None  # Already sent today

            # Mark as sent (24h TTL)
            self.redis.setex(dedup_key, 86400, "1")

            return {"type": achievement_type, "message": message}

        return None

    async def _check_daily_completion(self, user_id: int, today: str) -> Dict | None:
        """Check if user logged 3+ meals today"""

        consumed_count = await self.tracking_repo.count_consumed_meals_today(user_id)

        if consumed_count >= 3:
            achievement_type = "daily_completion"

            # Check deduplication
            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if self.redis.exists(dedup_key):
                return None

            # Mark as sent
            self.redis.setex(dedup_key, 86400, "1")

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

        # Get user's protein target from their goal
        goal = await self.user_profile_repo.get_active_goal(user_id)
        protein_target = goal.protein_target if goal else 50  # Default 50g

        if protein_consumed >= protein_target:
            achievement_type = "nutrition_target"

            # Check deduplication
            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if self.redis.exists(dedup_key):
                return None

            # Mark as sent
            self.redis.setex(dedup_key, 86400, "1")

            return {
                "type": achievement_type,
                "message": f"Protein goal achieved! Hit {int(protein_consumed)}g target!"
            }

        return None
