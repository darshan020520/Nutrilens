from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.models.database import UserProfile, UserGoal, UserPath, UserPreference, User
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository


class OnboardingRepository(IOnboardingRepository):


    def __init__(self, db: Session):
        self.db = db


    def get_profile(self, user_id: int) -> Optional[UserProfile]:
        return self.db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    def create_or_update_profile(self, user_id: int, profile_data: dict) -> UserProfile:
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
        profile = self.get_profile(user_id)
        if profile:
            profile.goal_calories = goal_calories
            self.db.commit()



    def get_goal(self, user_id: int) -> Optional[UserGoal]:
        return self.db.query(UserGoal).filter(UserGoal.user_id == user_id).first()

    def create_or_update_goal(self, user_id: int, goal_data: dict) -> UserGoal:
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


    def get_path(self, user_id: int) -> Optional[UserPath]:
        return self.db.query(UserPath).filter(UserPath.user_id == user_id).first()

    def create_or_update_path(self, user_id: int, path_type: str, meal_windows: list, meals_per_day: int) -> UserPath:
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


    def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        return self.db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

    def create_or_update_preferences(self, user_id: int, pref_data: dict) -> UserPreference:
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


    def update_user_onboarding_step(self, user_id: int, step_updates: dict) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            for key, value in step_updates.items():
                setattr(user, key, value)
            self.db.commit()