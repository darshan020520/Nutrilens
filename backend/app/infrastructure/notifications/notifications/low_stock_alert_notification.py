"""
Low stock alert notification implementation.

Triggered when inventory items are running low.
Available on: Push + Email
Priority: Normal
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class LowStockAlertNotification(BaseNotification):
    """
    Alert for low stock items.

    Triggered by events:
    - scheduled_inventory_check (worker at 8 AM)

    Context includes:
    - low_stock_items: List of items running low
    - item_count: Number of low stock items
    """

    def get_notification_type(self) -> str:
        """Low stock alert notification type."""
        return "low_stock_alert"

    def determine_channels(self) -> List[str]:
        """
        Low stock alerts on Push + Email.

        Push: Quick notification
        Email: Detailed list with suggestions
        """
        return ["push", "email"]

    def calculate_priority(self) -> str:
        """
        Low stock alerts are normal priority.

        Important but not urgent.
        """
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for low stock alert templates.

        Template variables:
        - low_stock_items: [{"name": "Eggs", "quantity": 2, "threshold": 6}, ...]
        - item_count: 4
        """
        return {
            "low_stock_items": self.metadata.get("low_stock_items", []),
            "item_count": self.metadata.get("item_count", 0),
        }
