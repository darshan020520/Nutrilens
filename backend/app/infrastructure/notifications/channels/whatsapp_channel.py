import asyncio
import logging
from typing import Dict, Any
from twilio.rest import Client
from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppChannel:
    def __init__(self, account_sid: str = None, auth_token: str = None, from_number: str = None):
        self.account_sid = account_sid or getattr(settings, "twilio_account_sid", None)
        self.auth_token = auth_token or getattr(settings, "twilio_auth_token", None)
        self.from_number = from_number or getattr(settings, "twilio_whatsapp_number", "whatsapp:+14155238886")

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
        try:
            if not self.client:
                raise Exception("Twilio client not initialized")

            to_number = user_phone if user_phone.startswith("whatsapp:") else f"whatsapp:{user_phone}"

            loop = asyncio.get_event_loop()
            message = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    to=to_number,
                    from_=self.from_number,
                    body=body,
                )
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
        if not user_phone:
            return False
        phone = user_phone.replace("whatsapp:", "")
        return phone.startswith("+") and len(phone) >= 10

    def get_channel_type(self) -> str:
        return "whatsapp"
