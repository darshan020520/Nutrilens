"""
Domain models for notification system.

This package contains pure domain models with no external dependencies.
"""

from .notification import (
    NotificationMessage,
    NotificationType,
    NotificationPriority,
    ChannelType,
    DeliveryResult
)

__all__ = [
    "NotificationMessage",
    "NotificationType",
    "NotificationPriority",
    "ChannelType",
    "DeliveryResult"
]
