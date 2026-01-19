"""
User Profile Repository Implementation

PostgreSQL implementation of user profile data access.

Consolidates queries from:
- constraint_builder_service.py:47-50
- dependencies.py:217-218
- final_meal_optimizer.py:885-888
- And 10+ other services
"""

import logging
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference

logger = logging.getLogger(__name__)


class UserProfileRepository(IUserProfileRepository):
    """
    PostgreSQL implementation of user profile repository.

    Consolidates user profile-related queries from across the codebase.
    """

    def __init__(self, db: Session):
        """
        Initialize repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    async def get_profile(self, user_id: int) -> Optional[UserProfile]:
        """
        Get user profile by user ID.

        COPY-PASTED QUERY FROM: constraint_builder_service.py:47

        Args:
            user_id: User ID

        Returns:
            UserProfile if found, None otherwise
        """
        return self.db.query(UserProfile).filter_by(user_id=user_id).first()

    async def get_active_goal(self, user_id: int) -> Optional[UserGoal]:
        """
        Get active user goal by user ID.

        COPY-PASTED QUERY FROM: constraint_builder_service.py:48

        Args:
            user_id: User ID

        Returns:
            Active UserGoal if found (where is_active=True), None otherwise
        """
        return self.db.query(UserGoal).filter_by(
            user_id=user_id,
            is_active=True
        ).first()

    async def get_path(self, user_id: int) -> Optional[UserPath]:
        """
        Get user path (meal plan settings) by user ID.

        COPY-PASTED QUERY FROM: constraint_builder_service.py:49

        Args:
            user_id: User ID

        Returns:
            UserPath if found, None otherwise
        """
        return self.db.query(UserPath).filter_by(user_id=user_id).first()

    async def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        """
        Get user dietary preferences by user ID.

        COPY-PASTED QUERY FROM: constraint_builder_service.py:50

        Args:
            user_id: User ID

        Returns:
            UserPreference if found, None otherwise
        """
        return self.db.query(UserPreference).filter_by(user_id=user_id).first()

    async def get_meal_windows(self, user_id: int) -> List[Dict]:
        """
        Get user's meal timing windows.

        COPY-PASTED LOGIC FROM: dependencies.py:217-218

        Convenience method that extracts meal_windows from UserPath.
        Returns empty list if UserPath not found or meal_windows is None.

        Args:
            user_id: User ID

        Returns:
            List of meal window dicts, e.g.:
            [
                {"meal": "breakfast", "start": "08:00", "end": "09:00"},
                {"meal": "lunch", "start": "12:00", "end": "13:00"},
                {"meal": "dinner", "start": "19:00", "end": "20:00"}
            ]
            Empty list if not found
        """
        # COPY-PASTED FROM dependencies.py:217-218 - NO CHANGES
        user_path = self.db.query(UserPath).filter_by(user_id=user_id).first()
        meal_windows = user_path.meal_windows if user_path and user_path.meal_windows else []
        return meal_windows

    async def get_all_user_data(self, user_id: int) -> Dict:
        """
        Get all user profile data in one operation.

        Fetches profile, goal, path, and preferences.
        This method exists for performance when all data is needed.

        REPLACES PATTERN FROM: constraint_builder_service.py:47-50
        (4 separate queries → 1 method call)

        Args:
            user_id: User ID

        Returns:
            Dict with keys:
            {
                "profile": UserProfile | None,
                "goal": UserGoal | None,
                "path": UserPath | None,
                "preferences": UserPreference | None
            }
        """
        # NOTE: Currently implemented as 4 separate queries for simplicity.
        # Could be optimized with joins later without changing interface.
        return {
            "profile": await self.get_profile(user_id),
            "goal": await self.get_active_goal(user_id),
            "path": await self.get_path(user_id),
            "preferences": await self.get_preferences(user_id)
        }
