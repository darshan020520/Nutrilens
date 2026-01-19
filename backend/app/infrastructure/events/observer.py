"""
IObserver - Observer interface

All observers must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Dict


class IObserver(ABC):
    """Observer interface - all observers must implement update()"""

    @abstractmethod
    async def update(self, event: Dict) -> None:
        """
        Called when EventPublisher publishes an event.

        Args:
            event: {
                "type": "meal_logged",
                "timestamp": "2026-01-02T12:30:00Z",
                "data": {...}  # Event-specific data
            }
        """
        pass
