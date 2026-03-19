import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class EventPublisher:

    def __init__(self):
        self._observers: List = []

    def attach(self, observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)
            logger.info(f"Observer {observer.__class__.__name__} attached")

    def detach(self, observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)
            logger.info(f"Observer {observer.__class__.__name__} detached")

    async def publish(self, event_type: str, data: Dict) -> None:

        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        for observer in self._observers:
            try:
                await observer.update(event)
            except Exception as e:
                logger.error(
                    f"Observer {observer.__class__.__name__} failed: {e}"
                )
