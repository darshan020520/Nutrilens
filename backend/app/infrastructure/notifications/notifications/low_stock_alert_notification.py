from typing import Dict, Any, List
from ..base_notification import BaseNotification


class LowStockAlertNotification(BaseNotification):
    def get_notification_type(self) -> str:
        return "low_stock_alert"

    def determine_channels(self) -> List[str]:
        return ["email", "whatsapp"]

    def calculate_priority(self) -> str:
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        return {
            "low_stock_items": self.metadata.get("low_stock_items", []),
            "item_count": self.metadata.get("item_count", 0),
        }
