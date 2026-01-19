"""
Base interface for notification channels (Strategy Pattern).

Each channel (Email, SMS, Push, WhatsApp) implements this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from app.domain.notifications import NotificationMessage, DeliveryResult
from app.models.database import User


class INotificationChannel(ABC):
    """
    Interface for notification delivery channels (Strategy Pattern).

    Each concrete channel (EmailChannel, SMSChannel, PushChannel) implements
    this interface, allowing them to be used interchangeably.

    This follows the Strategy Pattern:
    - Define family of algorithms (delivery methods)
    - Encapsulate each one
    - Make them interchangeable

    Example:
        email_channel = EmailChannel(sendgrid_client)
        sms_channel = SMSChannel(twilio_client)

        # Both can be used interchangeably
        for channel in [email_channel, sms_channel]:
            result = await channel.send(notification)
    """

    @abstractmethod
    async def send(self, notification: NotificationMessage, user: User) -> DeliveryResult:
        """
        Send notification via this channel.

        Args:
            notification: The notification to send
            user: The recipient user (contains email, phone, device tokens, etc.)

        Returns:
            DeliveryResult indicating success or failure

        Example:
            result = await email_channel.send(notification, user)
            if result.success:
                print(f"Sent via {result.channel}")
            else:
                print(f"Failed: {result.error}")
        """
        pass

    @abstractmethod
    def validate(self, user: User) -> bool:
        """
        Check if user can receive notifications via this channel.

        Args:
            user: The user to validate

        Returns:
            True if user has required credentials (email verified, phone opt-in, etc.)

        Example:
            if email_channel.validate(user):
                await email_channel.send(notification, user)
        """
        pass

    @abstractmethod
    def get_channel_type(self) -> str:
        """
        Get the channel type identifier.

        Returns:
            Channel type: "email", "sms", "push", "whatsapp"

        Example:
            channel_type = email_channel.get_channel_type()  # "email"
        """
        pass
