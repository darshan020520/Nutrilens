"""
EventPublisher - Core Observer pattern implementation

Publisher maintains list of observers and notifies them when events occur.
"""
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publisher in Observer pattern.
    Maintains list of observers, notifies them when events occur.
    """

    def __init__(self):
        self._observers: List = []

    def attach(self, observer) -> None:
        """Register an observer"""
        if observer not in self._observers:
            self._observers.append(observer)
            logger.info(f"Observer {observer.__class__.__name__} attached")

    def detach(self, observer) -> None:
        """Remove an observer"""
        if observer in self._observers:
            self._observers.remove(observer)
            logger.info(f"Observer {observer.__class__.__name__} detached")

    async def publish(self, event_type: str, data: Dict) -> None:
        """
        Notify all observers about event.

        Args:
            event_type: "meal_logged", "meal_skipped", etc.
            data: Event data (user_id, meal info, daily_totals, etc.)
        """
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        # Notify all observers (don't let one failure stop others)
        for observer in self._observers:
            try:
                await observer.update(event)
            except Exception as e:
                logger.error(
                    f"Observer {observer.__class__.__name__} failed: {e}"
                )
