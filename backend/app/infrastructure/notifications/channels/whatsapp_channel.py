"""
WhatsApp channel implementation using Twilio WhatsApp API.

Sends notifications via WhatsApp using Twilio's WhatsApp integration.
"""

import logging
from typing import Dict, Any
from twilio.rest import Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppChannel:
    """
    WhatsApp notification channel using Twilio.

    Strategy Pattern implementation for WhatsApp delivery.
    """

    def __init__(self, account_sid: str = None, auth_token: str = None, from_number: str = None):
        """
        Initialize WhatsApp channel.

        Args:
            account_sid: Twilio account SID (defaults to settings.TWILIO_ACCOUNT_SID)
            auth_token: Twilio auth token (defaults to settings.TWILIO_AUTH_TOKEN)
            from_number: Twilio WhatsApp number (defaults to settings.TWILIO_WHATSAPP_NUMBER)
        """
        self.account_sid = account_sid or getattr(settings, "TWILIO_ACCOUNT_SID", None)
        self.auth_token = auth_token or getattr(settings, "TWILIO_AUTH_TOKEN", None)
        self.from_number = from_number or getattr(settings, "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials not configured, WhatsApp sending will fail")

    async def send(
        self,
        user_phone: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Send WhatsApp message via Twilio.

        Args:
            user_phone: Recipient phone number (E.164 format: +1234567890)
            title: Not used for WhatsApp
            body: WhatsApp message body
            data: Additional metadata

        Returns:
            {"success": bool, "channel": "whatsapp", "error": str, "external_id": str}
        """
        try:
            if not self.client:
                raise Exception("Twilio client not initialized")

            # WhatsApp numbers must be prefixed with "whatsapp:"
            to_number = user_phone if user_phone.startswith("whatsapp:") else f"whatsapp:{user_phone}"

            # Send WhatsApp message
            message = self.client.messages.create(
                to=to_number,
                from_=self.from_number,
                body=body
            )

            logger.info(f"WhatsApp sent to {user_phone}, SID: {message.sid}")
            return {
                "success": True,
                "channel": "whatsapp",
                "external_id": message.sid,
                "error": None
            }

        except Exception as e:
            logger.error(f"Failed to send WhatsApp to {user_phone}: {e}", exc_info=True)
            return {
                "success": False,
                "channel": "whatsapp",
                "error": str(e),
                "external_id": None
            }

    def validate(self, user_phone: str) -> bool:
        """
        Validate that WhatsApp can be sent to user.

        Args:
            user_phone: User's phone number

        Returns:
            True if valid phone number
        """
        if not user_phone:
            return False
        # Remove whatsapp: prefix if present
        phone = user_phone.replace("whatsapp:", "")
        # Basic validation: starts with + and has digits
        return phone.startswith("+") and len(phone) >= 10

    def get_channel_type(self) -> str:
        """Get channel type."""
        return "whatsapp"
