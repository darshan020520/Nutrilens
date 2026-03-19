from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime

from app.models.database import UserProfile, UserGoal, UserPath, UserPreference, User
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository


class OnboardingRepository(IOnboardingRepository):

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, user_id: int) -> Optional[UserProfile]:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalars().first()

    async def create_or_update_profile(self, user_id: int, profile_data: dict) -> UserProfile:
        profile = await self.get_profile(user_id)
        if not profile:
            profile = UserProfile(user_id=user_id)

        for key, value in profile_data.items():
            setattr(profile, key, value)

        if not profile.id:
            self.db.add(profile)
        await self.db.commit()
        await self.db.refresh(profile)

        return profile

    async def update_profile_goal_calories(self, user_id: int, goal_calories: float) -> None:
        profile = await self.get_profile(user_id)
        if profile:
            profile.goal_calories = goal_calories
            await self.db.commit()

    async def get_goal(self, user_id: int) -> Optional[UserGoal]:
        result = await self.db.execute(
            select(UserGoal).where(UserGoal.user_id == user_id)
        )
        return result.scalars().first()

    async def create_or_update_goal(self, user_id: int, goal_data: dict) -> UserGoal:
        goal = await self.get_goal(user_id)
        if not goal:
            goal = UserGoal(user_id=user_id)

        for key, value in goal_data.items():
            setattr(goal, key, value)

        if not goal.id:
            self.db.add(goal)
        await self.db.commit()
        await self.db.refresh(goal)

        return goal

    async def get_path(self, user_id: int) -> Optional[UserPath]:
        result = await self.db.execute(
            select(UserPath).where(UserPath.user_id == user_id)
        )
        return result.scalars().first()

    async def create_or_update_path(self, user_id: int, path_type: str, meal_windows: list, meals_per_day: int) -> UserPath:
        path = await self.get_path(user_id)
        if not path:
            path = UserPath(user_id=user_id)

        path.path_type = path_type
        path.meal_windows = meal_windows
        path.meals_per_day = meals_per_day

        if not path.id:
            self.db.add(path)
        await self.db.commit()
        await self.db.refresh(path)

        return path

    async def get_preferences(self, user_id: int) -> Optional[UserPreference]:
        result = await self.db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        return result.scalars().first()

    async def create_or_update_preferences(self, user_id: int, pref_data: dict) -> UserPreference:
        preferences = await self.get_preferences(user_id)
        if not preferences:
            preferences = UserPreference(user_id=user_id)

        for key, value in pref_data.items():
            setattr(preferences, key, value)

        if not preferences.id:
            self.db.add(preferences)
        await self.db.commit()
        await self.db.refresh(preferences)

        return preferences

    async def update_user_onboarding_step(self, user_id: int, step_updates: dict) -> None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if user:
            for key, value in step_updates.items():
                setattr(user, key, value)
            await self.db.commit()
