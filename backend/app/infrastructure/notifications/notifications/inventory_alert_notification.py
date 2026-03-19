from typing import Dict, Any, List
from ..base_notification import BaseNotification


class InventoryAlertNotification(BaseNotification):

    def get_notification_type(self) -> str:
        return "inventory_alert"

    def determine_channels(self) -> List[str]:
        return ["email", "whatsapp"]

    def calculate_priority(self) -> str:
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "alert_type": self.metadata.get("alert_type", "general"),
            "message": self.metadata.get("message", "Inventory alert"),
            "item_count": self.metadata.get("item_count", 0),
        }
