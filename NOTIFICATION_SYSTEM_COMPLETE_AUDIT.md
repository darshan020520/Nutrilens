# Notification System - Complete Architecture Audit

**Date:** 2026-01-01
**Purpose:** Compare OLD vs NEW architecture, design cleanest notification system

---

## PART 1: OLD Architecture (tracking_agent.py)

### A. User-Triggered Notifications (Synchronous - during API calls)

#### 1. **Meal Logging Achievements** (tracking_agent.py:487-536)
**Trigger:** After user logs a meal
**Location:** `tracking_agent.py:log_meal_consumption()`
**Logic:** `_check_meal_achievements()` (line 1396-1541)

**Achievement Types:**
- **Streak achievements** (7-day, 14-day, 30-day)
  - Condition: 21+ meal logs in last 7 days
  - Redis key: `achievement_sent:{user_id}:streak_{7/14/30}day:{date}`
  - TTL: 24 hours

- **Daily completion** (3 meals logged)
  - Condition: 3+ meals logged today
  - Redis key: `achievement_sent:{user_id}:daily_completion:{date}`
  - TTL: 24 hours

- **Nutrition target** (protein goal)
  - Condition: `protein_consumed >= protein_target` (currently hardcoded 50g)
  - Redis key: `achievement_sent:{user_id}:nutrition_target:{date}`
  - TTL: 24 hours

**Delivery:**
1. **Push notification** via `notification_service.send_achievement()` → Redis queue
2. **WebSocket** via `websocket_manager.broadcast_to_user()` → Real-time UI update

---

#### 2. **Progress Update** (tracking_agent.py:544-575)
**Trigger:** After meal logging (every meal)
**Location:** `tracking_agent.py:log_meal_consumption()`

**Data sent:**
- Compliance rate
- Calories consumed
- Calories remaining

**Delivery:**
1. **Push notification** via `notification_service.send_progress_update()` → Redis queue
2. **WebSocket** event_type: `macro_update` → Real-time dashboard update

---

#### 3. **Meal Logged Event** (tracking_agent.py:578-590)
**Trigger:** After meal logging
**Location:** `tracking_agent.py:log_meal_consumption()`

**Delivery:**
- **WebSocket only** event_type: `meal_logged`
- No push notification

---

#### 4. **Inventory Updated Event** (tracking_agent.py:392-410)
**Trigger:** After inventory deduction during meal logging
**Location:** `tracking_agent.py:log_meal_consumption()`

**Delivery:**
- **WebSocket only** event_type: `inventory_updated`
- No push notification

---

### B. Worker-Triggered Notifications (Asynchronous - background worker)

#### 5. **Inventory Alerts - Expiring Items** (tracking_agent.py:1345)
**Trigger:** Worker at 8 AM daily (notification_worker.py:99-106)
**Location:** `tracking_agent.py:check_and_send_inventory_alert()`

**Logic:**
- Check items expiring within 3 days
- Redis key: `inventory_alert:{user_id}:expiring:{date}`
- TTL: 24 hours (sent once per day)

**Delivery:**
- **Push notification** via `notification_service.send_inventory_alert(alert_type="expiring")`

---

#### 6. **Inventory Alerts - Low Stock** (tracking_agent.py:1370)
**Trigger:** Worker at 8 AM daily (notification_worker.py:99-106)
**Location:** `tracking_agent.py:check_and_send_inventory_alert()`

**Logic:**
- Check restock list for urgent items
- Redis key: `inventory_alert:{user_id}:restock:{date}`
- TTL: 24 hours (sent once per day)

**Delivery:**
- **Push notification** via `notification_service.send_inventory_alert(alert_type="low_stock")`

---

#### 7. **Meal Reminders** (tracking_agent.py:1894)
**Trigger:** Worker every 5 minutes (notification_worker.py:112-128)
**Location:** `notification_worker.py:_trigger_meal_reminders()`

**Logic:**
- Find meals with `planned_datetime` in 25-35 minutes
- Send reminder 30 minutes before meal

**Delivery:**
- **Push notification** via `notification_service.send_meal_reminder()`

---

#### 8. **Daily Summary** (notification_worker.py:181-202)
**Trigger:** Worker at 9 PM daily
**Location:** `notification_worker.py:_trigger_daily_summaries()`

**Data:**
- Meals consumed
- Compliance rate
- Total calories

**Delivery:**
- **Push notification** via `notification_service.send_daily_summary()`

---

#### 9. **Weekly Report** (notification_worker.py:204-228)
**Trigger:** Worker at 8 PM every Sunday
**Location:** `notification_worker.py:_trigger_weekly_reports()`

**Data:**
- Average compliance
- Total meals consumed
- Weekly analytics

**Delivery:**
- **Push notification** via `notification_service.send_weekly_report()`

---

## PART 2: NEW v2 Architecture

### Services Layer

#### meal_tracking_service.py
- **Has:** `notification_service` injected (line 41, 55)
- **Missing:** Achievement checking logic
- **Missing:** Progress update logic
- **Missing:** WebSocket events
- **Comment:** Line 121-122 says "notifications can be async/background task"

#### meal_logging_orchestrator.py
- **Has:** Event publishing (line 137): `_publish_meal_logged_events()`
  - Calls `event_publisher.publish_meal_logged()` → WebSocket + Event bus
- **Has:** Notification sending (line 145): `_send_meal_logged_notifications()`
  - Only sends **inventory alert** for critical items
  - **Missing:** Achievements
  - **Missing:** Progress update
  - **Missing:** Meal logged notification

---

### Events Layer (meal_events.py)

**MealEventPublisher** has methods:
1. `publish_meal_logged()` (line 43)
   - Sends to WebSocket
   - Publishes to event bus
2. `publish_external_meal_logged()` (line 84)
3. `publish_meal_skipped()` (line 122)
4. `publish_inventory_updated()` (line 160)

**Event data structure:**
```python
{
    "event_type": "meal_logged",
    "user_id": 123,
    "timestamp": "2026-01-01T12:00:00",
    "data": {
        "meal_log": {...},
        "daily_summary": {...},
        "inventory_changes": [...]
    }
}
```

---

## PART 3: Comparison Matrix

| Feature | OLD (v1) | NEW (v2) | Status |
|---------|----------|----------|--------|
| **Achievements** | ✅ Redis dedup | ❌ Missing | **MISSING** |
| **Progress update** | ✅ After meal log | ❌ Missing | **MISSING** |
| **Meal logged event** | ✅ WebSocket | ✅ Event publisher | **EXISTS** |
| **Inventory updated** | ✅ WebSocket | ✅ Event publisher | **EXISTS** |
| **Inventory alerts** | ✅ Worker-triggered | ⚠️ Orchestrator (wrong) | **WRONG LOCATION** |
| **Meal reminders** | ✅ Worker-triggered | ❌ Missing | **MISSING** |
| **Daily summary** | ✅ Worker-triggered | ❌ Missing | **MISSING** |
| **Weekly report** | ✅ Worker-triggered | ❌ Missing | **MISSING** |

---

## PART 4: Architecture Issues

### Issue 1: Synchronous Notifications Block API Response
**Location:** `meal_logging_orchestrator.py:145`

```python
await self._send_meal_logged_notifications(...)  # BLOCKS
```

**Problem:** API waits for Redis push to complete before responding

---

### Issue 2: Inventory Alert in Wrong Place
**Location:** `meal_logging_orchestrator.py:564`

Orchestrator sends inventory alert for **critical items after meal logging**.

**Problem:** This should be worker-triggered at 8 AM, not user-triggered.

---

### Issue 3: Missing Achievement System
**Impact:** Users don't get achievement notifications in v2

**Required:**
- Redis deduplication keys
- Achievement checking logic
- Notification + WebSocket delivery

---

### Issue 4: WebSocket vs Event Publisher Confusion
**OLD:** Direct WebSocket calls in tracking_agent
**NEW:** Event publisher with WebSocket + Event bus

**Problem:** Event publisher adds complexity but event bus is not used

---

### Issue 5: No Worker Integration
**OLD:** `notification_worker.py` calls `tracking_agent` methods
**NEW:** Worker still calls OLD tracking_agent (line 241-242)

```python
tracking_agent = TrackingAgent(db, user.id)
result = await tracking_agent.check_and_send_inventory_alert()
```

**Problem:** Worker bypasses v2 architecture completely

---

## PART 5: Best Practices Analysis

### Principle 1: Separation of Concerns
**User-triggered notifications** → Should be in orchestrator/service
**Worker-triggered notifications** → Should be in dedicated worker
**Delivery mechanism** → Should be abstracted (NotificationService)

---

### Principle 2: Async by Default
**Immediate response required?** → WebSocket real-time update
**Background delivery OK?** → Queue to Redis
**Don't block API response** → Fire and forget

---

### Principle 3: Single Responsibility
**NotificationService** → Queue management, provider selection, retry logic
**EventPublisher** → Real-time WebSocket updates
**AchievementService** → Achievement logic + Redis dedup
**Worker** → Time-based triggers only

---

### Principle 4: Idempotency
**Redis deduplication keys** → Prevent duplicate notifications
**TTL on keys** → Auto-cleanup
**Key format:** `{type}:{user_id}:{subtype}:{date}`

---

## PART 6: Proposed Clean Architecture

### Layer 1: API/Orchestrator (User Actions)

**After meal logging:**
1. ✅ Calculate daily totals (service)
2. ✅ Deduct inventory (service)
3. ✅ Check achievements (NEW: AchievementService)
4. ✅ Publish WebSocket event (EventPublisher) - fire and forget
5. ❌ NO push notifications here (let worker handle)

**Response time:** < 500ms

---

### Layer 2: Services

#### AchievementService (NEW)
**Responsibility:** Check achievements with Redis dedup

**Methods:**
- `check_meal_achievements(user_id, meal_result)` → List[Achievement]
- `check_streak(user_id)` → Optional[Achievement]
- `check_daily_completion(user_id)` → Optional[Achievement]
- `check_nutrition_target(user_id, daily_totals)` → Optional[Achievement]

**Returns achievements, doesn't send notifications**

---

#### EventPublisher (EXISTS)
**Responsibility:** Real-time WebSocket updates

**Events:**
- `meal_logged` → Update meal list
- `achievement_unlocked` → Show achievement popup
- `macro_update` → Update dashboard
- `inventory_updated` → Update inventory status

**Fire and forget - doesn't block**

---

#### NotificationService (EXISTS)
**Responsibility:** Queue notifications to Redis

**Methods:**
- `send_achievement()` → Queue
- `send_progress_update()` → Queue
- `send_meal_reminder()` → Queue
- `send_inventory_alert()` → Queue
- `send_daily_summary()` → Queue
- `send_weekly_report()` → Queue

**Consumer process sends via providers (Push/Email/SMS)**

---

### Layer 3: Worker (Time-Based Triggers)

**NotificationWorker:**
1. **Every 5 minutes:** Check upcoming meals → send reminders
2. **8 AM daily:** Check inventory → send expiring/low stock alerts
3. **9 PM daily:** Send daily summaries
4. **8 PM Sunday:** Send weekly reports

**Worker triggers, NotificationService queues, Consumer sends**

---

### Layer 4: Background Consumers

**Redis Queue Processor:**
- Pulls from priority queues (urgent/high/normal/low)
- Sends via providers (FCM/SendGrid/Twilio)
- Retries on failure (3 attempts)
- Logs to database

**Runs continuously, separate from worker**

---

## PART 7: Data Flow Diagrams

### User-Triggered Flow (Meal Logging)

```
User → API → Orchestrator → MealTrackingService
                ↓
        AchievementService.check_achievements()
                ↓
        [Achievement 1, Achievement 2, ...]
                ↓
        EventPublisher.publish_achievement() → WebSocket (real-time)
                ↓
        Return response (200 OK)

(Background - doesn't block)
NotificationWorker checks achievements → NotificationService.send_achievement() → Redis queue
```

---

### Worker-Triggered Flow (Inventory Alerts)

```
NotificationWorker (8 AM daily)
        ↓
Check expiring items (via InventoryService)
        ↓
NotificationService.send_inventory_alert()
        ↓
Redis queue (high priority)
        ↓
Consumer pulls from queue
        ↓
Send via FCM/Email/SMS
```

---

## PART 8: Redis Key Schema

### Achievement Deduplication
```
achievement_sent:{user_id}:streak_7day:{YYYY-MM-DD}
achievement_sent:{user_id}:daily_completion:{YYYY-MM-DD}
achievement_sent:{user_id}:nutrition_target:{YYYY-MM-DD}
TTL: 86400 seconds (24 hours)
```

### Inventory Alert Deduplication
```
inventory_alert:{user_id}:expiring:{YYYY-MM-DD}
inventory_alert:{user_id}:restock:{YYYY-MM-DD}
TTL: 86400 seconds (24 hours)
```

### Notification Queues
```
notifications:urgent
notifications:high
notifications:normal
notifications:low
```

---

## PART 9: Implementation Priority

### Phase 1: Fix Blocking Issues
1. ✅ Make event publishing fire-and-forget (orchestrator)
2. ✅ Remove notifications from orchestrator (move to worker)

### Phase 2: Migrate Achievements
1. ✅ Create AchievementService
2. ✅ Integrate into meal_logging_orchestrator
3. ✅ Publish achievement events to WebSocket

### Phase 3: Worker Refactoring
1. ✅ Worker uses v2 services (not tracking_agent)
2. ✅ Worker triggers notifications via NotificationService
3. ✅ Remove tracking_agent from worker

### Phase 4: Cleanup
1. ✅ Remove tracking_agent.py (deprecated)
2. ✅ Update tests

---

## PART 10: Open Questions

1. **WebSocket vs Event Bus:** Event publisher has event_bus but it's not used. Remove it?
2. **Progress updates:** Should we send after EVERY meal or daily summary only?
3. **Inventory alert after meal:** Remove from orchestrator or keep?
4. **Protein target:** Hardcoded to 50g. Get from user goals?

---

Ready to implement?