import logging
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference

logger = logging.getLogger(__name__)


class UserProfileRepository(IUserProfileRepository):
    def __init__(self, db: Session):
        self.db = db

    async def get_profile(self, user_id: int) -> Optional[UserProfile]:
        return self.db.query(UserProfile).filter_by(user_id=user_id).first()

    async def get_active_goal(self, user_id: int) -> Optional[UserGoal]:
        return self.db.query(UserGoal).filter_by(
            user_id=user_id,
            is_active=True
        ).first()

    async def get_path(self, user_id: int) -> Optional[UserPath]:
        return self.db.query(UserPath).filter_by(user_id=user_id).first()

    async def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        return self.db.query(UserPreference).filter_by(user_id=user_id).first()

    async def get_meal_windows(self, user_id: int) -> List[Dict]:
        user_path = self.db.query(UserPath).filter_by(user_id=user_id).first()
        meal_windows = user_path.meal_windows if user_path and user_path.meal_windows else []
        return meal_windows

    async def get_all_user_data(self, user_id: int) -> Dict:
        return {
            "profile": await self.get_profile(user_id),
            "goal": await self.get_active_goal(user_id),
            "path": await self.get_path(user_id),
            "preferences": await self.get_preferences(user_id)
        }
