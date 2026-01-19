"""
General inventory alert notification implementation.

Triggered by inventory-related events.
Available on: Push + Email
Priority: Normal
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class InventoryAlertNotification(BaseNotification):
    """
    General inventory alert notification.

    Triggered by events:
    - inventory_updated (general alerts)

    Context includes:
    - alert_type: Type of inventory alert
    - message: Alert message
    - item_count: Number of items affected
    """

    def get_notification_type(self) -> str:
        """Inventory alert notification type."""
        return "inventory_alert"

    def determine_channels(self) -> List[str]:
        """
        Inventory alerts on Push + Email.

        Push: Quick notification
        Email: Detailed inventory information
        """
        return ["push", "email"]

    def calculate_priority(self) -> str:
        """
        General inventory alerts are normal priority.

        Not urgent but important for awareness.
        """
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for inventory alert templates.

        Template variables:
        - alert_type: "inventory_updated", "items_added", etc.
        - message: "Your inventory has been updated"
        - item_count: 5
        """
        return {
            "alert_type": self.metadata.get("alert_type", "general"),
            "message": self.metadata.get("message", "Inventory alert"),
            "item_count": self.metadata.get("item_count", 0),
        }
