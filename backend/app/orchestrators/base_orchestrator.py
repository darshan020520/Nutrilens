from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class BaseOrchestrator:
    def __init__(self, event_publisher: Optional[Any] = None):

        self.event_publisher = event_publisher

    async def publish_event(self, event_type: str, event_data: Any) -> None:

        if self.event_publisher:
            try:
                await self.event_publisher.publish(event_type, event_data)
                logger.info(f"Published event: {event_type}")
            except Exception as e:
                logger.error(f"Failed to publish event {event_type}: {str(e)}")
