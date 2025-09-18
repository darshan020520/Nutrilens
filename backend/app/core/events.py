# backend/app/core/events.py
"""
Event system for real-time updates
"""

from typing import Dict, List, Callable, Any
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    """Types of events in the system"""
    MEAL_LOGGED = "meal_logged"
    MEAL_SKIPPED = "meal_skipped"
    INVENTORY_UPDATED = "inventory_updated"
    PLAN_GENERATED = "plan_generated"
    RECEIPT_PROCESSED = "receipt_processed"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    ALERT_TRIGGERED = "alert_triggered"

class EventBus:
    """Central event bus for the application"""
    
    def __init__(self):
        self.listeners: Dict[EventType, List[Callable]] = {}
        self.event_queue = asyncio.Queue()
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """Subscribe to an event type"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe from an event type"""
        if event_type in self.listeners:
            self.listeners[event_type].remove(callback)
    
    async def emit(self, event_type: EventType, data: Dict[str, Any]):
        """Emit an event to all listeners"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.event_queue.put(event)
    
    async def process_events(self):
        """Process events from the queue"""
        while True:
            try:
                event = await self.event_queue.get()
                event_type = event["type"]
                
                if event_type in self.listeners:
                    for callback in self.listeners[event_type]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(event["data"])
                            else:
                                callback(event["data"])
                        except Exception as e:
                            logger.error(f"Error in event listener: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error processing event: {str(e)}")
                await asyncio.sleep(1)

# Global event bus
event_bus = EventBus()