"""
Factory for creating notification objects based on notification type.

Maps notification_type → Notification class using Factory Pattern.
"""

from typing import Dict, Any
from ..base_notification import BaseNotification
from ..notifications import (
    AchievementNotification,
    MealReminderNotification,
    DailySummaryNotification,
    WeeklyReportNotification,
    InventoryAlertNotification,
    ExpiryAlertNotification,
    LowStockAlertNotification,
    ProgressUpdateNotification,
)


class NotificationFactory:
    """
    Factory for creating notification objects (Factory Pattern).

    Maps notification_type to concrete notification class.
    Each notification class implements BaseNotification's Template Pattern.

    Usage:
        factory = NotificationFactory()
        notification = factory.create_notification(
            notification_type="achievement",
            user_id=123,
            metadata={"achievement_type": "streak_7day", ...}
        )
        notification_data = notification.create()  # Returns dict to queue
    """

    # Map notification_type → Notification class
    _notification_types = {
        "achievement": AchievementNotification,
        "meal_reminder": MealReminderNotification,
        "daily_summary": DailySummaryNotification,
        "weekly_report": WeeklyReportNotification,
        "inventory_alert": InventoryAlertNotification,
        "expiry_alert": ExpiryAlertNotification,
        "low_stock_alert": LowStockAlertNotification,
        "progress_update": ProgressUpdateNotification,
    }

    @classmethod
    def create_notification(
        cls,
        notification_type: str,
        user_id: int,
        metadata: Dict[str, Any]
    ) -> BaseNotification:
        """
        Create notification object based on type.

        Args:
            notification_type: Type of notification (achievement, meal_reminder, etc.)
            user_id: Recipient user ID
            metadata: Event-specific data for notification context

        Returns:
            Notification object (subclass of BaseNotification)

        Raises:
            ValueError: If notification_type is not supported

        Example:
            # Create achievement notification
            notification = NotificationFactory.create_notification(
                notification_type="achievement",
                user_id=123,
                metadata={
                    "achievement_type": "streak_7day",
                    "achievement_name": "7-Day Streak Master",
                    "description": "Logged meals for 7 consecutive days",
                    "message": "Congratulations!"
                }
            )

            # Get notification data to queue
            notification_data = notification.create()
            # Returns:
            # {
            #     "user_id": 123,
            #     "type": "achievement",
            #     "priority": "high",
            #     "channels": ["push", "email"],
            #     "context": {...},
            #     "metadata": {...},
            #     "created_at": "2026-01-08T..."
            # }
        """
        notification_class = cls._notification_types.get(notification_type)

        if notification_class is None:
            raise ValueError(
                f"Unknown notification type: {notification_type}. "
                f"Supported types: {list(cls._notification_types.keys())}"
            )

        return notification_class(user_id=user_id, metadata=metadata)

    @classmethod
    def get_supported_types(cls) -> list:
        """
        Get list of supported notification types.

        Returns:
            List of supported notification type strings
        """
        return list(cls._notification_types.keys())
