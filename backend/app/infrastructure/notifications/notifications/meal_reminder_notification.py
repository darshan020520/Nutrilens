"""
Meal reminder notification implementation.

Triggered 30 minutes before scheduled meal time.
Available on: Push + SMS
Priority: Normal to Urgent (based on time)
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class MealReminderNotification(BaseNotification):
    """
    Notification to remind users about upcoming meals.

    Triggered by events:
    - scheduled_meal_reminder (worker checks 30 min before meals)

    Context includes:
    - meal_type: breakfast, lunch, dinner
    - recipe_name: Name of planned meal
    - time_until: Minutes until meal time
    - scheduled_time: Actual meal time
    """

    def get_notification_type(self) -> str:
        """Meal reminder notification type."""
        return "meal_reminder"

    def determine_channels(self) -> List[str]:
        """
        Meal reminders available on Push + SMS.

        Push: Primary channel for timely reminders
        SMS: Fallback for users who prefer text reminders
        """
        return ["push", "sms"]

    def calculate_priority(self) -> str:
        """
        Priority based on time until meal.

        - Urgent: 15 minutes or less
        - Normal: More than 15 minutes
        """
        time_until = self.metadata.get("time_until", 30)
        if time_until <= 15:
            return "urgent"
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for meal reminder templates.

        Template variables:
        - meal_type: "breakfast", "lunch", "dinner"
        - recipe_name: "Grilled Chicken Salad"
        - time_until: 30 (minutes)
        - scheduled_time: "12:30 PM"
        """
        return {
            "meal_type": self.metadata.get("meal_type", "meal"),
            "recipe_name": self.metadata.get("recipe_name", "your meal"),
            "time_until": self.metadata.get("time_until", 30),
            "scheduled_time": self.metadata.get("scheduled_time", ""),
        }
