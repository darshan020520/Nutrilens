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
        notification_class = cls._notification_types.get(notification_type)

        if notification_class is None:
            raise ValueError(
                f"Unknown notification type: {notification_type}. "
                f"Supported types: {list(cls._notification_types.keys())}"
            )

        return notification_class(user_id=user_id, metadata=metadata)

    @classmethod
    def get_supported_types(cls) -> list:
        return list(cls._notification_types.keys())
