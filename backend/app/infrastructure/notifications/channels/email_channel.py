import logging
from typing import Dict, Any
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailChannel:
    def __init__(self, api_key: str = None):

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

        try:
            if not self.client:
                raise Exception("SendGrid client not initialized")

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(user_email),
                subject=title,
                html_content=Content("text/html", body)
            )

            response = self.client.send(message)

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
        return bool(user_email and "@" in user_email)

    def get_channel_type(self) -> str:
        return "email"
