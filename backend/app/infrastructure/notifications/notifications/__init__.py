"""
Concrete notification type implementations.

Each notification type implements BaseNotification's Template Pattern
to define its specific channels, priority, and context building logic.
"""

from .achievement_notification import AchievementNotification
from .meal_reminder_notification import MealReminderNotification
from .daily_summary_notification import DailySummaryNotification
from .weekly_report_notification import WeeklyReportNotification
from .inventory_alert_notification import InventoryAlertNotification
from .expiry_alert_notification import ExpiryAlertNotification
from .low_stock_alert_notification import LowStockAlertNotification
from .progress_update_notification import ProgressUpdateNotification

__all__ = [
    "AchievementNotification",
    "MealReminderNotification",
    "DailySummaryNotification",
    "WeeklyReportNotification",
    "InventoryAlertNotification",
    "ExpiryAlertNotification",
    "LowStockAlertNotification",
    "ProgressUpdateNotification",
]
