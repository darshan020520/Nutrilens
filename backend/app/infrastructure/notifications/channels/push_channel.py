import logging
from typing import Dict, Any
import json
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class PushChannel:
    def __init__(self, server_key: str = None):
        self.server_key = server_key or getattr(settings, "FCM_SERVER_KEY", None)
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"

        if not self.server_key:
            logger.warning("FCM server key not configured, push sending will fail")

    async def send(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        try:
            if not self.server_key:
                raise Exception("FCM server key not configured")

            if not device_token:
                raise Exception("Device token not provided")

            payload = {
                "to": device_token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "data": data or {}
            }

            if data:
                notification = payload["notification"]
                if "icon" in data:
                    notification["icon"] = data["icon"]
                if "badge" in data:
                    notification["badge"] = data["badge"]
                if "sound" in data:
                    notification["sound"] = data["sound"]
                if "click_action" in data:
                    notification["click_action"] = data["click_action"]

            headers = {
                "Authorization": f"key={self.server_key}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.fcm_url,
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )

            if response.status_code == 200:
                result = response.json()
                if result.get("success", 0) > 0:
                    logger.info(f"Push notification sent to device")
                    return {
                        "success": True,
                        "channel": "push",
                        "external_id": result.get("results", [{}])[0].get("message_id", ""),
                        "error": None
                    }
                else:
                    error = result.get("results", [{}])[0].get("error", "Unknown error")
                    logger.error(f"FCM failed: {error}")
                    return {
                        "success": False,
                        "channel": "push",
                        "error": error,
                        "external_id": None
                    }
            else:
                error_msg = f"FCM returned status {response.status_code}"
                logger.error(f"Push notification failed: {error_msg}")
                return {
                    "success": False,
                    "channel": "push",
                    "error": error_msg,
                    "external_id": None
                }

        except Exception as e:
            logger.error(f"Failed to send push notification: {e}", exc_info=True)
            return {
                "success": False,
                "channel": "push",
                "error": str(e),
                "external_id": None
            }

    def validate(self, device_token: str) -> bool:
        return bool(device_token and len(device_token) > 20)

    def get_channel_type(self) -> str:
        return "push"
