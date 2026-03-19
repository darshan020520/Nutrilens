from abc import ABC, abstractmethod
from typing import Optional
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference


class IOnboardingRepository(ABC):
    """
    Interface for onboarding data access.

    Provides methods for managing user onboarding data (profile, goals, paths, preferences).
    """

    # ===== UserProfile Operations =====

    @abstractmethod
    def get_profile(self, user_id: int) -> Optional[UserProfile]:
        """
        Get user profile.

        EXTRACTED FROM: onboarding.py (service):125, 148, 221

        Args:
            user_id: User ID

        Returns:
            UserProfile if found, None otherwise
        """
        pass

    @abstractmethod
    def create_or_update_profile(self, user_id: int, profile_data: dict) -> UserProfile:
        """
        Create or update user profile.

        EXTRACTED FROM: onboarding.py (service):125-139

        Args:
            user_id: User ID
            profile_data: Profile data including BMR and TDEE

        Returns:
            Created or updated UserProfile
        """
        pass

    @abstractmethod
    def update_profile_goal_calories(self, user_id: int, goal_calories: float) -> None:
        """
        Update profile's goal_calories field.

        EXTRACTED FROM: onboarding.py (service):159

        Args:
            user_id: User ID
            goal_calories: Calculated goal calories
        """
        pass

    # ===== UserGoal Operations =====

    @abstractmethod
    def get_goal(self, user_id: int) -> Optional[UserGoal]:
        """
        Get user goal.

        EXTRACTED FROM: onboarding.py (service):166, 222

        Args:
            user_id: User ID

        Returns:
            UserGoal if found, None otherwise
        """
        pass

    @abstractmethod
    def create_or_update_goal(self, user_id: int, goal_data: dict) -> UserGoal:
        """
        Create or update user goal.

        EXTRACTED FROM: onboarding.py (service):166-176

        Args:
            user_id: User ID
            goal_data: Goal data including goal_type and macro_targets

        Returns:
            Created or updated UserGoal
        """
        pass

    # ===== UserPath Operations =====

    @abstractmethod
    def get_path(self, user_id: int) -> Optional[UserPath]:
        """
        Get user path.

        EXTRACTED FROM: onboarding.py (service):187, 223

        Args:
            user_id: User ID

        Returns:
            UserPath if found, None otherwise
        """
        pass

    @abstractmethod
    def create_or_update_path(self, user_id: int, path_type: str, meal_windows: list, meals_per_day: int) -> UserPath:
        """
        Create or update user path.

        EXTRACTED FROM: onboarding.py (service):187-198

        Args:
            user_id: User ID
            path_type: Path type (e.g., IF_16_8, TRADITIONAL)
            meal_windows: List of meal timing windows
            meals_per_day: Number of meals per day

        Returns:
            Created or updated UserPath
        """
        pass

    # ===== UserPreference Operations =====

    @abstractmethod
    def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        """
        Get user preferences.

        Args:
            user_id: User ID

        Returns:
            UserPreference if found, None otherwise
        """
        pass

    @abstractmethod
    def create_or_update_preferences(self, user_id: int, pref_data: dict) -> UserPreference:
        """
        Create or update user preferences.

        EXTRACTED FROM: onboarding.py (service):205-215

        Args:
            user_id: User ID
            pref_data: Preference data (dietary_type, allergies, etc.)

        Returns:
            Created or updated UserPreference
        """
        pass


    @abstractmethod
    def update_user_onboarding_step(self, user_id: int, step_updates: dict) -> None:

        pass