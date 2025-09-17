# backend/app/api/websocket_tracking.py
"""
WebSocket endpoints for real-time tracking updates
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.database import get_db, User, MealLog, UserInventory
from app.services.consumption_service import ConsumptionService
from app.agents.tracking_agent import TrackingAgent
from app.services.auth import get_current_user_websocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.user_states: Dict[int, Dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept and store WebSocket connection"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                if user_id in self.user_states:
                    del self.user_states[user_id]
        
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    async def send_personal_message(self, message: str, user_id: int):
        """Send message to specific user's connections"""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except:
                    # Connection might be closed
                    pass
    
    async def send_json_to_user(self, data: Dict, user_id: int):
        """Send JSON data to specific user"""
        message = json.dumps(data)
        await self.send_personal_message(message, user_id)
    
    async def broadcast_to_users(self, message: str, user_ids: List[int]):
        """Broadcast message to multiple users"""
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)
    
    def update_user_state(self, user_id: int, state: Dict):
        """Update cached user state"""
        self.user_states[user_id] = state
    
    def get_user_state(self, user_id: int) -> Optional[Dict]:
        """Get cached user state"""
        return self.user_states.get(user_id)

# Global connection manager
manager = ConnectionManager()

class RealTimeTracker:
    """Handles real-time tracking updates"""
    
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self.consumption_service = ConsumptionService(db)
        self.tracking_agent = TrackingAgent(db, user_id)
    
    async def get_real_time_status(self) -> Dict[str, Any]:
        """Get comprehensive real-time status"""
        
        # Get today's summary
        today_summary = self.consumption_service.get_today_summary(self.user_id)
        
        # Get inventory status
        inventory_status = self.tracking_agent.calculate_inventory_status()
        
        # Get tracking state
        tracking_state = self.tracking_agent.get_state()
        
        # Get next meal info
        next_meal = await self._get_next_meal_info()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "daily_progress": {
                "meals_consumed": today_summary.get("meals_consumed", 0),
                "meals_pending": today_summary.get("meals_pending", 0),
                "total_calories": today_summary.get("total_calories", 0),
                "total_macros": today_summary.get("total_macros", {}),
                "compliance_rate": today_summary.get("compliance_rate", 0),
                "progress": today_summary.get("progress", {})
            },
            "inventory": {
                "overall_percentage": inventory_status.get("overall_percentage", 0),
                "critical_items": len(inventory_status.get("critical_items", [])),
                "alerts": tracking_state.get("alerts", [])
            },
            "next_meal": next_meal,
            "hydration_reminder": self._get_contextual_hydration_reminder()
        }
    
    async def _get_next_meal_info(self) -> Optional[Dict]:
        """Get information about next meal"""
        from datetime import date
        
        today = date.today()
        
        next_meal = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == self.user_id,
                func.date(MealLog.planned_datetime) == today,
                MealLog.consumed_datetime.is_(None),
                MealLog.was_skipped.is_(False)
            )
        ).order_by(MealLog.planned_datetime).first()
        
        if not next_meal:
            return None
        
        time_until = (next_meal.planned_datetime - datetime.utcnow()).total_seconds() / 60
        
        return {
            "id": next_meal.id,
            "meal_type": next_meal.meal_type,
            "recipe": next_meal.recipe.title if next_meal.recipe else None,
            "scheduled_time": next_meal.planned_datetime.isoformat(),
            "time_until_minutes": max(0, time_until),
            "preparation_needed": time_until <= 30 and time_until > 0
        }
    
    def _get_contextual_hydration_reminder(self) -> str:
        """Get contextual hydration reminder based on time"""
        hour = datetime.now().hour
        
        reminders = {
            (6, 9): "Start your day with a glass of water! 💧",
            (9, 12): "Mid-morning hydration check - aim for 2-3 glasses by now",
            (12, 15): "Lunch time! Don't forget to hydrate with your meal",
            (15, 18): "Afternoon reminder: Stay hydrated to avoid the slump",
            (18, 21): "Evening hydration - have water with dinner",
            (21, 24): "Light hydration before bed - not too much!"
        }
        
        for time_range, reminder in reminders.items():
            if time_range[0] <= hour < time_range[1]:
                return reminder
        
        return "Stay hydrated throughout the day! 💧"
    
    async def handle_meal_logged(self, meal_log_id: int) -> Dict:
        """Handle meal logged event and send updates"""
        
        # Get updated summary
        summary = self.consumption_service.get_today_summary(self.user_id)
        
        # Check inventory after deduction
        inventory_status = self.tracking_agent.calculate_inventory_status()
        
        # Create update message
        update = {
            "event": "meal_logged",
            "data": {
                "meal_log_id": meal_log_id,
                "daily_progress": summary.get("progress", {}),
                "total_calories": summary.get("total_calories", 0),
                "meals_consumed": summary.get("meals_consumed", 0),
                "inventory_percentage": inventory_status.get("overall_percentage", 0)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check for alerts
        if inventory_status.get("critical_items"):
            update["alerts"] = [
                f"Low stock: {item['name']}" 
                for item in inventory_status["critical_items"][:3]
            ]
        
        return update
    
    async def handle_inventory_update(self, items_updated: List[Dict]) -> Dict:
        """Handle inventory update event"""
        
        # Get new inventory status
        inventory_status = self.tracking_agent.calculate_inventory_status()
        
        # Check for new expiring items
        expiry_check = self.tracking_agent.check_expiring_items()
        
        update = {
            "event": "inventory_updated",
            "data": {
                "items_updated": len(items_updated),
                "overall_percentage": inventory_status.get("overall_percentage", 0),
                "critical_items": inventory_status.get("critical_items", []),
                "expiring_items": expiry_check.get("expiring_items", [])
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return update
    
    async def generate_progress_update(self) -> Dict:
        """Generate periodic progress update"""
        
        status = await self.get_real_time_status()
        
        return {
            "event": "progress_update",
            "data": status,
            "timestamp": datetime.utcnow().isoformat()
        }

# WebSocket endpoint
@router.websocket("/ws/tracking")
async def websocket_tracking_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT token for authentication"),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time tracking updates
    
    Sends real-time updates for:
    - Meal consumption logging
    - Inventory changes
    - Progress updates
    - Alerts and notifications
    """
    
    # Authenticate user
    user = await get_current_user_websocket(token, db)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    # Connect
    await manager.connect(websocket, user.id)
    
    # Initialize tracker
    tracker = RealTimeTracker(db, user.id)
    
    # Send initial status
    initial_status = await tracker.get_real_time_status()
    await manager.send_json_to_user({
        "event": "connected",
        "data": initial_status
    }, user.id)
    
    # Start periodic updates task
    async def send_periodic_updates():
        while True:
            try:
                await asyncio.sleep(60)  # Update every minute
                
                # Check if still connected
                if user.id not in manager.active_connections:
                    break
                
                # Send progress update
                update = await tracker.generate_progress_update()
                await manager.send_json_to_user(update, user.id)
                
                # Check for meal reminders
                next_meal = await tracker._get_next_meal_info()
                if next_meal and next_meal["time_until_minutes"] <= 15:
                    await manager.send_json_to_user({
                        "event": "meal_reminder",
                        "data": {
                            "message": f"Your {next_meal['meal_type']} is coming up in {int(next_meal['time_until_minutes'])} minutes!",
                            "meal": next_meal
                        }
                    }, user.id)
                
            except Exception as e:
                logger.error(f"Error in periodic updates: {str(e)}")
                break
    
    # Start periodic updates in background
    update_task = asyncio.create_task(send_periodic_updates())
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "meal_logged":
                meal_log_id = message.get("meal_log_id")
                if meal_log_id:
                    update = await tracker.handle_meal_logged(meal_log_id)
                    await manager.send_json_to_user(update, user.id)
            
            elif message.get("type") == "inventory_update":
                items = message.get("items", [])
                update = await tracker.handle_inventory_update(items)
                await manager.send_json_to_user(update, user.id)
            
            elif message.get("type") == "request_status":
                status = await tracker.get_real_time_status()
                await manager.send_json_to_user({
                    "event": "status_response",
                    "data": status
                }, user.id)
            
            elif message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        update_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error for user {user.id}: {str(e)}")
        manager.disconnect(websocket, user.id)
        update_task.cancel()


# backend/app/services/notification_service.py
"""
Push notification service for real-time updates
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.database import User, MealLog, UserInventory, UserProfile
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for managing push notifications"""
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_queue = asyncio.Queue()
    
    async def send_meal_reminder(
        self,
        user_id: int,
        meal_type: str,
        recipe_name: str,
        time_until: int
    ) -> bool:
        """Send meal reminder notification"""
        
        notification = {
            "user_id": user_id,
            "type": "meal_reminder",
            "title": f"{meal_type.capitalize()} Reminder",
            "body": f"Time to prepare {recipe_name}! Starting in {time_until} minutes.",
            "data": {
                "meal_type": meal_type,
                "recipe": recipe_name,
                "time_until": time_until
            },
            "priority": "high" if time_until <= 15 else "normal"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def send_inventory_alert(
        self,
        user_id: int,
        alert_type: str,
        items: List[str]
    ) -> bool:
        """Send inventory alert notification"""
        
        if alert_type == "low_stock":
            title = "Low Stock Alert"
            body = f"Running low on: {', '.join(items[:3])}"
        elif alert_type == "expiring":
            title = "Expiry Alert"
            body = f"Items expiring soon: {', '.join(items[:3])}"
        else:
            return False
        
        notification = {
            "user_id": user_id,
            "type": "inventory_alert",
            "title": title,
            "body": body,
            "data": {
                "alert_type": alert_type,
                "items": items
            },
            "priority": "normal"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def send_progress_update(
        self,
        user_id: int,
        compliance_rate: float,
        calories_consumed: float,
        calories_remaining: float
    ) -> bool:
        """Send daily progress update"""
        
        notification = {
            "user_id": user_id,
            "type": "progress_update",
            "title": "Daily Progress",
            "body": f"Compliance: {compliance_rate:.0f}% | {calories_consumed:.0f} cal consumed | {calories_remaining:.0f} cal remaining",
            "data": {
                "compliance_rate": compliance_rate,
                "calories_consumed": calories_consumed,
                "calories_remaining": calories_remaining
            },
            "priority": "low"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def send_achievement(
        self,
        user_id: int,
        achievement_type: str,
        message: str
    ) -> bool:
        """Send achievement notification"""
        
        notification = {
            "user_id": user_id,
            "type": "achievement",
            "title": "Achievement Unlocked! 🏆",
            "body": message,
            "data": {
                "achievement_type": achievement_type
            },
            "priority": "normal"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def process_notification_queue(self):
        """Process notifications from queue"""
        
        while True:
            try:
                notification = await self.notification_queue.get()
                
                # In production, integrate with push notification service
                # (Firebase Cloud Messaging, AWS SNS, OneSignal, etc.)
                
                # For now, log the notification
                logger.info(f"Notification for user {notification['user_id']}: {notification['title']}")
                
                # Store in database for history
                from app.models.database import AgentInteraction
                
                interaction = AgentInteraction(
                    user_id=notification["user_id"],
                    agent_type="notification",
                    interaction_type=notification["type"],
                    response_text=notification["body"],
                    context_data=notification["data"],
                    created_at=datetime.utcnow()
                )
                
                self.db.add(interaction)
                self.db.commit()
                
            except Exception as e:
                logger.error(f"Error processing notification: {str(e)}")
                await asyncio.sleep(1)
    
    def check_achievements(self, user_id: int) -> List[Dict]:
        """Check for new achievements"""
        
        achievements = []
        
        # Check streak achievement
        week_ago = datetime.utcnow() - timedelta(days=7)
        meal_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.planned_datetime >= week_ago,
                MealLog.consumed_datetime.isnot(None)
            )
        ).all()
        
        if len(meal_logs) >= 21:  # 3 meals x 7 days
            achievements.append({
                "type": "week_streak",
                "message": "7-day perfect streak! All meals logged this week!"
            })
        
        # Check calorie goal achievement
        from app.models.database import UserProfile
        
        profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if profile and profile.goal_calories:
            today_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    func.date(MealLog.consumed_datetime) == datetime.utcnow().date()
                )
            ).all()
            
            total_calories = sum(
                log.recipe.macros_per_serving.get("calories", 0) * log.portion_multiplier
                for log in today_logs
                if log.recipe and log.recipe.macros_per_serving
            )
            
            if abs(total_calories - profile.goal_calories) < profile.goal_calories * 0.05:
                achievements.append({
                    "type": "perfect_calories",
                    "message": "Perfect calorie target! Within 5% of your goal!"
                })
        
        return achievements


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


# backend/app/main.py updates for WebSocket
"""
Add WebSocket support to main FastAPI app
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.api.websocket_tracking import router as websocket_router
from app.services.notification_service import NotificationService
from app.core.events import event_bus

app = FastAPI(title="NutriLens AI", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket router
app.include_router(websocket_router, prefix="/api/v1")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    # Start event processor
    asyncio.create_task(event_bus.process_events())
    
    # Start notification processor
    # notification_service = NotificationService(get_db())
    # asyncio.create_task(notification_service.process_notification_queue())
    
    logger.info("Background tasks started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down background tasks")