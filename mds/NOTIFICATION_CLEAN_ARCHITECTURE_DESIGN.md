# Notification System - Clean Architecture Design
## Based on Industry Best Practices (2025)

**Date:** 2026-01-02
**Approach:** Learning from established patterns, not reinventing the wheel

---

## Research Summary

### Key Patterns Identified

1. **Observer Pattern** - For event-driven notifications
2. **Strategy Pattern** - For multi-channel delivery (FCM/Email/SMS)
3. **Domain Events** - For in-process event handling (DDD)
4. **Integration Events** - For cross-boundary notifications
5. **Producer-Consumer** - For async processing via queue
6. **Celery Beat** - For scheduled/recurring tasks

**Sources:**
- [Observer Design Pattern in Notification Service](https://www.suprsend.com/post/observer-design-pattern-in-notification-service-for-building-scalable-applications-with-loose-coupling)
- [Notification Architecture Design Pattern 2025](https://techshitanshu.com/notification-architecture-design-pattern/)
- [Domain Events in Clean Architecture](https://www.ronnydelgado.com/my-blog/domain-events-ddd-clean-architecture)
- [Microsoft - Domain Events Design and Implementation](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/domain-events-design-implementation)
- [Celery Task Queues with Redis](https://blog.naveenpn.com/implementing-task-queues-in-python-using-celery-and-redis-scalable-background-jobs)
- [Celery Periodic Tasks](https://antoniodimariano.medium.com/how-to-run-periodic-tasks-in-celery-28e1abf8b458)

---

## PART 1: Clean Architecture Layers

### Layer 1: Domain Layer (Core Business Logic)

**Domain Events** - Things that happened in the domain

```python
# domain/events/meal_events.py
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

@dataclass
class DomainEvent:
    """Base class for all domain events"""
    occurred_at: datetime
    user_id: int

@dataclass
class MealLoggedEvent(DomainEvent):
    """Domain event: User logged a meal"""
    meal_log_id: int
    meal_type: str
    recipe_name: str
    macros: Dict[str, float]
    daily_totals: Dict[str, float]

@dataclass
class AchievementUnlockedEvent(DomainEvent):
    """Domain event: User unlocked achievement"""
    achievement_type: str
    achievement_message: str
```

**Why Domain Events?**
> "A domain event is something that happened in the domain that you want other parts of the same domain (in-process) to be aware of." - [Microsoft DDD Docs](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/domain-events-design-implementation)

---

### Layer 2: Application Layer (Use Cases)

**Event Handlers** - React to domain events

```python
# application/event_handlers/meal_event_handlers.py
from typing import Protocol
from domain.events.meal_events import MealLoggedEvent

class EventHandler(Protocol):
    """Base protocol for event handlers"""
    async def handle(self, event: DomainEvent) -> None:
        ...

class AchievementChecker:
    """Checks for achievements when meal logged"""

    def __init__(self, achievement_service, event_bus):
        self.achievement_service = achievement_service
        self.event_bus = event_bus

    async def handle(self, event: MealLoggedEvent) -> None:
        achievements = await self.achievement_service.check_achievements(
            user_id=event.user_id,
            daily_totals=event.daily_totals
        )

        for achievement in achievements:
            # Raise new domain event
            self.event_bus.publish(AchievementUnlockedEvent(
                occurred_at=datetime.utcnow(),
                user_id=event.user_id,
                achievement_type=achievement.type,
                achievement_message=achievement.message
            ))

class NotificationDispatcher:
    """Dispatches notifications for events"""

    def __init__(self, notification_producer):
        self.producer = notification_producer

    async def handle(self, event: AchievementUnlockedEvent) -> None:
        # Queue notification (doesn't send directly)
        await self.producer.queue_notification(
            user_id=event.user_id,
            notification_type="achievement",
            data={
                "type": event.achievement_type,
                "message": event.achievement_message
            }
        )
```

**Why Event Handlers?**
> "With Domain Events, you can decouple the core business logic from secondary processes like sending notifications." - [7 Smart Ways to Use Domain Events](https://medium.com/@maged_/7-smart-ways-to-use-domain-events-like-a-pro-ddd-clean-arch-net-9-d7283b80718d)

---

### Layer 3: Infrastructure Layer (External Systems)

**NotificationProducer** - Queues notifications to Redis

```python
# infrastructure/notifications/notification_producer.py
import redis
import json
from typing import Dict

class NotificationProducer:
    """Queues notifications - doesn't send them"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def queue_notification(
        self,
        user_id: int,
        notification_type: str,
        data: Dict,
        priority: str = "normal"
    ) -> bool:
        # Idempotency check
        idempotency_key = self._generate_key(user_id, notification_type, data)
        if await self._already_queued(idempotency_key):
            return True  # Already queued

        notification = {
            "user_id": user_id,
            "type": notification_type,
            "data": data,
            "priority": priority,
            "queued_at": datetime.utcnow().isoformat()
        }

        # Push to Redis queue
        queue_name = f"notifications:{priority}"
        self.redis.lpush(queue_name, json.dumps(notification))

        # Mark as queued (24hr TTL)
        self.redis.setex(f"notification_queued:{idempotency_key}", 86400, "1")

        return True
```

---

**NotificationConsumer** - Processes queue (separate worker process)

```python
# infrastructure/notifications/notification_consumer.py
import asyncio
import redis
import json
from typing import Dict

class NotificationConsumer:
    """Pulls from queue and sends notifications"""

    def __init__(self, redis_client: redis.Redis, provider_factory):
        self.redis = redis_client
        self.provider_factory = provider_factory
        self.running = True

    async def start(self):
        """Main consumer loop"""
        while self.running:
            await asyncio.gather(
                self._process_queue("urgent"),
                self._process_queue("high"),
                self._process_queue("normal"),
                self._process_queue("low")
            )
            await asyncio.sleep(5)

    async def _process_queue(self, priority: str):
        queue_name = f"notifications:{priority}"
        batch_size = 10 if priority in ["urgent", "high"] else 5

        for _ in range(batch_size):
            result = self.redis.brpop(queue_name, timeout=1)
            if not result:
                break

            _, notification_json = result
            notification = json.loads(notification_json)

            # Get appropriate provider (Strategy Pattern)
            provider = self.provider_factory.get_provider(notification)
            success = await provider.send(notification)

            if not success:
                await self._handle_retry(notification)
```

---

**Provider Strategy Pattern** - Multi-channel delivery

```python
# infrastructure/notifications/providers/base.py
from abc import ABC, abstractmethod
from typing import Dict

class NotificationProvider(ABC):
    """Base class for notification providers"""

    @abstractmethod
    async def send(self, notification: Dict) -> bool:
        """Send notification via this provider"""
        pass

# infrastructure/notifications/providers/fcm_provider.py
class FCMProvider(NotificationProvider):
    """Firebase Cloud Messaging provider"""

    async def send(self, notification: Dict) -> bool:
        # FCM-specific logic
        pass

# infrastructure/notifications/providers/email_provider.py
class EmailProvider(NotificationProvider):
    """Email provider (SendGrid)"""

    async def send(self, notification: Dict) -> bool:
        # Email-specific logic
        pass

# infrastructure/notifications/provider_factory.py
class ProviderFactory:
    """Creates appropriate provider based on user preferences"""

    def __init__(self, fcm_provider, email_provider, sms_provider):
        self.providers = {
            "push": fcm_provider,
            "email": email_provider,
            "sms": sms_provider
        }

    def get_provider(self, notification: Dict) -> NotificationProvider:
        # Get user preferences (cached)
        channel = self._get_preferred_channel(notification["user_id"])
        return self.providers[channel]
```

**Why Strategy Pattern?**
> "Each consumer fetches full payload and formats messages via Template pattern, while dispatchers consult user preferences, apply Strategy, and pass via Chain to the correct sender." - [Notification Architecture 2025](https://techshitanshu.com/notification-architecture-design-pattern/)

---

## PART 2: Worker Architecture (Celery Beat)

### Scheduled Tasks (Time-Based Triggers)

**Why Celery Beat?**
> "Celery Beat is a scheduler that announces tasks at regular intervals that will be executed by worker nodes." - [Celery Periodic Tasks](https://antoniodimariano.medium.com/how-to-run-periodic-tasks-in-celery-28e1abf8b458)

```python
# workers/celery_app.py
from celery import Celery
from celery.schedules import crontab

app = Celery('nutrilens')

app.conf.beat_schedule = {
    # Meal reminders every 5 minutes
    'check-meal-reminders': {
        'task': 'workers.tasks.check_meal_reminders',
        'schedule': crontab(minute='*/5')
    },
    # Inventory alerts at 8 AM daily
    'check-inventory-alerts': {
        'task': 'workers.tasks.check_inventory_alerts',
        'schedule': crontab(hour=8, minute=0)
    },
    # Daily summary at 9 PM
    'send-daily-summaries': {
        'task': 'workers.tasks.send_daily_summaries',
        'schedule': crontab(hour=21, minute=0)
    },
    # Weekly report Sunday 8 PM
    'send-weekly-reports': {
        'task': 'workers.tasks.send_weekly_reports',
        'schedule': crontab(day_of_week=0, hour=20, minute=0)
    }
}

# workers/tasks.py
from celery import shared_task

@shared_task
def check_meal_reminders():
    """Find upcoming meals and queue reminders"""
    # Query upcoming meals
    upcoming_meals = get_upcoming_meals(time_window=30)

    for meal in upcoming_meals:
        # Use NotificationProducer to queue
        producer.queue_notification(
            user_id=meal.user_id,
            notification_type="meal_reminder",
            data={"meal_type": meal.meal_type, "recipe": meal.recipe.title},
            priority="high"
        )

@shared_task
def check_inventory_alerts():
    """Check inventory and queue alerts"""
    users = get_active_users()

    for user in users:
        # Check expiring items
        expiring = inventory_service.get_expiring_items(user.id)
        if expiring:
            producer.queue_notification(
                user_id=user.id,
                notification_type="inventory_alert",
                data={"alert_type": "expiring", "items": expiring},
                priority="high"
            )
```

**Best Practices:**
> "You have to ensure only a single scheduler is running for a schedule at a time, otherwise you'd end up with duplicate tasks." - [Celery Best Practices](https://blog.naveenpn.com/implementing-task-queues-in-python-using-celery-and-redis-scalable-background-jobs)

---

## PART 3: Observer Pattern (WebSocket Events)

### Real-Time UI Updates

**Why Observer Pattern?**
> "The Observer pattern enables an object (subject) to send updates to interested parties (observers) when there's a change in its state, effectively decoupling subjects from observers." - [Observer Pattern in Notification Service](https://www.suprsend.com/post/observer-design-pattern-in-notification-service-for-building-scalable-applications-with-loose-coupling)

```python
# infrastructure/websocket/event_publisher.py
from typing import List, Protocol

class Observer(Protocol):
    """Observer interface - clients subscribe to events"""
    async def update(self, event_type: str, data: Dict) -> None:
        ...

class WebSocketEventPublisher:
    """Subject - publishes events to observers (WebSocket clients)"""

    def __init__(self):
        self._observers: Dict[int, List[Observer]] = {}  # user_id -> [observers]

    def subscribe(self, user_id: int, observer: Observer):
        """Client subscribes to user's events"""
        if user_id not in self._observers:
            self._observers[user_id] = []
        self._observers[user_id].append(observer)

    def unsubscribe(self, user_id: int, observer: Observer):
        """Client unsubscribes"""
        if user_id in self._observers:
            self._observers[user_id].remove(observer)

    async def publish(self, user_id: int, event_type: str, data: Dict):
        """Notify all observers for this user"""
        if user_id in self._observers:
            for observer in self._observers[user_id]:
                await observer.update(event_type, data)

# application/event_handlers/websocket_handler.py
class WebSocketNotifier:
    """Event handler that publishes to WebSocket"""

    def __init__(self, ws_publisher: WebSocketEventPublisher):
        self.ws_publisher = ws_publisher

    async def handle(self, event: AchievementUnlockedEvent):
        """When achievement unlocked, notify WebSocket clients"""
        await self.ws_publisher.publish(
            user_id=event.user_id,
            event_type="achievement_unlocked",
            data={
                "type": event.achievement_type,
                "message": event.achievement_message
            }
        )
```

---

## PART 4: Complete Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                          │
│  ┌──────────────────┐              ┌──────────────────┐            │
│  │  REST API        │              │  WebSocket       │            │
│  │  (FastAPI)       │              │  (Observer)      │            │
│  └────────┬─────────┘              └────────┬─────────┘            │
└───────────┼──────────────────────────────────┼──────────────────────┘
            │                                  │
┌───────────┼──────────────────────────────────┼──────────────────────┐
│           │        APPLICATION LAYER         │                      │
│           ▼                                  ▼                      │
│  ┌─────────────────┐              ┌──────────────────┐             │
│  │ MealTrackingUC  │─────────────▶│  EventBus        │             │
│  └────────┬────────┘               └────────┬─────────┘             │
│           │ Publishes                       │ Dispatches            │
│           │ MealLoggedEvent                 │ to handlers           │
│           │                                 │                       │
│           │              ┌──────────────────┼────────────┐          │
│           │              ▼                  ▼            ▼          │
│           │   ┌────────────────┐  ┌──────────────┐  ┌─────────┐   │
│           │   │ Achievement    │  │ WebSocket    │  │ Notif   │   │
│           │   │ Checker        │  │ Notifier     │  │ Dispatch│   │
│           │   └───────┬────────┘  └──────────────┘  └────┬────┘   │
│           │           │ Publishes                        │         │
│           │           │ AchievementEvent                 │         │
│           │           └──────────────────────────────────┘         │
└───────────┼──────────────────────────────────────────────┼─────────┘
            │                                              │
┌───────────┼──────────────────────────────────────────────┼─────────┐
│           │       INFRASTRUCTURE LAYER                   │         │
│           ▼                                              ▼         │
│  ┌──────────────┐                          ┌──────────────────┐   │
│  │  Services    │                          │ Notification     │   │
│  │  Repos       │                          │ Producer         │   │
│  │  DB          │                          │ (Queue to Redis) │   │
│  └──────────────┘                          └────────┬─────────┘   │
└───────────────────────────────────────────────────────┼───────────┘
                                                        │
                                           ┌────────────▼──────────┐
                                           │   Redis Queues        │
                                           │  ┌─────────────────┐  │
                                           │  │ urgent          │  │
                                           │  │ high            │  │
                                           │  │ normal          │  │
                                           │  │ low             │  │
                                           │  └─────────────────┘  │
                                           └────────────┬──────────┘
                                                        │
┌───────────────────────────────────────────────────────┼───────────┐
│                    WORKER PROCESSES                   │           │
│  ┌────────────────────────────┐        ┌─────────────▼────────┐  │
│  │  Celery Beat Scheduler     │        │ Notification         │  │
│  │  ┌──────────────────────┐  │        │ Consumer             │  │
│  │  │ Every 5min: Reminders│  │        │ ┌────────────────┐   │  │
│  │  │ 8 AM: Inventory      │──┼───────▶│ │ Pull from queue│   │  │
│  │  │ 9 PM: Daily Summary  │  │        │ │ Strategy Pattern│   │  │
│  │  │ Sun 8PM: Weekly      │  │        │ │ Send via provider  │  │
│  │  └──────────────────────┘  │        │ └────────┬───────┘   │  │
│  └────────────────────────────┘        └──────────┼───────────┘  │
└───────────────────────────────────────────────────┼──────────────┘
                                                     │
                                        ┌────────────┴──────────┐
                                        │                       │
                                   ┌────▼────┐  ┌────▼────┐  ┌▼────┐
                                   │   FCM   │  │  Email  │  │ SMS │
                                   │Provider │  │Provider │  │Prov │
                                   └─────────┘  └─────────┘  └─────┘
```

---

## PART 5: Who is What?

### Publishers (Subjects)
1. **MealTrackingService** - Publishes `MealLoggedEvent`
2. **AchievementService** - Publishes `AchievementUnlockedEvent`
3. **InventoryService** - Publishes `InventoryUpdatedEvent`
4. **Celery Beat** - Triggers scheduled tasks (time-based publisher)

### Observers (Subscribers)
1. **AchievementChecker** - Observes `MealLoggedEvent`, checks achievements
2. **WebSocketNotifier** - Observes all events, publishes to WebSocket clients
3. **NotificationDispatcher** - Observes events, queues notifications
4. **AnalyticsTracker** - Observes events, logs to analytics DB

### Strategy (Providers)
1. **FCMProvider** - Sends push notifications
2. **EmailProvider** - Sends emails
3. **SMSProvider** - Sends SMS
4. **ProviderFactory** - Selects provider based on user preferences

### Worker Components
1. **Celery Beat** - Scheduler (triggers time-based tasks)
2. **Celery Worker** - Executes tasks (queries DB, queues notifications)
3. **NotificationConsumer** - Processes Redis queue, sends notifications

---

## PART 6: Data Flow Examples

### Example 1: User Logs Meal (User-Triggered)

```
User logs meal
    ↓
API → MealTrackingService.log_meal()
    ↓
EventBus.publish(MealLoggedEvent)
    ↓
┌─────────────────┬──────────────────┬───────────────────┐
│                 │                  │                   │
▼                 ▼                  ▼                   ▼
AchievementChecker WebSocketNotifier NotificationDispatch AnalyticsTracker
│                 │                  │                   │
│ checks          │ publishes        │ queues            │ logs
│ achievements    │ to WS clients    │ to Redis          │ to DB
│                 │                  │                   │
└─►EventBus.publish│                 └─►Redis queue      │
   (AchievementEvent)│                      ↓             │
        │           │                 NotificationConsumer│
        │           │                      ↓             │
        └───────────┴────────────►WebSocket + Push       │
                                                          │
API returns 200 OK ◄──────────────────────────────────────┘
(doesn't wait for notifications)
```

**Key Point:** API doesn't wait for notifications to be sent!

---

### Example 2: Scheduled Inventory Alert (Worker-Triggered)

```
Celery Beat (8 AM daily)
    ↓
Triggers: check_inventory_alerts task
    ↓
Celery Worker executes
    ↓
InventoryService.get_expiring_items(all users)
    ↓
For each user with expiring items:
    NotificationProducer.queue_notification()
    ↓
Redis queue (high priority)
    ↓
NotificationConsumer pulls from queue
    ↓
ProviderFactory.get_provider(user preferences)
    ↓
FCMProvider.send() / EmailProvider.send()
    ↓
User receives notification
```

**Key Point:** Worker queries, queues, consumer sends. Decoupled.

---

## PART 7: Implementation Priority

### Phase 1: Core Infrastructure
1. ✅ Domain Events (MealLoggedEvent, AchievementUnlockedEvent)
2. ✅ EventBus (in-memory observer pattern)
3. ✅ NotificationProducer (queue to Redis with idempotency)
4. ✅ NotificationConsumer (pull from Redis, send via providers)

### Phase 2: Strategy Pattern
5. ✅ Provider abstraction (base class)
6. ✅ FCMProvider implementation
7. ✅ EmailProvider implementation
8. ✅ ProviderFactory (user preference-based selection)

### Phase 3: Event Handlers
9. ✅ AchievementChecker (observes MealLoggedEvent)
10. ✅ WebSocketNotifier (observes all events)
11. ✅ NotificationDispatcher (observes events, queues)

### Phase 4: Worker Integration
12. ✅ Celery setup with Redis broker
13. ✅ Celery Beat schedule configuration
14. ✅ Scheduled tasks (meal reminders, inventory, summaries)

### Phase 5: Migration
15. ✅ Migrate orchestrator to use EventBus
16. ✅ Remove direct notification calls from orchestrator
17. ✅ Update worker to use new producer
18. ✅ Delete old tracking_agent

---

## Summary

**Patterns Used:**
- **Observer Pattern** - EventBus, WebSocket
- **Strategy Pattern** - Notification providers
- **Producer-Consumer** - Redis queue
- **Domain Events** - MealLogged, AchievementUnlocked
- **Clean Architecture** - Layers with dependency inversion

**Worker Architecture:**
- **Celery Beat** - Scheduler (time-based triggers)
- **Celery Worker** - Task executor (queries, queues)
- **NotificationConsumer** - Queue processor (sends)

**Key Principles:**
1. ✅ Events don't block API responses
2. ✅ Notifications queued, not sent directly
3. ✅ Workers trigger, producers queue, consumers send
4. ✅ Strategy pattern for multi-channel delivery
5. ✅ Idempotency to prevent duplicates

Ready to implement?

---

**Sources:**
- [Observer Design Pattern in Notification Service](https://www.suprsend.com/post/observer-design-pattern-in-notification-service-for-building-scalable-applications-with-loose-coupling)
- [Notification Architecture Design Pattern 2025](https://techshitanshu.com/notification-architecture-design-pattern/)
- [Domain Events in DDD Clean Architecture](https://www.ronnydelgado.com/my-blog/domain-events-ddd-clean-architecture)
- [Microsoft - Domain Events Design](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/domain-events-design-implementation)
- [Implementing Task Queues with Celery and Redis](https://blog.naveenpn.com/implementing-task-queues-in-python-using-celery-and-redis-scalable-background-jobs)
- [Celery Periodic Tasks Guide](https://antoniodimariano.medium.com/how-to-run-periodic-tasks-in-celery-28e1abf8b458)
- [7 Smart Ways to Use Domain Events](https://medium.com/@maged_/7-smart-ways-to-use-domain-events-like-a-pro-ddd-clean-arch-net-9-d7283b80718d)
