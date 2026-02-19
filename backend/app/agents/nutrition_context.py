"""
Nutrition Context Builder - Clean Architecture Implementation

This module provides a centralized context builder that gathers all user nutrition
data using the repository pattern and dependency injection.

Design Principles:
- Accept dependencies via constructor (DI pattern)
- Use repositories for data access (no direct db.query())
- Async methods to support V2 services
- Factory function for instantiation

Author: NutriLens AI Team
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
import json
import logging

from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.repositories.interfaces.tracking_repository import ITrackingRepository
from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.repositories.interfaces.consumption_analytics_repository import IConsumptionAnalyticsRepository
from app.services.onboarding import OnboardingService

logger = logging.getLogger(__name__)


class UserContext:
    """
    Context builder that gathers user data using clean architecture patterns.

    Architecture:
    - Accepts repositories via constructor (DI pattern)
    - Uses repositories for all data access
    - Async methods for V2 service compatibility
    - No direct database queries

    Usage:
        # Via factory function (recommended)
        context = create_user_context(db, user_id)
        data = await context.build_context()

        # Or with explicit DI
        context = UserContext(
            user_id=user_id,
            user_profile_repo=user_profile_repo,
            tracking_repo=tracking_repo,
            ...
        )
    """

    def __init__(
        self,
        user_id: int,
        user_profile_repo: IUserProfileRepository,
        tracking_repo: ITrackingRepository,
        inventory_repo: IInventoryRepository,
        recipe_repo: IRecipeRepository,
        analytics_repo: IConsumptionAnalyticsRepository,
        onboarding_service: OnboardingService
    ):
        """
        Initialize context builder with injected dependencies.

        Args:
            user_id: User ID to build context for
            user_profile_repo: Repository for user profile data
            tracking_repo: Repository for meal tracking data
            inventory_repo: Repository for inventory data
            recipe_repo: Repository for recipe data
            analytics_repo: Repository for consumption analytics
            onboarding_service: Service for nutritional calculations
        """
        self.user_id = user_id
        self.user_profile_repo = user_profile_repo
        self.tracking_repo = tracking_repo
        self.inventory_repo = inventory_repo
        self.recipe_repo = recipe_repo
        self.analytics_repo = analytics_repo
        self.onboarding_service = onboarding_service

    async def build_context(self, minimal: bool = False) -> Dict[str, Any]:
        """
        Build complete user context using repositories.

        Args:
            minimal: If True, only include essential data (faster)

        Returns:
            Dict containing all user context data
        """
        try:
            # Essential context (always included)
            context = {
                "user_id": self.user_id,
                "timestamp": datetime.utcnow().isoformat(),
                "profile": await self._get_profile_basic(),
                "targets": await self._get_targets(),
                "today": await self._get_today_consumption(),
                "inventory_summary": await self._get_inventory_summary()
            }

            # Extended context (optional for performance)
            if not minimal:
                context.update({
                    "week": await self._get_weekly_stats(),
                    "preferences": await self._get_preferences(),
                    "history": await self._get_meal_history(days=7),
                    "upcoming": await self._get_upcoming_meals()
                })

            return context

        except Exception as e:
            logger.error(f"Error building context for user {self.user_id}: {str(e)}")
            return {
                "user_id": self.user_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def _get_profile_basic(self) -> Dict[str, Any]:
        """
        Get basic user profile using repository.

        Uses: IUserProfileRepository.get_profile(), get_active_goal()
        """
        try:
            profile = await self.user_profile_repo.get_profile(self.user_id)
            goal = await self.user_profile_repo.get_active_goal(self.user_id)

            if not profile:
                return {"error": "Profile not found"}

            return {
                "age": profile.age,
                "weight_kg": profile.weight_kg,
                "height_cm": profile.height_cm,
                "sex": profile.sex,
                "goal_type": goal.goal_type.value if goal else "general_health",
                "activity_level": profile.activity_level.value if profile.activity_level else "sedentary"
            }
        except Exception as e:
            logger.error(f"Error getting profile: {str(e)}")
            return {"error": str(e)}

    async def _get_targets(self) -> Dict[str, float]:
        """
        Get daily nutritional targets using OnboardingService.

        Uses: OnboardingService.get_calculated_targets()
        """
        try:
            result = await self.onboarding_service.get_calculated_targets(self.user_id)

            goal_calories = result.get("goal_calories", 2000)
            macro_targets = result.get("macro_targets", {"protein": 0.3, "carbs": 0.4, "fat": 0.3})

            return {
                "calories": goal_calories,
                "protein_g": (goal_calories * macro_targets.get("protein", 0.3)) / 4,
                "carbs_g": (goal_calories * macro_targets.get("carbs", 0.4)) / 4,
                "fat_g": (goal_calories * macro_targets.get("fat", 0.3)) / 9,
                "fiber_g": result.get("fiber_g", 25)
            }
        except Exception as e:
            logger.error(f"Error getting targets: {str(e)}")
            return {
                "calories": 2000,
                "protein_g": 100,
                "carbs_g": 250,
                "fat_g": 65,
                "fiber_g": 25
            }

    async def _get_today_consumption(self) -> Dict[str, Any]:
        """
        Get today's consumption summary using analytics repository.

        Uses: IConsumptionAnalyticsRepository.get_today_summary()
        """
        try:
            summary = await self.analytics_repo.get_today_summary(self.user_id)

            if not summary:
                return self._empty_consumption()

            return {
                "consumed": {
                    "calories": summary.get("total_calories", 0),
                    "protein_g": summary.get("total_protein_g", 0),
                    "carbs_g": summary.get("total_carbs_g", 0),
                    "fat_g": summary.get("total_fat_g", 0)
                },
                "remaining": {
                    "calories": summary.get("remaining_calories", 0),
                    "protein_g": summary.get("remaining_protein_g", 0),
                    "carbs_g": summary.get("remaining_carbs_g", 0),
                    "fat_g": summary.get("remaining_fat_g", 0)
                },
                "meals_consumed": summary.get("meals_consumed", 0),
                "meals_pending": summary.get("meals_pending", 0),
                "compliance_rate": summary.get("compliance_rate", 0)
            }
        except Exception as e:
            logger.error(f"Error getting today's consumption: {str(e)}")
            return self._empty_consumption()

    def _empty_consumption(self) -> Dict[str, Any]:
        """Return empty consumption data structure."""
        return {
            "consumed": {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0},
            "remaining": {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0},
            "meals_consumed": 0,
            "meals_pending": 0,
            "compliance_rate": 0
        }

    async def _get_inventory_summary(self) -> Dict[str, Any]:
        """
        Get inventory status summary using repository.

        Uses: IInventoryRepository.get_inventory_status_summary()
        """
        try:
            summary = await self.inventory_repo.get_inventory_status_summary(self.user_id)

            return {
                "total_items": summary.get("total_items", 0),
                "expiring_soon": summary.get("expiring_soon_count", 0),
                "low_stock": summary.get("low_stock_count", 0),
                "categories": summary.get("categories", {}),
                "estimated_days": summary.get("estimated_days_remaining", 0)
            }
        except Exception as e:
            logger.error(f"Error getting inventory summary: {str(e)}")
            return {
                "total_items": 0,
                "expiring_soon": 0,
                "low_stock": 0,
                "categories": {},
                "estimated_days": 0
            }

    async def _get_weekly_stats(self) -> Dict[str, Any]:
        """
        Get weekly consumption statistics using repository.

        Uses: IConsumptionAnalyticsRepository.get_consumption_trends()
        """
        try:
            trends = await self.analytics_repo.get_consumption_trends(self.user_id, days=7)

            if not trends:
                return self._empty_weekly_stats()

            return {
                "avg_calories": trends.get("avg_daily_calories", 0),
                "avg_protein": trends.get("avg_daily_protein", 0),
                "compliance_rate": trends.get("adherence_rate", 0) * 100,
                "favorite_meals": await self._get_favorite_meals(days=7),
                "meal_timing_patterns": trends.get("meal_timing_patterns", {})
            }
        except Exception as e:
            logger.error(f"Error getting weekly stats: {str(e)}")
            return self._empty_weekly_stats()

    def _empty_weekly_stats(self) -> Dict[str, Any]:
        """Return empty weekly stats structure."""
        return {
            "avg_calories": 0,
            "avg_protein": 0,
            "compliance_rate": 0,
            "favorite_meals": [],
            "meal_timing_patterns": {}
        }

    async def _get_favorite_meals(self, days: int = 7) -> List[str]:
        """Get most consumed recipes using repository."""
        try:
            most_consumed = await self.analytics_repo.get_most_consumed_recipes(
                self.user_id, days=days, limit=3
            )
            return [r.get("recipe_name", "") for r in most_consumed]
        except Exception:
            return []

    async def _get_preferences(self) -> Dict[str, Any]:
        """
        Get user preferences using repository.

        Uses: IUserProfileRepository.get_preferences()
        """
        try:
            pref = await self.user_profile_repo.get_preferences(self.user_id)

            if not pref:
                return self._empty_preferences()

            cuisines = getattr(pref, 'preferred_cuisines', None) or getattr(pref, 'cuisines', [])
            dietary = getattr(pref, 'dietary_restrictions', None) or getattr(pref, 'dietary', [])
            allergies = getattr(pref, 'allergens', None) or getattr(pref, 'allergies', [])
            spice = getattr(pref, 'spice_preference', None) or getattr(pref, 'spice_level', 'medium')

            return {
                "cuisines": cuisines if cuisines else [],
                "dietary": dietary if dietary else [],
                "allergies": allergies if allergies else [],
                "spice_level": spice if spice else "medium"
            }
        except Exception as e:
            logger.error(f"Error getting preferences: {str(e)}")
            return self._empty_preferences()

    def _empty_preferences(self) -> Dict[str, Any]:
        """Return empty preferences structure."""
        return {
            "cuisines": [],
            "dietary": [],
            "allergies": [],
            "spice_level": "medium"
        }

    async def _get_meal_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get recent meal history using repository.

        Uses: ITrackingRepository.get_consumed_meals()
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            consumed_meals = await self.tracking_repo.get_consumed_meals(
                self.user_id, start_date, end_date
            )

            meals = []
            for meal in consumed_meals[:20]:
                meals.append({
                    "meal": meal.recipe.title if meal.recipe else "Unknown",
                    "meal_type": meal.meal_type,
                    "date": str(meal.consumed_datetime.date()) if meal.consumed_datetime else "",
                    "calories": meal.recipe.macros_per_serving.get("calories", 0) if meal.recipe and meal.recipe.macros_per_serving else 0
                })

            return meals
        except Exception as e:
            logger.error(f"Error getting meal history: {str(e)}")
            return []

    async def _get_upcoming_meals(self) -> List[Dict[str, Any]]:
        """
        Get upcoming planned meals using repository.

        Uses: ITrackingRepository.get_pending_meals()
        """
        try:
            today = date.today()
            pending_meals = await self.tracking_repo.get_pending_meals(self.user_id, today)

            meals = []
            for meal in pending_meals:
                meals.append({
                    "meal_type": meal.meal_type,
                    "recipe": meal.recipe.title if meal.recipe else "No recipe",
                    "time": meal.planned_datetime.strftime("%H:%M") if meal.planned_datetime else "",
                    "calories": meal.recipe.macros_per_serving.get("calories", 0) if meal.recipe and meal.recipe.macros_per_serving else 0,
                    "protein_g": meal.recipe.macros_per_serving.get("protein_g", 0) if meal.recipe and meal.recipe.macros_per_serving else 0
                })

            return meals
        except Exception as e:
            logger.error(f"Error getting upcoming meals: {str(e)}")
            return []

    async def get_makeable_recipes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recipes user can make with current inventory.

        Uses: IInventoryRepository + IRecipeRepository
        """
        try:
            # Get user inventory
            inventory_items = await self.inventory_repo.get_all_for_user(
                user_id=self.user_id,
                include_zero_quantity=False
            )

            if not inventory_items:
                return []

            # Convert to dict for recipe matching
            user_item_quantities = {
                inv.item_id: inv.quantity_grams
                for inv in inventory_items
            }

            # Get makeable recipe candidates
            candidates = await self.recipe_repo.get_makeable_recipe_candidates(
                user_item_quantities=user_item_quantities,
                min_match_pct=80.0,
                limit=limit
            )

            # Format response
            result = []
            for candidate in candidates:
                recipe = candidate.get("recipe")
                if recipe:
                    macros = recipe.macros_per_serving or {}
                    result.append({
                        "id": recipe.id,
                        "title": recipe.title,
                        "match_percentage": candidate.get("match_percentage", 0),
                        "calories": macros.get("calories", 0),
                        "protein_g": macros.get("protein_g", 0),
                        "missing_items": candidate.get("missing_items", [])
                    })

            return result
        except Exception as e:
            logger.error(f"Error getting makeable recipes: {str(e)}")
            return []

    async def get_goal_aligned_recipes(self, count: int = 20) -> List[Dict[str, Any]]:
        """
        Get recipes aligned with user's fitness goal.

        Uses: IRecipeRepository.get_filtered_recipes()
        """
        try:
            profile = await self._get_profile_basic()
            goal_type = profile.get("goal_type", "general_health")

            # Get user preferences for filtering
            prefs = await self._get_preferences()
            allergens = prefs.get("allergies", [])

            # Use recipe repository for filtered recipes
            recipes = await self.recipe_repo.get_filtered_recipes(
                goal_type=goal_type,
                exclude_allergens=allergens if allergens else None
            )

            # Format response (limit to count)
            result = []
            for recipe in recipes[:count]:
                macros = recipe.macros_per_serving or {}
                result.append({
                    "id": recipe.id,
                    "title": recipe.title,
                    "description": recipe.description,
                    "prep_time_min": recipe.prep_time_min,
                    "calories": macros.get("calories", 0),
                    "protein_g": macros.get("protein_g", 0),
                    "carbs_g": macros.get("carbs_g", 0),
                    "fat_g": macros.get("fat_g", 0)
                })

            return result
        except Exception as e:
            logger.error(f"Error getting goal-aligned recipes: {str(e)}")
            return []

    async def to_llm_context(self) -> str:
        """
        Format context as string for LLM consumption.

        Returns:
            JSON string formatted for LLM prompts
        """
        context = await self.build_context(minimal=False)
        return json.dumps(context, indent=2)

    def __repr__(self):
        return f"<UserContext user_id={self.user_id}>"
