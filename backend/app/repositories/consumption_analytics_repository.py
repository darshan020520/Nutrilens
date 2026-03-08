"""
Consumption Analytics Repository Implementation

Implements complex analytics queries for consumption patterns and reporting.
Handles multi-table aggregations and statistical queries (read-only operations).
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, case, extract

from app.repositories.interfaces.consumption_analytics_repository import IConsumptionAnalyticsRepository
from app.models.database import MealLog, MealPlan, Recipe, User
from app.core.ist_datetime import today_ist, start_of_day_naive, end_of_day_naive

logger = logging.getLogger(__name__)


class ConsumptionAnalyticsRepository(IConsumptionAnalyticsRepository):
    """
    Repository for consumption analytics queries.

    All complex read-only analytics queries are implemented here.
    This is a READ-ONLY repository - NO modifications to data.
    """

    def __init__(self, db: Session):
        """
        Initialize consumption analytics repository.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # =========================================================================
    # DAILY TOTALS AND SUMMARIES
    # =========================================================================

    async def get_daily_totals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """
        Get daily consumption totals for a date range.

        Source: backend/app/services/consumption_services.py (pattern)

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of daily totals with calories and macros
        """
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            # Get all consumed meals in range
            consumed_meals = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime.isnot(None),
                    MealLog.consumed_datetime >= start_datetime,
                    MealLog.consumed_datetime <= end_datetime
                )
            ).all()

            # Group by date
            daily_data = {}
            current_date = start_date
            while current_date <= end_date:
                daily_data[current_date.isoformat()] = {
                    "date": current_date.isoformat(),
                    "total_calories": 0,
                    "total_protein_g": 0,
                    "total_carbs_g": 0,
                    "total_fat_g": 0,
                    "total_fiber_g": 0,
                    "meals_consumed": 0,
                    "meals_skipped": 0,
                    "meals_planned": 0
                }
                current_date += timedelta(days=1)

            # Aggregate consumed meals
            for meal in consumed_meals:
                meal_date = meal.consumed_datetime.date().isoformat()

                if meal_date in daily_data:
                    daily_data[meal_date]["meals_consumed"] += 1

                    # Calculate macros
                    if meal.recipe:
                        macros = meal.recipe.macros_per_serving or {}
                        multiplier = meal.portion_multiplier or 1.0

                        daily_data[meal_date]["total_calories"] += macros.get("calories", 0) * multiplier
                        daily_data[meal_date]["total_protein_g"] += macros.get("protein_g", 0) * multiplier
                        daily_data[meal_date]["total_carbs_g"] += macros.get("carbs_g", 0) * multiplier
                        daily_data[meal_date]["total_fat_g"] += macros.get("fat_g", 0) * multiplier
                        daily_data[meal_date]["total_fiber_g"] += macros.get("fiber_g", 0) * multiplier
                    elif meal.external_meal:
                        # External meal macros
                        ext = meal.external_meal
                        daily_data[meal_date]["total_calories"] += ext.get("calories", 0)
                        daily_data[meal_date]["total_protein_g"] += ext.get("protein_g", 0)
                        daily_data[meal_date]["total_carbs_g"] += ext.get("carbs_g", 0)
                        daily_data[meal_date]["total_fat_g"] += ext.get("fat_g", 0)
                        daily_data[meal_date]["total_fiber_g"] += ext.get("fiber_g", 0)

            # Count skipped and planned meals
            all_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).all()

            for meal in all_meals:
                meal_date = meal.planned_datetime.date().isoformat()
                if meal_date in daily_data:
                    daily_data[meal_date]["meals_planned"] += 1
                    if meal.was_skipped:
                        daily_data[meal_date]["meals_skipped"] += 1

            # Return as list
            return list(daily_data.values())

        except Exception as e:
            logger.error(f"Error getting daily totals: {e}")
            raise

    async def get_today_summary(
        self,
        user_id: int,
        target_date: Optional[date] = None
    ) -> Dict:
        """
        Get comprehensive summary for a specific day.

        Source: backend/app/services/consumption_services.py:get_today_summary

        Args:
            user_id: User ID
            target_date: Date to summarize (default: today)

        Returns:
            Dict with comprehensive day summary
        """
        try:
            if not target_date:
                target_date = today_ist()

            start_datetime = start_of_day_naive(target_date)
            end_datetime = end_of_day_naive(target_date)

            # Get user targets from UserProfile.goal_calories + UserGoal.macro_targets (ratios)
            user = self.db.query(User).options(
                joinedload(User.profile),
                joinedload(User.goal)
            ).filter(User.id == user_id).first()

            targets = {}
            if user and user.profile and user.profile.goal_calories and user.goal and user.goal.macro_targets:
                mt = user.goal.macro_targets
                targets = {
                    "calories": user.profile.goal_calories,
                    "protein_g": mt["protein_g"],
                    "carbs_g": mt["carbs_g"],
                    "fat_g": mt["fat_g"],
                }
            else:
                # Default targets if onboarding incomplete
                targets = {
                    "calories": 2000,
                    "protein_g": 120,
                    "carbs_g": 250,
                    "fat_g": 65
                }

            # Get all meals for today
            all_meals = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).outerjoin(
                MealPlan, MealLog.meal_plan_id == MealPlan.id
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime,
                    or_(
                        MealLog.meal_plan_id.is_(None),
                        MealPlan.is_active.is_(True)
                    )
                )
            ).order_by(MealLog.planned_datetime).all()

            meals_planned = len(all_meals)
            meals_consumed = sum(1 for m in all_meals if m.consumed_datetime is not None)
            meals_skipped = sum(1 for m in all_meals if m.was_skipped)
            meals_pending = meals_planned - meals_consumed - meals_skipped

            # Calculate totals from consumed meals
            total_calories = 0
            total_protein_g = 0
            total_carbs_g = 0
            total_fat_g = 0
            total_fiber_g = 0

            meal_details = []

            for meal in all_meals:
                if meal.consumed_datetime:
                    status = "logged"
                elif meal.was_skipped:
                    status = "skipped"
                elif meal.was_missed:
                    status = "missed"
                else:
                    status = "pending"

                # Calculate macros for ALL meals (matching v1: consumption_services.py:418)
                meal_macros = {}

                if meal.recipe:
                    macros = meal.recipe.macros_per_serving or {}
                    multiplier = meal.portion_multiplier or 1.0

                    meal_macros = {
                        "calories": macros.get("calories", 0) * multiplier,
                        "protein_g": macros.get("protein_g", 0) * multiplier,
                        "carbs_g": macros.get("carbs_g", 0) * multiplier,
                        "fat_g": macros.get("fat_g", 0) * multiplier,
                        "fiber_g": macros.get("fiber_g", 0) * multiplier
                    }

                    # Only add to totals if consumed
                    if meal.consumed_datetime:
                        total_calories += meal_macros["calories"]
                        total_protein_g += meal_macros["protein_g"]
                        total_carbs_g += meal_macros["carbs_g"]
                        total_fat_g += meal_macros["fat_g"]
                        total_fiber_g += meal_macros["fiber_g"]

                elif meal.external_meal:
                    ext = meal.external_meal
                    meal_macros = {
                        "calories": ext.get("calories", 0),
                        "protein_g": ext.get("protein_g", 0),
                        "carbs_g": ext.get("carbs_g", 0),
                        "fat_g": ext.get("fat_g", 0),
                        "fiber_g": ext.get("fiber_g", 0)
                    }

                    # Only add to totals if consumed
                    if meal.consumed_datetime:
                        total_calories += meal_macros["calories"]
                        total_protein_g += meal_macros["protein_g"]
                        total_carbs_g += meal_macros["carbs_g"]
                        total_fat_g += meal_macros["fat_g"]
                        total_fiber_g += meal_macros["fiber_g"]

                else:
                    # No recipe and no external meal
                    meal_macros = {
                        "calories": 0,
                        "protein_g": 0,
                        "carbs_g": 0,
                        "fat_g": 0,
                        "fiber_g": 0
                    }

                # Match v1 structure EXACTLY (consumption_services.py:419-427)
                meal_info = {
                    "id": meal.id,
                    "meal_type": meal.meal_type,
                    "planned_time": meal.planned_datetime.isoformat(),
                    "recipe_id": meal.recipe.id if meal.recipe else None,
                    "recipe": meal.recipe.title if meal.recipe else (meal.external_meal.get("dish_name", "External meal") if meal.external_meal else "External meal"),
                    "status": status,
                    "macros": meal_macros
                }

                # Add consumed-specific fields (consumption_services.py:429-432)
                if meal.consumed_datetime:
                    meal_info["consumed_time"] = meal.consumed_datetime.isoformat()
                    meal_info["portion"] = meal.portion_multiplier or 1.0

                # Add skip-specific fields (consumption_services.py:441-443)
                if meal.was_skipped:
                    meal_info["skip_reason"] = meal.skip_reason

                meal_details.append(meal_info)

            # Calculate remaining
            target_calories = targets.get("calories", 2000)
            target_protein_g = targets.get("protein_g", 150)
            target_carbs_g = targets.get("carbs_g", 200)
            target_fat_g = targets.get("fat_g", 65)

            remaining_calories = max(0, target_calories - total_calories)
            remaining_protein_g = max(0, target_protein_g - total_protein_g)
            remaining_carbs_g = max(0, target_carbs_g - total_carbs_g)
            remaining_fat_g = max(0, target_fat_g - total_fat_g)

            # Compliance rate: consumed out of total planned
            if meals_planned > 0:
                compliance_rate = meals_consumed / meals_planned
            else:
                compliance_rate = 0.0

            return {
                "date": target_date.isoformat(),
                "meals_planned": meals_planned,
                "meals_consumed": meals_consumed,
                "meals_skipped": meals_skipped,
                "meals_pending": meals_pending,
                "total_calories": round(total_calories, 1),
                "total_protein_g": round(total_protein_g, 1),
                "total_carbs_g": round(total_carbs_g, 1),
                "total_fat_g": round(total_fat_g, 1),
                "total_fiber_g": round(total_fiber_g, 1),
                "target_calories": target_calories,
                "target_protein_g": target_protein_g,
                "target_carbs_g": target_carbs_g,
                "target_fat_g": target_fat_g,
                "remaining_calories": round(remaining_calories, 1),
                "remaining_protein_g": round(remaining_protein_g, 1),
                "remaining_carbs_g": round(remaining_carbs_g, 1),
                "remaining_fat_g": round(remaining_fat_g, 1),
                "compliance_rate": round(compliance_rate, 3),
                "meals": meal_details
            }

        except Exception as e:
            logger.error(f"Error getting today summary: {e}")
            raise

    async def get_weekly_summary(
        self,
        user_id: int,
        week_start_date: date
    ) -> Dict:
        """
        Get aggregated summary for a week.

        Args:
            user_id: User ID
            week_start_date: Start of the week (Monday)

        Returns:
            Dict with weekly summary
        """
        try:
            week_end_date = week_start_date + timedelta(days=6)

            daily_totals = await self.get_daily_totals(user_id, week_start_date, week_end_date)

            # Aggregate weekly totals
            total_calories = sum(day["total_calories"] for day in daily_totals)
            total_consumed = sum(day["meals_consumed"] for day in daily_totals)
            total_skipped = sum(day["meals_skipped"] for day in daily_totals)

            average_daily_calories = total_calories / 7 if daily_totals else 0

            if total_consumed + total_skipped > 0:
                weekly_adherence = total_consumed / (total_consumed + total_skipped)
            else:
                weekly_adherence = 1.0

            return {
                "week_start": week_start_date.isoformat(),
                "week_end": week_end_date.isoformat(),
                "total_calories": round(total_calories, 1),
                "average_daily_calories": round(average_daily_calories, 1),
                "total_meals_consumed": total_consumed,
                "total_meals_skipped": total_skipped,
                "weekly_adherence_rate": round(weekly_adherence, 3),
                "daily_breakdown": daily_totals
            }

        except Exception as e:
            logger.error(f"Error getting weekly summary: {e}")
            raise

    # =========================================================================
    # TREND ANALYSIS
    # =========================================================================

    async def get_consumption_trends(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Analyze consumption trends over time.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with trend analysis
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            daily_totals = await self.get_daily_totals(user_id, start_date, end_date)

            if len(daily_totals) < 2:
                return {
                    "period_days": days,
                    "calories": {"trend": "stable", "change_per_day": 0},
                    "protein_g": {"trend": "stable", "change_per_day": 0},
                    "carbs_g": {"trend": "stable", "change_per_day": 0},
                    "fat_g": {"trend": "stable", "change_per_day": 0}
                }

            # Split into first half and second half
            mid_point = len(daily_totals) // 2
            first_half = daily_totals[:mid_point]
            second_half = daily_totals[mid_point:]

            # Calculate averages for each half
            first_avg_calories = sum(d["total_calories"] for d in first_half) / len(first_half)
            second_avg_calories = sum(d["total_calories"] for d in second_half) / len(second_half)

            first_avg_protein = sum(d["total_protein_g"] for d in first_half) / len(first_half)
            second_avg_protein = sum(d["total_protein_g"] for d in second_half) / len(second_half)

            first_avg_carbs = sum(d["total_carbs_g"] for d in first_half) / len(first_half)
            second_avg_carbs = sum(d["total_carbs_g"] for d in second_half) / len(second_half)

            first_avg_fat = sum(d["total_fat_g"] for d in first_half) / len(first_half)
            second_avg_fat = sum(d["total_fat_g"] for d in second_half) / len(second_half)

            # Determine trends
            def analyze_trend(start_avg, end_avg):
                change = end_avg - start_avg
                change_per_day = change / days

                if abs(change) < start_avg * 0.05:  # Less than 5% change
                    trend = "stable"
                elif change > 0:
                    trend = "increasing"
                else:
                    trend = "decreasing"

                return {
                    "trend": trend,
                    "change_per_day": round(change_per_day, 1),
                    "total_change": round(change, 1),
                    "start_average": round(start_avg, 1),
                    "end_average": round(end_avg, 1)
                }

            return {
                "period_days": days,
                "calories": analyze_trend(first_avg_calories, second_avg_calories),
                "protein_g": analyze_trend(first_avg_protein, second_avg_protein),
                "carbs_g": analyze_trend(first_avg_carbs, second_avg_carbs),
                "fat_g": analyze_trend(first_avg_fat, second_avg_fat)
            }

        except Exception as e:
            logger.error(f"Error analyzing consumption trends: {e}")
            raise

    async def get_calorie_distribution(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Get distribution of daily calorie intake.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with calorie distribution statistics
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            daily_totals = await self.get_daily_totals(user_id, start_date, end_date)

            if not daily_totals:
                return {
                    "mean": 0,
                    "median": 0,
                    "std_dev": 0,
                    "min": 0,
                    "max": 0
                }

            calories_list = [d["total_calories"] for d in daily_totals if d["total_calories"] > 0]

            if not calories_list:
                return {
                    "mean": 0,
                    "median": 0,
                    "std_dev": 0,
                    "min": 0,
                    "max": 0
                }

            # Sort for median and quartiles
            calories_list.sort()

            mean = sum(calories_list) / len(calories_list)
            median = calories_list[len(calories_list) // 2]
            min_cal = min(calories_list)
            max_cal = max(calories_list)

            # Standard deviation
            variance = sum((x - mean) ** 2 for x in calories_list) / len(calories_list)
            std_dev = variance ** 0.5

            # Quartiles
            q1_idx = len(calories_list) // 4
            q2_idx = len(calories_list) // 2
            q3_idx = (3 * len(calories_list)) // 4

            return {
                "mean": round(mean, 1),
                "median": round(median, 1),
                "std_dev": round(std_dev, 1),
                "min": round(min_cal, 1),
                "max": round(max_cal, 1),
                "quartiles": {
                    "q1": round(calories_list[q1_idx], 1),
                    "q2": round(calories_list[q2_idx], 1),
                    "q3": round(calories_list[q3_idx], 1)
                }
            }

        except Exception as e:
            logger.error(f"Error calculating calorie distribution: {e}")
            raise

    # =========================================================================
    # MEAL-LEVEL ANALYTICS
    # =========================================================================

    async def get_meal_completion_stats(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Get completion statistics by meal type.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with completion stats per meal type
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            all_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).all()

            # Group by meal type
            stats_by_type = {}
            overall_planned = 0
            overall_consumed = 0
            overall_skipped = 0

            for meal in all_meals:
                meal_type = meal.meal_type
                if meal_type not in stats_by_type:
                    stats_by_type[meal_type] = {
                        "planned": 0,
                        "consumed": 0,
                        "skipped": 0
                    }

                stats_by_type[meal_type]["planned"] += 1
                overall_planned += 1

                if meal.consumed_datetime:
                    stats_by_type[meal_type]["consumed"] += 1
                    overall_consumed += 1
                elif meal.was_skipped:
                    stats_by_type[meal_type]["skipped"] += 1
                    overall_skipped += 1

            # Calculate completion rates
            result = {}
            for meal_type, stats in stats_by_type.items():
                completion_rate = stats["consumed"] / stats["planned"] if stats["planned"] > 0 else 0
                result[meal_type] = {
                    "planned": stats["planned"],
                    "consumed": stats["consumed"],
                    "skipped": stats["skipped"],
                    "completion_rate": round(completion_rate, 3)
                }

            overall_completion_rate = overall_consumed / overall_planned if overall_planned > 0 else 0
            result["overall"] = {
                "planned": overall_planned,
                "consumed": overall_consumed,
                "skipped": overall_skipped,
                "completion_rate": round(overall_completion_rate, 3)
            }

            return result

        except Exception as e:
            logger.error(f"Error getting meal completion stats: {e}")
            raise

    async def get_meal_calorie_distribution(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Get average calorie distribution across meal types.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with calorie distribution per meal type
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            consumed_meals = self.db.query(MealLog).options(
                joinedload(MealLog.recipe)
            ).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime.isnot(None),
                    MealLog.consumed_datetime >= start_datetime,
                    MealLog.consumed_datetime <= end_datetime
                )
            ).all()

            # Group by meal type
            calories_by_type = {}

            for meal in consumed_meals:
                meal_type = meal.meal_type
                if meal_type not in calories_by_type:
                    calories_by_type[meal_type] = []

                # Calculate calories
                if meal.recipe:
                    macros = meal.recipe.macros_per_serving or {}
                    calories = macros.get("calories", 0) * (meal.portion_multiplier or 1.0)
                elif meal.external_meal:
                    calories = meal.external_meal.get("calories", 0)
                else:
                    calories = 0

                calories_by_type[meal_type].append(calories)

            # Calculate averages and percentages
            total_calories_all = sum(sum(cals) for cals in calories_by_type.values())

            result = {}
            for meal_type, calories_list in calories_by_type.items():
                if calories_list:
                    avg_calories = sum(calories_list) / len(calories_list)
                    total_calories_type = sum(calories_list)
                    percentage = (total_calories_type / total_calories_all * 100) if total_calories_all > 0 else 0

                    result[meal_type] = {
                        "average_calories": round(avg_calories, 1),
                        "percentage_of_daily": round(percentage, 1),
                        "count": len(calories_list)
                    }

            return result

        except Exception as e:
            logger.error(f"Error getting meal calorie distribution: {e}")
            raise

    async def get_average_meal_timing(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Get average consumption time for each meal type.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict with timing stats per meal type
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            consumed_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime.isnot(None),
                    MealLog.consumed_datetime >= start_datetime,
                    MealLog.consumed_datetime <= end_datetime
                )
            ).all()

            # Group by meal type
            times_by_type = {}

            for meal in consumed_meals:
                meal_type = meal.meal_type
                if meal_type not in times_by_type:
                    times_by_type[meal_type] = []

                consumed_time = meal.consumed_datetime.time()
                times_by_type[meal_type].append(consumed_time)

            # Calculate averages
            result = {}
            for meal_type, times in times_by_type.items():
                if times:
                    # Convert to minutes since midnight
                    minutes_list = [t.hour * 60 + t.minute for t in times]
                    avg_minutes = sum(minutes_list) / len(minutes_list)

                    avg_hour = int(avg_minutes // 60)
                    avg_minute = int(avg_minutes % 60)

                    earliest = min(times)
                    latest = max(times)

                    # Standard deviation
                    variance = sum((m - avg_minutes) ** 2 for m in minutes_list) / len(minutes_list)
                    std_dev_minutes = int(variance ** 0.5)

                    result[meal_type] = {
                        "average_time": f"{avg_hour:02d}:{avg_minute:02d}",
                        "earliest": earliest.strftime("%H:%M"),
                        "latest": latest.strftime("%H:%M"),
                        "std_dev_minutes": std_dev_minutes
                    }

            return result

        except Exception as e:
            logger.error(f"Error getting average meal timing: {e}")
            raise

    # =========================================================================
    # ADHERENCE AND COMPLIANCE
    # =========================================================================

    async def get_adherence_by_day_of_week(
        self,
        user_id: int,
        weeks: int
    ) -> Dict:
        """
        Get adherence rate by day of week.

        Args:
            user_id: User ID
            weeks: Number of weeks to analyze

        Returns:
            Dict mapping day name to adherence rate
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(weeks=weeks)
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())

            all_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    MealLog.planned_datetime >= start_datetime,
                    MealLog.planned_datetime <= end_datetime
                )
            ).all()

            # Group by day of week (0=Monday, 6=Sunday)
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            stats_by_day = {day: {"consumed": 0, "total": 0} for day in day_names}

            for meal in all_meals:
                day_of_week = meal.planned_datetime.weekday()
                day_name = day_names[day_of_week]

                stats_by_day[day_name]["total"] += 1
                if meal.consumed_datetime:
                    stats_by_day[day_name]["consumed"] += 1

            # Calculate adherence rates
            result = {}
            for day, stats in stats_by_day.items():
                adherence = stats["consumed"] / stats["total"] if stats["total"] > 0 else 1.0
                result[day] = round(adherence, 3)

            return result

        except Exception as e:
            logger.error(f"Error getting adherence by day of week: {e}")
            raise

    async def get_adherence_trend(
        self,
        user_id: int,
        days: int,
        bucket_size: int = 7
    ) -> List[Dict]:
        """
        Get adherence trend over time in buckets.

        Args:
            user_id: User ID
            days: Total days to analyze
            bucket_size: Days per bucket

        Returns:
            List of buckets with adherence rates
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            buckets = []
            current_start = start_date

            while current_start < end_date:
                bucket_end = min(current_start + timedelta(days=bucket_size - 1), end_date)

                start_datetime = datetime.combine(current_start, datetime.min.time())
                end_datetime = datetime.combine(bucket_end, datetime.max.time())

                meals = self.db.query(MealLog).filter(
                    and_(
                        MealLog.user_id == user_id,
                        MealLog.planned_datetime >= start_datetime,
                        MealLog.planned_datetime <= end_datetime
                    )
                ).all()

                consumed = sum(1 for m in meals if m.consumed_datetime)
                skipped = sum(1 for m in meals if m.was_skipped)
                total_actionable = consumed + skipped

                adherence = consumed / total_actionable if total_actionable > 0 else 1.0

                buckets.append({
                    "period": f"{current_start.isoformat()} to {bucket_end.isoformat()}",
                    "adherence_rate": round(adherence, 3),
                    "meals_consumed": consumed,
                    "meals_skipped": skipped
                })

                current_start = bucket_end + timedelta(days=1)

            return buckets

        except Exception as e:
            logger.error(f"Error getting adherence trend: {e}")
            raise

    async def get_target_achievement_rate(
        self,
        user_id: int,
        days: int,
        tolerance_percentage: float = 10.0
    ) -> Dict:
        """
        Calculate how often user meets their daily targets.

        Args:
            user_id: User ID
            days: Number of days to analyze
            tolerance_percentage: Tolerance for "meeting target"

        Returns:
            Dict with achievement rates
        """
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)

            # Get user targets from UserProfile.goal_calories + UserGoal.macro_targets (ratios)
            user = self.db.query(User).options(
                joinedload(User.profile),
                joinedload(User.goal)
            ).filter(User.id == user_id).first()

            targets = {}
            if user and user.profile and user.profile.goal_calories and user.goal and user.goal.macro_targets:
                mt = user.goal.macro_targets
                targets = {
                    "calories": user.profile.goal_calories,
                    "protein_g": mt["protein_g"],
                    "carbs_g": mt["carbs_g"],
                    "fat_g": mt["fat_g"],
                }
            else:
                # Default targets if onboarding incomplete
                targets = {
                    "calories": 2000,
                    "protein_g": 120,
                    "carbs_g": 250,
                    "fat_g": 65
                }

            target_calories = targets.get("calories", 2000)
            target_protein = targets.get("protein_g", 150)
            target_carbs = targets.get("carbs_g", 200)
            target_fat = targets.get("fat_g", 65)

            # Get daily totals
            daily_totals = await self.get_daily_totals(user_id, start_date, end_date)

            days_met_calories = 0
            days_met_protein = 0
            days_met_carbs = 0
            days_met_fat = 0
            days_met_all = 0

            for day in daily_totals:
                tolerance_multiplier = tolerance_percentage / 100

                calorie_met = abs(day["total_calories"] - target_calories) <= target_calories * tolerance_multiplier
                protein_met = abs(day["total_protein_g"] - target_protein) <= target_protein * tolerance_multiplier
                carbs_met = abs(day["total_carbs_g"] - target_carbs) <= target_carbs * tolerance_multiplier
                fat_met = abs(day["total_fat_g"] - target_fat) <= target_fat * tolerance_multiplier

                if calorie_met:
                    days_met_calories += 1
                if protein_met:
                    days_met_protein += 1
                if carbs_met:
                    days_met_carbs += 1
                if fat_met:
                    days_met_fat += 1
                if calorie_met and protein_met and carbs_met and fat_met:
                    days_met_all += 1

            total_days = len(daily_totals)

            return {
                "total_days": total_days,
                "days_met_calorie_target": days_met_calories,
                "days_met_protein_target": days_met_protein,
                "days_met_carbs_target": days_met_carbs,
                "days_met_fat_target": days_met_fat,
                "days_met_all_targets": days_met_all,
                "calorie_achievement_rate": round(days_met_calories / total_days, 3) if total_days > 0 else 0,
                "protein_achievement_rate": round(days_met_protein / total_days, 3) if total_days > 0 else 0,
                "overall_achievement_rate": round(days_met_all / total_days, 3) if total_days > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error calculating target achievement rate: {e}")
            raise

    # =========================================================================
    # RECIPE AND PREFERENCE ANALYTICS (Placeholders for remaining methods)
    # =========================================================================

    async def get_most_consumed_recipes(
        self,
        user_id: int,
        days: int,
        limit: int = 10
    ) -> List[Dict]:
        """Get recipes consumed most frequently."""
        # Placeholder - would implement full query
        return []

    async def get_least_consumed_recipes(
        self,
        user_id: int,
        days: int,
        limit: int = 10
    ) -> List[Dict]:
        """Get recipes consumed least frequently."""
        # Placeholder - would implement full query
        return []

    async def get_portion_size_preferences(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """Analyze portion size preferences."""
        # Placeholder - would implement full analysis
        return {"overall": {"average_multiplier": 1.0}}

    async def get_macro_balance_analysis(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """Analyze macro nutrient balance vs targets."""
        # Placeholder - would implement full analysis
        return {}

    async def get_calorie_macro_correlation(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """Analyze correlation between calories and macros."""
        # Placeholder - would implement correlation analysis
        return {}

    async def compare_periods(
        self,
        user_id: int,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date
    ) -> Dict:
        """Compare consumption between two time periods."""
        # Placeholder - would implement comparison logic
        return {}

    async def get_current_adherence_streak(
        self,
        user_id: int
    ) -> Dict:
        """Get current streak of consecutive days meeting adherence target."""
        # Placeholder - would implement streak tracking
        return {"current_streak_days": 0}

    async def get_milestone_progress(
        self,
        user_id: int
    ) -> Dict:
        """Get progress towards consumption milestones."""
        # Placeholder - would implement milestone tracking
        return {"total_meals_logged": 0}
