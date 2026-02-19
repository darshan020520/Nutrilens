"""
External Meal Service - Business logic for external meal estimation and logging.

This service handles:
- LLM-based nutrition estimation for external meals
- Logging external meals (replacing planned meals or adding new ones)
- Generating insights and recommendations for external meal logging
- Retrieving remaining meals for potential adjustment

Extracted from: backend/app/api/tracking.py:854-1095
"""

from typing import Dict, List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func

from app.models.database import MealLog, Recipe, User
from app.repositories.interfaces import ITrackingRepository, IConsumptionAnalyticsRepository
from app.core.llm_orchestrator import LLMOrchestrator
from app.core.exceptions import TokenBudgetExceeded
from app.schemas.normaliser import NutritionEstimateResult
from app.core.ist_datetime import now_ist_naive, today_ist

import logging

logger = logging.getLogger(__name__)


class ExternalMealService:
    """
    Service for handling external meal estimation and logging.

    External meals are meals consumed outside of planned recipes (e.g., restaurant meals,
    eating out, etc.) that require nutrition estimation.
    """

    def __init__(
        self,
        tracking_repo: ITrackingRepository,
        analytics_repo: IConsumptionAnalyticsRepository,
        llm_orchestrator: LLMOrchestrator
    ):
        """
        Initialize ExternalMealService with required repositories.

        Args:
            tracking_repo: Repository for meal log data access
            analytics_repo: Repository for consumption analytics queries
        """
        self.tracking_repo = tracking_repo
        self.analytics_repo = analytics_repo
        self.llm_orchestrator = llm_orchestrator

    async def estimate_nutrition(
        self,
        user_id: int,
        dish_name: str,
        portion_size: str,
        restaurant_name: Optional[str] = None,
        cuisine_type: Optional[str] = None
    ) -> Dict:
        """
        Get LLM-based nutrition estimate for an external meal.

        This method:
        1. Takes dish description and portion size
        2. Uses OpenAI to estimate macronutrients
        3. Returns estimate with confidence score
        4. Does NOT create any database entries

        Source: backend/app/api/tracking.py:854-904

        Args:
            dish_name: Name of the dish (e.g., "Chicken Tikka Masala")
            portion_size: Portion description (e.g., "large plate", "2 cups")
            restaurant_name: Optional restaurant name for better estimation
            cuisine_type: Optional cuisine type (e.g., "Indian", "Italian")

        Returns:
            Dict: {
                "calories": 650,
                "protein_g": 35.0,
                "carbs_g": 45.0,
                "fat_g": 30.0,
                "fiber_g": 5.0,
                "confidence": "high",
                "reasoning": "Explanation of estimation...",
                "dish_name": "Chicken Tikka Masala",
                "portion_size": "large plate",
                "estimation_method": "llm"
            }

        Raises:
            ValueError: If dish_name or portion_size is empty
            Exception: If LLM estimation fails
        """
        try:
            # Validate inputs
            if not dish_name or not dish_name.strip():
                raise ValueError("dish_name is required")
            if not portion_size or not portion_size.strip():
                raise ValueError("portion_size is required")

            # Get LLM estimation via centralized orchestrator
            logger.info(f"Estimating nutrition for: {dish_name} ({portion_size})")
            result = await self.llm_orchestrator.run(
                user_id=user_id,
                slug="estimate_nutrition",
                variables={
                    "dish_name": dish_name,
                    "portion_size": portion_size,
                    "restaurant_name": restaurant_name or "Not specified",
                    "cuisine_type": cuisine_type or "Not specified"
                },
                response_model=NutritionEstimateResult
            )

            # Convert Pydantic model to dict and add extra fields
            estimation = result.model_dump()
            estimation["dish_name"] = dish_name
            estimation["portion_size"] = portion_size
            estimation["estimation_method"] = "llm"

            logger.info(f"Nutrition estimation complete: {estimation['calories']} calories (confidence: {estimation['confidence']})")

            return estimation

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error estimating external meal nutrition: {e}")
            raise Exception(f"Failed to estimate meal nutrition: {str(e)}")

    async def log_external_meal(
        self,
        user_id: int,
        meal_data: Dict,
        meal_log_id_to_replace: Optional[int] = None,
        meal_type: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict:
        """
        Log an external meal (restaurant, eating out, etc.).

        This method can:
        1. Replace a planned meal with external meal data
        2. Add a new external meal without replacing anything
        3. Update daily consumption totals
        4. Provide insights and recommendations

        Source: backend/app/api/tracking.py:907-1095

        Args:
            user_id: User ID
            meal_data: External meal nutrition data (dict with calories, protein_g, etc.)
            meal_log_id_to_replace: Optional ID of planned meal to replace
            meal_type: Required if not replacing (breakfast, lunch, dinner, snack)
            notes: Optional notes about the meal

        Returns:
            Dict: {
                "success": True,
                "meal_log_id": 123,
                "meal_type": "lunch",
                "dish_name": "Chicken Tikka Masala",
                "restaurant_name": "Indian Palace",
                "consumed_at": "2025-11-25T12:30:00",
                "macros": {"calories": 650, "protein_g": 35, ...},
                "replaced_meal": True,
                "original_recipe": "Grilled Chicken Salad",
                "updated_daily_totals": {...},
                "remaining_calories": 850,
                "remaining_meals_today": [...],
                "insights": ["Replaced planned 'Grilled Chicken' with external meal"],
                "recommendations": ["Consider lighter options for remaining meals"]
            }

        Raises:
            ValueError: If meal_log_id_to_replace not found or invalid
            ValueError: If meal_type not provided when adding new meal
            ValueError: If trying to log already consumed meal
        """
        try:
            # Validate meal_data
            required_fields = ["dish_name", "portion_size", "calories", "protein_g", "carbs_g", "fat_g"]
            for field in required_fields:
                if field not in meal_data:
                    raise ValueError(f"meal_data missing required field: {field}")

            consumed_at = meal_data.get("consumed_at") or now_ist_naive()

            # Build external_meal JSON data
            external_meal_data = {
                "dish_name": meal_data["dish_name"],
                "portion_size": meal_data["portion_size"],
                "restaurant_name": meal_data.get("restaurant_name"),
                "cuisine_type": meal_data.get("cuisine_type"),
                "calories": meal_data["calories"],
                "protein_g": meal_data["protein_g"],
                "carbs_g": meal_data["carbs_g"],
                "fat_g": meal_data["fat_g"],
                "fiber_g": meal_data.get("fiber_g", 0),
                "logged_at": consumed_at.isoformat() if isinstance(consumed_at, datetime) else consumed_at
            }

            replaced_meal = False
            original_recipe_name = None
            meal_log = None

            # CASE 1: Replacing an existing planned meal
            if meal_log_id_to_replace:
                meal_log = await self._replace_planned_meal(
                    user_id=user_id,
                    meal_log_id=meal_log_id_to_replace,
                    consumed_at=consumed_at,
                    external_meal_data=external_meal_data,
                    notes=notes
                )
                replaced_meal = True
                # Get original recipe name if it exists (for insights)
                if hasattr(meal_log, 'recipe') and meal_log.recipe:
                    original_recipe_name = meal_log.recipe.title

            # CASE 2: Adding new external meal
            else:
                if not meal_type:
                    raise ValueError("meal_type is required when not replacing an existing meal")

                meal_log = await self._create_external_meal(
                    user_id=user_id,
                    meal_type=meal_type,
                    consumed_at=consumed_at,
                    external_meal_data=external_meal_data,
                    notes=notes
                )

            # Get updated daily summary
            today_summary = await self.analytics_repo.get_today_summary(user_id)

            # Get remaining meals for today (for potential adjustment)
            remaining_meals = await self.get_remaining_meals_for_adjustment(
                user_id=user_id,
                target_date=today_ist()
            )

            # Generate insights and recommendations
            insights = self._generate_external_meal_insights(
                meal_data=meal_data,
                daily_summary=today_summary,
                replaced_meal=replaced_meal,
                original_recipe_name=original_recipe_name
            )

            recommendations = await self._generate_external_meal_recommendations(
                daily_summary=today_summary,
                has_remaining_meals=len(remaining_meals) > 0,
                user_id=user_id,
                dish_name=meal_data["dish_name"]
            )

            # Calculate remaining calories
            total_calories = today_summary.get("total_calories", 0)
            target_calories = today_summary.get("target_calories", 2000)
            remaining_calories = max(0, target_calories - total_calories)

            logger.info(f"External meal logged: {meal_data['dish_name']} for user {user_id}")

            return {
                "success": True,
                "meal_log_id": meal_log.id,
                "meal_type": meal_log.meal_type,
                "dish_name": meal_data["dish_name"],
                "restaurant_name": meal_data.get("restaurant_name"),
                "consumed_at": consumed_at.isoformat() if isinstance(consumed_at, datetime) else consumed_at,
                "macros": {
                    "calories": meal_data["calories"],
                    "protein_g": meal_data["protein_g"],
                    "carbs_g": meal_data["carbs_g"],
                    "fat_g": meal_data["fat_g"],
                    "fiber_g": meal_data.get("fiber_g", 0)
                },
                "replaced_meal": replaced_meal,
                "original_recipe": original_recipe_name,
                "updated_daily_totals": today_summary,
                "remaining_calories": remaining_calories,
                "remaining_meals_today": remaining_meals if remaining_meals else None,
                "insights": insights,
                "recommendations": recommendations
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error logging external meal: {e}")
            raise

    async def get_remaining_meals_for_adjustment(
        self,
        user_id: int,
        target_date: date
    ) -> List[Dict]:
        """
        Get remaining planned meals for a given date that could be adjusted/replaced.

        Source: backend/app/api/tracking.py:1017-1040

        Args:
            user_id: User ID
            target_date: Date to check (usually today)

        Returns:
            List[Dict]: List of remaining meal options:
            [
                {
                    "meal_log_id": 123,
                    "meal_type": "dinner",
                    "recipe_name": "Grilled Salmon",
                    "planned_time": "19:00",
                    "planned_calories": 450
                },
                ...
            ]
        """
        try:
            # Get all pending (not consumed, not skipped) meals for the date
            pending_meals = await self.tracking_repo.get_pending_meals(user_id, target_date)

            remaining_meal_options = []
            for meal in pending_meals:
                # Only include meals with recipes (planned meals)
                if hasattr(meal, 'recipe') and meal.recipe:
                    planned_time = meal.planned_datetime.strftime("%H:%M") if meal.planned_datetime else "00:00"
                    planned_calories = meal.recipe.macros_per_serving.get("calories", 0) if hasattr(meal.recipe, 'macros_per_serving') else 0

                    remaining_meal_options.append({
                        "meal_log_id": meal.id,
                        "meal_type": meal.meal_type,
                        "recipe_name": meal.recipe.title,
                        "planned_time": planned_time,
                        "planned_calories": planned_calories
                    })

            return remaining_meal_options

        except Exception as e:
            logger.error(f"Error getting remaining meals: {e}")
            raise

    # ===== Private Helper Methods =====

    async def _replace_planned_meal(
        self,
        user_id: int,
        meal_log_id: int,
        consumed_at: datetime,
        external_meal_data: Dict,
        notes: Optional[str] = None
    ) -> MealLog:
        """
        Replace a planned meal with external meal data.

        Source: backend/app/api/tracking.py:953-985

        Args:
            user_id: User ID
            meal_log_id: ID of meal log to replace
            consumed_at: Consumption timestamp
            external_meal_data: External meal nutrition data
            notes: Optional notes

        Returns:
            MealLog: Updated meal log

        Raises:
            ValueError: If meal not found or already consumed
        """
        # Use repository to replace planned meal with external meal
        meal_log = await self.tracking_repo.replace_planned_with_external(
            meal_log_id=meal_log_id,
            user_id=user_id,
            consumed_at=consumed_at,
            external_meal_data=external_meal_data
        )

        # Update notes if provided (repository method doesn't handle notes)
        if notes and hasattr(meal_log, 'notes'):
            meal_log.notes = notes
            # Note: Actual update would happen via repository in production
            # For now, this is just setting the attribute

        return meal_log

    async def _create_external_meal(
        self,
        user_id: int,
        meal_type: str,
        consumed_at: datetime,
        external_meal_data: Dict,
        notes: Optional[str] = None
    ) -> MealLog:
        """
        Create a new external meal log entry.

        Source: backend/app/api/tracking.py:987-1012

        Args:
            user_id: User ID
            meal_type: Type of meal (breakfast, lunch, dinner, snack)
            consumed_at: Consumption timestamp
            external_meal_data: External meal nutrition data
            notes: Optional notes

        Returns:
            MealLog: Created meal log
        """
        # Use repository to create external meal log
        meal_log = await self.tracking_repo.create_external_meal_log(
            user_id=user_id,
            meal_type=meal_type,
            consumed_at=consumed_at,
            external_meal_data=external_meal_data
        )

        # Update notes if provided
        if notes and hasattr(meal_log, 'notes'):
            meal_log.notes = notes

        return meal_log

    def _generate_external_meal_insights(
        self,
        meal_data: Dict,
        daily_summary: Dict,
        replaced_meal: bool,
        original_recipe_name: Optional[str] = None
    ) -> List[str]:
        """
        Generate insights about the logged external meal.

        Source: backend/app/api/tracking.py:1042-1058

        Args:
            meal_data: External meal data
            daily_summary: Today's consumption summary
            replaced_meal: Whether this replaced a planned meal
            original_recipe_name: Name of replaced recipe (if applicable)

        Returns:
            List[str]: Insights about the external meal logging
        """
        insights = []

        total_calories = daily_summary.get("total_calories", 0)
        target_calories = daily_summary.get("target_calories", 2000)

        # Calorie tracking insights
        if total_calories > target_calories * 1.1:
            over_amount = int(total_calories - target_calories)
            insights.append(f"You're {over_amount} calories over your daily target")
        elif total_calories < target_calories * 0.9:
            remaining = int(target_calories - total_calories)
            insights.append(f"You have {remaining} calories remaining for today")
        else:
            insights.append("You're within your calorie target - great job!")

        # Replacement insights
        if replaced_meal and original_recipe_name:
            insights.append(f"Replaced planned '{original_recipe_name}' with external meal")

        # Meal-specific insights
        calories = meal_data.get("calories", 0)
        if calories > 800:
            insights.append(f"This was a high-calorie meal ({calories} calories)")
        elif calories < 300:
            insights.append(f"This was a light meal ({calories} calories)")

        return insights

    async def _generate_external_meal_recommendations(
        self,
        daily_summary: Dict,
        has_remaining_meals: bool,
        user_id: int = 0,
        dish_name: str = ""
    ) -> List[str]:
        """
        Generate recommendations based on external meal logging.
        Uses AI with hardcoded fallback.
        """
        total_calories = daily_summary.get("total_calories", 0)
        target_calories = daily_summary.get("target_calories", 2000)
        protein_g = daily_summary.get("total_macros", {}).get("protein_g", 0)
        target_protein = daily_summary.get("target_macros", {}).get("protein_g", 150)

        # Try AI recommendations
        if self.llm_orchestrator and user_id:
            try:
                from app.schemas.recommendation import RecommendationResponse
                result = await self.llm_orchestrator.run(
                    user_id=user_id,
                    slug="external_meal_recommendations",
                    variables={
                        "dish_name": dish_name,
                        "total_calories": int(total_calories),
                        "target_calories": int(target_calories),
                        "protein_g": round(protein_g, 1),
                        "target_protein": round(target_protein, 1),
                        "has_remaining_meals": "Yes" if has_remaining_meals else "No",
                    },
                    response_model=RecommendationResponse
                )
                return result.recommendations
            except (TokenBudgetExceeded, Exception) as e:
                logger.warning(f"AI external meal recommendations unavailable ({type(e).__name__}), using fallback")

        # Fallback: hardcoded logic
        recommendations = []

        if total_calories > target_calories * 1.1 and has_remaining_meals:
            recommendations.append("Consider lighter options for remaining meals today")
            recommendations.append("You might want to skip a meal or have a small snack instead")
        elif total_calories < target_calories * 0.7:
            recommendations.append("You have plenty of room for more meals today")
            recommendations.append("Make sure to eat enough to meet your nutrition goals")
        elif total_calories >= target_calories * 0.9 and total_calories <= target_calories * 1.1:
            recommendations.append("You're on track with your calorie goals!")
            if has_remaining_meals:
                recommendations.append("Stick to your planned meals for the rest of the day")

        if protein_g < target_protein * 0.5:
            recommendations.append("Focus on protein-rich foods for remaining meals")

        return recommendations
