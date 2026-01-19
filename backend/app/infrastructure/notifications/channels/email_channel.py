"""
Email channel implementation using SendGrid.

Sends notifications via email using SendGrid API.
"""

import logging
from typing import Dict, Any
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailChannel:
    """
    Email notification channel using SendGrid.

    Strategy Pattern implementation for email delivery.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize email channel.

        Args:
            api_key: SendGrid API key (defaults to settings.SENDGRID_API_KEY)
        """
        self.api_key = api_key or getattr(settings, "SENDGRID_API_KEY", None)
        self.from_email = getattr(settings, "SENDGRID_FROM_EMAIL", "noreply@nutrilens.com")
        self.from_name = getattr(settings, "SENDGRID_FROM_NAME", "NutriLens")

        if self.api_key:
            self.client = SendGridAPIClient(self.api_key)
        else:
            self.client = None
            logger.warning("SendGrid API key not configured, email sending will fail")

    async def send(
        self,
        user_email: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Send email via SendGrid.

        Args:
            user_email: Recipient email address
            title: Email subject
            body: Email body (HTML)
            data: Additional metadata

        Returns:
            {"success": bool, "channel": "email", "error": str, "external_id": str}
        """
        try:
            if not self.client:
                raise Exception("SendGrid client not initialized")

            # Create email
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(user_email),
                subject=title,
                html_content=Content("text/html", body)
            )

            # Send via SendGrid
            response = self.client.send(message)

            # Check response
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent to {user_email}")
                return {
                    "success": True,
                    "channel": "email",
                    "external_id": response.headers.get("X-Message-Id", ""),
                    "error": None
                }
            else:
                error_msg = f"SendGrid returned status {response.status_code}"
                logger.error(f"Failed to send email to {user_email}: {error_msg}")
                return {
                    "success": False,
                    "channel": "email",
                    "error": error_msg,
                    "external_id": None
                }

        except Exception as e:
            logger.error(f"Failed to send email to {user_email}: {e}", exc_info=True)
            return {
                "success": False,
                "channel": "email",
                "error": str(e),
                "external_id": None
            }

    def validate(self, user_email: str) -> bool:
        """
        Validate that email can be sent to user.

        Args:
            user_email: User's email address

        Returns:
            True if valid email address
        """
        return bool(user_email and "@" in user_email)

    def get_channel_type(self) -> str:
        """Get channel type."""
        return "email"
