"""
User Profile Repository Interface

Defines contract for user profile-related data access.

Consolidates access to:
- UserProfile (demographics, BMR, TDEE, goal_calories)
- UserGoal (goal_type, macro_targets, is_active)
- UserPath (path_type, meals_per_day, meal_windows)
- UserPreference (dietary_type, allergies, cuisine_preferences)
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference


class IUserProfileRepository(ABC):
    """
    Interface for user profile data access.

    All database queries for user profile-related models go through this interface.
    This consolidates UserProfile, UserGoal, UserPath, and UserPreference queries.
    """

    @abstractmethod
    async def get_profile(self, user_id: int) -> Optional[UserProfile]:
        """
        Get user profile by user ID.

        Args:
            user_id: User ID

        Returns:
            UserProfile if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_active_goal(self, user_id: int) -> Optional[UserGoal]:
        """
        Get active user goal by user ID.

        Args:
            user_id: User ID

        Returns:
            Active UserGoal if found (where is_active=True), None otherwise
        """
        pass

    @abstractmethod
    async def get_path(self, user_id: int) -> Optional[UserPath]:
        """
        Get user path (meal plan settings) by user ID.

        Args:
            user_id: User ID

        Returns:
            UserPath if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        """
        Get user dietary preferences by user ID.

        Args:
            user_id: User ID

        Returns:
            UserPreference if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_meal_windows(self, user_id: int) -> List[Dict]:
        """
        Get user's meal timing windows.

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
        pass

    @abstractmethod
    async def get_all_user_data(self, user_id: int) -> Dict:
        """
        Get all user profile data in one query (optimization).

        Fetches profile, goal, path, and preferences in a single operation.
        Useful when you need all user data at once (e.g., constraint building).

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
        pass
