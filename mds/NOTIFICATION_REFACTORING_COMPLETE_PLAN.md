# Notification System Refactoring - Complete Plan

**Date:** 2026-01-06
**Objective:** Refactor notification system following clean architecture with proper separation of Producer/Consumer, Template Pattern, Strategy Pattern, and Factory Pattern

---

## CURRENT STATE ANALYSIS (Facts from Codebase)

### What We Have Now:

**NotificationService** (`backend/app/services/notification_service.py`)
- **Lines 68-993:** Single class doing BOTH producer AND consumer work
- **Lines 71-88:** Constructor creates Redis client directly (should use singleton)
- **Lines 152-344:** Producer methods (send_meal_reminder, send_achievement, etc.)
- **Lines 348-404:** `_queue_notification()` - queues to Redis
- **Lines 432-455:** `process_notification_queue()` - consumer loop
- **Lines 457-483:** `_process_priority_queue()` - reads from Redis
- **Lines 514-545:** `_send_notification()` - actual sending
- **Lines 547-693:** `_send_via_provider()` - if/elif chain (NO Strategy Pattern)
- **Lines 824-855:** `_generate_email_html()` - hardcoded HTML in Python (NO Template Pattern)

**Problems:**
1. ❌ Violates SRP - one class does queuing AND sending
2. ❌ No Template Pattern - templates hardcoded in Python strings
3. ❌ No Strategy Pattern - if/elif chain for channels
4. ❌ No Factory Pattern - no factories for templates or strategies
5. ❌ Creates own Redis client instead of using singleton

**NotificationWorker** (`backend/app/workers/notification_worker.py`)
- **Lines 22-70:** `NotificationWorker.run()` - periodic event publisher
- **Lines 72-109:** Checks time conditions (9PM, Sunday 8PM, 8AM, every 5 min)
- **Lines 130-179:** Triggers meal reminders by calling `notification_service.send_meal_reminder()`
- **Lines 257-271:** `run_notification_queue_processor()` - consumer process

**Key Insight:** Worker IS a periodic event publisher (like our EventPublisher but time-based)

**Docker Setup** (`docker-compose.yml`)
- **Lines 96-111:** `notification-worker` container runs producer mode
- **Lines 114-130:** `notification-processor` container runs consumer mode
- Same file, different command-line args

---

## INDUSTRY BEST PRACTICES (Research Findings)

### 1. Producer-Consumer Separation

**Producer Responsibilities:**
- Determine IF notification should be sent
- Build notification content using templates
- Queue message to Redis
- NEVER knows about actual delivery

**Consumer Responsibilities:**
- Poll/listen for queued messages
- Select delivery channel using strategy
- Send via appropriate provider
- Handle retries and failures
- Log delivery status

**Key Pattern:** Both communicate via Message Queue (Redis in our case)

### 2. Template Pattern for Notification Generation

**Purpose:** Define algorithm structure, subclasses implement specific steps

```
NotificationGenerator (abstract)
├── generate() - template method
│   ├── 1. validate_prerequisites()
│   ├── 2. fetch_context_data()
│   ├── 3. render_template()
│   ├── 4. enrich_notification()
│   ├── 5. validate_content()
│   └── 6. apply_user_preferences()

EmailNotificationGenerator extends NotificationGenerator
├── validate_prerequisites() - check recipient email
├── enrich_notification() - add unsubscribe link
└── validate_content() - check email length

SMSNotificationGenerator extends NotificationGenerator
├── validate_prerequisites() - check phone/opt-in
├── enrich_notification() - truncate to 160 chars
└── validate_content() - ensure SMS format

PushNotificationGenerator extends NotificationGenerator
├── validate_prerequisites() - check device tokens
├── enrich_notification() - add action buttons
└── validate_content() - check title/body length
```

### 3. Strategy Pattern for Channel Selection

**Purpose:** Encapsulate delivery algorithms, make them interchangeable

```
INotificationChannel (interface)
├── send(notification: Notification) -> bool
├── validate(user: User) -> bool

EmailChannel implements INotificationChannel
├── send() - SendGrid/SES integration
├── validate() - check email verified

SMSChannel implements INotificationChannel
├── send() - Twilio integration
├── validate() - check phone verified, opt-in

PushChannel implements INotificationChannel
├── send() - FCM integration
├── validate() - check device tokens

ChannelStrategyFactory
├── create_strategies(user, notification_type) -> List[INotificationChannel]
├── Returns ordered list: [primary, fallback1, fallback2]
```

### 4. Factory Pattern for Templates

**Purpose:** Create appropriate template instances without exposing creation logic

```
TemplateFactory
├── create_template(type: NotificationType, channel: ChannelType) -> Template
├── Returns: Rendered template object

Template Types:
- AchievementTemplate
- MealReminderTemplate
- DailySummaryTemplate
- InventoryAlertTemplate

Channel Variants:
- Each template can render for: Email, SMS, Push
```

### 5. Periodic Event Publisher Pattern

**Current Understanding:**
- NotificationWorker IS a periodic event publisher
- Similar to EventPublisher but triggered by TIME instead of USER ACTIONS
- Should follow same clean architecture principles

**Architecture:**
```
PeriodicEventPublisher (NotificationWorker)
├── Triggered by: Time schedules (cron-like)
├── Checks: What needs to happen now?
├── Publishes: Events to NotificationProducer
└── Uses: Same NotificationProducer as real-time events

Real-Time EventPublisher
├── Triggered by: User actions (meal logged)
├── Publishes: Events to observers
└── NotificationObserver uses NotificationProducer

Both feed into:
NotificationProducer → Redis Queue → NotificationConsumer
```

---

## PROPOSED ARCHITECTURE

### Component Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                     EVENT PUBLISHERS                             │
├─────────────────────────────────────────────────────────────────┤
│  1. EventPublisher (Real-time)                                  │
│     - Triggered by: User actions                                │
│     - Observers: WebSocketObserver, NotificationObserver        │
│                                                                  │
│  2. PeriodicEventPublisher (Scheduled)                          │
│     - Triggered by: Time schedules                              │
│     - Calls: NotificationProducer directly                      │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│              NOTIFICATION PRODUCER (Generation)                  │
├─────────────────────────────────────────────────────────────────┤
│  NotificationProducer                                            │
│  ├── Responsibilities:                                          │
│  │   - Check if notification should be sent                     │
│  │   - Use TemplateFactory to get template                      │
│  │   - Use NotificationGenerator to build content               │
│  │   - Queue to Redis                                           │
│  │                                                              │
│  ├── Uses:                                                      │
│  │   - TemplateFactory (creates templates)                      │
│  │   - NotificationGenerator (Template Pattern)                 │
│  │   - Redis (queue storage)                                    │
│  │                                                              │
│  └── Methods:                                                   │
│      - send_achievement(user_id, type, message)                 │
│      - send_meal_reminder(user_id, meal_type, ...)              │
│      - send_daily_summary(user_id, summary_data)                │
│      - _queue_notification(notification_data) → Redis           │
└─────────────────────────────────────────────────────────────────┘
                           ↓
                    Redis Queues
          (notifications:high, notifications:normal, etc.)
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│             NOTIFICATION CONSUMER (Delivery)                     │
├─────────────────────────────────────────────────────────────────┤
│  NotificationConsumer                                            │
│  ├── Responsibilities:                                          │
│  │   - Poll Redis queues                                        │
│  │   - Use ChannelStrategyFactory to get strategies             │
│  │   - Try each strategy until success                          │
│  │   - Handle retries and failures                              │
│  │   - Log delivery results                                     │
│  │                                                              │
│  ├── Uses:                                                      │
│  │   - ChannelStrategyFactory (creates strategies)              │
│  │   - INotificationChannel implementations                     │
│  │   - Redis (queue reading)                                    │
│  │   - DeliveryLog (audit trail)                                │
│  │                                                              │
│  └── Methods:                                                   │
│      - process_notification_queue() - infinite loop              │
│      - _process_priority_queue(priority) - batch processing     │
│      - _send_notification(data) - deliver via strategies        │
│      - _handle_failed_notification(data) - retry logic          │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                  CHANNEL STRATEGIES                              │
├─────────────────────────────────────────────────────────────────┤
│  INotificationChannel (interface)                                │
│  ├── send(notification_data: Dict) -> bool                      │
│  └── validate(user: User) -> bool                               │
│                                                                  │
│  Implementations:                                                │
│  ├── PushNotificationChannel (FCM)                              │
│  ├── EmailNotificationChannel (SendGrid)                        │
│  ├── SMSNotificationChannel (Twilio)                            │
│  └── WhatsAppNotificationChannel (Twilio)                       │
│                                                                  │
│  ChannelStrategyFactory                                          │
│  └── create_strategies(user, type) -> List[INotificationChannel]│
└─────────────────────────────────────────────────────────────────┘
```

### File Structure

```
backend/app/
├── domain/
│   └── notifications/
│       ├── __init__.py
│       ├── notification.py              # Domain models
│       └── template.py                  # Template domain model
│
├── infrastructure/
│   ├── events/
│   │   ├── event_publisher.py           # ✅ EXISTS - Real-time
│   │   └── periodic_event_publisher.py  # NEW - Scheduled (refactored worker)
│   │
│   ├── observers/
│   │   ├── websocket_observer.py        # ✅ EXISTS
│   │   └── notification_observer.py     # ✅ EXISTS
│   │
│   ├── notifications/
│   │   ├── producers/
│   │   │   ├── __init__.py
│   │   │   ├── notification_producer.py # NEW - Producer only
│   │   │   └── generators/
│   │   │       ├── __init__.py
│   │   │       ├── base_generator.py    # Template Pattern base
│   │   │       ├── email_generator.py   # Email-specific
│   │   │       ├── sms_generator.py     # SMS-specific
│   │   │       └── push_generator.py    # Push-specific
│   │   │
│   │   ├── consumers/
│   │   │   ├── __init__.py
│   │   │   └── notification_consumer.py # NEW - Consumer only
│   │   │
│   │   ├── channels/
│   │   │   ├── __init__.py
│   │   │   ├── base_channel.py          # INotificationChannel interface
│   │   │   ├── email_channel.py         # Strategy implementation
│   │   │   ├── sms_channel.py           # Strategy implementation
│   │   │   ├── push_channel.py          # Strategy implementation
│   │   │   └── whatsapp_channel.py      # Strategy implementation
│   │   │
│   │   ├── factories/
│   │   │   ├── __init__.py
│   │   │   ├── template_factory.py      # Template Factory
│   │   │   └── channel_factory.py       # Channel Strategy Factory
│   │   │
│   │   └── templates/
│   │       ├── __init__.py
│   │       └── template_renderer.py     # Template rendering logic
│   │
│   └── redis/
│       └── queue_manager.py             # Redis queue abstraction
│
├── services/
│   └── notification_service.py          # REFACTOR - Split into Producer/Consumer
│
├── workers/
│   └── notification_worker.py           # REFACTOR - Rename to periodic_event_publisher.py
│
└── templates/                           # NEW - Actual template files
    └── notifications/
        ├── achievement_email.html
        ├── achievement_push.json
        ├── meal_reminder_email.html
        ├── meal_reminder_sms.txt
        ├── daily_summary_email.html
        └── inventory_alert_push.json
```

---

## IMPLEMENTATION SEQUENCE

### Phase 1: Create Infrastructure (Interfaces & Base Classes)

**Step 1.1: Domain Models**
- Create `domain/notifications/notification.py`
  - NotificationMessage (data class)
  - NotificationType (enum)
  - NotificationPriority (enum)

**Step 1.2: Channel Interface (Strategy Pattern)**
- Create `infrastructure/notifications/channels/base_channel.py`
  - INotificationChannel (ABC)
  - DeliveryResult (data class)

**Step 1.3: Generator Base (Template Pattern)**
- Create `infrastructure/notifications/producers/generators/base_generator.py`
  - NotificationGenerator (ABC with template method)

**Step 1.4: Template Domain Model**
- Create `domain/notifications/template.py`
  - NotificationTemplate (domain model)
  - TemplateVariable (value object)

### Phase 2: Template Management

**Step 2.1: Template Files**
- Create `templates/notifications/` directory
- Add Jinja2 templates for each notification type × channel

**Step 2.2: Template Renderer**
- Create `infrastructure/notifications/templates/template_renderer.py`
  - Jinja2 integration
  - Template loading from files
  - Variable validation

**Step 2.3: Template Factory**
- Create `infrastructure/notifications/factories/template_factory.py`
  - TemplateFactory (loads and creates templates)

### Phase 3: Notification Producer

**Step 3.1: Generators (Template Pattern Implementation)**
- Create `infrastructure/notifications/producers/generators/email_generator.py`
- Create `infrastructure/notifications/producers/generators/sms_generator.py`
- Create `infrastructure/notifications/producers/generators/push_generator.py`

**Step 3.2: Notification Producer**
- Create `infrastructure/notifications/producers/notification_producer.py`
  - Queuing logic only
  - Uses generators to build content
  - Writes to Redis
  - NO sending logic

**Step 3.3: Update NotificationObserver**
- Update `infrastructure/observers/notification_observer.py`
  - Use NotificationProducer instead of NotificationService

### Phase 4: Notification Consumer

**Step 4.1: Channel Strategies (Strategy Pattern Implementation)**
- Create `infrastructure/notifications/channels/email_channel.py`
- Create `infrastructure/notifications/channels/sms_channel.py`
- Create `infrastructure/notifications/channels/push_channel.py`
- Create `infrastructure/notifications/channels/whatsapp_channel.py`

**Step 4.2: Channel Factory**
- Create `infrastructure/notifications/factories/channel_factory.py`
  - ChannelStrategyFactory (creates ordered strategy list)

**Step 4.3: Notification Consumer**
- Create `infrastructure/notifications/consumers/notification_consumer.py`
  - Queue polling logic
  - Uses channel strategies for delivery
  - Retry logic with exponential backoff
  - Dead letter queue handling

### Phase 5: Periodic Event Publisher

**Step 5.1: Refactor Worker**
- Rename `workers/notification_worker.py` to `infrastructure/events/periodic_event_publisher.py`
- Update to use NotificationProducer
- Keep time-based triggering logic
- Remove consumer code (that's in NotificationConsumer now)

**Step 5.2: Update Docker**
- Update docker-compose.yml
  - Producer container uses PeriodicEventPublisher
  - Consumer container uses NotificationConsumer

### Phase 6: Dependency Injection

**Step 6.1: Update dependencies.py**
- Add NotificationProducer factory
- Add NotificationConsumer factory
- Add TemplateFactory singleton
- Add ChannelStrategyFactory singleton
- Update existing dependencies

**Step 6.2: Update main.py**
- Initialize factories at startup
- Update lifespan events

### Phase 7: Migration & Cleanup

**Step 7.1: Migrate Existing Usage**
- Find all calls to old NotificationService
- Update to use NotificationProducer
- Verify no direct sending (everything queued)

**Step 7.2: Remove Old Code**
- Delete old `services/notification_service.py` (after migration)
- Clean up unused imports

**Step 7.3: Testing**
- Test real-time notifications (meal logged → achievement)
- Test periodic notifications (daily summary, meal reminders)
- Test all channels (Email, SMS, Push)
- Test retry logic
- Test template rendering

---

## KEY DESIGN DECISIONS

### 1. Why Separate Producer and Consumer?

**Current Problem:**
```python
# Same class does both!
class NotificationService:
    async def send_achievement(self, ...):  # Producer
        await self._queue_notification(...)

    async def process_notification_queue(self):  # Consumer
        await self._send_notification(...)
```

**Solution:**
```python
# Producer (used by observers, periodic publisher)
class NotificationProducer:
    async def send_achievement(self, ...):
        notification = self.generator.generate(...)
        await self.queue.enqueue(notification)

# Consumer (separate process)
class NotificationConsumer:
    async def process_queue(self):
        messages = await self.queue.dequeue_batch()
        for msg in messages:
            await self._deliver(msg)
```

**Benefits:**
- Single Responsibility Principle
- Can scale independently (more consumers if needed)
- Producer never blocked by slow delivery
- Clear separation of concerns

### 2. Why Template Pattern for Generators?

**Current Problem:**
```python
# Hardcoded in send_achievement()
notification_data = {
    "title": "Achievement Unlocked!",
    "body": message,
}
```

**Solution:**
```python
class NotificationGenerator(ABC):
    def generate(self, ...):  # Template method
        self.validate_prerequisites()
        context = self.fetch_context_data()
        template = self.template_factory.create(...)
        content = template.render(context)
        enriched = self.enrich_notification(content)
        return enriched

class EmailGenerator(NotificationGenerator):
    def enrich_notification(self, content):
        return {
            **content,
            "unsubscribe_url": self._generate_unsubscribe_link()
        }
```

**Benefits:**
- Algorithm structure defined once
- Subclasses customize specific steps
- Easy to add new channels
- DRY principle

### 3. Why Strategy Pattern for Channels?

**Current Problem:**
```python
# if/elif chain
if provider == NotificationProvider.PUSH:
    return await _mock_send_provider(...)
elif provider == NotificationProvider.EMAIL:
    return await _mock_send_provider(...)
```

**Solution:**
```python
# Each channel is a strategy
class EmailChannel(INotificationChannel):
    async def send(self, notification):
        return await self.email_service.send(...)

class SMSChannel(INotificationChannel):
    async def send(self, notification):
        return await self.sms_service.send(...)

# Factory creates ordered list
strategies = channel_factory.create_strategies(user, type)
for strategy in strategies:
    result = await strategy.send(notification)
    if result.success:
        break
```

**Benefits:**
- Open/Closed Principle (add new channels without modifying existing)
- Easy to test (mock individual strategies)
- Fallback logic clean (try strategies in order)
- Each channel encapsulates its logic

### 4. Why Template Files Instead of Python Strings?

**Current Problem:**
```python
html_content = f"""
<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>{body}</body>
</html>
"""
```

**Solution:**
```jinja2
{# templates/notifications/achievement_email.html #}
<!DOCTYPE html>
<html>
<head><title>{{ title }}</title></head>
<body>
    <h1>{{ achievement_icon }} Achievement Unlocked!</h1>
    <p>{{ message }}</p>
</body>
</html>
```

**Benefits:**
- Separation of concerns (design vs logic)
- Easy for non-programmers to edit
- Template syntax validation
- Reusable across notification types
- Versioning and rollback support

### 5. Why Periodic Event Publisher Same as EventPublisher?

**Conceptual Alignment:**
- EventPublisher: Reacts to USER ACTIONS → publishes events
- PeriodicEventPublisher: Reacts to TIME → publishes events
- Both publish to same NotificationProducer

**Architecture:**
```
User Action → EventPublisher → NotificationObserver → NotificationProducer → Queue
Time Schedule → PeriodicEventPublisher → NotificationProducer → Queue
                                                              ↓
                                                    NotificationConsumer
```

**Benefits:**
- Consistent architecture
- Same clean principles
- Both trigger notifications without knowing delivery details
- Easy to understand flow

---

## REDIS SINGLETON FIX

**Current Problem:**
```python
# notification_service.py line 73-78
self.redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    decode_responses=True
)
```

**Solution:**
```python
from app.core.redis_client import get_redis_client

class NotificationProducer:
    def __init__(self):
        self.redis = get_redis_client()  # Use singleton
```

**Benefits:**
- Connection pooling
- Consistent with rest of codebase
- Single source of truth

---

## VERIFICATION CHECKLIST

After implementation, verify:

- [ ] NotificationProducer ONLY queues, never sends
- [ ] NotificationConsumer ONLY sends, never decides eligibility
- [ ] All templates in files, not Python strings
- [ ] Template Factory creates all template instances
- [ ] Channel Strategy Factory creates all channel instances
- [ ] Each channel is a separate strategy class
- [ ] Each generator extends NotificationGenerator base
- [ ] Redis singleton used everywhere
- [ ] PeriodicEventPublisher follows same pattern as EventPublisher
- [ ] Docker containers updated (producer/consumer separation)
- [ ] All existing notifications still work
- [ ] No direct sending in API endpoints (everything queued)

---

## NEXT STEPS

1. **Review this plan** - Discuss and clarify any points
2. **Confirm sequence** - Agree on implementation order
3. **Start Phase 1** - Create interfaces and base classes
4. **Test incrementally** - Each phase verified before next
5. **Migrate gradually** - One notification type at a time
6. **Remove old code** - Clean up after migration complete

---

## QUESTIONS TO RESOLVE

1. **Template Storage:** Use files only, or also database for runtime editing?
2. **Queue Library:** Continue with raw Redis, or use higher-level library (Celery/BullMQ/Sidekiq)?
3. **Retry Strategy:** Exponential backoff (2^n minutes) or fixed delays?
4. **Dead Letter Queue:** Separate Redis key, or different database?
5. **Template Versioning:** Track in database, or Git only?
6. **Channel Fallback:** Always try all channels, or respect user preference strictly?

---

This plan provides a complete, clean architecture refactoring following industry best practices while maintaining our existing functionality.
