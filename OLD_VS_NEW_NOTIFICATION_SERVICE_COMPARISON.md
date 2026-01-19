# OLD vs NEW Notification Service - Complete Comparison

## CRITICAL FINDING: Why Old Service Is Still Being Used

### Location of Old Service Usage:
1. **`backend/app/agents/tracking_agent.py:1345, 1370`** - Calls `notification_service.send_inventory_alert()`
2. **`backend/app/orchestrators/meal_logging_orchestrator.py`** - Unknown usage (needs verification)
3. **`backend/app/services/meal_tracking_service.py`** - Unknown usage (needs verification)
4. **`backend/app/services/notification_scheduler.py`** - Unknown usage (needs verification)
5. **`backend/app/api/notifications.py`** - Unknown usage (needs verification)

### Why Still Using Old Service?
**TrackingAgent was created BEFORE the new clean architecture was implemented.**

The `check_and_send_inventory_alert()` method was written when the old NotificationService was the only notification system. It directly instantiates and calls NotificationService instead of using EventPublisher.

---

## What OLD NotificationService Does

### File: `backend/app/services/notification_service.py`

#### Key Capabilities:

1. **User Preference Checking** (Lines 359-369)
   ```python
   preferences = self._get_user_preferences(notification_data["user_id"])

   if not self._should_send_notification(preferences, notification_type):
       # Don't send if user disabled this type
       return True
   ```
   **Checks if user has enabled/disabled specific notification types.**

2. **Quiet Hours / Do Not Disturb** (Lines 374-377)
   ```python
   if not self._is_allowed_time(preferences, notification_data["priority"]):
       # User is in quiet hours - schedule for later
       return await self._schedule_notification(notification_data, preferences)
   ```
   **Respects user's quiet hours and schedules notifications for later.**

3. **Scheduled Notification Support** (Lines 406-426)
   ```python
   async def _schedule_notification(self, notification_data: Dict, preferences: Dict) -> bool:
       # Calculate next allowed time
       next_allowed_time = self._calculate_next_allowed_time(preferences)

       # Use Redis sorted set for scheduled notifications
       score = next_allowed_time.timestamp()
       self.redis_client.zadd("notifications:scheduled", {json.dumps(scheduled_data): score})
   ```
   **Can delay notifications to a future time (e.g., after quiet hours end).**

4. **Retry Tracking** (Lines 385-388)
   ```python
   notification_data["retry_count"] = 0
   notification_data["max_retries"] = self.max_retries
   notification_data["queued_at"] = datetime.utcnow().isoformat()
   ```
   **Adds retry metadata for failed delivery attempts.**

5. **Hardcoded Title/Body Generation** (Lines 191-202)
   ```python
   if alert_type == "low_stock":
       title = "Low Stock Alert"
       body = f"Running low on: {', '.join(items[:3])}"
   elif alert_type == "expiring":
       title = "Expiry Alert"
       body = f"Items expiring soon: {', '.join(items[:3])}"
   ```
   **Creates notification text directly (NOT using templates).**

6. **Direct Redis Queuing** (Lines 381-400)
   ```python
   queue_name = f"notifications:{notification_data['priority']}"
   result = self.redis_client.lpush(queue_name, json.dumps(notification_data))
   ```
   **Queues directly to priority-based Redis queues.**

7. **Notification Structure Created** (Lines 204-217)
   ```python
   notification_data = {
       "type": NotificationType.INVENTORY_ALERT,
       "user_id": user_id,
       "priority": priority,
       "data": {
           "alert_type": alert_type,
           "items": items,
           "item_count": len(items)
       },
       "title": title,
       "body": body,
       "action_url": "/inventory",
       "created_at": datetime.utcnow().isoformat()
   }
   ```

---

## What NEW Notification Architecture Does

### BaseNotification + Factory + Observer + Consumer

#### Key Capabilities:

1. **Template-Based Rendering** ✅
   - **OLD:** Hardcodes title/body in Python
   - **NEW:** Uses Jinja2 templates per channel (push/email/sms/whatsapp)
   - **Location:** Consumer renders templates consumer-side

2. **Channel Selection** ✅
   - **OLD:** Sends to single channel based on provider enum
   - **NEW:** Notification defines available channels, consumer picks based on user preference
   - **Location:** `BaseNotification.determine_channels()`, `Consumer._select_preferred_channel()`

3. **Priority Calculation** ✅
   - **OLD:** Priority passed manually by caller
   - **NEW:** Each notification type calculates its own priority dynamically
   - **Location:** `BaseNotification.calculate_priority()`

4. **Context Building** ✅
   - **OLD:** Data dict with fixed structure
   - **NEW:** Each notification type builds its own context for templates
   - **Location:** `BaseNotification.build_notification_context()`

5. **Redis Queuing** ✅
   - **OLD:** `notifications:{priority}` queues
   - **NEW:** `notifications:queue:{priority}` queues
   - **Location:** `NotificationObserver._queue_to_redis()`

6. **Retry Metadata** ✅
   - **OLD:** Added in `_queue_notification()`
   - **NEW:** Added in `BaseNotification._add_common_metadata()`
   - **Location:** Lines 241-253

7. **User Preferences** ❌ **MISSING**
   - **OLD:** Checks `NotificationPreference` table before sending
   - **NEW:** Has TODO comment (line 348): "In future, this should come from user.notification_preferences"
   - **Location:** `Consumer._select_preferred_channel()` (NOT IMPLEMENTED)

8. **Quiet Hours / DND** ❌ **MISSING**
   - **OLD:** Respects quiet hours, schedules for later
   - **NEW:** NOT IMPLEMENTED

9. **Scheduled Notifications** ❌ **MISSING**
   - **OLD:** Uses Redis sorted set to schedule for future
   - **NEW:** NOT IMPLEMENTED

---

## MISSING CAPABILITIES IN NEW ARCHITECTURE

### 1. User Notification Preferences ❌ CRITICAL

**What's Missing:**
- No check if user has disabled notification types
- No check for preferred channel (push vs email vs SMS)

**Where It Should Be:**
Consumer should check `NotificationPreference` table BEFORE rendering/sending.

**Old Service Code** (lines 359-369):
```python
preferences = self._get_user_preferences(notification_data["user_id"])

if not self._should_send_notification(preferences, notification_type):
    logger.info(f"Notification {notification_type} disabled for user {notification_data['user_id']}")
    return True  # Don't send
```

**New Service Code** (line 347-348):
```python
# Get user's notification preferences
# For now, use a simple priority: push > email > sms > whatsapp
# In future, this should come from user.notification_preferences
```

**Fix Required:** Add user preference lookup in Consumer.

---

### 2. Quiet Hours / Do Not Disturb ❌ CRITICAL

**What's Missing:**
- No respect for user's quiet hours
- No automatic rescheduling

**Where It Should Be:**
Consumer OR Observer should check quiet hours BEFORE queuing.

**Old Service Code** (lines 374-377):
```python
if not self._is_allowed_time(preferences, notification_data["priority"]):
    print("[QUEUE NOTIFICATION] ⏰ In quiet hours - scheduling for later")
    return await self._schedule_notification(notification_data, preferences)
```

**New Service:** NOT IMPLEMENTED

**Fix Required:** Add quiet hours check in Observer or Consumer.

---

### 3. Delayed/Scheduled Notifications ❌ MEDIUM

**What's Missing:**
- Can't schedule notifications for specific times
- Can't delay to after quiet hours

**Where It Should Be:**
Separate scheduler component OR Redis sorted set pattern.

**Old Service Code** (lines 406-426):
```python
async def _schedule_notification(self, notification_data: Dict, preferences: Dict) -> bool:
    next_allowed_time = self._calculate_next_allowed_time(preferences)

    # Use Redis sorted set
    score = next_allowed_time.timestamp()
    self.redis_client.zadd("notifications:scheduled", {json.dumps(scheduled_data): score})
```

**New Service:** NOT IMPLEMENTED

**Fix Required:** Add Redis sorted set for delayed delivery OR APScheduler job.

---

## IMPROVED CAPABILITIES IN NEW ARCHITECTURE

### 1. Template-Based Rendering ✅ BETTER
**OLD:** Hardcoded strings in Python
**NEW:** Jinja2 templates per channel

### 2. Factory Pattern ✅ BETTER
**OLD:** Single service with type enums
**NEW:** Separate class per notification type

### 3. Observer Pattern ✅ BETTER
**OLD:** Direct service calls
**NEW:** Event-driven architecture via EventPublisher

### 4. Dynamic Priority ✅ BETTER
**OLD:** Caller passes priority manually
**NEW:** Each notification calculates priority based on context

### 5. Channel Selection ✅ BETTER
**OLD:** Single provider enum
**NEW:** Multiple available channels, user preference picks one

### 6. Clean Architecture ✅ BETTER
**OLD:** Mixed concerns (business logic + notifications)
**NEW:** Separated domain and infrastructure layers

---

## WHY TrackingAgent STILL USES OLD SERVICE

### Root Cause:
`TrackingAgent.check_and_send_inventory_alert()` was written BEFORE the new architecture existed.

### Evidence:
```python
# backend/app/agents/tracking_agent.py:1345
await self.notification_service.send_inventory_alert(
    user_id=self.user_id,
    alert_type="expiring",
    items=item_names,
    priority=NotificationPriority.HIGH
)
```

### Why Not Flagged?
1. **Method Name:** `check_and_send_inventory_alert()` implies it sends notifications (domain + infrastructure mixed)
2. **Old Pattern:** Directly instantiates NotificationService instead of using EventPublisher
3. **Before Migration:** Created before EventPublisher/Observer pattern was implemented

### Where Else Old Service Used?
Need to check these files:
```
backend/app/dependencies.py
backend/app/orchestrators/meal_logging_orchestrator.py
backend/app/services/meal_tracking_service.py
backend/app/api/notifications.py
backend/app/services/notification_scheduler.py
```

---

## ACTION ITEMS TO COMPLETE MIGRATION

### Priority 1: Add Missing Capabilities to NEW Architecture

1. **Implement User Preferences in Consumer** ✅ CRITICAL
   - Add `_get_user_preferences()` method
   - Check if notification type is enabled
   - Check if channel is allowed

2. **Implement Quiet Hours / DND** ✅ CRITICAL
   - Add quiet hours check in Observer before queuing
   - Add `_schedule_for_later()` if in quiet hours

3. **Implement Delayed Notifications** ⚠️ MEDIUM
   - Add Redis sorted set for scheduled notifications
   - Add background worker to check scheduled set

### Priority 2: Remove All OLD NotificationService Usage

1. **TrackingAgent**
   - Create new `get_inventory_alert_data()` method
   - Remove `notification_service` dependency
   - Update `check_and_send_inventory_alert()` to use EventPublisher OR deprecate

2. **Verify Other Files**
   ```bash
   grep -r "NotificationService\(" backend/app/ --include="*.py"
   grep -r "notification_service\." backend/app/ --include="*.py"
   ```

3. **Update NotificationWorker**
   - Remove old service calls
   - Use EventPublisher for ALL notifications

### Priority 3: Database Preferences

Verify `NotificationPreference` table structure:
```sql
-- What fields exist?
-- notification_type enabled/disabled?
-- quiet_hours_start / quiet_hours_end?
-- preferred_channel?
```

---

## COMPARISON SUMMARY TABLE

| Capability | OLD Service | NEW Architecture | Status |
|------------|-------------|------------------|--------|
| Template Rendering | ❌ Hardcoded | ✅ Jinja2 | BETTER |
| Factory Pattern | ❌ Single Service | ✅ Per-Type Classes | BETTER |
| Observer Pattern | ❌ Direct Calls | ✅ Event-Driven | BETTER |
| Dynamic Priority | ❌ Manual | ✅ Calculated | BETTER |
| Channel Selection | ⚠️ Single Provider | ✅ Multi-Channel | BETTER |
| Clean Architecture | ❌ Mixed Concerns | ✅ Layered | BETTER |
| **User Preferences** | ✅ Implemented | ❌ Missing | **REGRESSION** |
| **Quiet Hours** | ✅ Implemented | ❌ Missing | **REGRESSION** |
| **Scheduled Delivery** | ✅ Implemented | ❌ Missing | **REGRESSION** |
| Retry Metadata | ✅ Implemented | ✅ Implemented | SAME |
| Redis Queuing | ✅ Implemented | ✅ Implemented | SAME |

---

## CONCLUSION

### Why Old Service Still Used:
**TrackingAgent was written before new architecture and never migrated.**

### Critical Gaps in New Architecture:
1. ❌ User preferences not checked
2. ❌ Quiet hours not respected
3. ❌ Delayed notifications not supported

### Next Steps:
1. **Add missing features to NEW architecture** (user prefs, quiet hours)
2. **Migrate TrackingAgent** to use EventPublisher
3. **Verify and migrate all other OLD service usages**
4. **Deprecate and remove OLD NotificationService**

**Without these fixes, the new architecture is INCOMPLETE and may spam users or send at inappropriate times.**
