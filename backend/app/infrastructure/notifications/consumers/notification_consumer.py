"""
Notification Consumer - Processes queued notifications from Redis.

Polls Redis priority queues, renders templates, and sends via appropriate channel.
Industry standard consumer-side processing pattern (SendGrid, Firebase, Twilio).
"""

import logging
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.redis_client import get_redis_client
from app.models.database import User, get_db
from ..templates.template_renderer import TemplateRenderer
from ..factories.channel_strategy_factory import ChannelStrategyFactory
from .retry_config import RetryConfig

logger = logging.getLogger(__name__)


class NotificationConsumer:
    """
    Consumes notifications from Redis queues and delivers them.

    Consumer Flow:
    1. Poll Redis queues by priority (urgent → high → normal → low)
    2. Deserialize notification data
    3. Get user from database
    4. Get user's preferred channel
    5. Validate user can receive on that channel
    6. Render template for channel
    7. Send via channel strategy
    8. Handle success/failure with retry logic

    Industry Standard Pattern:
    - SendGrid: Dequeues template ID + data, renders and sends
    - Firebase: Dequeues notification, formats for platform, sends
    - Twilio: Dequeues message, validates, sends via appropriate transport
    """

    # Redis queue keys by priority (same as NotificationObserver)
    QUEUE_KEYS = {
        "urgent": "notifications:queue:urgent",
        "high": "notifications:queue:high",
        "normal": "notifications:queue:normal",
        "low": "notifications:queue:low",
    }

    # Queue processing order (urgent first)
    PRIORITY_ORDER = ["urgent", "high", "normal", "low"]

    # Dead letter queue for failed notifications
    DEAD_LETTER_QUEUE = "notifications:dead_letter"

    def __init__(self, db_session_factory=None):
        """
        Initialize notification consumer.

        Args:
            db_session_factory: Factory function to get database session
                               (defaults to get_db)
        """
        self.redis_client = get_redis_client()
        self.template_renderer = TemplateRenderer()
        self.channel_factory = ChannelStrategyFactory()
        self.db_session_factory = db_session_factory or get_db
        self.running = False
        self.current_task = None
        self.retry_count = 0
        self.max_connection_retries = 10

    async def start(self, shutdown_timeout: int = 30, brpop_timeout: int = 5):
        """
        Start consumer loop using BRPOP (blocking pop).

        Uses industry-standard blocking reads instead of polling:
        - BRPOP blocks until data arrives (zero latency, no CPU waste)
        - Checks multiple queues in priority order
        - Graceful shutdown with task completion waiting

        Args:
            shutdown_timeout: Seconds to wait for current task on shutdown (default: 30)
            brpop_timeout: BRPOP timeout in seconds (default: 5, allows periodic running check)
        """
        self.running = True
        logger.info("NotificationConsumer started with BRPOP")

        try:
            while self.running:
                try:
                    # BRPOP: Blocks until notification available (or timeout)
                    # Check queues in priority order: urgent, high, normal, low
                    queue_keys = [self.QUEUE_KEYS[p] for p in self.PRIORITY_ORDER]

                    result = await self.redis_client.brpop(queue_keys, timeout=brpop_timeout)

                    if result:
                        # Reset connection retry count on successful operation
                        self.retry_count = 0

                        # result is (queue_key, notification_json)
                        queue_key, notification_json = result

                        # Determine priority from queue_key
                        priority = self._get_priority_from_queue_key(queue_key)

                        # Process notification (track as current task for graceful shutdown)
                        self.current_task = asyncio.create_task(
                            self._process_notification(notification_json, priority)
                        )
                        await self.current_task
                        self.current_task = None

                except asyncio.CancelledError:
                    logger.info("Consumer received cancellation signal")
                    break

                except Exception as e:
                    # Connection error or other Redis failure
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
        """
        Extract priority level from queue key.

        Args:
            queue_key: Redis queue key (e.g., "notifications:queue:urgent")

        Returns:
            Priority level (e.g., "urgent")
        """
        for priority, key in self.QUEUE_KEYS.items():
            if key == queue_key:
                return priority
        return "normal"

    async def _graceful_shutdown(self, timeout: int):
        """
        Gracefully shutdown consumer, waiting for current task to complete.

        Implements Celery-style soft shutdown pattern:
        - Wait up to timeout seconds for current task
        - Log if task doesn't complete in time

        Args:
            timeout: Max seconds to wait for task completion
        """
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
        """
        Handle Redis connection errors with exponential backoff.

        Industry standard retry pattern with backoff:
        - Retry 1: Wait 1 second (2^0)
        - Retry 2: Wait 2 seconds (2^1)
        - Retry 3: Wait 4 seconds (2^2)
        - ...
        - Max: Wait 60 seconds (capped)

        Args:
            error: The exception that occurred
        """
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
        """
        Process a single notification.

        Args:
            notification_json: Serialized notification data from queue
            priority: Priority level (for logging)
        """
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
        """
        Send notification to user.

        Args:
            notification_data: Notification dict from queue
            user: User object from database
            db: Database session
        """
        try:
            # Extract notification info
            user_id = notification_data.get("user_id")
            notification_type = notification_data.get("type")
            available_channels = notification_data.get("channels", [])
            context = notification_data.get("context", {})
            priority = notification_data.get("priority", "normal")
            retry_count = notification_data.get("metadata", {}).get("retry_count", 0)

            # Get user's preferred channel (from available channels)
            preferred_channel = self._get_user_preferred_channel(
                user, available_channels
            )

            if not preferred_channel:
                logger.warning(
                    f"User {user_id} has no valid channel from {available_channels}, skipping"
                )
                return

            # Get channel strategy
            channel = self.channel_factory.get_channel(preferred_channel)

            # Validate user can receive on this channel
            if not self._validate_user_channel(user, preferred_channel, channel):
                logger.warning(
                    f"User {user_id} cannot receive on {preferred_channel}, skipping"
                )
                return

            # Render template
            user_data = self._get_user_data(user)
            rendered = self.template_renderer.render(
                notification_type=notification_type,
                channel=preferred_channel,
                context=context,
                user_data=user_data
            )

            # Send via channel
            result = await self._send_via_channel(
                channel=channel,
                user=user,
                preferred_channel=preferred_channel,
                rendered=rendered
            )

            # Handle result
            if result["success"]:
                logger.info(
                    f"Successfully sent {notification_type} to user {user_id} via {preferred_channel}"
                )
            else:
                # Failed - handle retry
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

    def _get_user_preferred_channel(
        self,
        user: User,
        available_channels: list
    ) -> Optional[str]:
        """
        Get user's preferred channel from available channels.

        Args:
            user: User object
            available_channels: List of channels available for this notification

        Returns:
            Preferred channel or None
        """
        # Get user's notification preferences
        # For now, use a simple priority: push > email > sms > whatsapp
        # In future, this should come from user.notification_preferences

        channel_priority = ["push", "email", "sms", "whatsapp"]

        for channel in channel_priority:
            if channel in available_channels:
                return channel

        return None

    def _validate_user_channel(
        self,
        user: User,
        channel_type: str,
        channel
    ) -> bool:
        """
        Validate that user can receive notifications on this channel.

        Args:
            user: User object
            channel_type: Channel type string
            channel: Channel strategy instance

        Returns:
            True if user can receive on this channel
        """
        if channel_type == "email":
            return channel.validate(user.email)
        elif channel_type == "sms":
            return channel.validate(getattr(user, "phone", None))
        elif channel_type == "push":
            return channel.validate(getattr(user, "device_token", None))
        elif channel_type == "whatsapp":
            return channel.validate(getattr(user, "phone", None))
        else:
            return False

    def _get_user_data(self, user: User) -> Dict[str, Any]:
        """
        Extract user data for template rendering.

        Args:
            user: User object

        Returns:
            Dict with user data for templates
        """
        return {
            "user_name": user.username or "User",
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
        """
        Send notification via channel strategy.

        Args:
            channel: Channel strategy instance
            user: User object
            preferred_channel: Channel type
            rendered: Rendered notification dict

        Returns:
            Result dict from channel
        """
        title = rendered.get("title", "")
        body = rendered.get("body", "")
        data = rendered.get("data", {})

        if preferred_channel == "email":
            return await channel.send(user.email, title, body, data)
        elif preferred_channel == "sms":
            return await channel.send(getattr(user, "phone", ""), title, body, data)
        elif preferred_channel == "push":
            return await channel.send(getattr(user, "device_token", ""), title, body, data)
        elif preferred_channel == "whatsapp":
            return await channel.send(getattr(user, "phone", ""), title, body, data)
        else:
            return {"success": False, "channel": preferred_channel, "error": "Unknown channel"}

    async def _handle_failure(
        self,
        notification_data: Dict[str, Any],
        error: str,
        retry_count: int
    ):
        """
        Handle failed notification delivery with retry logic.

        Args:
            notification_data: Original notification data
            error: Error message
            retry_count: Current retry count
        """
        max_retries = notification_data.get("metadata", {}).get("max_retries", 5)

        if retry_count < max_retries:
            # Retry - increment retry count and requeue
            retry_count += 1
            notification_data["metadata"]["retry_count"] = retry_count

            # Calculate retry delay with exponential backoff
            retry_delay = RetryConfig.calculate_delay(retry_count)

            logger.warning(
                f"Notification failed (attempt {retry_count}/{max_retries}), "
                f"retrying in {retry_delay}s: {error}"
            )

            # Requeue to same priority queue after delay
            # For now, immediate requeue (in production, use Redis ZADD with score=timestamp+delay)
            priority = notification_data.get("priority", "normal")
            queue_key = self.QUEUE_KEYS.get(priority, self.QUEUE_KEYS["normal"])
            notification_json = json.dumps(notification_data)
            await self.redis_client.lpush(queue_key, notification_json)

        else:
            # Max retries exceeded - move to dead letter queue
            logger.error(
                f"Notification failed after {max_retries} attempts, "
                f"moving to dead letter queue: {error}"
            )

            notification_data["metadata"]["final_error"] = error
            notification_data["metadata"]["failed_at"] = datetime.utcnow().isoformat()
            notification_json = json.dumps(notification_data)
            await self.redis_client.lpush(self.DEAD_LETTER_QUEUE, notification_json)
