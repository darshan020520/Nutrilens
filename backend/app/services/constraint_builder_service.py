"""
Constraint Builder Service

Service for building optimization constraints from user profile.

ALL CODE COPY-PASTED FROM planning_agent.py:839-884 - ZERO LOGIC CHANGES
"""

import logging

from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.services.final_meal_optimizer import OptimizationConstraints

logger = logging.getLogger(__name__)


class ConstraintBuilderService:
    """
    Service for building optimization constraints from user data.

    BUSINESS LOGIC COPY-PASTED FROM: planning_agent.py:839-884
    """

    def __init__(self, user_profile_repo: IUserProfileRepository):
        """
        Initialize constraint builder service.

        Args:
            user_profile_repo: User profile repository
        """
        self.user_profile_repo = user_profile_repo

    async def build_constraints(self, user_id: int) -> OptimizationConstraints:
        """
        Build optimization constraints from user profile.

        EXACT COPY-PASTE FROM: planning_agent.py:839-884

        Args:
            user_id: User ID

        Returns:
            Optimization constraints
        """
        # REFACTORED: Use repository instead of direct DB queries
        # Original: planning_agent.py:841-844 (4 direct DB queries)
        profile = await self.user_profile_repo.get_profile(user_id)
        goal = await self.user_profile_repo.get_active_goal(user_id)
        path = await self.user_profile_repo.get_path(user_id)
        preferences = await self.user_profile_repo.get_preferences(user_id)

        # COPY-PASTED FROM planning_agent.py:846-854 - NO CHANGES
        # Default values if no profile
        if not profile or not profile.goal_calories:
            return OptimizationConstraints(
                daily_calories_min=1800,
                daily_calories_max=2200,
                daily_protein_min=120,
                meals_per_day=3,
                max_recipe_repeat_in_days=2
            )

        # COPY-PASTED FROM planning_agent.py:856-864 - NO CHANGES
        # Get macro ratios from UserGoal.macro_targets JSON field
        if goal and goal.macro_targets:
            protein_ratio = goal.macro_targets.get('protein', 0.30)
            carb_ratio = goal.macro_targets.get('carbs', 0.40)
            fat_ratio = goal.macro_targets.get('fat', 0.30)
        else:
            protein_ratio = 0.30
            carb_ratio = 0.40
            fat_ratio = 0.30

        # COPY-PASTED FROM planning_agent.py:866-869 - NO CHANGES
        # Calculate gram amounts from ratios
        daily_protein_g = (profile.goal_calories * protein_ratio) / 4
        daily_carbs_g = (profile.goal_calories * carb_ratio) / 4
        daily_fat_g = (profile.goal_calories * fat_ratio) / 9

        # COPY-PASTED FROM planning_agent.py:871-884 - NO CHANGES
        # Build constraints with actual data
        return OptimizationConstraints(
            daily_calories_min=profile.goal_calories * 0.95,
            daily_calories_max=profile.goal_calories * 1.05,
            daily_protein_min=daily_protein_g * 0.9,
            daily_carbs_min=daily_carbs_g * 0.8,
            daily_carbs_max=daily_carbs_g * 1.2,
            daily_fat_min=daily_fat_g * 0.8,
            daily_fat_max=daily_fat_g * 1.2,
            meals_per_day=path.meals_per_day if path else 3,
            max_recipe_repeat_in_days=2,
            dietary_restrictions=[preferences.dietary_type.value] if preferences and preferences.dietary_type else [],
            allergens=preferences.allergies if preferences and preferences.allergies else []
        )
