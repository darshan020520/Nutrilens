"""
Progress update notification implementation.

Triggered when user hits milestones or progress markers.
Available on: Push + Email
Priority: Normal
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class ProgressUpdateNotification(BaseNotification):
    """
    Notification for progress milestones.

    Triggered by events:
    - meal_logged (if milestone reached)

    Context includes:
    - milestone_type: Type of milestone reached
    - milestone_name: Name of milestone
    - progress_percentage: Current progress percentage
    - message: Progress message
    """

    def get_notification_type(self) -> str:
        """Progress update notification type."""
        return "progress_update"

    def determine_channels(self) -> List[str]:
        """
        Progress updates on Push + Email.

        Push: Immediate feedback
        Email: Detailed progress visualization
        """
        return ["push", "email"]

    def calculate_priority(self) -> str:
        """
        Progress updates are normal priority.

        Encouraging but not urgent.
        """
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for progress update templates.

        Template variables:
        - milestone_type: "calorie_goal", "protein_goal", "streak", etc.
        - milestone_name: "Daily Calorie Goal Reached"
        - progress_percentage: 85.5
        - message: "Great job! You've reached 85% of your goal"
        """
        return {
            "milestone_type": self.metadata.get("milestone_type", "general"),
            "milestone_name": self.metadata.get("milestone_name", "Progress Update"),
            "progress_percentage": self.metadata.get("progress_percentage", 0.0),
            "message": self.metadata.get("message", "Keep up the great work!"),
        }
