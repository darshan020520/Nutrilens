"""
Base notification generator using Template Pattern.

The Template Pattern defines the skeleton of an algorithm in a base class,
allowing subclasses to override specific steps without changing the algorithm's structure.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from app.domain.notifications import NotificationMessage, NotificationType, NotificationPriority, ChannelType
from app.models.database import User


class NotificationGenerator(ABC):
    """
    Base class for notification generators (Template Pattern).

    This class defines the algorithm structure for generating notifications.
    Subclasses (EmailGenerator, SMSGenerator, PushGenerator) customize specific steps.

    Template Method Pattern:
    - generate() is the "template method" - defines algorithm structure
    - validate_prerequisites(), fetch_context_data(), etc. are "hook methods" - customized by subclasses

    Example:
        class EmailGenerator(NotificationGenerator):
            def validate_prerequisites(self, user):
                if not user.email or not user.email_verified:
                    raise InvalidRecipientException("Email not verified")
                return user

            def enrich_notification(self, content, user):
                return {
                    **content,
                    "unsubscribe_url": f"https://app.com/unsubscribe/{user.id}"
                }

        # Usage
        generator = EmailGenerator(template_factory, user_repo)
        notification = generator.generate(
            user_id=123,
            notification_type=NotificationType.ACHIEVEMENT,
            data={"achievement": "7-day streak"}
        )
    """

    def __init__(self, user_repository, template_factory):
        """
        Initialize generator with dependencies.

        Args:
            user_repository: Repository for fetching user data
            template_factory: Factory for loading templates
        """
        self.user_repo = user_repository
        self.template_factory = template_factory

    def generate(
        self,
        user_id: int,
        notification_type: NotificationType,
        priority: NotificationPriority,
        data: Dict[str, Any]
    ) -> NotificationMessage:
        """
        Template Method - Defines the algorithm structure.

        This method orchestrates the notification generation process.
        Each step can be customized by subclasses.

        Steps:
        1. Validate prerequisites (channel-specific)
        2. Fetch context data (common + channel-specific)
        3. Load and render template
        4. Enrich with channel-specific data
        5. Validate final content
        6. Create NotificationMessage

        Args:
            user_id: Recipient user ID
            notification_type: Type of notification
            priority: Notification priority
            data: Additional data for template rendering

        Returns:
            NotificationMessage ready to be queued

        Raises:
            InvalidRecipientException: If user cannot receive via this channel
            InvalidContentException: If generated content is invalid
        """
        # Step 1: Validate prerequisites (e.g., email verified, phone opt-in)
        user = self.validate_prerequisites(user_id)

        # Step 2: Fetch context data for template rendering
        context = self.fetch_context_data(user, data)

        # Step 3: Load template and render content
        template = self.template_factory.get_template(
            channel=self.get_channel_type(),
            notification_type=notification_type
        )
        rendered_content = template.render(context)

        # Step 4: Enrich with channel-specific data (e.g., unsubscribe link, SMS truncation)
        enriched_data = self.enrich_notification(rendered_content, user, data)

        # Step 5: Validate final content
        self.validate_content(enriched_data)

        # Step 6: Create NotificationMessage
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

    # ===== Hook Methods - Subclasses override these =====

    @abstractmethod
    def get_channel_type(self) -> ChannelType:
        """
        Return the channel type this generator produces for.

        Returns:
            ChannelType (EMAIL, SMS, PUSH, WHATSAPP)

        Example:
            class EmailGenerator(NotificationGenerator):
                def get_channel_type(self):
                    return ChannelType.EMAIL
        """
        pass

    @abstractmethod
    def validate_prerequisites(self, user_id: int) -> User:
        """
        Validate that user can receive notifications via this channel.

        Args:
            user_id: User ID to validate

        Returns:
            User object if valid

        Raises:
            InvalidRecipientException: If user cannot receive via this channel

        Example:
            class EmailGenerator:
                def validate_prerequisites(self, user_id):
                    user = self.user_repo.get(user_id)
                    if not user.email or not user.email_verified:
                        raise InvalidRecipientException("Email not verified")
                    return user

            class SMSGenerator:
                def validate_prerequisites(self, user_id):
                    user = self.user_repo.get(user_id)
                    if not user.phone or not user.sms_opt_in:
                        raise InvalidRecipientException("SMS not opted in")
                    return user
        """
        pass

    def fetch_context_data(self, user: User, trigger_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch data needed for template rendering.

        This method can be overridden by subclasses to add channel-specific context.
        Default implementation includes common data.

        Args:
            user: The recipient user
            trigger_data: Data provided when notification was triggered

        Returns:
            Dictionary of context variables for template

        Example:
            class EmailGenerator:
                def fetch_context_data(self, user, trigger_data):
                    context = super().fetch_context_data(user, trigger_data)
                    context['unsubscribe_token'] = self._generate_token(user.id)
                    return context
        """
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
        """
        Enrich notification with channel-specific data.

        Args:
            rendered_content: Template rendering output
            user: Recipient user
            original_data: Original trigger data

        Returns:
            Enriched notification data with title, body, data, action_url

        Example:
            class EmailGenerator:
                def enrich_notification(self, content, user, data):
                    return {
                        "title": content.get("subject", "Notification"),
                        "body": content.get("html_body", ""),
                        "data": {
                            "unsubscribe_url": f"https://app.com/unsubscribe/{user.id}"
                        },
                        "action_url": content.get("action_url")
                    }

            class SMSGenerator:
                def enrich_notification(self, content, user, data):
                    body = content.get("text_body", "")
                    return {
                        "title": "",  # SMS has no title
                        "body": body[:160],  # Truncate to SMS limit
                        "data": {},
                        "action_url": None
                    }
        """
        pass

    @abstractmethod
    def validate_content(self, notification_data: Dict[str, Any]) -> None:
        """
        Validate the final notification content.

        Args:
            notification_data: The enriched notification data

        Raises:
            InvalidContentException: If content is invalid

        Example:
            class EmailGenerator:
                def validate_content(self, data):
                    if not data.get("body"):
                        raise InvalidContentException("Email body is empty")
                    if len(data["body"]) > 50000:
                        raise InvalidContentException("Email body too long")

            class SMSGenerator:
                def validate_content(self, data):
                    if len(data["body"]) > 160:
                        raise InvalidContentException("SMS body exceeds 160 characters")
        """
        pass


# Custom Exceptions
class InvalidRecipientException(Exception):
    """Raised when user cannot receive notifications via a specific channel"""
    pass


class InvalidContentException(Exception):
    """Raised when generated notification content is invalid"""
    pass
