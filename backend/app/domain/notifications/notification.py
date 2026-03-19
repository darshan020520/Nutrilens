from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional


class NotificationType(str, Enum):
    """Types of notifications supported by the system"""
    MEAL_REMINDER = "meal_reminder"
    INVENTORY_ALERT = "inventory_alert"
    PROGRESS_UPDATE = "progress_update"
    ACHIEVEMENT = "achievement"
    EXPIRY_ALERT = "expiry_alert"
    LOW_STOCK_ALERT = "low_stock_alert"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_REPORT = "weekly_report"


class NotificationPriority(str, Enum):
    """Priority levels for notification delivery"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ChannelType(str, Enum):
    """Delivery channels for notifications"""
    PUSH = "push"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


@dataclass
class NotificationMessage:
    """
    Domain model representing a notification message.

    This is a pure domain object with no infrastructure dependencies.
    It represents the core concept of a notification in our system.
    """

    # Identity
    user_id: int
    notification_type: NotificationType
    priority: NotificationPriority

    # Content
    title: str
    body: str
    data: Dict[str, Any] = field(default_factory=dict)

    # Routing
    channel: Optional[ChannelType] = None
    action_url: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 5
    next_retry_at: Optional[datetime] = None

    # Tracking
    queued_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "user_id": self.user_id,
            "notification_type": self.notification_type.value if isinstance(self.notification_type, Enum) else self.notification_type,
            "priority": self.priority.value if isinstance(self.priority, Enum) else self.priority,
            "title": self.title,
            "body": self.body,
            "data": self.data,
            "channel": self.channel.value if self.channel and isinstance(self.channel, Enum) else self.channel,
            "action_url": self.action_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationMessage":
        """Create from dictionary (deserialization)"""
        # Convert string enums back to enum types
        if isinstance(data.get("notification_type"), str):
            data["notification_type"] = NotificationType(data["notification_type"])
        if isinstance(data.get("priority"), str):
            data["priority"] = NotificationPriority(data["priority"])
        if isinstance(data.get("channel"), str):
            data["channel"] = ChannelType(data["channel"])

        # Convert ISO strings back to datetime
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("next_retry_at"), str):
            data["next_retry_at"] = datetime.fromisoformat(data["next_retry_at"])
        if isinstance(data.get("queued_at"), str):
            data["queued_at"] = datetime.fromisoformat(data["queued_at"])
        if isinstance(data.get("sent_at"), str):
            data["sent_at"] = datetime.fromisoformat(data["sent_at"])

        return cls(**data)

    def increment_retry(self) -> None:
        """Increment retry count"""
        self.retry_count += 1

    def has_retries_remaining(self) -> bool:
        """Check if notification can be retried"""
        return self.retry_count < self.max_retries

    def is_urgent(self) -> bool:
        """Check if notification is urgent"""
        return self.priority == NotificationPriority.URGENT


@dataclass
class DeliveryResult:
    """
    Result of a notification delivery attempt.

    Used by channel strategies to report success/failure.
    """

    success: bool
    channel: ChannelType
    message: str = ""
    error: Optional[str] = None
    external_id: Optional[str] = None  # ID from provider (SendGrid, Twilio, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)
    delivered_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "success": self.success,
            "channel": self.channel.value if isinstance(self.channel, Enum) else self.channel,
            "message": self.message,
            "error": self.error,
            "external_id": self.external_id,
            "metadata": self.metadata,
            "delivered_at": self.delivered_at.isoformat()
        }
