from typing import Dict, Any, List
from ..base_notification import BaseNotification


class WeeklyReportNotification(BaseNotification):

    def get_notification_type(self) -> str:
        return "weekly_report"

    def determine_channels(self) -> List[str]:
        return ["email"]

    def calculate_priority(self) -> str:
        return "low"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "start_date": self.metadata.get("start_date", ""),
            "end_date": self.metadata.get("end_date", ""),
            "total_meals": self.metadata.get("total_meals", 0),
            "average_compliance": self.metadata.get("average_compliance", 0.0),
            "weight_change": self.metadata.get("weight_change", 0.0),
            "achievements_unlocked": self.metadata.get("achievements_unlocked", 0),
        }
