# Notification System Architecture - Complete Analysis

**Date:** 2026-01-06
**Analysis of:** Current implementation vs Industry best practices

---

## QUESTION 1: What Code Runs in Worker vs Processor?

### **Current Docker Setup:**

```yaml
notification-worker:
  command: python -m app.workers.notification_worker producer
  # Runs: NotificationWorker.run()

notification-processor:
  command: python -m app.workers.notification_worker consumer
  # Runs: run_notification_queue_processor()
```

### **Both Use SAME File:** `app/workers/notification_worker.py`

```python
# notification_worker.py main() function routes based on argument:

if mode == "producer":
    worker = NotificationWorker()
    await worker.run()  # ← Triggers scheduled notifications

elif mode == "consumer":
    await run_notification_queue_processor()  # ← Processes Redis queue
```

### **Producer Container (notification-worker):**

**What it does:**
- Runs `NotificationWorker.run()` in infinite loop (30s cycle)
- **Triggers** scheduled notifications at specific times:
  - Meal reminders (every 5 minutes)
  - Daily summaries (9 PM)
  - Weekly reports (Sunday 8 PM)
  - Inventory alerts (8 AM)

**How it works:**
```python
# Producer side
db = session_factory()
notification_service = NotificationService(db)

# Calls queuing methods:
await notification_service.send_meal_reminder(...)  # → Redis queue
await notification_service.send_daily_summary(...)  # → Redis queue
```

**Redis interaction:** WRITES to Redis queues (lpush)

### **Consumer Container (notification-processor):**

**What it does:**
- Runs `run_notification_queue_processor()` in infinite loop
- **Processes** notifications from Redis queues
- Sends via actual providers (Push/Email/SMS)

**How it works:**
```python
# Consumer side
db = session_factory()
notification_service = NotificationService(db)

# Calls processing method:
await notification_service.process_notification_queue()
  → _process_priority_queue("high")
    → redis.brpop("notifications:high")  # ← Read from Redis
    → _send_notification(notification_data)
      → _send_via_provider(data, provider)
```

**Redis interaction:** READS from Redis queues (brpop)

---

## QUESTION 2: Is This the Right Way?

### **✅ GOOD Parts:**

1. **Separation of Concerns:**
   - Producer: Triggers/Queues
   - Consumer: Sends
   - ✅ This is CORRECT

2. **Same Codebase:**
   - Both use `notification_worker.py`
   - ✅ This is STANDARD (Celery, Sidekiq, Bull all do this)

3. **Redis Queue:**
   - ✅ Industry standard for background jobs

4. **Multiple Containers:**
   - Producer can scale independently from consumer
   - ✅ This allows horizontal scaling

### **❌ PROBLEMS:**

1. **NotificationService Does TOO MUCH:**
   ```python
   class NotificationService:
       # Queuing (Producer side)
       async def send_achievement(...):
           await self._queue_notification(...)

       # Processing (Consumer side)
       async def process_notification_queue():
           await self._process_priority_queue(...)

       # Sending (Consumer side)
       async def _send_notification(...):
           await self._send_via_provider(...)
   ```

   **Problem:** Single class handles BOTH producer AND consumer logic

   **Industry standard:** Separate classes
   - `NotificationProducer` (queuing only)
   - `NotificationConsumer` (processing only)

2. **No Template Pattern:**
   ```python
   # Current: Templates built inline
   notification_data = {
       "title": "Achievement Unlocked!",
       "body": message,  # ← Hardcoded template
   }
   ```

   **Industry standard:** Template factory
   ```python
   template = NotificationTemplateFactory.create(
       type="achievement",
       data={"achievement_type": "streak_7day"}
   )
   ```

3. **No Strategy Pattern for Channels:**
   ```python
   # Current: if/elif chain
   if provider == NotificationProvider.PUSH:
       return await _mock_send_provider(...)
   elif provider == NotificationProvider.EMAIL:
       return await _mock_send_provider(...)
   ```

   **Industry standard:** Strategy pattern
   ```python
   strategy = ChannelStrategyFactory.create(provider)
   return await strategy.send(notification_data)
   ```

4. **Template Generation is Primitive:**
   ```python
   def _generate_email_html(self, notification_data: Dict) -> str:
       title = notification_data["title"]
       body = notification_data["body"]

       html_content = f"""
       <!DOCTYPE html>
       <html>
       <head><title>{title}</title></head>
       <body>{body}</body>
       </html>
       """
   ```

   **Problems:**
   - No template files
   - No localization support
   - No personalization
   - Hardcoded HTML in Python

---

## QUESTION 3: Is NotificationService Using Same Code as Processor?

**YES, and that's the PROBLEM.**

### **Current Architecture:**

```
┌────────────────────────────────────────────────┐
│  NotificationService                           │
│  (Used by BOTH producer AND consumer)          │
├────────────────────────────────────────────────┤
│  Producer Methods:                             │
│  • send_achievement()                          │
│  • send_meal_reminder()                        │
│  • _queue_notification() → Redis               │
│                                                 │
│  Consumer Methods:                             │
│  • process_notification_queue()                │
│  • _process_priority_queue()                   │
│  • _send_notification()                        │
│  • _send_via_provider()                        │
└────────────────────────────────────────────────┘
```

**Problem:** Violates Single Responsibility Principle (SRP)

### **Industry Standard Architecture:**

```
┌────────────────────────────────────────────────┐
│  NotificationProducer                          │
│  (Used by API/Worker to QUEUE)                 │
├────────────────────────────────────────────────┤
│  • send_achievement()                          │
│  • send_meal_reminder()                        │
│  • _queue_notification() → Redis               │
└────────────────────────────────────────────────┘
                     ↓
              Redis Queue
                     ↓
┌────────────────────────────────────────────────┐
│  NotificationConsumer                          │
│  (Used by dedicated consumer process)          │
├────────────────────────────────────────────────┤
│  • process_queue()                             │
│  • _send_via_channel(channel_strategy)         │
└────────────────────────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────┐
│  Channel Strategies (Strategy Pattern)         │
├────────────────────────────────────────────────┤
│  • PushNotificationStrategy                    │
│  • EmailNotificationStrategy                   │
│  • SMSNotificationStrategy                     │
└────────────────────────────────────────────────┘
                     ↓
┌────────────────────────────────────────────────┐
│  Template Engine (Template Method Pattern)     │
├────────────────────────────────────────────────┤
│  • AchievementTemplate                         │
│  • MealReminderTemplate                        │
│  • DailySummaryTemplate                        │
└────────────────────────────────────────────────┘
```

---

## QUESTION 4: Missing Patterns

### **1. Template Factory Pattern - MISSING ❌**

**Current:**
```python
# Hardcoded in send_achievement()
notification_data = {
    "title": "Achievement Unlocked!",
    "body": message,
    "type": NotificationType.ACHIEVEMENT,
}
```

**Should be:**
```python
# Template factory creates templates
class NotificationTemplateFactory:
    @staticmethod
    def create(type: NotificationType, data: Dict) -> NotificationTemplate:
        templates = {
            NotificationType.ACHIEVEMENT: AchievementTemplate,
            NotificationType.MEAL_REMINDER: MealReminderTemplate,
            NotificationType.INVENTORY_ALERT: InventoryAlertTemplate,
        }
        return templates[type](data)

class AchievementTemplate(NotificationTemplate):
    def render_push(self) -> Dict:
        return {
            "title": "Achievement Unlocked!",
            "body": self.data["message"],
            "icon": "🏆"
        }

    def render_email(self) -> str:
        return render_template("achievement_email.html", **self.data)

    def render_sms(self) -> str:
        return f"Achievement: {self.data['message']}"
```

### **2. Strategy Pattern for Channels - MISSING ❌**

**Current:**
```python
# if/elif chain in _send_via_provider()
if provider == NotificationProvider.PUSH:
    return await _mock_send_provider(...)
elif provider == NotificationProvider.EMAIL:
    return await _mock_send_provider(...)
```

**Should be:**
```python
# Strategy pattern
class INotificationChannel(ABC):
    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        pass

class PushNotificationChannel(INotificationChannel):
    def __init__(self, fcm_client):
        self.fcm_client = fcm_client

    async def send(self, notification: Notification) -> bool:
        user = await self.get_user(notification.user_id)
        message = notification.template.render_push()
        return await self.fcm_client.send(user.fcm_token, message)

class EmailNotificationChannel(INotificationChannel):
    def __init__(self, email_client):
        self.email_client = email_client

    async def send(self, notification: Notification) -> bool:
        user = await self.get_user(notification.user_id)
        html = notification.template.render_email()
        return await self.email_client.send(user.email, html)

# Factory creates channels
class ChannelFactory:
    @staticmethod
    def create(provider: NotificationProvider) -> INotificationChannel:
        channels = {
            NotificationProvider.PUSH: PushNotificationChannel(fcm_client),
            NotificationProvider.EMAIL: EmailNotificationChannel(email_client),
            NotificationProvider.SMS: SMSNotificationChannel(twilio_client),
        }
        return channels[provider]
```

### **3. Template Files - MISSING ❌**

**Current:** HTML hardcoded in Python

**Should be:**
```
backend/
  templates/
    notifications/
      achievement_email.html
      achievement_push.json
      meal_reminder_email.html
      daily_summary_email.html
```

**With Jinja2:**
```html
<!-- achievement_email.html -->
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
</head>
<body>
    <h1>🏆 Achievement Unlocked!</h1>
    <p>{{ message }}</p>
    <p>Type: {{ achievement_type }}</p>
</body>
</html>
```

---

## RECOMMENDATION: Refactoring Sequence

### **Phase 1: Separate Producer/Consumer (Highest Priority)**

1. Create `NotificationProducer` class (queuing only)
2. Create `NotificationConsumer` class (processing only)
3. Update worker to use correct class based on mode

### **Phase 2: Add Strategy Pattern for Channels**

1. Create `INotificationChannel` interface
2. Implement concrete channels (Push, Email, SMS)
3. Create `ChannelFactory`
4. Update consumer to use strategies

### **Phase 3: Add Template Pattern**

1. Create `NotificationTemplate` base class
2. Implement concrete templates (Achievement, MealReminder, etc.)
3. Create `TemplateFactory`
4. Move to template files with Jinja2

### **Phase 4: Fix Redis Singleton**

1. Use `get_redis_client()` everywhere
2. Remove DB from NotificationProducer constructor

---

## Summary

**Your Questions Answered:**

1. **What's running in worker vs processor?**
   - Both use same file, routed by command-line arg
   - Worker = Producer (triggers)
   - Processor = Consumer (sends)

2. **Is this the right way?**
   - ✅ Separation is good
   - ❌ Single class doing both is wrong
   - ❌ Missing design patterns

3. **Is NotificationService used by both?**
   - YES, and that's the problem
   - Should be two classes: Producer + Consumer

4. **What about templates and strategies?**
   - ❌ No template pattern
   - ❌ No strategy pattern
   - ❌ No factory patterns
   - ❌ Templates hardcoded in Python

**Industry Standard:** Celery, Sidekiq, Bull all separate:
- Task definition (Producer)
- Worker/Consumer (Consumer)
- With proper abstractions and patterns
