from typing import Dict, Any, List
from ..base_notification import BaseNotification


class MealReminderNotification(BaseNotification):
    def get_notification_type(self) -> str:
        return "meal_reminder"

    def determine_channels(self) -> List[str]:
        return ["push", "sms"]

    def calculate_priority(self) -> str:
        time_until = self.metadata.get("time_until", 30)
        if time_until <= 15:
            return "urgent"
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "meal_type": self.metadata.get("meal_type", "meal"),
            "recipe_name": self.metadata.get("recipe_name", "your meal"),
            "time_until": self.metadata.get("time_until", 30),
            "scheduled_time": self.metadata.get("scheduled_time", ""),
        }
