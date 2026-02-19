# Current Notification System - Simple Facts

**Date:** 2026-01-02
**Goal:** Understand what exists, not what should exist

---

## PART 1: What We Have Today

### NotificationService (Single Class)

**File:** `backend/app/services/notification_service.py`

**What it does:**
1. Has 6 public methods: `send_meal_reminder()`, `send_achievement()`, `send_inventory_alert()`, `send_progress_update()`, `send_daily_summary()`, `send_weekly_report()`
2. Each method builds a dict with notification data
3. Calls `_queue_notification()` → pushes to Redis
4. Returns True/False

**Current flow:**
```
Caller → NotificationService.send_achievement()
           ↓
       _queue_notification() → Redis lpush
           ↓
       Returns True/False
```

**Separate process:**
```
NotificationService.process_notification_queue() (infinite loop)
           ↓
       Redis brpop → get notification
           ↓
       _send_notification() → _send_via_provider()
           ↓
       Mock provider (prints to console)
```

---

## PART 2: Who Calls These Methods?

### OLD v1 (tracking_agent.py)

**Achievement:**
```python
# Line 503
await self.notification_service.send_achievement(
    user_id=self.user_id,
    achievement_type=achievement["type"],
    message=achievement["message"]
)
```

**Progress Update:**
```python
# Line 544
await self.notification_service.send_progress_update(
    user_id=self.user_id,
    compliance_rate=today_summary.get("compliance_rate", 0),
    calories_consumed=today_summary.get("total_calories", 0),
    calories_remaining=result.get("remaining_targets", {}).get("calories", 0)
)
```

**Inventory Alert:**
```python
# Line 1345
await self.notification_service.send_inventory_alert(
    user_id=self.user_id,
    alert_type="expiring",
    items=item_names
)
```

### NEW v2 (orchestrator)

**Inventory Alert:**
```python
# orchestrator line 564
await self.notification.send_inventory_alert(
    user_id=user_id,
    alert_type="low_stock",
    items=item_names
)
```

### Worker (notification_worker.py)

**Meal Reminder:**
```python
# Line 162
await notification_service.send_meal_reminder(
    user_id=meal.user_id,
    meal_type=meal.meal_type,
    recipe_name=meal.recipe.title if meal.recipe else "Your meal",
    time_until=time_until
)
```

**Daily Summary:**
```python
# Line 193
await notification_service.send_daily_summary(
    user_id=user.id,
    summary_data=summary
)
```

---

## PART 3: Current Problems (Facts Only)

### Problem 1: Orchestrator Waits for Redis Push
**Location:** `meal_logging_orchestrator.py:145`

```python
await self._send_meal_logged_notifications(...)  # Line 145
```

This calls:
```python
await self.notification.send_inventory_alert(...)  # Line 564
```

Which awaits Redis lpush. **API response blocked.**

---

### Problem 2: Achievement Logic Missing in v2
**OLD v1:** tracking_agent has `_check_meal_achievements()` (line 1396)
**NEW v2:** meal_tracking_service has no achievement logic

**Result:** Achievements not working in v2

---

### Problem 3: Progress Update Missing in v2
**OLD v1:** tracking_agent sends progress update after meal logging (line 544)
**NEW v2:** orchestrator doesn't send progress update

**Result:** Progress notifications not working in v2

---

### Problem 4: Worker Calls OLD tracking_agent
**Location:** `notification_worker.py:241`

```python
tracking_agent = TrackingAgent(db, user.id)
result = await tracking_agent.check_and_send_inventory_alert()
```

Worker bypasses v2 architecture completely.

---

### Problem 5: All Providers Are Mocked
**Location:** `notification_service.py:551-558`

```python
if provider == NotificationProvider.PUSH:
    return await _mock_send_provider(notification_data, "PUSH")
```

All notifications just print to console. **Not production-ready.**

---

## PART 4: What We Actually Need (No Assumptions)

### Requirement 1: Don't Block API Response
When user logs meal, API should return immediately. Notifications sent in background.

### Requirement 2: Achievement Checking in v2
After meal logging, check achievements (streak, daily completion, protein goal).

### Requirement 3: Progress Update in v2
After meal logging, send progress update notification.

### Requirement 4: Worker Uses v2 Services
Worker should call v2 services, not tracking_agent.

### Requirement 5: Real Providers
Implement actual FCM/Email/SMS sending (not mocked).

---

## PART 5: Questions to Discuss

### Question 1: Producer vs Consumer Separation

**Current:** Both in NotificationService class
- `send_achievement()` → producer (queues to Redis)
- `process_notification_queue()` → consumer (pulls from Redis)

**Question:** Should these be separate classes? Or keep in one class?

**Why separate?**
- Producer instantiated per request (in orchestrator/service)
- Consumer runs as single long-lived process
- Different lifecycles

**Why together?**
- Simpler
- Already works
- Just need to fix blocking issue

---

### Question 2: Where Does Achievement Checking Happen?

**Option A: In Service**
```python
class MealTrackingService:
    async def log_meal(...):
        # ... log meal logic
        achievements = self._check_achievements(user_id, daily_totals)
        for achievement in achievements:
            await self.notification_service.send_achievement(...)
```

**Option B: In Orchestrator**
```python
class MealLoggingOrchestrator:
    async def log_planned_meal(...):
        meal_result = await self.meal_tracking.log_meal(...)
        achievements = await self.achievement_service.check(user_id, meal_result)
        for achievement in achievements:
            await self.notification_service.send_achievement(...)
```

**Option C: Event-Based (with EventBus)**
```python
class MealTrackingService:
    async def log_meal(...):
        # ... log meal logic
        self.event_bus.publish(MealLoggedEvent(...))
        # Achievement handler listens and sends notification
```

**Which is cleaner? Which fits our architecture?**

---

### Question 3: Do We Need EventBus/Observer Pattern?

**Current:** Direct calls to notification_service
**Proposed:** EventBus with handlers

**Benefits:**
- Decoupled
- Easy to add new reactions (analytics, logging)
- Doesn't block

**Drawbacks:**
- More complexity
- More files/classes
- Harder to trace

**Question:** Is current direct call approach good enough? Or do we need EventBus?

---

### Question 4: Fire-and-Forget vs Await

**Current:**
```python
await self.notification.send_inventory_alert(...)  # Waits for Redis push
```

**Option A: Fire-and-forget (asyncio.create_task)**
```python
asyncio.create_task(self.notification.send_inventory_alert(...))
# API continues immediately
```

**Option B: Synchronous queue (fire-and-forget built-in)**
```python
self.notification.queue_notification(...)  # sync method, instant return
```

**Which approach?**

---

### Question 5: Do We Need Domain Events?

**Domain Event Example:**
```python
@dataclass
class MealLoggedEvent:
    user_id: int
    meal_type: str
    daily_totals: Dict
```

**Benefits:**
- Explicit what happened
- Type-safe
- Self-documenting

**Current:** Just pass dicts around

**Question:** Worth adding typed events? Or overkill?

---

### Question 6: Strategy Pattern for Providers

**Current:** if/elif chain in `_send_via_provider()`

```python
if provider == NotificationProvider.PUSH:
    return await _mock_send_provider(...)
elif provider == NotificationProvider.EMAIL:
    return await _mock_send_provider(...)
```

**Strategy Pattern:**
```python
class FCMProvider:
    async def send(self, notification):
        # actual FCM logic

provider = factory.get_provider(user_preferences)
await provider.send(notification)
```

**Question:** Is if/elif good enough? Or worth abstracting providers?

---

### Question 7: Worker Architecture

**Current:** Custom worker with infinite loop

**Alternative:** Use Celery

**Celery Benefits:**
- Industry standard
- Built-in scheduling (Celery Beat)
- Task retry, monitoring, distributed workers

**Current Benefits:**
- Simple
- No external dependencies
- Works

**Question:** Keep custom worker or migrate to Celery?

---

## PART 6: My Understanding (Tell Me If Wrong)

### Understanding 1: Redis Queue Works Fine
The producer-consumer with Redis is good. No major issues.
**Correct?**

### Understanding 2: Main Problem is Blocking
The `await notification.send_...()` in orchestrator blocks API.
Need fire-and-forget.
**Correct?**

### Understanding 3: Achievement Logic Just Needs Migration
We have working achievement logic in tracking_agent.
Just need to move it to v2 (service or orchestrator).
**Correct?**

### Understanding 4: Providers Need Implementation
Mocked providers need to become real (FCM SDK, SendGrid, Twilio).
This is separate from architecture discussion.
**Correct?**

### Understanding 5: Worker is Separate Concern
Worker triggers notifications at scheduled times.
Architecture doesn't change how worker works.
**Correct?**

---

## PART 7: Let's Discuss One by One

I want to understand YOUR perspective on:

1. **Producer/Consumer separation** - Necessary or overkill?
2. **Achievement checking location** - Service, Orchestrator, or Event-based?
3. **EventBus/Observer pattern** - Needed or over-engineering?
4. **Fire-and-forget approach** - asyncio.create_task or sync queue method?
5. **Domain Events** - Add typed events or keep dicts?
6. **Strategy pattern for providers** - Worth it or if/elif is fine?
7. **Celery vs custom worker** - Migrate or keep current?

Let's discuss each point. No assumptions. Just facts and tradeoffs.
