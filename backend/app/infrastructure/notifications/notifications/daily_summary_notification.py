from typing import Dict, Any, List
from ..base_notification import BaseNotification


class DailySummaryNotification(BaseNotification):
    def get_notification_type(self) -> str:
        return "daily_summary"

    def determine_channels(self) -> List[str]:
        return ["email"]

    def calculate_priority(self) -> str:
        return "low"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "date": self.metadata.get("date", ""),
            "meals_consumed": self.metadata.get("meals_consumed", 0),
            "compliance_rate": self.metadata.get("compliance_rate", 0.0),
            "calories_consumed": self.metadata.get("calories_consumed", 0),
            "protein_g": self.metadata.get("protein_g", 0),
        }
