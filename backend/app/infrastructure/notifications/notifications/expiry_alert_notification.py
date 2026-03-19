from typing import Dict, Any, List
from ..base_notification import BaseNotification


class ExpiryAlertNotification(BaseNotification):

    def get_notification_type(self) -> str:
        return "expiry_alert"

    def determine_channels(self) -> List[str]:
        return ["email", "whatsapp"]

    def calculate_priority(self) -> str:
        days_until_expiry = self.metadata.get("days_until_expiry", 7)
        if days_until_expiry <= 1:
            return "urgent"
        elif days_until_expiry <= 3:
            return "high"
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "expiring_items": self.metadata.get("expiring_items", []),
            "days_until_expiry": self.metadata.get("days_until_expiry", 0),
            "item_count": self.metadata.get("item_count", 0),
        }
