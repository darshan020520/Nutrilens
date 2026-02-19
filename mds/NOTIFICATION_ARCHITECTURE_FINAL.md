# Notification Architecture - Clean & Extensible

**Date:** 2026-01-02
**Goal:** Clear definitions, no mixing, no over-engineering

---

## Component Definitions (No Mixing)

### 1. Subject
**Definition:** The entity whose state changes
**In our system:** MealLog (state: planned → consumed)
**Responsibility:** Knows when its state changes
**Location:** Domain/Service layer

### 2. Publisher (Event Publisher)
**Definition:** Mechanism that notifies observers when subject state changes
**In our system:** EventPublisher class
**Responsibility:**
- Maintains list of observers
- Calls observer.update() when notified
**Location:** `infrastructure/events/event_publisher.py`

### 3. Observer (Interface)
**Definition:** Interface that all observers must implement
**In our system:** IObserver interface with update() method
**Responsibility:** Defines contract for observers
**Location:** `infrastructure/events/observer.py`

### 4. Concrete Observers
**Definition:** Classes that implement IObserver
**In our system:**
- NotificationObserver
- WebSocketObserver
- CalendarObserver (future)
- AnalyticsObserver (future)
**Responsibility:** React to subject state changes
**Location:** `infrastructure/observers/`

### 5. Strategy (Interface)
**Definition:** Interface for notification delivery channels
**In our system:** INotificationStrategy
**Responsibility:** Defines contract for delivery channels
**Location:** `infrastructure/notifications/strategies/base.py`

### 6. Concrete Strategies
**Definition:** Implementations of INotificationStrategy
**In our system:**
- FCMStrategy (Firebase push)
- EmailStrategy (SendGrid)
- SMSStrategy (Twilio)
**Responsibility:** Send notification via specific channel
**Location:** `infrastructure/notifications/strategies/`

### 7. Strategy Factory
**Definition:** Selects appropriate strategy based on user preferences
**In our system:** NotificationStrategyFactory
**Responsibility:** Return FCM/Email/SMS based on user preference
**Location:** `infrastructure/notifications/strategy_factory.py`

### 8. Notification Template
**Definition:** Standardizes notification message format
**In our system:** NotificationTemplate base class
**Responsibility:** Consistent title/body/data structure
**Location:** `infrastructure/notifications/templates/`

### 9. Notification Factory
**Definition:** Creates different notification types
**In our system:** NotificationFactory
**Responsibility:** Create achievement/reminder/alert notifications
**Location:** `infrastructure/notifications/notification_factory.py`

### 10. Priority Handler (Chain)
**Definition:** Processes notifications based on priority
**In our system:** PriorityHandler chain
**Responsibility:** Route to urgent/high/normal/low queues
**Location:** `infrastructure/notifications/priority_handler.py`

---

## Clean Architecture Layers

```
┌──────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER                          │
│  - MealLog (entity)                                      │
│  - State changes (planned → consumed)                    │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│                  APPLICATION LAYER                       │
│  - MealTrackingService (changes MealLog state)          │
│  - MealLoggingOrchestrator (coordinates)                │
└──────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────┐
│                INFRASTRUCTURE LAYER                      │
│  - EventPublisher (Observer Pattern)                    │
│  - Observers (Notification, WebSocket, Calendar)        │
│  - Strategies (FCM, Email, SMS - Strategy Pattern)      │
│  - Templates (Standardized messages)                    │
│  - Factories (Create notifications)                     │
│  - Priority Handlers (Chain of Responsibility)          │
└──────────────────────────────────────────────────────────┘
```

---

## File Structure (Clean Separation)

```
backend/app/
├── domain/
│   └── (no changes - MealLog entity exists)
│
├── services/
│   └── meal_tracking_service.py
│       - Calls event_publisher.publish() after state change
│
├── orchestrators/
│   └── meal_logging_orchestrator.py
│       - Coordinates meal logging
│       - Does NOT know about observers
│
├── infrastructure/
│   ├── events/
│   │   ├── event_publisher.py         # Publisher (Observer Pattern)
│   │   └── observer.py                # IObserver interface
│   │
│   ├── observers/
│   │   ├── notification_observer.py   # Concrete Observer
│   │   ├── websocket_observer.py      # Concrete Observer
│   │   ├── calendar_observer.py       # Concrete Observer (future)
│   │   └── analytics_observer.py      # Concrete Observer (future)
│   │
│   └── notifications/
│       ├── strategies/
│       │   ├── base.py                # INotificationStrategy
│       │   ├── fcm_strategy.py        # Concrete Strategy
│       │   ├── email_strategy.py      # Concrete Strategy
│       │   └── sms_strategy.py        # Concrete Strategy
│       │
│       ├── templates/
│       │   ├── base.py                # NotificationTemplate
│       │   ├── achievement_template.py
│       │   ├── reminder_template.py
│       │   └── alert_template.py
│       │
│       ├── strategy_factory.py        # Strategy Factory
│       ├── notification_factory.py    # Notification Factory
│       └── priority_handler.py        # Chain of Responsibility
```

---

## Code Implementation (No Over-Engineering)

### 1. IObserver Interface

```python
# infrastructure/events/observer.py
from abc import ABC, abstractmethod
from typing import Dict

class IObserver(ABC):
    """Observer interface - all observers must implement update()"""

    @abstractmethod
    async def update(self, event: Dict) -> None:
        """Called when subject state changes"""
        pass
```

**Clear Definition:** Contract that all observers follow.

---

### 2. EventPublisher (Publisher)

```python
# infrastructure/events/event_publisher.py
from typing import List, Dict
from infrastructure.events.observer import IObserver

class EventPublisher:
    """Publisher - maintains observers and notifies them"""

    def __init__(self):
        self._observers: List[IObserver] = []

    def attach(self, observer: IObserver) -> None:
        """Register an observer"""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: IObserver) -> None:
        """Remove an observer"""
        self._observers.remove(observer)

    async def publish(self, event_type: str, data: Dict) -> None:
        """Notify all observers about state change"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }

        for observer in self._observers:
            await observer.update(event)
```

**Clear Definition:**
- Knows observers
- Notifies them when state changes
- Nothing else

---

### 3. NotificationObserver (Concrete Observer)

```python
# infrastructure/observers/notification_observer.py
from infrastructure.events.observer import IObserver
from infrastructure.notifications.notification_factory import NotificationFactory
from infrastructure.notifications.priority_handler import PriorityHandler

class NotificationObserver(IObserver):
    """Observer that handles notifications"""

    def __init__(
        self,
        notification_factory: NotificationFactory,
        priority_handler: PriorityHandler
    ):
        self.notification_factory = notification_factory
        self.priority_handler = priority_handler

    async def update(self, event: Dict) -> None:
        """React to state change by creating and queuing notification"""

        # Check if we should send notification for this event
        if event["type"] == "meal_logged":
            await self._handle_meal_logged(event)

    async def _handle_meal_logged(self, event: Dict):
        # Check for achievements
        achievements = await self._check_achievements(event["data"])

        for achievement in achievements:
            # Create notification using factory
            notification = self.notification_factory.create_achievement_notification(
                user_id=event["data"]["user_id"],
                achievement_type=achievement["type"],
                message=achievement["message"]
            )

            # Route through priority handler (Chain of Responsibility)
            await self.priority_handler.handle(notification)
```

**Clear Definition:**
- Reacts to events
- Checks achievements
- Creates notifications (Factory)
- Routes through priority handler (Chain)

---

### 4. WebSocketObserver (Concrete Observer)

```python
# infrastructure/observers/websocket_observer.py
from infrastructure.events.observer import IObserver

class WebSocketObserver(IObserver):
    """Observer that broadcasts to WebSocket clients"""

    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager

    async def update(self, event: Dict) -> None:
        """React to state change by broadcasting to WebSocket"""

        if event["type"] == "meal_logged":
            await self.ws_manager.broadcast_to_user(
                user_id=event["data"]["user_id"],
                message={
                    "event_type": "meal_logged",
                    "data": event["data"]
                }
            )
```

**Clear Definition:**
- Reacts to events
- Broadcasts to WebSocket
- Nothing else

---

### 5. INotificationStrategy Interface

```python
# infrastructure/notifications/strategies/base.py
from abc import ABC, abstractmethod
from typing import Dict

class INotificationStrategy(ABC):
    """Strategy interface for notification delivery channels"""

    @abstractmethod
    async def send(self, notification: Dict) -> bool:
        """Send notification via this channel"""
        pass
```

**Clear Definition:** Contract for all delivery channels.

---

### 6. FCMStrategy (Concrete Strategy)

```python
# infrastructure/notifications/strategies/fcm_strategy.py
from infrastructure.notifications.strategies.base import INotificationStrategy
import firebase_admin
from firebase_admin import messaging

class FCMStrategy(INotificationStrategy):
    """Strategy for Firebase Cloud Messaging"""

    async def send(self, notification: Dict) -> bool:
        """Send push notification via FCM"""
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification["title"],
                    body=notification["body"]
                ),
                token=notification["fcm_token"]
            )

            response = messaging.send(message)
            return True
        except Exception as e:
            logger.error(f"FCM send failed: {e}")
            return False
```

**Clear Definition:** Sends via FCM, nothing else.

---

### 7. NotificationStrategyFactory

```python
# infrastructure/notifications/strategy_factory.py
from infrastructure.notifications.strategies.base import INotificationStrategy
from infrastructure.notifications.strategies.fcm_strategy import FCMStrategy
from infrastructure.notifications.strategies.email_strategy import EmailStrategy
from infrastructure.notifications.strategies.sms_strategy import SMSStrategy

class NotificationStrategyFactory:
    """Factory that selects delivery strategy based on user preference"""

    def __init__(self, user_preference_repo):
        self.user_prefs = user_preference_repo
        self.strategies = {
            "push": FCMStrategy(),
            "email": EmailStrategy(),
            "sms": SMSStrategy()
        }

    async def get_strategy(self, user_id: int) -> INotificationStrategy:
        """Get preferred delivery channel for user"""
        preference = await self.user_prefs.get_notification_preference(user_id)
        return self.strategies.get(preference, self.strategies["push"])
```

**Clear Definition:** Selects strategy based on user preference.

---

### 8. NotificationTemplate (Base)

```python
# infrastructure/notifications/templates/base.py
from abc import ABC, abstractmethod

class NotificationTemplate(ABC):
    """Template for standardizing notification format"""

    def build(self, data: Dict) -> Dict:
        """Template method - defines structure"""
        return {
            "title": self.get_title(data),
            "body": self.get_body(data),
            "data": self.get_data(data),
            "action_url": self.get_action_url(data)
        }

    @abstractmethod
    def get_title(self, data: Dict) -> str:
        pass

    @abstractmethod
    def get_body(self, data: Dict) -> str:
        pass

    def get_data(self, data: Dict) -> Dict:
        return data

    def get_action_url(self, data: Dict) -> str:
        return "/"
```

**Clear Definition:** Standardizes notification structure.

---

### 9. AchievementTemplate (Concrete Template)

```python
# infrastructure/notifications/templates/achievement_template.py
from infrastructure.notifications.templates.base import NotificationTemplate

class AchievementTemplate(NotificationTemplate):
    """Template for achievement notifications"""

    def get_title(self, data: Dict) -> str:
        return "Achievement Unlocked!"

    def get_body(self, data: Dict) -> str:
        return data["message"]

    def get_action_url(self, data: Dict) -> str:
        return "/achievements"
```

**Clear Definition:** Achievement-specific message format.

---

### 10. NotificationFactory

```python
# infrastructure/notifications/notification_factory.py
from infrastructure.notifications.templates.achievement_template import AchievementTemplate
from infrastructure.notifications.templates.reminder_template import ReminderTemplate

class NotificationFactory:
    """Factory for creating different notification types"""

    def __init__(self):
        self.templates = {
            "achievement": AchievementTemplate(),
            "reminder": ReminderTemplate(),
            "alert": AlertTemplate()
        }

    def create_achievement_notification(self, user_id: int, achievement_type: str, message: str) -> Dict:
        template = self.templates["achievement"]
        return template.build({
            "user_id": user_id,
            "achievement_type": achievement_type,
            "message": message,
            "type": "achievement"
        })

    def create_reminder_notification(self, user_id: int, meal_type: str, time_until: int) -> Dict:
        template = self.templates["reminder"]
        return template.build({
            "user_id": user_id,
            "meal_type": meal_type,
            "time_until": time_until,
            "type": "reminder"
        })
```

**Clear Definition:** Creates typed notifications.

---

### 11. PriorityHandler (Chain of Responsibility)

```python
# infrastructure/notifications/priority_handler.py
import redis

class PriorityHandler:
    """Routes notifications to priority queues"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def handle(self, notification: Dict) -> None:
        """Route to appropriate priority queue"""
        priority = self._determine_priority(notification)
        queue_name = f"notifications:{priority}"

        self.redis.lpush(queue_name, json.dumps(notification))

    def _determine_priority(self, notification: Dict) -> str:
        """Determine priority based on notification type"""
        if notification["type"] == "achievement":
            return "high"
        elif notification["type"] == "reminder":
            return "urgent"
        elif notification["type"] == "alert":
            return "high"
        else:
            return "normal"
```

**Clear Definition:** Routes to priority queues.

---

## How They Work Together

### Flow: User Logs Meal

```python
# 1. Service changes state
class MealTrackingService:
    def __init__(self, event_publisher):
        self.event_publisher = event_publisher

    async def log_meal(self, user_id, meal_log_id):
        # Change state
        meal_log = await self.repo.mark_as_consumed(meal_log_id)

        # Publish event
        await self.event_publisher.publish("meal_logged", {
            "user_id": user_id,
            "meal_log": meal_log,
            "daily_totals": daily_totals
        })

# 2. EventPublisher notifies all observers
class EventPublisher:
    async def publish(self, event_type, data):
        for observer in self._observers:
            await observer.update({"type": event_type, "data": data})

# 3. NotificationObserver reacts
class NotificationObserver:
    async def update(self, event):
        achievements = check_achievements(event["data"])
        for achievement in achievements:
            notification = self.factory.create_achievement_notification(...)
            await self.priority_handler.handle(notification)

# 4. WebSocketObserver reacts independently
class WebSocketObserver:
    async def update(self, event):
        await self.ws_manager.broadcast(event)

# 5. CalendarObserver reacts independently (future)
class CalendarObserver:
    async def update(self, event):
        await self.calendar_sync.add_meal(event["data"])
```

---

## What to Implement Now vs Later

### Implement Now (Minimum for v2):
1. ✅ EventPublisher (Observer Pattern core)
2. ✅ IObserver interface
3. ✅ NotificationObserver (concrete)
4. ✅ WebSocketObserver (concrete)
5. ✅ INotificationStrategy interface
6. ✅ FCMStrategy (one strategy to start)
7. ✅ NotificationFactory (basic)
8. ✅ PriorityHandler (basic routing)

### Add Later (Extensibility):
9. EmailStrategy, SMSStrategy (more strategies)
10. NotificationTemplate (standardize format)
11. CalendarObserver (new observer)
12. AnalyticsObserver (new observer)

---

## Extension Points (How to Add New Features)

### Adding Google Calendar Sync:
```python
# Just create new observer
class CalendarObserver(IObserver):
    async def update(self, event):
        await google_calendar.sync(event["data"])

# Register it
event_publisher.attach(CalendarObserver())
```
**No changes to existing code.**

### Adding SMS Channel:
```python
# Just create new strategy
class SMSStrategy(INotificationStrategy):
    async def send(self, notification):
        await twilio.send_sms(notification)

# Add to factory
strategy_factory.strategies["sms"] = SMSStrategy()
```
**No changes to existing code.**

---

## Summary: Clear Definitions

| Component | Responsibility | Pattern |
|-----------|---------------|---------|
| EventPublisher | Notify observers | Observer (Publisher) |
| IObserver | Define observer contract | Observer (Interface) |
| NotificationObserver | React by creating notifications | Observer (Concrete) |
| WebSocketObserver | React by broadcasting | Observer (Concrete) |
| INotificationStrategy | Define delivery contract | Strategy (Interface) |
| FCMStrategy | Send via Firebase | Strategy (Concrete) |
| NotificationFactory | Create typed notifications | Factory Method |
| NotificationTemplate | Standardize format | Template |
| PriorityHandler | Route by priority | Chain of Responsibility |

**No mixing. No confusion. Clear extension points.**

Ready to implement?