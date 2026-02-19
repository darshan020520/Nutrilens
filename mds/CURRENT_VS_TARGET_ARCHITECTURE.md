# Current Implementation vs Target Architecture

**Date:** 2026-01-02

---

## CURRENT IMPLEMENTATION

### 1. NotificationService (Lines 68-900+)
**Does Everything:**
- Lines 83-88: Initializes providers (FCM, Email, SMS, WhatsApp)
- Lines 152-344: 6 public methods (send_achievement, send_reminder, etc.)
- Lines 348-404: _queue_notification() → Redis lpush
- Lines 432-512: process_notification_queue() → Consumer pulls from Redis
- Lines 547-558: _send_via_provider() → if/elif chain (mocked)

**Problems:**
- ❌ Producer + Consumer in same class
- ❌ Heavy initialization even when just queuing
- ❌ No Strategy pattern (if/elif chain)
- ❌ All providers mocked

---

### 2. MealEventPublisher (meal_events.py)
**Current:**
- Lines 43-83: publish_meal_logged() → sends to WebSocket + event_bus
- Line 76: event_bus parameter exists but NEVER used (always None)

**Problems:**
- ❌ Only publishes to WebSocket
- ❌ Not a real Observer pattern
- ❌ event_bus dead code

---

### 3. Orchestrator (Lines 120-169)
**Current:**
- Line 137: await self._publish_meal_logged_events() → WebSocket
- Line 145: await self._send_meal_logged_notifications() → **BLOCKS API**

**Problems:**
- ❌ Knows about WebSocket AND Notification (2 dependencies)
- ❌ Blocks on notification
- ❌ No achievement checking

---

## TARGET ARCHITECTURE

### Observer Pattern Core

```
EventPublisher
├─> NotificationObserver (check achievements, queue notifications)
├─> WebSocketObserver (broadcast to clients)
├─> CalendarObserver (future)
└─> AnalyticsObserver (future)

Separate Consumer:
Redis Queue → Strategy Factory → FCM/Email/SMS Strategy
```

---

## MIGRATION PLAN

### Phase 1: Create Foundation (No Breaking Changes)

**Create NEW files:**
1. `infrastructure/events/observer.py` - IObserver interface
2. `infrastructure/events/event_publisher.py` - EventPublisher
3. `infrastructure/observers/websocket_observer.py` - Wrap existing WebSocket
4. `services/achievement_service.py` - Extract from tracking_agent

**Result:** New code exists, old code untouched

---

### Phase 2: NotificationObserver

**Create:**
5. `infrastructure/observers/notification_observer.py`
   - Uses AchievementService to check achievements
   - Calls existing NotificationService.send_achievement() for now

**Result:** Can publish events, observers react, still uses old NotificationService

---

### Phase 3: Strategy Pattern

**Create:**
6. `infrastructure/notifications/strategies/base.py` - INotificationStrategy
7. `infrastructure/notifications/strategies/fcm_strategy.py` - Extract from NotificationService._init_push_provider()
8. `infrastructure/notifications/strategy_factory.py`

**Result:** Providers using Strategy pattern

---

### Phase 4: Split Producer/Consumer

**Create:**
9. `infrastructure/notifications/notification_producer.py` - Extract _queue_notification()
10. `infrastructure/notifications/notification_consumer.py` - Extract process_notification_queue()

**Result:** Producer and Consumer separated

---

### Phase 5: Switch Orchestrator

**Update:**
11. Orchestrator uses EventPublisher only
12. Delete _publish_meal_logged_events()
13. Delete _send_meal_logged_notifications()

**Result:** Clean orchestrator, non-blocking

---

### Phase 6: Cleanup

14. Delete old NotificationService
15. Delete MealEventPublisher
16. Update worker

---

## WHAT STAYS THE SAME

✅ Redis queue names (notifications:urgent/high/normal/low)
✅ Notification data format
✅ User preferences logic
✅ Retry logic
✅ Database models

---

## QUESTIONS FOR YOU

1. **Should we start with Phase 1?** (Create IObserver, EventPublisher, WebSocketObserver, AchievementService)

2. **Do you want to see the actual code for these 4 files before we create them?**

3. **Or do you want to discuss the approach more first?**
