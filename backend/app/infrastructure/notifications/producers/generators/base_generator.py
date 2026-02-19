from abc import ABC, abstractmethod
from typing import Dict, Any
from app.domain.notifications import NotificationMessage, NotificationType, NotificationPriority, ChannelType
from app.models.database import User


class NotificationGenerator(ABC):

    def __init__(self, user_repository, template_factory):

        self.user_repo = user_repository
        self.template_factory = template_factory

    def generate(
        self,
        user_id: int,
        notification_type: NotificationType,
        priority: NotificationPriority,
        data: Dict[str, Any]
    ) -> NotificationMessage:

        user = self.validate_prerequisites(user_id)

        context = self.fetch_context_data(user, data)

        template = self.template_factory.get_template(
            channel=self.get_channel_type(),
            notification_type=notification_type
        )
        rendered_content = template.render(context)

        enriched_data = self.enrich_notification(rendered_content, user, data)

        self.validate_content(enriched_data)

        notification = NotificationMessage(
            user_id=user_id,
            notification_type=notification_type,
            priority=priority,
            channel=self.get_channel_type(),
            title=enriched_data.get("title", ""),
            body=enriched_data.get("body", ""),
            data=enriched_data.get("data", {}),
            action_url=enriched_data.get("action_url")
        )

        return notification


    @abstractmethod
    def get_channel_type(self) -> ChannelType:
        pass

    @abstractmethod
    def validate_prerequisites(self, user_id: int) -> User:
        pass

    def fetch_context_data(self, user: User, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **trigger_data,
            "user_name": user.username or "User",
            "user_email": user.email,
        }

    @abstractmethod
    def enrich_notification(
        self,
        rendered_content: Dict[str, Any],
        user: User,
        original_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    def validate_content(self, notification_data: Dict[str, Any]) -> None:
        pass

class InvalidRecipientException(Exception):
    pass


class InvalidContentException(Exception):
    pass
