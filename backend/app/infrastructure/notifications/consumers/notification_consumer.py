import logging
import json
import asyncio
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.redis_client import get_redis_client
from app.models.database import User, get_db
from ..templates.template_renderer import TemplateRenderer
from ..factories.channel_strategy_factory import ChannelStrategyFactory
from .retry_config import RetryConfig

logger = logging.getLogger(__name__)


class NotificationConsumer:

    QUEUE_KEYS = {
        "urgent": "notifications:queue:urgent",
        "high": "notifications:queue:high",
        "normal": "notifications:queue:normal",
        "low": "notifications:queue:low",
    }

    PRIORITY_ORDER = ["urgent", "high", "normal", "low"]

    DEAD_LETTER_QUEUE = "notifications:dead_letter"

    def __init__(self, db_session_factory=None):

        self.redis_client = get_redis_client()
        self.template_renderer = TemplateRenderer()
        self.channel_factory = ChannelStrategyFactory()
        self.db_session_factory = db_session_factory or get_db
        self.running = False
        self.current_task = None
        self.retry_count = 0
        self.max_connection_retries = 10

    async def start(self, shutdown_timeout: int = 30, brpop_timeout: int = 5):
        self.running = True
        logger.info("NotificationConsumer started with BRPOP")

        try:
            while self.running:
                try:
                    queue_keys = [self.QUEUE_KEYS[p] for p in self.PRIORITY_ORDER]

                    result = await self.redis_client.brpop(queue_keys, timeout=brpop_timeout)

                    if result:
                        self.retry_count = 0
                        queue_key, notification_json = result

                        priority = self._get_priority_from_queue_key(queue_key)

                        self.current_task = asyncio.create_task(
                            self._process_notification(notification_json, priority)
                        )
                        await self.current_task
                        self.current_task = None

                except asyncio.CancelledError:
                    logger.info("Consumer received cancellation signal")
                    break

                except Exception as e:
                    await self._handle_connection_error(e)

        except Exception as e:
            logger.error(f"NotificationConsumer crashed: {e}", exc_info=True)
        finally:
            await self._graceful_shutdown(shutdown_timeout)

    async def stop(self):
        """Stop consumer loop gracefully."""
        logger.info("Stop requested, will complete current task if any")
        self.running = False

    def _get_priority_from_queue_key(self, queue_key: str) -> str:
        for priority, key in self.QUEUE_KEYS.items():
            if key == queue_key:
                return priority
        return "normal"

    async def _graceful_shutdown(self, timeout: int):

        if self.current_task and not self.current_task.done():
            logger.info(f"Waiting up to {timeout}s for current task to complete")
            try:
                await asyncio.wait_for(self.current_task, timeout=timeout)
                logger.info("Current task completed successfully")
            except asyncio.TimeoutError:
                logger.warning(f"Current task didn't complete within {timeout}s, cancelling")
                self.current_task.cancel()
            except Exception as e:
                logger.error(f"Error during graceful shutdown: {e}")

        logger.info("NotificationConsumer stopped")

    async def _handle_connection_error(self, error: Exception):
        self.retry_count += 1

        if self.retry_count > self.max_connection_retries:
            logger.error(
                f"Redis connection failed after {self.max_connection_retries} attempts, stopping consumer"
            )
            self.running = False
            return

        # Exponential backoff with cap at 60 seconds
        delay = min(2 ** (self.retry_count - 1), 60)

        logger.warning(
            f"Redis connection error (attempt {self.retry_count}/{self.max_connection_retries}), "
            f"retrying in {delay}s: {error}"
        )

        await asyncio.sleep(delay)

    async def _process_notification(self, notification_json: str, priority: str):
        try:
            # Deserialize
            notification_data = json.loads(notification_json)

            user_id = notification_data.get("user_id")
            notification_type = notification_data.get("type")

            logger.info(
                f"Processing {priority} notification: {notification_type} for user {user_id}"
            )

            # Get user from database
            db = next(self.db_session_factory())
            try:
                user = db.query(User).filter(User.id == user_id).first()

                if not user:
                    logger.error(f"User {user_id} not found, dropping notification")
                    return

                # Process and send
                await self._send_notification(notification_data, user, db)

            finally:
                db.close()

        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize notification: {e}")
        except Exception as e:
            logger.error(f"Failed to process notification: {e}", exc_info=True)

    async def _send_notification(
        self,
        notification_data: Dict[str, Any],
        user: User,
        db: Session
    ):

        try:
            user_id = notification_data.get("user_id")
            notification_type = notification_data.get("type")
            available_channels = notification_data.get("channels", [])
            context = notification_data.get("context", {})
            priority = notification_data.get("priority", "normal")
            retry_count = notification_data.get("metadata", {}).get("retry_count", 0)

            # Try channels in priority order, falling through if validation fails
            preferred_channel = None
            channel = None
            for candidate in self._get_user_channel_candidates(user, available_channels):
                candidate_channel = self.channel_factory.get_channel(candidate)
                if self._validate_user_channel(user, candidate, candidate_channel):
                    preferred_channel = candidate
                    channel = candidate_channel
                    break
                logger.debug(
                    f"User {user_id} cannot receive on {candidate}, trying next channel"
                )

            if not preferred_channel:
                logger.warning(
                    f"User {user_id} has no valid channel from {available_channels}, skipping"
                )
                return

            user_data = self._get_user_data(user)
            rendered = self.template_renderer.render(
                notification_type=notification_type,
                channel=preferred_channel,
                context=context,
                user_data=user_data
            )

            result = await self._send_via_channel(
                channel=channel,
                user=user,
                preferred_channel=preferred_channel,
                rendered=rendered
            )

            if result["success"]:
                logger.info(
                    f"Successfully sent {notification_type} to user {user_id} via {preferred_channel}"
                )
            else:
                await self._handle_failure(
                    notification_data,
                    result["error"],
                    retry_count
                )

        except Exception as e:
            logger.error(
                f"Failed to send notification: {e}",
                exc_info=True
            )
            # Queue for retry
            await self._handle_failure(
                notification_data,
                str(e),
                notification_data.get("metadata", {}).get("retry_count", 0)
            )

    def _get_user_channel_candidates(
        self,
        user: User,
        available_channels: list
    ) -> list:
        """Return channels in priority order, filtered by notification type AND user preferences."""
        channel_priority = ["push", "email", "sms", "whatsapp"]
        enabled = set(available_channels)
        # Intersect with user's enabled providers if preference exists
        pref = user.notification_preference
        if pref and pref.enabled_providers:
            enabled = enabled.intersection(set(pref.enabled_providers))
        return [ch for ch in channel_priority if ch in enabled]

    def _validate_user_channel(
        self,
        user: User,
        channel_type: str,
        channel
    ) -> bool:
        pref = user.notification_preference
        if channel_type == "email":
            return channel.validate(user.email)
        elif channel_type == "sms":
            phone = pref.phone_number if pref else None
            return channel.validate(phone)
        elif channel_type == "push":
            # No device_token stored on User — push requires FCM integration
            return False
        elif channel_type == "whatsapp":
            phone = pref.whatsapp_number if pref else None
            return channel.validate(phone)
        else:
            return False

    def _get_user_data(self, user: User) -> Dict[str, Any]:
        return {
            "user_name": (user.profile.name if user.profile else None) or user.email.split("@")[0],
            "user_email": user.email,
            "unsubscribe_url": f"https://app.nutrilens.com/settings/notifications?user={user.id}",
        }

    async def _send_via_channel(
        self,
        channel,
        user: User,
        preferred_channel: str,
        rendered: Dict[str, Any]
    ) -> Dict[str, Any]:

        title = rendered.get("title", "")
        body = rendered.get("body", "")
        data = rendered.get("data", {})
        pref = user.notification_preference

        if preferred_channel == "email":
            return await channel.send(user.email, title, body, data)
        elif preferred_channel == "sms":
            phone = pref.phone_number if pref else ""
            return await channel.send(phone, title, body, data)
        elif preferred_channel == "push":
            return {"success": False, "channel": "push", "error": "No device token configured"}
        elif preferred_channel == "whatsapp":
            phone = pref.whatsapp_number if pref else ""
            return await channel.send(phone, title, body, data)
        else:
            return {"success": False, "channel": preferred_channel, "error": "Unknown channel"}

    async def _handle_failure(
        self,
        notification_data: Dict[str, Any],
        error: str,
        retry_count: int
    ):

        max_retries = notification_data.get("metadata", {}).get("max_retries", 5)

        if retry_count < max_retries:

            retry_count += 1
            notification_data["metadata"]["retry_count"] = retry_count

            retry_delay = RetryConfig.calculate_delay(retry_count)

            logger.warning(
                f"Notification failed (attempt {retry_count}/{max_retries}), "
                f"retrying in {retry_delay}s: {error}"
            )

            priority = notification_data.get("priority", "normal")
            queue_key = self.QUEUE_KEYS.get(priority, self.QUEUE_KEYS["normal"])
            notification_json = json.dumps(notification_data)
            await self.redis_client.lpush(queue_key, notification_json)

        else:
            logger.error(
                f"Notification failed after {max_retries} attempts, "
                f"moving to dead letter queue: {error}"
            )

            notification_data["metadata"]["final_error"] = error
            notification_data["metadata"]["failed_at"] = datetime.utcnow().isoformat()
            notification_json = json.dumps(notification_data)
            await self.redis_client.lpush(self.DEAD_LETTER_QUEUE, notification_json)
