"""
Expiry alert notification implementation.

Triggered when inventory items are expiring soon.
Available on: Push + Email + SMS
Priority: Normal to Urgent (based on days until expiry)
"""

from typing import Dict, Any, List
from ..base_notification import BaseNotification


class ExpiryAlertNotification(BaseNotification):
    """
    Alert for items expiring soon.

    Triggered by events:
    - scheduled_inventory_check (worker at 8 AM)

    Context includes:
    - expiring_items: List of items expiring
    - days_until_expiry: Days until expiry
    - item_count: Number of items expiring
    """

    def get_notification_type(self) -> str:
        """Expiry alert notification type."""
        return "expiry_alert"

    def determine_channels(self) -> List[str]:
        """
        Expiry alerts on Push + Email + SMS.

        All channels available due to importance.
        User preference determines which is used.
        """
        return ["push", "email", "sms"]

    def calculate_priority(self) -> str:
        """
        Priority based on days until expiry.

        - Urgent: 1 day or less
        - High: 2-3 days
        - Normal: 4+ days
        """
        days_until_expiry = self.metadata.get("days_until_expiry", 7)
        if days_until_expiry <= 1:
            return "urgent"
        elif days_until_expiry <= 3:
            return "high"
        return "normal"

    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context for expiry alert templates.

        Template variables:
        - expiring_items: [{"name": "Milk", "expiry_date": "2026-01-09"}, ...]
        - days_until_expiry: 1
        - item_count: 3
        """
        return {
            "expiring_items": self.metadata.get("expiring_items", []),
            "days_until_expiry": self.metadata.get("days_until_expiry", 0),
            "item_count": self.metadata.get("item_count", 0),
        }
