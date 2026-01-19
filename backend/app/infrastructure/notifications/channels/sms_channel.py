"""
SMS channel implementation using Twilio.

Sends notifications via SMS using Twilio API.
"""

import logging
from typing import Dict, Any
from twilio.rest import Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSChannel:
    """
    SMS notification channel using Twilio.

    Strategy Pattern implementation for SMS delivery.
    """

    def __init__(self, account_sid: str = None, auth_token: str = None, from_number: str = None):
        """
        Initialize SMS channel.

        Args:
            account_sid: Twilio account SID (defaults to settings.TWILIO_ACCOUNT_SID)
            auth_token: Twilio auth token (defaults to settings.TWILIO_AUTH_TOKEN)
            from_number: Twilio phone number (defaults to settings.TWILIO_PHONE_NUMBER)
        """
        self.account_sid = account_sid or getattr(settings, "TWILIO_ACCOUNT_SID", None)
        self.auth_token = auth_token or getattr(settings, "TWILIO_AUTH_TOKEN", None)
        self.from_number = from_number or getattr(settings, "TWILIO_PHONE_NUMBER", None)

        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials not configured, SMS sending will fail")

    async def send(
        self,
        user_phone: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Send SMS via Twilio.

        Args:
            user_phone: Recipient phone number (E.164 format: +1234567890)
            title: Not used for SMS
            body: SMS message body (max 160 chars already handled by renderer)
            data: Additional metadata

        Returns:
            {"success": bool, "channel": "sms", "error": str, "external_id": str}
        """
        try:
            if not self.client:
                raise Exception("Twilio client not initialized")

            if not self.from_number:
                raise Exception("Twilio from_number not configured")

            # Send SMS
            message = self.client.messages.create(
                to=user_phone,
                from_=self.from_number,
                body=body
            )

            logger.info(f"SMS sent to {user_phone}, SID: {message.sid}")
            return {
                "success": True,
                "channel": "sms",
                "external_id": message.sid,
                "error": None
            }

        except Exception as e:
            logger.error(f"Failed to send SMS to {user_phone}: {e}", exc_info=True)
            return {
                "success": False,
                "channel": "sms",
                "error": str(e),
                "external_id": None
            }

    def validate(self, user_phone: str) -> bool:
        """
        Validate that SMS can be sent to user.

        Args:
            user_phone: User's phone number

        Returns:
            True if valid phone number (basic check for + and digits)
        """
        if not user_phone:
            return False
        # Basic validation: starts with + and has digits
        return user_phone.startswith("+") and len(user_phone) >= 10

    def get_channel_type(self) -> str:
        """Get channel type."""
        return "sms"
