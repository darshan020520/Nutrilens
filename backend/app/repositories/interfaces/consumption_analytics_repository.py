"""
Consumption Analytics Repository Interface

Defines data access operations for complex consumption analytics and reporting.
Handles multi-table aggregations and statistical queries for consumption patterns.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Optional


class IConsumptionAnalyticsRepository(ABC):
    """
    Interface for consumption analytics data access operations.

    Responsibilities:
    - Daily consumption totals and summaries
    - Multi-day trend analysis
    - Macro and calorie aggregations
    - Adherence and compliance statistics
    - Pattern analysis (timing, preferences, etc.)

    This is a DATA ACCESS layer - NO business logic here.
    Only complex read queries for analytics purposes.
    """

    # =========================================================================
    # DAILY TOTALS AND SUMMARIES
    # =========================================================================

    @abstractmethod
    async def get_daily_totals(
        self,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """
        Get daily consumption totals for a date range.

        Aggregates all consumed meals per day with calories and macros.

        Args:
            user_id: User ID
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of daily totals: [
                {
                    "date": "2025-11-25",
                    "total_calories": 2150,
                    "total_protein_g": 180,
                    "total_carbs_g": 210,
                    "total_fat_g": 65,
                    "total_fiber_g": 30,
                    "meals_consumed": 4,
                    "meals_skipped": 1,
                    "meals_planned": 5
                },
                ...
            ]
        """
        pass

    @abstractmethod
    async def get_today_summary(
        self,
        user_id: int,
        target_date: Optional[date] = None
    ) -> Dict:
        """
        Get comprehensive summary for a specific day (defaults to today).

        Args:
            user_id: User ID
            target_date: Date to summarize (default: today)

        Returns:
            Dict: {
                "date": "2025-11-25",
                "meals_planned": 5,
                "meals_consumed": 3,
                "meals_skipped": 1,
                "meals_pending": 1,
                "total_calories": 1450,
                "total_protein_g": 120,
                "total_carbs_g": 150,
                "total_fat_g": 45,
                "total_fiber_g": 25,
                "target_calories": 2000,
                "target_protein_g": 150,
                "target_carbs_g": 200,
                "target_fat_g": 65,
                "remaining_calories": 550,
                "remaining_protein_g": 30,
                "remaining_carbs_g": 50,
                "remaining_fat_g": 20,
                "compliance_rate": 0.75,
                "meals": [
                    {
                        "meal_type": "breakfast",
                        "recipe_name": "Oatmeal",
                        "status": "consumed",
                        "time": "08:30",
                        "calories": 350,
                        "macros": {...}
                    },
                    ...
                ]
            }
        """
        pass

    @abstractmethod
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
            Dict: {
                "week_start": "2025-11-18",
                "week_end": "2025-11-24",
                "total_calories": 14500,
                "average_daily_calories": 2071,
                "total_meals_consumed": 28,
                "total_meals_skipped": 7,
                "weekly_adherence_rate": 0.80,
                "daily_breakdown": [...]
            }
        """
        pass

    # =========================================================================
    # TREND ANALYSIS
    # =========================================================================

    @abstractmethod
    async def get_consumption_trends(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Analyze consumption trends over time.

        Calculates whether calories/macros are trending up, down, or stable.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict: {
                "period_days": 14,
                "calories": {
                    "trend": "increasing",  # increasing, decreasing, stable
                    "change_per_day": 25,   # average daily change
                    "total_change": 350,
                    "start_average": 2000,
                    "end_average": 2350
                },
                "protein_g": {...},
                "carbs_g": {...},
                "fat_g": {...},
                "adherence": {
                    "trend": "stable",
                    "start_rate": 0.85,
                    "end_rate": 0.83
                }
            }
        """
        pass

    @abstractmethod
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
            Dict: {
                "mean": 2100,
                "median": 2050,
                "std_dev": 200,
                "min": 1600,
                "max": 2500,
                "quartiles": {
                    "q1": 1950,
                    "q2": 2050,
                    "q3": 2250
                },
                "days_over_target": 8,
                "days_under_target": 6,
                "days_within_10_percent": 10
            }
        """
        pass

    # =========================================================================
    # MEAL-LEVEL ANALYTICS
    # =========================================================================

    @abstractmethod
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
            Dict: {
                "breakfast": {
                    "planned": 14,
                    "consumed": 12,
                    "skipped": 2,
                    "completion_rate": 0.857
                },
                "lunch": {...},
                "dinner": {...},
                "snack": {...},
                "overall": {
                    "planned": 56,
                    "consumed": 45,
                    "skipped": 11,
                    "completion_rate": 0.804
                }
            }
        """
        pass

    @abstractmethod
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
            Dict: {
                "breakfast": {
                    "average_calories": 450,
                    "percentage_of_daily": 22,
                    "count": 12
                },
                "lunch": {...},
                "dinner": {...},
                "snack": {...}
            }
        """
        pass

    @abstractmethod
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
            Dict: {
                "breakfast": {
                    "average_time": "08:15",
                    "earliest": "07:30",
                    "latest": "09:45",
                    "std_dev_minutes": 35
                },
                "lunch": {...},
                "dinner": {...},
                "snack": {...}
            }
        """
        pass

    # =========================================================================
    # ADHERENCE AND COMPLIANCE
    # =========================================================================

    @abstractmethod
    async def get_adherence_by_day_of_week(
        self,
        user_id: int,
        weeks: int
    ) -> Dict:
        """
        Get adherence rate by day of week.

        Identifies patterns like "lower adherence on weekends".

        Args:
            user_id: User ID
            weeks: Number of weeks to analyze

        Returns:
            Dict: {
                "Monday": 0.95,
                "Tuesday": 0.88,
                "Wednesday": 0.92,
                "Thursday": 0.85,
                "Friday": 0.78,
                "Saturday": 0.65,
                "Sunday": 0.70
            }
        """
        pass

    @abstractmethod
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
            bucket_size: Days per bucket (default 7 for weekly)

        Returns:
            List of buckets: [
                {
                    "period": "2025-11-11 to 2025-11-17",
                    "adherence_rate": 0.82,
                    "meals_consumed": 23,
                    "meals_skipped": 5
                },
                {
                    "period": "2025-11-18 to 2025-11-24",
                    "adherence_rate": 0.87,
                    "meals_consumed": 26,
                    "meals_skipped": 4
                }
            ]
        """
        pass

    @abstractmethod
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
            tolerance_percentage: Tolerance for "meeting target" (default 10%)

        Returns:
            Dict: {
                "total_days": 14,
                "days_met_calorie_target": 10,
                "days_met_protein_target": 8,
                "days_met_carbs_target": 9,
                "days_met_fat_target": 11,
                "days_met_all_targets": 6,
                "calorie_achievement_rate": 0.714,
                "protein_achievement_rate": 0.571,
                "overall_achievement_rate": 0.429
            }
        """
        pass

    # =========================================================================
    # RECIPE AND PREFERENCE ANALYTICS
    # =========================================================================

    @abstractmethod
    async def get_most_consumed_recipes(
        self,
        user_id: int,
        days: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get recipes consumed most frequently.

        Args:
            user_id: User ID
            days: Number of days to analyze
            limit: Max recipes to return

        Returns:
            List: [
                {
                    "recipe_id": 5,
                    "recipe_name": "Chicken Salad",
                    "consumption_count": 8,
                    "average_portion": 1.1,
                    "total_calories": 3200
                },
                ...
            ]
        """
        pass

    @abstractmethod
    async def get_least_consumed_recipes(
        self,
        user_id: int,
        days: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get recipes consumed least frequently (but were planned).

        Identifies recipes user might not like.

        Args:
            user_id: User ID
            days: Number of days to analyze
            limit: Max recipes to return

        Returns:
            List: [
                {
                    "recipe_id": 12,
                    "recipe_name": "Brussels Sprouts Bowl",
                    "times_planned": 5,
                    "times_consumed": 1,
                    "skip_rate": 0.8
                },
                ...
            ]
        """
        pass

    @abstractmethod
    async def get_portion_size_preferences(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Analyze portion size preferences.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict: {
                "overall": {
                    "average_multiplier": 1.05,
                    "median_multiplier": 1.0,
                    "typically_smaller": 0.25,  # 25% of meals
                    "typically_larger": 0.15    # 15% of meals
                },
                "by_meal_type": {
                    "breakfast": 0.9,
                    "lunch": 1.1,
                    "dinner": 1.15,
                    "snack": 0.8
                },
                "by_recipe": [
                    {
                        "recipe_name": "Chicken Salad",
                        "average_multiplier": 1.2
                    },
                    ...
                ]
            }
        """
        pass

    # =========================================================================
    # MACRO BALANCE ANALYTICS
    # =========================================================================

    @abstractmethod
    async def get_macro_balance_analysis(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Analyze macro nutrient balance vs targets.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict: {
                "protein": {
                    "average_daily_grams": 145,
                    "target_grams": 150,
                    "average_percentage_of_calories": 25,
                    "days_over_target": 6,
                    "days_under_target": 8,
                    "deficit_average": -5
                },
                "carbs": {...},
                "fat": {...},
                "overall_balance": "good"  # good, needs_adjustment, poor
            }
        """
        pass

    @abstractmethod
    async def get_calorie_macro_correlation(
        self,
        user_id: int,
        days: int
    ) -> Dict:
        """
        Analyze correlation between total calories and macro distribution.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dict: {
                "high_calorie_days": {
                    "average_calories": 2400,
                    "protein_percentage": 28,
                    "carbs_percentage": 42,
                    "fat_percentage": 30
                },
                "low_calorie_days": {
                    "average_calories": 1700,
                    "protein_percentage": 30,
                    "carbs_percentage": 38,
                    "fat_percentage": 32
                },
                "correlation": {
                    "calories_vs_protein": 0.65,
                    "calories_vs_carbs": 0.82,
                    "calories_vs_fat": 0.45
                }
            }
        """
        pass

    # =========================================================================
    # COMPARATIVE ANALYTICS
    # =========================================================================

    @abstractmethod
    async def compare_periods(
        self,
        user_id: int,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date
    ) -> Dict:
        """
        Compare consumption between two time periods.

        Useful for "this week vs last week" comparisons.

        Args:
            user_id: User ID
            period1_start: Period 1 start date
            period1_end: Period 1 end date
            period2_start: Period 2 start date
            period2_end: Period 2 end date

        Returns:
            Dict: {
                "period1": {
                    "label": "2025-11-11 to 2025-11-17",
                    "average_daily_calories": 2050,
                    "adherence_rate": 0.82,
                    ...
                },
                "period2": {
                    "label": "2025-11-18 to 2025-11-24",
                    "average_daily_calories": 2180,
                    "adherence_rate": 0.87,
                    ...
                },
                "changes": {
                    "calorie_change": +130,
                    "calorie_change_percentage": 6.3,
                    "adherence_change": +0.05,
                    "interpretation": "improved"  # improved, declined, stable
                }
            }
        """
        pass

    # =========================================================================
    # STREAK AND MILESTONE TRACKING
    # =========================================================================

    @abstractmethod
    async def get_current_adherence_streak(
        self,
        user_id: int
    ) -> Dict:
        """
        Get current streak of consecutive days meeting adherence target.

        Adherence target: 80% of planned meals consumed.

        Args:
            user_id: User ID

        Returns:
            Dict: {
                "current_streak_days": 5,
                "streak_start_date": "2025-11-20",
                "longest_streak_days": 12,
                "longest_streak_period": "2025-10-05 to 2025-10-16"
            }
        """
        pass

    @abstractmethod
    async def get_milestone_progress(
        self,
        user_id: int
    ) -> Dict:
        """
        Get progress towards consumption milestones.

        Args:
            user_id: User ID

        Returns:
            Dict: {
                "total_meals_logged": 245,
                "total_days_tracked": 60,
                "milestones_achieved": [
                    {"name": "First meal logged", "date": "2025-09-25"},
                    {"name": "7-day streak", "date": "2025-10-02"},
                    {"name": "100 meals logged", "date": "2025-11-10"}
                ],
                "next_milestone": {
                    "name": "250 meals logged",
                    "progress": 245,
                    "target": 250,
                    "percentage": 98
                }
            }
        """
        pass