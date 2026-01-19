"""
Weekly report notification implementation.

Triggered every Sunday at 8 PM with weekly analytics.
Available on: Email only
Priority: Low
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class WeeklyReportNotification(BaseNotification):
    """
    Weekly nutrition and progress report.

    Triggered by events:
    - scheduled_weekly_report (worker on Sunday 8 PM)

    Context includes:
    - start_date: Week start date
    - end_date: Week end date
    - total_meals: Total meals logged
    - average_compliance: Average compliance rate
    - weight_change: Weight change during week
    - achievements_unlocked: Achievements during week
    """

    def get_notification_type(self) -> str:
        """Weekly report notification type."""
        return "weekly_report"

    def determine_channels(self) -> List[str]:
        """
        Weekly reports only via Email.

        Detailed report with charts, tables, and insights.
        """
        return ["email"]

    def calculate_priority(self) -> str:
        """
        Weekly reports are low priority.

        Non-urgent analytical content.
        """
        return "low"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for weekly report templates.

        Template variables:
        - start_date: "2026-01-01"
        - end_date: "2026-01-07"
        - total_meals: 21
        - average_compliance: 88.5
        - weight_change: -1.2
        - achievements_unlocked: 2
        """
        return {
            "start_date": self.metadata.get("start_date", ""),
            "end_date": self.metadata.get("end_date", ""),
            "total_meals": self.metadata.get("total_meals", 0),
            "average_compliance": self.metadata.get("average_compliance", 0.0),
            "weight_change": self.metadata.get("weight_change", 0.0),
            "achievements_unlocked": self.metadata.get("achievements_unlocked", 0),
        }
