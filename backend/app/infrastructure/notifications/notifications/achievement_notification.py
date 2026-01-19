"""
Achievement notification implementation.

Triggered when user unlocks achievements (7-day streak, etc.)
Available on: Push + Email
Priority: High
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class AchievementNotification(BaseNotification):
    """
    Notification for unlocked achievements.

    Triggered by events:
    - meal_logged (if achievement unlocked)

    Context includes:
    - achievement_type: Type of achievement (streak_7day, etc.)
    - achievement_name: Display name
    - description: Achievement description
    - message: Congratulatory message
    """

    def get_notification_type(self) -> str:
        """Achievement notification type."""
        return "achievement"

    def determine_channels(self) -> List[str]:
        """
        Achievements available on Push + Email.

        Push: Immediate celebration notification
        Email: Detailed achievement card with badge
        """
        return ["push", "email"]

    def calculate_priority(self) -> str:
        """
        Achievements are high priority.

        Users want immediate feedback when they unlock achievements.
        """
        return "high"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for achievement templates.

        Template variables:
        - achievement_type: streak_7day, first_meal, etc.
        - achievement_name: "7-Day Streak Master"
        - description: "Logged meals for 7 consecutive days"
        - message: Congratulatory message
        - user_name: Recipient name (added by consumer)
        """
        return {
            "achievement_type": self.metadata.get("achievement_type", "unknown"),
            "achievement_name": self.metadata.get("achievement_name", "Achievement Unlocked"),
            "description": self.metadata.get("description", ""),
            "message": self.metadata.get("message", "Congratulations on your achievement!"),
        }
