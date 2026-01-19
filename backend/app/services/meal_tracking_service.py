"""
Meal Tracking Service

Business logic for meal tracking operations.
Extracted from TrackingAgent to follow clean service pattern.
Uses repositories for all data access.
"""

import logging
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple

from app.repositories.interfaces.tracking_repository import ITrackingRepository
from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.repositories.interfaces.consumption_analytics_repository import IConsumptionAnalyticsRepository
from app.services.notification_service import NotificationService, NotificationPriority
from app.models.database import MealLog, User

logger = logging.getLogger(__name__)


class MealTrackingService:
    """
    Service for meal tracking business logic.

    Responsibilities:
    - Meal logging with validation
    - Meal skipping with adherence analysis
    - Daily summary generation
    - Consumption history analysis
    - Insights and recommendations

    NO database access - uses repositories only.
    """

    def __init__(
        self,
        tracking_repo: ITrackingRepository,
        inventory_repo: IInventoryRepository,
        analytics_repo: IConsumptionAnalyticsRepository,
        notification_service: NotificationService
    ):
        """
        Initialize meal tracking service.

        Args:
            tracking_repo: Repository for tracking data access
            inventory_repo: Repository for inventory data access
            analytics_repo: Repository for analytics queries
            notification_service: Service for sending notifications
        """
        self.tracking_repo = tracking_repo
        self.inventory_repo = inventory_repo
        self.analytics_repo = analytics_repo
        self.notification_service = notification_service

    # =========================================================================
    # CORE MEAL TRACKING
    # =========================================================================

    async def log_meal(
        self,
        user_id: int,
        meal_log_id: int,
        portion_multiplier: float,
        notes: Optional[str] = None
    ) -> Dict:
        """
        Log meal consumption with automatic inventory deduction.

        Source: backend/app/agents/tracking_agent.py:log_meal_consumption

        Args:
            user_id: User ID
            meal_log_id: ID of meal log to mark as consumed
            portion_multiplier: Portion size multiplier
            notes: Optional notes about the meal

        Returns:
            Dict with meal logging results, insights, and recommendations

        Raises:
            ValueError: If meal cannot be logged (validation fails)
        """
        try:
            # 1. Validate meal log
            meal_log = await self._validate_meal_for_logging(user_id, meal_log_id)

            # 2. Mark as consumed
            consumed_at = datetime.utcnow()
            meal_log = await self.tracking_repo.mark_as_consumed(
                meal_log_id=meal_log_id,
                user_id=user_id,
                consumed_at=consumed_at,
                portion_multiplier=portion_multiplier,
                notes=notes
            )

            # 3. Deduct ingredients from inventory
            deducted_items = []
            if meal_log.recipe and meal_log.recipe.ingredients:
                deduction_results = await self.inventory_repo.deduct_recipe_ingredients(
                    user_id=user_id,
                    recipe=meal_log.recipe,
                    portion_multiplier=portion_multiplier
                )
                deducted_items = [r for r in deduction_results if r.get("success")]

            # 4. Calculate macros consumed
            macros_consumed = self._calculate_meal_macros(meal_log)

            # 5. Get updated daily totals
            daily_totals = await self.analytics_repo.get_today_summary(user_id)

            # 6. Generate insights
            insights = self._generate_meal_insights(meal_log, daily_totals)

            # 7. Generate recommendations
            recommendations = self._generate_meal_recommendations(daily_totals)

            # 8. Send notification if configured
            # (Optional - notifications can be async/background task)

            logger.info(f"User {user_id} logged meal {meal_log_id}")

            # Match v1 structure exactly (consumption_services.py:102-115)
            return {
                "status": "success",
                "logged_meal": {
                    "id": meal_log.id,
                    "meal_type": meal_log.meal_type,
                    "recipe": meal_log.recipe.title if meal_log.recipe else "Unknown",
                    "consumed_at": consumed_at.isoformat(),
                    "portion_multiplier": portion_multiplier,
                    "macros": macros_consumed
                },
                "updated_totals": daily_totals,
                "remaining_targets": daily_totals.get("remaining_macros", {}),
                "inventory_changes": deducted_items,
                "insights": insights,  # FIX: Add insights to return value
                "recommendations": recommendations  # FIX: Add recommendations to return value
            }

        except ValueError as e:
            logger.error(f"Validation error logging meal: {e}")
            raise
        except Exception as e:
            logger.error(f"Error logging meal: {e}")
            raise

    async def skip_meal(
        self,
        user_id: int,
        meal_log_id: int,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Mark meal as skipped with adherence analysis.

        Source: backend/app/agents/tracking_agent.py:track_skipped_meals

        Args:
            user_id: User ID
            meal_log_id: ID of meal log to mark as skipped
            reason: Optional skip reason

        Returns:
            Dict with skip results and adherence impact

        Raises:
            ValueError: If meal cannot be skipped (validation fails)
        """
        try:
            # 1. Validate meal log
            meal_log = await self._validate_meal_for_skipping(user_id, meal_log_id)

            # 2. Mark as skipped
            meal_log = await self.tracking_repo.mark_as_skipped(
                meal_log_id=meal_log_id,
                user_id=user_id,
                reason=reason
            )

            # 3. Calculate adherence impact
            adherence_rate = await self.calculate_adherence_rate(user_id, days=7)
            adherence_impact = self._analyze_adherence_impact(adherence_rate)

            # 4. Analyze skip patterns
            skip_patterns = await self._analyze_skip_patterns(user_id, days=14)

            # 5. Generate insights
            insights = self._generate_skip_insights(meal_log, adherence_rate, skip_patterns)

            # 6. Generate recommendations
            recommendations = self._generate_skip_recommendations(adherence_rate, skip_patterns)

            logger.info(f"User {user_id} skipped meal {meal_log_id}")

            return {
                "success": True,
                "meal_log_id": meal_log_id,
                "meal_type": meal_log.meal_type,
                "recipe_name": meal_log.recipe.title if meal_log.recipe else "Unknown",
                "reason": reason,
                "adherence_impact": adherence_impact,
                "updated_adherence_rate": adherence_rate,
                "skip_patterns": skip_patterns,
                "insights": insights,
                "recommendations": recommendations
            }

        except ValueError as e:
            logger.error(f"Validation error skipping meal: {e}")
            raise
        except Exception as e:
            logger.error(f"Error skipping meal: {e}")
            raise

    async def get_today_summary(self, user_id: int) -> Dict:
        """
        Get comprehensive today's summary.

        Args:
            user_id: User ID

        Returns:
            Dict with today's consumption summary
        """
        try:
            summary = await self.analytics_repo.get_today_summary(user_id)
            return {
                "success": True,
                **summary
            }

        except Exception as e:
            logger.error(f"Error getting today summary: {e}")
            raise

    async def get_consumption_history(
        self,
        user_id: int,
        days: int,
        include_details: bool = True
    ) -> Dict:
        """
        Get historical consumption data.

        Args:
            user_id: User ID
            days: Number of days to retrieve
            include_details: Include meal-level details

        Returns:
            Dict with consumption history and statistics
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - datetime.timedelta(days=days)

            # Get daily totals
            daily_totals = await self.analytics_repo.get_daily_totals(
                user_id, start_date, end_date
            )

            # Get statistics
            counts = await self.tracking_repo.count_meals_by_status(
                user_id, start_date, end_date
            )

            adherence_rate = await self.tracking_repo.get_adherence_rate(user_id, days)

            # Get trends
            trends = await self.analytics_repo.get_consumption_trends(user_id, days)

            return {
                "success": True,
                "history": daily_totals,
                "statistics": {
                    "total_meals_planned": counts["total"],
                    "total_meals_consumed": counts["consumed"],
                    "total_meals_skipped": counts["skipped"],
                    "overall_compliance": adherence_rate,
                    "trends": trends
                }
            }

        except Exception as e:
            logger.error(f"Error getting consumption history: {e}")
            raise

    # =========================================================================
    # VALIDATION
    # =========================================================================

    async def _validate_meal_for_logging(
        self,
        user_id: int,
        meal_log_id: int
    ) -> MealLog:
        """
        Validate that meal can be logged.

        Source: backend/app/api/tracking.py:144-160

        Args:
            user_id: User ID
            meal_log_id: Meal log ID

        Returns:
            MealLog if valid

        Raises:
            ValueError: If meal cannot be logged
        """
        meal_log = await self.tracking_repo.get_by_id(meal_log_id, user_id)

        if not meal_log:
            raise ValueError(f"Meal log {meal_log_id} not found")

        if meal_log.consumed_datetime is not None:
            raise ValueError("This meal has already been logged")

        if meal_log.was_skipped:
            raise ValueError("Cannot log a meal that has been skipped")

        return meal_log

    async def _validate_meal_for_skipping(
        self,
        user_id: int,
        meal_log_id: int
    ) -> MealLog:
        """
        Validate that meal can be skipped.

        Source: backend/app/api/tracking.py:229-251

        Args:
            user_id: User ID
            meal_log_id: Meal log ID

        Returns:
            MealLog if valid

        Raises:
            ValueError: If meal cannot be skipped
        """
        meal_log = await self.tracking_repo.get_by_id(meal_log_id, user_id)

        if not meal_log:
            raise ValueError(f"Meal log {meal_log_id} not found")

        if meal_log.was_skipped:
            raise ValueError("This meal is already marked as skipped")

        if meal_log.consumed_datetime is not None:
            raise ValueError("Cannot skip a meal that has already been logged")

        return meal_log

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    async def calculate_adherence_rate(self, user_id: int, days: int) -> float:
        """
        Calculate adherence rate over period.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Adherence rate (0.0 to 1.0)
        """
        return await self.tracking_repo.get_adherence_rate(user_id, days)

    async def _analyze_skip_patterns(self, user_id: int, days: int) -> Dict:
        """
        Analyze skipping patterns.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with skip pattern analysis
        """
        try:
            # Get skip frequency by meal type
            skip_frequency = await self.tracking_repo.get_skip_frequency_by_meal_type(
                user_id, days
            )

            # Get meal timing patterns
            timing_patterns = await self.tracking_repo.get_meal_timing_patterns(
                user_id, days
            )

            return {
                "skip_frequency_by_type": skip_frequency,
                "timing_patterns": timing_patterns
            }

        except Exception as e:
            logger.error(f"Error analyzing skip patterns: {e}")
            return {}

    def _analyze_adherence_impact(self, adherence_rate: float) -> Dict:
        """
        Analyze impact of skip on adherence.

        Args:
            adherence_rate: Current adherence rate

        Returns:
            Dict with adherence impact analysis
        """
        if adherence_rate >= 0.90:
            level = "excellent"
            message = "Your adherence remains excellent"
        elif adherence_rate >= 0.80:
            level = "good"
            message = "Your adherence is still good"
        elif adherence_rate >= 0.70:
            level = "fair"
            message = "Your adherence could be improved"
        else:
            level = "needs_improvement"
            message = "Consider reviewing your meal plan"

        return {
            "level": level,
            "message": message,
            "rate": adherence_rate
        }

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _calculate_meal_macros(self, meal_log: MealLog) -> Dict:
        """
        Calculate macros for consumed meal.

        Args:
            meal_log: MealLog entity

        Returns:
            Dict with macro nutrients
        """
        if meal_log.recipe:
            macros = meal_log.recipe.macros_per_serving or {}
            multiplier = meal_log.portion_multiplier or 1.0

            return {
                "calories": macros.get("calories", 0) * multiplier,
                "protein_g": macros.get("protein_g", 0) * multiplier,
                "carbs_g": macros.get("carbs_g", 0) * multiplier,
                "fat_g": macros.get("fat_g", 0) * multiplier,
                "fiber_g": macros.get("fiber_g", 0) * multiplier
            }
        elif meal_log.external_meal:
            ext = meal_log.external_meal
            return {
                "calories": ext.get("calories", 0),
                "protein_g": ext.get("protein_g", 0),
                "carbs_g": ext.get("carbs_g", 0),
                "fat_g": ext.get("fat_g", 0),
                "fiber_g": ext.get("fiber_g", 0)
            }
        else:
            return {
                "calories": 0,
                "protein_g": 0,
                "carbs_g": 0,
                "fat_g": 0,
                "fiber_g": 0
            }

    # =========================================================================
    # INSIGHTS & RECOMMENDATIONS
    # =========================================================================

    def _generate_meal_insights(
        self,
        meal_log: MealLog,
        daily_totals: Dict
    ) -> List[str]:
        """
        Generate insights after meal logging.

        Source: backend/app/agents/tracking_agent.py:_generate_meal_insights

        Args:
            meal_log: Logged meal
            daily_totals: Today's totals

        Returns:
            List of insight messages
        """
        insights = []

        total_calories = daily_totals.get("total_calories", 0)
        target_calories = daily_totals.get("target_calories", 2000)
        remaining_calories = daily_totals.get("remaining_calories", 0)

        # Calorie insights
        if remaining_calories < 0:
            insights.append(f"You've exceeded your daily calorie target by {abs(remaining_calories):.0f} calories")
        elif remaining_calories < 200:
            insights.append(f"You're close to your daily calorie target with {remaining_calories:.0f} calories remaining")
        elif remaining_calories < 500:
            insights.append(f"Good progress! {remaining_calories:.0f} calories remaining for today")

        # Meal completion insights
        meals_consumed = daily_totals.get("meals_consumed", 0)
        meals_planned = daily_totals.get("meals_planned", 0)

        if meals_consumed == meals_planned:
            insights.append("You've completed all planned meals for today!")

        # Protein insights
        total_protein = daily_totals.get("total_protein_g", 0)
        target_protein = daily_totals.get("target_protein_g", 150)

        if total_protein >= target_protein:
            insights.append(f"Great! You've met your protein target ({total_protein:.0f}g)")

        return insights

    def _generate_meal_recommendations(self, daily_totals: Dict) -> List[str]:
        """
        Generate recommendations after meal logging.

        Args:
            daily_totals: Today's totals

        Returns:
            List of recommendation messages
        """
        recommendations = []

        remaining_calories = daily_totals.get("remaining_calories", 0)
        remaining_protein = daily_totals.get("remaining_protein_g", 0)

        # Calorie recommendations
        if remaining_calories > 500:
            recommendations.append("Consider adding a healthy snack to meet your calorie target")
        elif remaining_calories < -200:
            recommendations.append("Consider lighter portions for remaining meals")

        # Protein recommendations
        if remaining_protein > 30:
            recommendations.append(f"Aim for {remaining_protein:.0f}g more protein today")

        # Hydration reminder (generic)
        recommendations.append("Don't forget to stay hydrated!")

        return recommendations

    def _generate_skip_insights(
        self,
        meal_log: MealLog,
        adherence_rate: float,
        skip_patterns: Dict
    ) -> List[str]:
        """
        Generate insights after meal skip.

        Source: backend/app/agents/tracking_agent.py:_generate_skip_insights

        Args:
            meal_log: Skipped meal
            adherence_rate: Current adherence rate
            skip_patterns: Skip pattern analysis

        Returns:
            List of insight messages
        """
        insights = []

        # Adherence insight
        if adherence_rate < 0.80:
            insights.append(f"Your adherence rate is {adherence_rate:.1%}. Consider reviewing your meal plan.")
        else:
            insights.append(f"Your adherence rate is still good at {adherence_rate:.1%}")

        # Pattern insights
        meal_type = meal_log.meal_type
        skip_freq = skip_patterns.get("skip_frequency_by_type", {})

        if meal_type in skip_freq and skip_freq[meal_type] > 0.2:
            insights.append(f"You tend to skip {meal_type} more often. Consider adjusting timing or recipes.")

        return insights

    def _generate_skip_recommendations(
        self,
        adherence_rate: float,
        skip_patterns: Dict
    ) -> List[str]:
        """
        Generate recommendations after meal skip.

        Args:
            adherence_rate: Current adherence rate
            skip_patterns: Skip pattern analysis

        Returns:
            List of recommendation messages
        """
        recommendations = []

        if adherence_rate < 0.80:
            recommendations.append("Try meal prep to make adherence easier")
            recommendations.append("Consider recipes that are quicker to prepare")

        recommendations.append("Log skip reasons to identify patterns")

        return recommendations