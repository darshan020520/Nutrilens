import logging
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference

logger = logging.getLogger(__name__)


class UserProfileRepository(IUserProfileRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, user_id: int) -> Optional[UserProfile]:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalars().first()

    async def get_active_goal(self, user_id: int) -> Optional[UserGoal]:
        result = await self.db.execute(
            select(UserGoal).where(
                UserGoal.user_id == user_id,
                UserGoal.is_active == True
            )
        )
        return result.scalars().first()

    async def get_path(self, user_id: int) -> Optional[UserPath]:
        result = await self.db.execute(
            select(UserPath).where(UserPath.user_id == user_id)
        )
        return result.scalars().first()

    async def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        result = await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        return result.scalars().first()

    async def get_meal_windows(self, user_id: int) -> List[Dict]:
        result = await self.db.execute(
            select(UserPath).where(UserPath.user_id == user_id)
        )
        user_path = result.scalars().first()
        meal_windows = user_path.meal_windows if user_path and user_path.meal_windows else []
        return meal_windows

    async def get_all_user_data(self, user_id: int) -> Dict:
        return {
            "profile": await self.get_profile(user_id),
            "goal": await self.get_active_goal(user_id),
            "path": await self.get_path(user_id),
            "preferences": await self.get_preferences(user_id)
        }
