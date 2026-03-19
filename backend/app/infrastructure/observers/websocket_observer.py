"""
WebSocketObserver - Broadcasts events to WebSocket clients

Wraps existing ConnectionManager to send events to user's WebSocket connections.
"""
import logging
from typing import Dict
from app.infrastructure.events.observer import IObserver

logger = logging.getLogger(__name__)


class WebSocketObserver(IObserver):
    """
    Observer that broadcasts events to WebSocket clients.
    Wraps existing ConnectionManager.
    """

    def __init__(self, websocket_manager):
        """
        Args:
            websocket_manager: Existing singleton WebSocket manager
        """
        self.ws_manager = websocket_manager

    async def update(self, event: Dict) -> None:
        """
        Broadcast event to user's WebSocket connections.

        Args:
            event: Event dict from EventPublisher
        """
        try:
            # Extract user_id
            user_id = event["data"].get("user_id")
            if not user_id:
                logger.warning("Event missing user_id, cannot broadcast to WebSocket")
                return

            # Broadcast to all user's WebSocket connections
            await self.ws_manager.broadcast_to_user(
                user_id=user_id,
                message=event
            )
        except Exception as e:
            logger.error(f"WebSocketObserver failed: {e}")
