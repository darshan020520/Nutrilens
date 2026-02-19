from typing import Dict, Any, List
from ..base_notification import BaseNotification


class AchievementNotification(BaseNotification):
    def get_notification_type(self) -> str:
        return "achievement"

    def determine_channels(self) -> List[str]:
        return ["push", "email", "whatsapp"]

    def calculate_priority(self) -> str:
        return "high"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "achievement_type": self.metadata.get("achievement_type", "unknown"),
            "achievement_name": self.metadata.get("achievement_name", "Achievement Unlocked"),
            "description": self.metadata.get("description", ""),
            "message": self.metadata.get("message", "Congratulations on your achievement!"),
        }
