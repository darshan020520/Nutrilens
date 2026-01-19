"""
Base Orchestrator

Base class for all orchestrators with common functionality.
"""

from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class BaseOrchestrator:
    """
    Base orchestrator with common functionality.

    Orchestrators coordinate services but contain NO business logic.
    """

    def __init__(self, event_publisher: Optional[Any] = None):
        """
        Initialize orchestrator.

        Args:
            event_publisher: Optional event publisher for publishing events
        """
        self.event_publisher = event_publisher

    async def publish_event(self, event_type: str, event_data: Any) -> None:
        """
        Publish event if publisher is available.

        Args:
            event_type: Type of event (e.g., "meal_plan.generated")
            event_data: Event data to publish
        """
        if self.event_publisher:
            try:
                await self.event_publisher.publish(event_type, event_data)
                logger.info(f"Published event: {event_type}")
            except Exception as e:
                logger.error(f"Failed to publish event {event_type}: {str(e)}")
                # Don't raise - event publishing should not break main workflow
