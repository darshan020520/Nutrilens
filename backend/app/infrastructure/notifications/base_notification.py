"""
Base notification class using Template Pattern for notification creation.

The Template Pattern defines the algorithm for creating notifications.
Subclasses customize specific steps: channels, priority, and context building.

This is NOT for template file rendering - that happens in the consumer.
This is for creating the notification data structure to queue.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime


class BaseNotification(ABC):
    """
    Base class for notification creation (Template Pattern).

    Template Method Pattern for notification CREATION:
    - create() is the "template method" - defines the algorithm structure
    - determine_channels(), calculate_priority(), build_notification_context()
      are "hook methods" - customized by each notification type

    This creates the notification data to queue, NOT the rendered content.
    Template rendering happens consumer-side.

    Example:
        class AchievementNotification(BaseNotification):
            def __init__(self, user_id, metadata):
                self.user_id = user_id
                self.achievement_type = metadata.get("achievement_type")
                self.achievement_name = metadata.get("achievement_name")

            def determine_channels(self):
                return ["push", "email"]  # Achievements on push + email

            def calculate_priority(self):
                return "high"  # Achievements are high priority

            def build_notification_context(self):
                return {
                    "achievement_type": self.achievement_type,
                    "achievement_name": self.achievement_name,
                    "user_id": self.user_id
                }

        # Usage by factory
        notification = AchievementNotification(user_id=123, metadata={...})
        notification_data = notification.create()  # Returns dict to queue
    """

    def __init__(self, user_id: int, metadata: Dict[str, Any]):
        """
        Initialize notification with user and event metadata.

        Args:
            user_id: Recipient user ID
            metadata: Event-specific data for notification context
        """
        self.user_id = user_id
        self.metadata = metadata

    def create(self) -> Dict[str, Any]:
        """
        Template Method - Algorithm for creating notification data.

        This orchestrates the notification creation process:
        1. Determine available channels for this notification type
        2. Calculate priority/severity
        3. Build notification context (data for template rendering)
        4. Add common metadata (timestamps, retry config)

        Returns:
            Complete notification dictionary ready to queue to Redis:
            {
                "user_id": int,
                "type": str,
                "priority": str,
                "channels": List[str],
                "context": Dict,
                "metadata": Dict,
                "created_at": str (ISO format)
            }

        Note: This does NOT render templates or check user preferences.
        Consumer will:
        - Get user preferences
        - Pick preferred channel from available channels
        - Render template with context
        - Send via channel strategy
        """
        # Step 1: Determine available channels for this notification type
        channels = self.determine_channels()

        # Step 2: Calculate priority/severity
        priority = self.calculate_priority()

        # Step 3: Build notification context for template rendering
        context = self.build_notification_context()

        # Step 4: Add common metadata
        common_metadata = self._add_common_metadata()

        # Step 5: Return complete notification data
        return {
            "user_id": self.user_id,
            "type": self.get_notification_type(),
            "priority": priority,
            "channels": channels,
            "context": context,
            "metadata": common_metadata,
            "created_at": datetime.utcnow().isoformat()
        }

    # ===== Hook Methods - Subclasses MUST override these =====

    @abstractmethod
    def get_notification_type(self) -> str:
        """
        Return the notification type identifier.

        Returns:
            NotificationType value (achievement, meal_reminder, etc.)

        Example:
            class AchievementNotification:
                def get_notification_type(self):
                    return "achievement"
        """
        pass

    @abstractmethod
    def determine_channels(self) -> List[str]:
        """
        Determine which channels are available for this notification type.

        This defines which channels CAN be used for this notification.
        Consumer will pick ONE based on user preference.

        Returns:
            List of available channel types (push, email, sms, whatsapp)

        Examples:
            class AchievementNotification:
                def determine_channels(self):
                    return ["push", "email"]  # Achievements on push + email

            class MealReminderNotification:
                def determine_channels(self):
                    return ["push", "sms"]  # Reminders on push + SMS

            class DailySummaryNotification:
                def determine_channels(self):
                    return ["email"]  # Summaries only via email

            class UrgentInventoryAlert:
                def determine_channels(self):
                    return ["push", "email", "sms"]  # All channels for urgent
        """
        pass

    @abstractmethod
    def calculate_priority(self) -> str:
        """
        Calculate priority/severity of this notification.

        Returns:
            Priority level: "low", "normal", "high", "urgent"

        Examples:
            class AchievementNotification:
                def calculate_priority(self):
                    return "high"  # Achievements are high priority

            class MealReminderNotification:
                def calculate_priority(self):
                    if self.metadata.get("time_until") <= 15:
                        return "urgent"  # 15 min or less = urgent
                    return "normal"

            class WeeklyReportNotification:
                def calculate_priority(self):
                    return "low"  # Reports are low priority

            class ExpiryAlertNotification:
                def calculate_priority(self):
                    days_until_expiry = self.metadata.get("days_until_expiry", 7)
                    if days_until_expiry <= 1:
                        return "urgent"
                    elif days_until_expiry <= 3:
                        return "high"
                    return "normal"
        """
        pass

    @abstractmethod
    def build_notification_context(self) -> Dict[str, Any]:
        """
        Build context data for template rendering.

        This data will be used by the consumer to render templates.
        Include all variables needed by the template files.

        Returns:
            Dictionary of context variables for Jinja2 template rendering

        Examples:
            class AchievementNotification:
                def build_notification_context(self):
                    return {
                        "achievement_type": self.metadata.get("achievement_type"),
                        "achievement_name": self.metadata.get("achievement_name"),
                        "description": self.metadata.get("description"),
                        "icon": self._get_achievement_icon()
                    }

            class MealReminderNotification:
                def build_notification_context(self):
                    return {
                        "meal_type": self.metadata.get("meal_type"),
                        "recipe_name": self.metadata.get("recipe_name"),
                        "time_until": self.metadata.get("time_until"),
                        "scheduled_time": self.metadata.get("scheduled_time")
                    }

            class DailySummaryNotification:
                def build_notification_context(self):
                    return {
                        "date": self.metadata.get("date"),
                        "meals_consumed": self.metadata.get("meals_consumed"),
                        "compliance_rate": self.metadata.get("compliance_rate"),
                        "calories_consumed": self.metadata.get("calories_consumed"),
                        "protein_g": self.metadata.get("protein_g")
                    }
        """
        pass

    # ===== Common Helper Methods =====

    def _add_common_metadata(self) -> Dict[str, Any]:
        """
        Add common metadata to all notifications.

        Returns:
            Dictionary with retry config and other common metadata
        """
        return {
            "retry_count": 0,
            "max_retries": 5,
            "source": "notification_system",
            "version": "1.0"
        }
