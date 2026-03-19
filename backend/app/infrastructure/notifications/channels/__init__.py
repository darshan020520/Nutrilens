"""
Notification channel strategies.

Each channel implements Strategy Pattern for delivery.
"""

from .base_channel import INotificationChannel
from .email_channel import EmailChannel
from .sms_channel import SMSChannel
from .push_channel import PushChannel
from .whatsapp_channel import WhatsAppChannel

__all__ = [
    "INotificationChannel",
    "EmailChannel",
    "SMSChannel",
    "PushChannel",
    "WhatsAppChannel",
]
