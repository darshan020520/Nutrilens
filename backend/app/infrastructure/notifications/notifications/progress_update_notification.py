from typing import Dict, Any, List
from ..base_notification import BaseNotification


class ProgressUpdateNotification(BaseNotification):
    def get_notification_type(self) -> str:
        return "progress_update"

    def determine_channels(self) -> List[str]:
        return ["whatsapp", "email"]

    def calculate_priority(self) -> str:
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "milestone_type": self.metadata.get("milestone_type", "general"),
            "milestone_name": self.metadata.get("milestone_name", "Progress Update"),
            "progress_percentage": self.metadata.get("progress_percentage", 0.0),
            "message": self.metadata.get("message", "Keep up the great work!"),
        }
