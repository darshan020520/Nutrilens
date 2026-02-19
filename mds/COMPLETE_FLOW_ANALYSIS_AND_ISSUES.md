# Complete End-to-End Flow Analysis

## Executive Summary

**Status**: ⚠️ **CRITICAL DATA MISMATCH FOUND**

The notification architecture has a fundamental data structure mismatch between what the scheduler sends and what the observer expects. This will cause notifications to fail silently.

---

## Flow 1: User-Triggered Events (e.g., Meal Logging)

### 1.1 Trigger Point
**File**: `backend/app/orchestrators/meal_logging_orchestrator.py:500`

```python
await self.event_publisher.publish(
    event_type="meal_logged",
    data={
        "user_id": user_id,
        "meal_log": meal_result.get("logged_meal"),
        "daily_totals": daily_summary,  # ✅ CORRECT KEY
        "inventory_changes": meal_result.get("inventory_changes", []),
        "inventory_status": inventory_status
    }
)
```

**Data Shape**:
```python
{
    "user_id": 123,
    "meal_log": {...},
    "daily_totals": {  # ✅ Matches what observer expects
        "compliance_rate": 85.0,
        "calories_consumed": 1800,
        ...
    },
    "inventory_changes": [...],
    "inventory_status": {...}
}
```

### 1.2 EventPublisher Wrapping
**File**: `backend/app/infrastructure/events/event_publisher.py:42`

```python
event = {
    "type": event_type,  # "meal_logged"
    "timestamp": datetime.utcnow().isoformat(),
    "data": data  # Original data passed through unchanged
}
```

**Wrapped Event**:
```python
{
    "type": "meal_logged",
    "timestamp": "2026-01-09T10:30:00.123456",
    "data": {
        "user_id": 123,
        "meal_log": {...},
        "daily_totals": {...},  # ✅ Still correct
        "inventory_changes": [...],
        "inventory_status": {...}
    }
}
```

### 1.3 NotificationObserver Routing
**File**: `backend/app/infrastructure/observers/notification_observer.py:61`

```python
async def update(self, event: Dict) -> None:
    event_type = event.get("type")  # "meal_logged"
    event_data = event.get("data", {})  # Extract inner data

    handler = self._get_event_handler(event_type)  # → _handle_meal_logged
    await handler(event_data)  # Pass unwrapped data
```

### 1.4 Meal Logged Handler
**File**: `backend/app/infrastructure/observers/notification_observer.py:108`

```python
async def _handle_meal_logged(self, event_data: Dict) -> None:
    user_id = event_data.get("user_id")  # ✅ 123
    daily_totals = event_data.get("daily_totals", {})  # ✅ EXISTS

    # Check achievements
    if self.achievement_service:
        achievements = await self.achievement_service.check_achievements(
            user_id=user_id,
            daily_totals=daily_totals  # ✅ Correct data
        )

    # Create achievement notifications...
```

**Notification Creation**:
```python
await self._create_and_queue_notification(
    notification_type="achievement",  # Factory key
    user_id=user_id,  # 123
    metadata={
        "achievement_type": achievement.get("type"),
        "achievement_name": achievement.get("name"),
        "description": achievement.get("description"),
        "message": achievement.get("message"),
    }
)
```

### 1.5 Factory Creation
**File**: `backend/app/infrastructure/notifications/factories/notification_factory.py:97`

```python
notification_class = cls._notification_types.get(notification_type)
# notification_type="achievement" → AchievementNotification

return notification_class(user_id=user_id, metadata=metadata)
# Returns: AchievementNotification(user_id=123, metadata={...})
```

### 1.6 Template Pattern Execution
**File**: `backend/app/infrastructure/notifications/base_notification.py:64`

```python
def create(self) -> Dict[str, Any]:
    channels = self.determine_channels()  # ["push", "email"]
    priority = self.calculate_priority()  # "high"
    context = self.build_notification_context()  # {...}
    common_metadata = self._add_common_metadata()  # {retry_count: 0, ...}

    return {
        "user_id": self.user_id,  # 123
        "type": self.get_notification_type(),  # "achievement"
        "priority": priority,  # "high"
        "channels": channels,  # ["push", "email"]
        "context": context,  # Template rendering data
        "metadata": common_metadata,  # {retry_count: 0, max_retries: 5, ...}
        "created_at": datetime.utcnow().isoformat()
    }
```

**Returned Notification Data**:
```python
{
    "user_id": 123,
    "type": "achievement",
    "priority": "high",
    "channels": ["push", "email"],
    "context": {
        "achievement_type": "streak_7day",
        "achievement_name": "7-Day Streak Master",
        "description": "Logged meals for 7 consecutive days",
        "message": "Congratulations!"
    },
    "metadata": {
        "retry_count": 0,
        "max_retries": 5,
        "source": "notification_system",
        "version": "1.0"
    },
    "created_at": "2026-01-09T10:30:01.234567"
}
```

### 1.7 Redis Queueing
**File**: `backend/app/infrastructure/observers/notification_observer.py:356`

```python
async def _queue_to_redis(self, notification_data: Dict[str, Any]) -> None:
    priority = notification_data.get("priority", "normal")  # "high"
    queue_key = self.QUEUE_KEYS.get(priority, self.QUEUE_KEYS["normal"])
    # queue_key = "notifications:queue:high"

    notification_json = json.dumps(notification_data)
    # Serializes entire notification dict

    await self.redis_client.lpush(queue_key, notification_json)
    # Pushes to Redis list: LPUSH = add to head, BRPOP = remove from tail (FIFO)
```

**Redis Queue Structure**:
```
Queue: "notifications:queue:high"
Item: '{"user_id": 123, "type": "achievement", "priority": "high", ...}'
```

### 1.8 Consumer Dequeue
**File**: `backend/app/infrastructure/notifications/consumers/notification_consumer.py:98`

```python
# BRPOP blocks until data available (or timeout)
queue_keys = [self.QUEUE_KEYS[p] for p in self.PRIORITY_ORDER]
# ["notifications:queue:urgent", "notifications:queue:high", ...]

result = await self.redis_client.brpop(queue_keys, timeout=brpop_timeout)
# result = ("notifications:queue:high", '{"user_id": 123, ...}')

if result:
    queue_key, notification_json = result
    priority = self._get_priority_from_queue_key(queue_key)  # "high"
    await self._process_notification(notification_json, priority)
```

### 1.9 Consumer Processing
**File**: `backend/app/infrastructure/notifications/consumers/notification_consumer.py:207`

```python
async def _process_notification(self, notification_json: str, priority: str):
    # Deserialize
    notification_data = json.loads(notification_json)
    # {
    #     "user_id": 123,
    #     "type": "achievement",
    #     "priority": "high",
    #     "channels": ["push", "email"],
    #     "context": {...},
    #     "metadata": {...}
    # }

    user_id = notification_data.get("user_id")  # 123
    notification_type = notification_data.get("type")  # "achievement"

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    # Send notification
    await self._send_notification(notification_data, user, db)
```

### 1.10 Notification Sending
**File**: `backend/app/infrastructure/notifications/consumers/notification_consumer.py:162`

```python
async def _send_notification(
    self,
    notification_data: Dict[str, Any],
    user: User,
    db: Session
):
    # Extract info
    user_id = notification_data.get("user_id")  # 123
    notification_type = notification_data.get("type")  # "achievement"
    available_channels = notification_data.get("channels", [])  # ["push", "email"]
    context = notification_data.get("context", {})  # {achievement_type: ..., achievement_name: ...}
    priority = notification_data.get("priority", "normal")  # "high"

    # Get user's preferred channel
    preferred_channel = self._get_user_preferred_channel(user, available_channels)
    # Returns: "push" (highest priority from available)

    # Get channel strategy
    channel = self.channel_factory.get_channel(preferred_channel)
    # Returns: PushChannel instance

    # Validate user can receive
    if not self._validate_user_channel(user, preferred_channel, channel):
        return  # User has no device_token, skip

    # Render template
    user_data = self._get_user_data(user)  # {user_name: ..., user_email: ..., unsubscribe_url: ...}
    rendered = self.template_renderer.render(
        notification_type=notification_type,  # "achievement"
        channel=preferred_channel,  # "push"
        context=context,  # {achievement_type: ..., achievement_name: ...}
        user_data=user_data  # {user_name: ..., user_email: ...}
    )
    # Returns: {title: "Achievement Unlocked!", body: "7-Day Streak Master", data: {...}}

    # Send via channel
    result = await channel.send(user.device_token, title, body, data)
    # Calls Firebase FCM API
```

### 1.11 Channel Sending
**File**: `backend/app/infrastructure/notifications/channels/push_channel.py` (example)

```python
async def send(self, device_token: str, title: str, body: str, data: Dict) -> Dict:
    # Call Firebase FCM
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=data,
        token=device_token
    )

    response = messaging.send(message)
    return {"success": True, "channel": "push", "message_id": response}
```

---

## ✅ Flow 1 Summary: User-Triggered Events WORK CORRECTLY

**Data Flow**:
```
Orchestrator → EventPublisher → NotificationObserver → Factory → BaseNotification
→ Redis Queue → NotificationConsumer → Channel → User Device
```

**Key Data Transformations**:
1. Orchestrator sends `{"user_id": 123, "daily_totals": {...}}`
2. EventPublisher wraps as `{"type": "meal_logged", "timestamp": "...", "data": {...}}`
3. Observer unwraps to get original data, routes to handler
4. Handler calls factory with `notification_type + user_id + metadata`
5. Factory creates notification object
6. BaseNotification.create() returns structured dict with `{user_id, type, priority, channels, context, metadata}`
7. Observer queues to Redis
8. Consumer dequeues, deserializes, sends via channel

**No Issues Found**: ✅

---

## Flow 2: Scheduled Events (e.g., Daily Summary)

### 2.1 APScheduler Trigger
**File**: `backend/app/workers/notification_worker.py:70`

```python
# Schedule daily summaries (every day at 9 PM UTC)
self.scheduler.add_job(
    self._trigger_daily_summaries,  # Method to call
    trigger=CronTrigger(hour=21, minute=0),
    id='daily_summaries',
    name='Daily Summaries',
    replace_existing=True
)
```

### 2.2 Trigger Method Execution
**File**: `backend/app/workers/notification_worker.py:183`

```python
async def _trigger_daily_summaries(self):
    db = self.session_factory()
    try:
        consumption_service = ConsumptionService(db)
        active_users = db.query(User).filter(User.is_active == True).all()

        for user in active_users:
            summary = consumption_service.get_today_summary(user.id)
            # Returns: {
            #     "success": True,
            #     "date": "2026-01-09",
            #     "meals": [...],
            #     "totals": {...},
            #     ...
            # }

            if summary.get("success"):
                await self.event_publisher.publish(
                    event_type="scheduled_daily_summary",
                    data={
                        "user_id": user.id,
                        "summary_data": summary  # ❌ WRONG KEY!
                    }
                )
```

**Published Event Data**:
```python
{
    "user_id": 123,
    "summary_data": {  # ❌ WRONG! Observer expects flat structure
        "success": True,
        "date": "2026-01-09",
        "meals_consumed": 3,
        "compliance_rate": 85.0,
        "calories_consumed": 1800,
        "protein_g": 120,
        ...
    }
}
```

### 2.3 Observer Handler
**File**: `backend/app/infrastructure/observers/notification_observer.py:224`

```python
async def _handle_daily_summary(self, event_data: Dict) -> None:
    user_id = event_data.get("user_id")  # ✅ 123

    await self._create_and_queue_notification(
        notification_type="daily_summary",
        user_id=user_id,
        metadata={
            "date": event_data.get("date"),  # ❌ None (key doesn't exist!)
            "meals_consumed": event_data.get("meals_consumed", 0),  # ❌ 0 (default)
            "compliance_rate": event_data.get("compliance_rate", 0.0),  # ❌ 0.0
            "calories_consumed": event_data.get("calories_consumed", 0),  # ❌ 0
            "protein_g": event_data.get("protein_g", 0),  # ❌ 0
        }
    )
```

**PROBLEM**: Observer expects keys directly in `event_data`:
- `event_data.get("date")`
- `event_data.get("meals_consumed")`
- `event_data.get("compliance_rate")`

But worker sends:
- `event_data.get("summary_data").get("date")`
- `event_data.get("summary_data").get("meals_consumed")`
- `event_data.get("summary_data").get("compliance_rate")`

**Result**: All values will be None or defaults, notification will have empty data!

---

## ⚠️ CRITICAL ISSUES FOUND

### Issue 1: Daily Summary Data Mismatch

**Location**: `backend/app/workers/notification_worker.py:200-206`

**Problem**: Worker sends nested structure, observer expects flat structure

**Current (WRONG)**:
```python
await self.event_publisher.publish(
    event_type="scheduled_daily_summary",
    data={
        "user_id": user.id,
        "summary_data": summary  # ❌ Nested!
    }
)
```

**Observer Expects**:
```python
{
    "user_id": 123,
    "date": "2026-01-09",
    "meals_consumed": 3,
    "compliance_rate": 85.0,
    "calories_consumed": 1800,
    "protein_g": 120
}
```

**Fix Required**:
```python
await self.event_publisher.publish(
    event_type="scheduled_daily_summary",
    data={
        "user_id": user.id,
        "date": summary.get("date"),
        "meals_consumed": summary.get("meals_consumed", 0),
        "compliance_rate": summary.get("compliance_rate", 0.0),
        "calories_consumed": summary.get("calories_consumed", 0),
        "protein_g": summary.get("protein_g", 0),
    }
)
```

### Issue 2: Weekly Report Data Mismatch

**Location**: `backend/app/workers/notification_worker.py:238-245`

**Problem**: Same issue - nested `report_data` instead of flat structure

**Current (WRONG)**:
```python
await self.event_publisher.publish(
    event_type="scheduled_weekly_report",
    data={
        "user_id": user.id,
        "report_data": analytics["analytics"]  # ❌ Nested!
    }
)
```

**Observer Expects** (`notification_observer.py:244`):
```python
{
    "user_id": 123,
    "start_date": "2026-01-02",
    "end_date": "2026-01-09",
    "total_meals": 21,
    "average_compliance": 82.0,
    "weight_change": -1.5,
    "achievements_unlocked": 2
}
```

**Fix Required**:
```python
analytics_data = analytics.get("analytics", {})
await self.event_publisher.publish(
    event_type="scheduled_weekly_report",
    data={
        "user_id": user.id,
        "start_date": analytics_data.get("start_date"),
        "end_date": analytics_data.get("end_date"),
        "total_meals": analytics_data.get("total_meals", 0),
        "average_compliance": analytics_data.get("average_compliance", 0.0),
        "weight_change": analytics_data.get("weight_change", 0.0),
        "achievements_unlocked": analytics_data.get("achievements_unlocked", 0),
    }
)
```

### Issue 3: Meal Reminder Data Mismatch

**Location**: `backend/app/workers/notification_worker.py:159-168`

**Problem**: Sends `time_until_minutes` but observer expects `time_until`

**Current (WRONG)**:
```python
await self.event_publisher.publish(
    event_type="scheduled_meal_reminder",
    data={
        "user_id": meal.user_id,
        "meal_type": meal.meal_type,
        "recipe_name": meal.recipe.title if meal.recipe else "Your meal",
        "time_until_minutes": time_until,  # ❌ Wrong key!
        "meal_id": meal.id
    }
)
```

**Observer Expects** (`notification_observer.py:261`):
```python
{
    "user_id": 123,
    "meal_type": "lunch",
    "recipe_name": "Grilled Chicken",
    "time_until": 30,  # ✅ Correct key
    "scheduled_time": "12:30 PM"
}
```

**Fix Required**:
```python
await self.event_publisher.publish(
    event_type="scheduled_meal_reminder",
    data={
        "user_id": meal.user_id,
        "meal_type": meal.meal_type,
        "recipe_name": meal.recipe.title if meal.recipe else "Your meal",
        "time_until": time_until,  # ✅ Fixed key
        "scheduled_time": meal.planned_datetime.strftime("%I:%M %p"),  # Add this
    }
)
```

### Issue 4: Inventory Check Data Mismatch

**Location**: `backend/app/workers/notification_worker.py:278-284`

**Problem**: Sends nested `alerts` structure, observer expects flat structure

**Current (WRONG)**:
```python
await self.event_publisher.publish(
    event_type="scheduled_inventory_check",
    data={
        "user_id": user.id,
        "alerts": result.get("alerts", [])  # ❌ Wrong structure!
    }
)
```

**Observer Expects** (`notification_observer.py:276`):
```python
{
    "user_id": 123,
    "expiring_items": [
        {"name": "Milk", "expiry_date": "2026-01-12"},
        {"name": "Chicken", "expiry_date": "2026-01-13"}
    ],
    "days_until_expiry": 3,
    "low_stock_items": [
        {"name": "Eggs", "quantity": 2},
        {"name": "Bread", "quantity": 1}
    ]
}
```

**Fix Required**: Need to understand what `tracking_agent.check_and_send_inventory_alert()` returns and map it correctly.

---

## Design Principle Violations

### 1. ❌ Interface Segregation Principle (ISP)

**Problem**: NotificationObserver event handlers expect specific data shapes, but there's no interface contract defining what data each event type requires.

**Impact**:
- Producers (orchestrators, workers) don't know what data format to send
- No compile-time or runtime validation of event data
- Silent failures when data doesn't match

**Solution**: Define event data classes/schemas:
```python
# backend/app/infrastructure/events/event_schemas.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MealLoggedEventData:
    user_id: int
    meal_log: dict
    daily_totals: dict
    inventory_changes: List[dict]
    inventory_status: dict

@dataclass
class DailySummaryEventData:
    user_id: int
    date: str
    meals_consumed: int
    compliance_rate: float
    calories_consumed: int
    protein_g: int
```

### 2. ❌ Single Responsibility Principle (SRP)

**Problem**: NotificationWorker is doing TWO things:
1. Fetching data (from ConsumptionService, TrackingAgent, database)
2. Publishing events

**Impact**:
- Hard to test event publishing separately from data fetching
- Mixing business logic (what data to fetch) with infrastructure (event publishing)

**Solution**: Create dedicated event trigger services:
```python
class DailySummaryTriggerService:
    def __init__(self, consumption_service, event_publisher):
        self.consumption_service = consumption_service
        self.event_publisher = event_publisher

    async def trigger_for_user(self, user_id: int):
        summary = self.consumption_service.get_today_summary(user_id)
        await self.event_publisher.publish(
            event_type="scheduled_daily_summary",
            data=DailySummaryEventData(
                user_id=user_id,
                date=summary.get("date"),
                meals_consumed=summary.get("meals_consumed", 0),
                ...
            ).to_dict()
        )
```

### 3. ✅ Dependency Inversion Principle (DIP) - FOLLOWED

**Good**: NotificationWorker depends on EventPublisher abstraction, not concrete implementations.

### 4. ✅ Open/Closed Principle (OCP) - FOLLOWED

**Good**:
- Adding new notification types doesn't require modifying BaseNotification
- Adding new channels doesn't require modifying NotificationConsumer

### 5. ❌ Liskov Substitution Principle (LSP)

**Problem**: All notification types implement BaseNotification, but they have different metadata requirements that aren't enforced.

**Impact**: Easy to create invalid notifications with missing data

**Solution**: Use type-specific metadata classes:
```python
@dataclass
class AchievementMetadata:
    achievement_type: str
    achievement_name: str
    description: str
    message: str

class AchievementNotification(BaseNotification):
    def __init__(self, user_id: int, metadata: AchievementMetadata):
        # Type checking enforces correct metadata
        ...
```

---

## Data Object Analysis

### 1. Event Data from Orchestrator (meal_logged)

**Data Shape**:
```python
{
    "user_id": 123,
    "meal_log": {
        "id": 456,
        "meal_type": "lunch",
        "planned_datetime": "2026-01-09T12:00:00",
        "consumed_datetime": "2026-01-09T12:15:00",
        "recipe_id": 789,
        ...
    },
    "daily_totals": {
        "compliance_rate": 85.0,
        "calories_consumed": 1800,
        "protein_g": 120,
        "carbs_g": 200,
        "fat_g": 60,
        ...
    },
    "inventory_changes": [
        {"item_id": 1, "quantity_change": -2, "item_name": "Chicken Breast"},
        ...
    ],
    "inventory_status": {
        "total_items": 45,
        "low_stock_count": 3,
        ...
    }
}
```

**Issues**:
- ✅ No overloading - all fields are relevant
- ❌ `inventory_changes` and `inventory_status` are NOT used by notification observer
- **Recommendation**: Remove unused fields or document why they're included (maybe for other observers?)

### 2. Notification Data to Redis Queue

**Data Shape**:
```python
{
    "user_id": 123,
    "type": "achievement",
    "priority": "high",
    "channels": ["push", "email"],
    "context": {
        "achievement_type": "streak_7day",
        "achievement_name": "7-Day Streak Master",
        "description": "Logged meals for 7 consecutive days",
        "message": "Congratulations!"
    },
    "metadata": {
        "retry_count": 0,
        "max_retries": 5,
        "source": "notification_system",
        "version": "1.0"
    },
    "created_at": "2026-01-09T10:30:01.234567"
}
```

**Issues**:
- ✅ All fields are used
- ✅ No overloading
- ✅ Clear separation between context (template data) and metadata (system data)

### 3. Rendered Notification from Template

**Data Shape**:
```python
{
    "title": "Achievement Unlocked!",
    "body": "Congratulations! You've unlocked 7-Day Streak Master",
    "data": {
        "achievement_type": "streak_7day",
        "achievement_name": "7-Day Streak Master",
        "action": "view_achievements"
    }
}
```

**Issues**:
- ✅ All fields are used
- ✅ No overloading
- ✅ Minimal data for efficiency

---

## Recommendations

### Priority 1: FIX DATA MISMATCHES (CRITICAL)

1. **Fix Daily Summary Event Data** - Lines 200-206 in `notification_worker.py`
2. **Fix Weekly Report Event Data** - Lines 238-245 in `notification_worker.py`
3. **Fix Meal Reminder Event Data** - Lines 159-168 in `notification_worker.py`
4. **Fix Inventory Check Event Data** - Lines 278-284 in `notification_worker.py`

### Priority 2: ADD EVENT DATA CONTRACTS

1. Create `backend/app/infrastructure/events/event_schemas.py`
2. Define dataclasses for each event type
3. Validate event data at EventPublisher.publish()
4. Update all producers to use schemas

### Priority 3: REFACTOR FOR SRP

1. Extract data fetching from NotificationWorker
2. Create dedicated trigger services
3. Worker only schedules and delegates

### Priority 4: ADD TYPE SAFETY

1. Add metadata type classes for each notification type
2. Update factory to enforce metadata types
3. Add runtime validation

---

## Test Plan

### Unit Tests Needed

1. **Test Event Data Validation**
   - Test that daily summary event data matches observer expectations
   - Test that weekly report event data matches observer expectations
   - Test that meal reminder event data matches observer expectations
   - Test that inventory check event data matches observer expectations

2. **Test Notification Creation**
   - Test that each notification type creates correct context
   - Test that priorities are calculated correctly
   - Test that channels are determined correctly

3. **Test Redis Queueing**
   - Test that notifications are queued to correct priority queue
   - Test that notification data serializes correctly

### Integration Tests Needed

1. **Test End-to-End Flow**
   - Trigger scheduled event → verify notification sent
   - Log meal → verify achievement notification sent
   - Skip meal → verify reminder notification sent

2. **Test Consumer Processing**
   - Queue notification → verify consumer dequeues and sends
   - Test retry logic with failed sends
   - Test dead letter queue with max retries

---

## Conclusion

**Flow Status**:
- ✅ User-Triggered Events: Working correctly
- ❌ Scheduled Events: Critical data mismatches

**Design Principles**:
- ✅ DIP: Followed
- ✅ OCP: Followed
- ❌ ISP: Violated (no interface contracts)
- ❌ SRP: Violated (worker does too much)
- ❌ LSP: Partially violated (no metadata type enforcement)

**Data Objects**:
- ✅ Redis queue data: Clean and minimal
- ⚠️ Event data: Some unused fields (inventory_changes, inventory_status)
- ❌ Scheduled event data: Wrong structure

**Next Steps**:
1. Fix all 4 data mismatches (Priority 1)
2. Add integration tests to catch these issues
3. Consider adding event data schemas for type safety
