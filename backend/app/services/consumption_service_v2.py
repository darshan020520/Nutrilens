"""
Consumption Service V2 - Refactored to use Repository Pattern

This is a refactored version of ConsumptionService that uses repositories instead of
direct database access. It maintains backward compatibility with the existing API.

Key Changes:
- Uses ITrackingRepository for meal log operations
- Uses IInventoryRepository for inventory operations
- Uses IConsumptionAnalyticsRepository for analytics queries
- No direct database session usage in business logic
- Cleaner separation of concerns

Refactored from: backend/app/services/consumption_services.py
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
import logging

from app.models.database import MealLog, Recipe, User
from app.repositories.interfaces import (
    ITrackingRepository,
    IInventoryRepository,
    IConsumptionAnalyticsRepository
)

logger = logging.getLogger(__name__)


class ConsumptionServiceV2:
    """
    Refactored consumption service using repository pattern.

    This service handles all meal consumption tracking and analytics
    while delegating data access to repositories.
    """

    def __init__(
        self,
        tracking_repo: ITrackingRepository,
        inventory_repo: IInventoryRepository,
        analytics_repo: IConsumptionAnalyticsRepository,
        db: Session  # Keep for backward compatibility with existing code
    ):
        """
        Initialize ConsumptionServiceV2 with repositories.

        Args:
            tracking_repo: Repository for meal log data access
            inventory_repo: Repository for inventory data access
            analytics_repo: Repository for analytics queries
            db: Database session (for backward compatibility)
        """
        self.tracking_repo = tracking_repo
        self.inventory_repo = inventory_repo
        self.analytics_repo = analytics_repo
        self.db = db  # Keep for methods not yet refactored

    # ===== PUBLIC API METHODS (5 required functions) =====

    async def log_meal_consumption(self, user_id: int, meal_data: Dict) -> Dict[str, Any]:
        """
        Log meal consumption with atomic transaction.

        Source: backend/app/services/consumption_services.py:33-119

        Args:
            user_id: User ID
            meal_data: {
                "meal_log_id": Optional[int],  # If provided, marks existing meal as consumed
                "recipe_id": Optional[int],    # If creating new meal
                "meal_type": str,              # breakfast, lunch, dinner, snack
                "timestamp": Optional[datetime],
                "portion_multiplier": float,   # Default 1.0
                "notes": Optional[str]
            }

        Returns:
            Dict: {
                "status": "success",
                "logged_meal": {...},
                "updated_totals": {...},
                "remaining_targets": {...},
                "inventory_changes": [...]
            }
        """
        try:
            meal_log = None

            # Get or create meal log
            if meal_data.get("meal_log_id"):
                meal_log = await self.tracking_repo.get_by_id(
                    meal_data["meal_log_id"],
                    user_id
                )

                if not meal_log:
                    return {"status": "error", "error": "Meal log not found"}

                if meal_log.consumed_datetime:
                    return {"status": "error", "error": "Meal already logged"}
            else:
                # Create new meal log
                meal_log = await self.tracking_repo.create(
                    user_id=user_id,
                    recipe_id=meal_data.get("recipe_id"),
                    meal_type=meal_data["meal_type"],
                    planned_datetime=meal_data.get("timestamp", datetime.utcnow()),
                    notes=meal_data.get("notes")
                )

            # Mark as consumed
            portion_multiplier = meal_data.get("portion_multiplier", 1.0)
            consumed_at = datetime.utcnow()

            meal_log = await self.tracking_repo.mark_as_consumed(
                meal_log_id=meal_log.id,
                user_id=user_id,
                consumed_at=consumed_at,
                portion_multiplier=portion_multiplier,
                notes=meal_data.get("notes")
            )

            # Auto-deduct ingredients from inventory
            inventory_changes = []
            if meal_log.recipe_id:
                deduction_result = await self.auto_deduct_ingredients(
                    recipe_id=meal_log.recipe_id,
                    portion_multiplier=portion_multiplier,
                    user_id=user_id
                )
                inventory_changes = deduction_result.get("deducted_items", [])

            # Calculate consumed macros
            macros = self._calculate_meal_macros(meal_log)

            # Get updated daily totals
            daily_totals = await self.analytics_repo.get_today_summary(user_id)

            # Get remaining targets
            remaining_targets = self._calculate_remaining_targets(user_id, daily_totals)

            return {
                "status": "success",
                "logged_meal": {
                    "id": meal_log.id,
                    "meal_type": meal_log.meal_type,
                    "recipe": meal_log.recipe.title if hasattr(meal_log, 'recipe') and meal_log.recipe else "External",
                    "consumed_at": consumed_at.isoformat(),
                    "portion_multiplier": portion_multiplier,
                    "macros": macros
                },
                "updated_totals": daily_totals.get("total_macros", {}),
                "remaining_targets": remaining_targets,
                "inventory_changes": inventory_changes
            }

        except Exception as e:
            logger.error(f"Error in log_meal_consumption: {str(e)}")
            return {"status": "error", "error": str(e)}

    async def auto_deduct_ingredients(
        self,
        recipe_id: int,
        portion_multiplier: float,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Auto-deduct ingredients with concurrency handling.

        Source: backend/app/services/consumption_services.py:121-185

        Args:
            recipe_id: Recipe ID
            portion_multiplier: Portion multiplier
            user_id: User ID

        Returns:
            Dict: {
                "success": True,
                "deducted_items": [...],
                "failed_deductions": [...],
                "total_deducted": int,
                "total_failed": int
            }
        """
        try:
            # Get recipe (using db for now, can be moved to recipe repository later)
            from app.models.database import Recipe
            recipe = self.db.query(Recipe).filter(Recipe.id == recipe_id).first()

            if not recipe:
                return {
                    "success": False,
                    "error": "Recipe not found"
                }

            # Use repository to deduct recipe ingredients
            deduction_results = await self.inventory_repo.deduct_recipe_ingredients(
                user_id=user_id,
                recipe=recipe,
                portion_multiplier=portion_multiplier
            )

            # Separate successful and failed deductions
            deducted_items = [r for r in deduction_results if r.get("success")]
            failed_deductions = [r for r in deduction_results if not r.get("success")]

            return {
                "success": True,
                "deducted_items": deducted_items,
                "failed_deductions": failed_deductions,
                "total_deducted": len(deducted_items),
                "total_failed": len(failed_deductions)
            }

        except Exception as e:
            logger.error(f"Error in auto_deduct_ingredients: {str(e)}")
            return {"success": False, "error": str(e)}

    async def track_portions(self, user_id: int, meal_data: Dict) -> Dict[str, Any]:
        """
        Track and validate portion sizes.

        Source: backend/app/services/consumption_services.py:187-235

        Args:
            user_id: User ID
            meal_data: {
                "meal_log_id": Optional[int],
                "portion_multiplier": float
            }

        Returns:
            Dict: {
                "success": True,
                "validated_portion": float,
                "old_portion": Optional[float],
                "adjustment": Optional[float],
                "preference_updated": bool
            }
        """
        try:
            portion_multiplier = meal_data.get("portion_multiplier", 1.0)
            meal_log_id = meal_data.get("meal_log_id")

            # Validate portion size (0.25x - 3.0x)
            if not (0.25 <= portion_multiplier <= 3.0):
                return {
                    "success": False,
                    "error": "Portion multiplier must be between 0.25 and 3.0"
                }

            # Update portion in meal log if provided
            if meal_log_id:
                meal_log = await self.tracking_repo.get_by_id(meal_log_id, user_id)

                if meal_log:
                    old_portion = meal_log.portion_multiplier or 1.0

                    # Update portion using repository
                    # Note: This would need a new repository method
                    # For now, using direct DB access
                    meal_log.portion_multiplier = portion_multiplier
                    self.db.commit()

                    # Learn from portion adjustment
                    self._learn_portion_preference(user_id, meal_log.recipe_id, portion_multiplier)

                    return {
                        "success": True,
                        "validated_portion": portion_multiplier,
                        "old_portion": old_portion,
                        "adjustment": portion_multiplier - old_portion,
                        "preference_updated": True
                    }

            return {
                "success": True,
                "validated_portion": portion_multiplier,
                "within_range": True
            }

        except Exception as e:
            logger.error(f"Error in track_portions: {str(e)}")
            return {"success": False, "error": str(e)}

    async def handle_skip_meal(self, user_id: int, meal_info: Dict) -> Dict[str, Any]:
        """
        Handle meal skipping with pattern analysis.

        Source: backend/app/services/consumption_services.py:237-294

        Args:
            user_id: User ID
            meal_info: {
                "meal_log_id": int,
                "reason": Optional[str]
            }

        Returns:
            Dict: {
                "success": True,
                "meal_log_id": int,
                "meal_type": str,
                "recipe": str,
                "reason": str,
                "skip_analysis": {...},
                "adherence_impact": {...},
                "recommendation": str
            }
        """
        try:
            meal_log_id = meal_info.get("meal_log_id")
            reason = meal_info.get("reason")

            if not meal_log_id:
                return {"success": False, "error": "meal_log_id required"}

            # Get meal log
            meal_log = await self.tracking_repo.get_by_id(meal_log_id, user_id)

            if not meal_log:
                return {"success": False, "error": "Meal log not found"}

            if meal_log.was_skipped:
                return {"success": False, "error": "Meal already marked as skipped"}

            if meal_log.consumed_datetime:
                return {"success": False, "error": "Cannot skip consumed meal"}

            # Mark as skipped using repository
            meal_log = await self.tracking_repo.mark_as_skipped(
                meal_log_id=meal_log_id,
                user_id=user_id,
                reason=reason
            )

            # Analyze skip patterns
            skip_analysis = await self._analyze_skip_patterns(user_id, meal_log.meal_type)

            # Recalculate adherence
            adherence = await self._calculate_daily_adherence(user_id)

            return {
                "success": True,
                "meal_log_id": meal_log.id,
                "meal_type": meal_log.meal_type,
                "recipe": meal_log.recipe.title if hasattr(meal_log, 'recipe') and meal_log.recipe else "Unknown",
                "reason": reason,
                "skip_analysis": skip_analysis,
                "adherence_impact": adherence,
                "recommendation": self._get_skip_recommendation(skip_analysis)
            }

        except Exception as e:
            logger.error(f"Error in handle_skip_meal: {str(e)}")
            return {"success": False, "error": str(e)}

    async def generate_consumption_analytics(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """
        Generate comprehensive consumption analytics.

        Source: backend/app/services/consumption_services.py:296-343

        Args:
            user_id: User ID
            days: Number of days to analyze (default: 7)

        Returns:
            Dict: Comprehensive analytics including trends, patterns, compliance
        """
        try:
            start_date = datetime.utcnow().date() - timedelta(days=days)
            end_date = datetime.utcnow().date()

            # Get consumption trends
            trends = await self.analytics_repo.get_consumption_trends(user_id, days)

            # Get adherence rate
            adherence_rate = await self.tracking_repo.get_adherence_rate(user_id, days)

            # Get meal completion stats
            completion_stats = await self.analytics_repo.get_meal_completion_stats(user_id, days)

            # Get daily totals
            daily_totals = await self.analytics_repo.get_daily_totals(user_id, start_date, end_date)

            return {
                "success": True,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                },
                "trends": trends,
                "adherence_rate": adherence_rate,
                "completion_stats": completion_stats,
                "daily_totals": daily_totals
            }

        except Exception as e:
            logger.error(f"Error in generate_consumption_analytics: {str(e)}")
            return {"success": False, "error": str(e)}

    # ===== ADDITIONAL PUBLIC METHODS =====

    async def get_today_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get today's consumption summary.

        Source: backend/app/services/consumption_services.py:345-504

        Args:
            user_id: User ID

        Returns:
            Dict: Today's summary with macros, targets, meals, compliance
        """
        try:
            summary = await self.analytics_repo.get_today_summary(user_id)

            if not summary:
                return {"success": False, "error": "Failed to get today's summary"}

            # Add recommendations
            summary["recommendations"] = self._get_daily_recommendations(summary)

            return {"success": True, **summary}

        except Exception as e:
            logger.error(f"Error in get_today_summary: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_consumption_history(
        self,
        user_id: int,
        days: int = 7,
        include_details: bool = False
    ) -> Dict[str, Any]:
        """
        Get consumption history for specified number of days.

        Source: backend/app/services/consumption_services.py:506-587

        Args:
            user_id: User ID
            days: Number of days to retrieve (default: 7)
            include_details: Include detailed meal information

        Returns:
            Dict: Consumption history with trends and patterns
        """
        try:
            start_date = datetime.utcnow().date() - timedelta(days=days)
            end_date = datetime.utcnow().date()

            # Get daily aggregates from analytics repo
            daily_totals = await self.analytics_repo.get_daily_totals(user_id, start_date, end_date)

            # Get trends from analytics repo
            trends = await self.analytics_repo.get_consumption_trends(user_id, days)

            # Build daily_data with meals array
            daily_data = []

            if include_details:
                # Get ALL meal logs (consumed, skipped, pending) from tracking repo
                meal_logs = await self.tracking_repo.get_by_date_range(user_id, start_date, end_date)

                # Group meals by date
                meals_by_date = {}
                for log in meal_logs:
                    log_date = log.planned_datetime.date().isoformat()

                    if log_date not in meals_by_date:
                        meals_by_date[log_date] = []

                    # Build meal detail matching v1 structure exactly
                    status = "logged" if log.consumed_datetime else ("skipped" if log.was_skipped else "pending")

                    meals_by_date[log_date].append({
                        "meal_type": log.meal_type,
                        "recipe_name": log.recipe.title if log.recipe else "External",
                        "status": status,
                        "time": log.consumed_datetime.isoformat() if log.consumed_datetime else log.planned_datetime.isoformat()
                    })

                # Merge aggregates with meal details
                for daily_total in daily_totals:
                    date = daily_total.get("date", "")
                    daily_data.append({
                        **daily_total,
                        "meals": meals_by_date.get(date, [])
                    })
            else:
                # Just use aggregates without meal details
                daily_data = daily_totals

            return {
                "success": True,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days
                },
                "daily_data": daily_data,
                "trends": trends
            }

        except Exception as e:
            logger.error(f"Error in get_consumption_history: {str(e)}")
            return {"success": False, "error": str(e)}

    # ===== PRIVATE HELPER METHODS =====

    def _calculate_meal_macros(self, meal_log: MealLog) -> Dict[str, float]:
        """Calculate macros for a single meal."""
        if not hasattr(meal_log, 'recipe') or not meal_log.recipe:
            return {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "fiber_g": 0}

        macros = meal_log.recipe.macros_per_serving or {}
        multiplier = meal_log.portion_multiplier or 1.0

        return {
            "calories": round(macros.get("calories", 0) * multiplier, 1),
            "protein_g": round(macros.get("protein_g", 0) * multiplier, 1),
            "carbs_g": round(macros.get("carbs_g", 0) * multiplier, 1),
            "fat_g": round(macros.get("fat_g", 0) * multiplier, 1),
            "fiber_g": round(macros.get("fiber_g", 0) * multiplier, 1)
        }

    def _calculate_remaining_targets(self, user_id: int, daily_totals: Dict) -> Dict[str, float]:
        """Calculate remaining macro targets for the day."""
        # Get user targets (using db for now, could be moved to user repository)
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user or not user.nutrition_targets:
            return {}

        targets = user.nutrition_targets
        consumed = daily_totals.get("total_macros", {})

        return {
            "calories": max(0, targets.get("calories", 2000) - consumed.get("calories", 0)),
            "protein_g": max(0, targets.get("protein_g", 150) - consumed.get("protein_g", 0)),
            "carbs_g": max(0, targets.get("carbs_g", 200) - consumed.get("carbs_g", 0)),
            "fat_g": max(0, targets.get("fat_g", 70) - consumed.get("fat_g", 0))
        }

    async def _analyze_skip_patterns(self, user_id: int, meal_type: str) -> Dict[str, Any]:
        """Analyze user's meal skipping patterns."""
        try:
            skip_frequency = await self.tracking_repo.get_skip_frequency_by_meal_type(user_id, days=30)

            meal_type_skip_rate = skip_frequency.get(meal_type, 0)

            return {
                "meal_type": meal_type,
                "skip_rate": meal_type_skip_rate,
                "is_frequent": meal_type_skip_rate > 20,  # > 20% skip rate
                "all_meal_types": skip_frequency
            }

        except Exception as e:
            logger.error(f"Error analyzing skip patterns: {str(e)}")
            return {}

    async def _calculate_daily_adherence(self, user_id: int) -> Dict[str, Any]:
        """Calculate today's adherence rate."""
        try:
            # Get today's summary
            today_summary = await self.analytics_repo.get_today_summary(user_id)

            if not today_summary:
                return {}

            return {
                "adherence_rate": today_summary.get("compliance_rate", 0),
                "meals_planned": today_summary.get("meals_planned", 0),
                "meals_consumed": today_summary.get("meals_consumed", 0),
                "meals_skipped": today_summary.get("meals_skipped", 0)
            }

        except Exception as e:
            logger.error(f"Error calculating daily adherence: {str(e)}")
            return {}

    def _learn_portion_preference(self, user_id: int, recipe_id: int, portion: float):
        """Learn from user's portion adjustments (placeholder for ML feature)."""
        # This would update user preferences / ML model
        # For now, just log the preference
        logger.info(f"User {user_id} prefers {portion}x portion for recipe {recipe_id}")

    def _get_skip_recommendation(self, skip_analysis: Dict) -> str:
        """Generate recommendation based on skip analysis."""
        skip_rate = skip_analysis.get("skip_rate", 0)
        meal_type = skip_analysis.get("meal_type", "meal")

        if skip_rate > 30:
            return f"You skip {meal_type} often ({skip_rate:.0f}%). Consider planning simpler meals or adjusting timing."
        elif skip_rate > 15:
            return f"Moderate {meal_type} skip rate ({skip_rate:.0f}%). Try to maintain consistency."
        else:
            return f"Good {meal_type} adherence! Keep it up."

    def _get_daily_recommendations(self, summary: Dict) -> List[str]:
        """Generate daily recommendations based on summary."""
        recommendations = []

        compliance_rate = summary.get("compliance_rate", 0)
        remaining_calories = summary.get("remaining_calories", 0)
        total_calories = summary.get("total_calories", 0)
        target_calories = summary.get("target_calories", 2000)

        # Compliance recommendations
        if compliance_rate >= 90:
            recommendations.append("Excellent adherence today! You're crushing your goals!")
        elif compliance_rate >= 70:
            recommendations.append("Good progress today. Stay consistent!")
        else:
            recommendations.append("Let's focus on completing your planned meals.")

        # Calorie recommendations
        if total_calories > target_calories * 1.1:
            recommendations.append(f"You're {int(total_calories - target_calories)} calories over target. Consider lighter options.")
        elif remaining_calories > target_calories * 0.3:
            recommendations.append(f"You have {int(remaining_calories)} calories remaining. Don't forget to eat!")

        return recommendations

    async def calculate_streak(self, user_id: int) -> int:
        """
        Calculate current streak of consecutive days with logged meals.

        MOVED FROM: dashboard_orchestrator.py:209-246

        Business logic:
        1. Get meal logs for each day going backwards from today
        2. Count consecutive days where at least one meal was consumed
        3. Stop when we hit a day with zero consumed meals
        4. Maximum check is 30 days

        Args:
            user_id: User ID

        Returns:
            Streak count (consecutive days with at least one logged meal)
        """
        try:
            today = date.today()
            streak = 0

            for days_ago in range(30):  # Check last 30 days max
                check_date = today - timedelta(days=days_ago)

                # Get all meal logs for this specific date using repository
                meals_on_date = await self.tracking_repo.get_by_date(
                    user_id=user_id,
                    target_date=check_date
                )

                # Count consumed meals (not skipped, has consumed_datetime)
                consumed_count = sum(
                    1 for meal in meals_on_date
                    if meal.consumed_datetime is not None and not meal.was_skipped
                )

                if consumed_count > 0:
                    streak += 1
                else:
                    break  # Streak broken

            return streak

        except Exception as e:
            logger.error(f"Error calculating streak for user {user_id}: {str(e)}")
            return 0