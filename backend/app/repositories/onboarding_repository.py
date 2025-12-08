"""
Onboarding Repository

Handles database operations for user onboarding data.
"""

from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.models.database import UserProfile, UserGoal, UserPath, UserPreference, User
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository


class OnboardingRepository(IOnboardingRepository):
    """
    Repository for onboarding data access.

    Handles CRUD operations for user profile, goal, path, and preference data.
    """

    def __init__(self, db: Session):
        """
        Initialize onboarding repository.

        Args:
            db: Database session
        """
        self.db = db

    # ===== UserProfile Operations =====

    def get_profile(self, user_id: int) -> Optional[UserProfile]:
        """
        Get user profile.

        EXTRACTED FROM: onboarding.py (service):125, 148, 221

        Args:
            user_id: User ID

        Returns:
            UserProfile if found, None otherwise
        """
        return self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

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
        profile = self.get_profile(user_id)
        if not profile:
            profile = UserProfile(user_id=user_id)

        # Update profile fields
        for key, value in profile_data.items():
            setattr(profile, key, value)

        if not profile.id:
            self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)

        return profile

    def update_profile_goal_calories(self, user_id: int, goal_calories: float) -> None:
        """
        Update profile's goal_calories field.

        EXTRACTED FROM: onboarding.py (service):159

        Args:
            user_id: User ID
            goal_calories: Calculated goal calories
        """
        profile = self.get_profile(user_id)
        if profile:
            profile.goal_calories = goal_calories
            self.db.commit()

    # ===== UserGoal Operations =====

    def get_goal(self, user_id: int) -> Optional[UserGoal]:
        """
        Get user goal.

        EXTRACTED FROM: onboarding.py (service):166, 222

        Args:
            user_id: User ID

        Returns:
            UserGoal if found, None otherwise
        """
        return self.db.query(UserGoal).filter(UserGoal.user_id == user_id).first()

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
        goal = self.get_goal(user_id)
        if not goal:
            goal = UserGoal(user_id=user_id)

        for key, value in goal_data.items():
            setattr(goal, key, value)

        if not goal.id:
            self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)

        return goal

    # ===== UserPath Operations =====

    def get_path(self, user_id: int) -> Optional[UserPath]:
        """
        Get user path.

        EXTRACTED FROM: onboarding.py (service):187, 223

        Args:
            user_id: User ID

        Returns:
            UserPath if found, None otherwise
        """
        return self.db.query(UserPath).filter(UserPath.user_id == user_id).first()

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
        path = self.get_path(user_id)
        if not path:
            path = UserPath(user_id=user_id)

        path.path_type = path_type
        path.meal_windows = meal_windows
        path.meals_per_day = meals_per_day

        if not path.id:
            self.db.add(path)
        self.db.commit()
        self.db.refresh(path)

        return path

    # ===== UserPreference Operations =====

    def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        """
        Get user preferences.

        Args:
            user_id: User ID

        Returns:
            UserPreference if found, None otherwise
        """
        return self.db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

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
        preferences = self.get_preferences(user_id)
        if not preferences:
            preferences = UserPreference(user_id=user_id)

        for key, value in pref_data.items():
            setattr(preferences, key, value)

        if not preferences.id:
            self.db.add(preferences)
        self.db.commit()
        self.db.refresh(preferences)

        return preferences

    # ===== User Onboarding Tracking Operations =====

    def update_user_onboarding_step(self, user_id: int, step_updates: dict) -> None:
        """
        Update user's onboarding tracking fields.

        EXTRACTED FROM: onboarding.py (API):43-48, 83-85, 123-125, 164-167

        Args:
            user_id: User ID
            step_updates: Dict with fields to update (e.g., {"basic_info_completed": True, "onboarding_current_step": 2})
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            for key, value in step_updates.items():
                setattr(user, key, value)
            self.db.commit()