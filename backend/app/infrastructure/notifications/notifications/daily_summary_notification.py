"""
Daily summary notification implementation.

Triggered at 9 PM daily with nutrition summary.
Available on: Email only
Priority: Low
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class DailySummaryNotification(BaseNotification):
    """
    Daily nutrition summary notification.

    Triggered by events:
    - scheduled_daily_summary (worker at 9 PM)

    Context includes:
    - date: Date of summary
    - meals_consumed: Number of meals logged
    - compliance_rate: Adherence to meal plan (%)
    - calories_consumed: Total calories
    - protein_g: Total protein in grams
    """

    def get_notification_type(self) -> str:
        """Daily summary notification type."""
        return "daily_summary"

    def determine_channels(self) -> List[str]:
        """
        Daily summaries only via Email.

        Email is best for detailed summaries with charts and tables.
        Too much information for push/SMS.
        """
        return ["email"]

    def calculate_priority(self) -> str:
        """
        Daily summaries are low priority.

        Non-urgent informational content.
        """
        return "low"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for daily summary templates.

        Template variables:
        - date: "2026-01-08"
        - meals_consumed: 3
        - compliance_rate: 85.5
        - calories_consumed: 1850
        - protein_g: 120
        """
        return {
            "date": self.metadata.get("date", ""),
            "meals_consumed": self.metadata.get("meals_consumed", 0),
            "compliance_rate": self.metadata.get("compliance_rate", 0.0),
            "calories_consumed": self.metadata.get("calories_consumed", 0),
            "protein_g": self.metadata.get("protein_g", 0),
        }
