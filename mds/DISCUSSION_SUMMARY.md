# Notification System Discussion Summary

**Date:** 2026-01-06

---

## YOUR REQUIREMENTS

1. ✅ **Separate Producer from Consumer** - Different classes, different responsibilities
2. ✅ **Both follow clean architecture** - Domain, Application, Infrastructure layers
3. ✅ **Template Pattern for notification generation** - Algorithm structure + channel variants
4. ✅ **Strategy Pattern for channel selection** - Encapsulated delivery strategies
5. ✅ **Factory Patterns** - TemplateFactory + ChannelStrategyFactory
6. ✅ **Worker as periodic event publisher** - Same pattern as EventPublisher
7. ✅ **Research industry patterns** - Celery, BullMQ, Sidekiq best practices

---

## KEY FINDINGS FROM CODEBASE SCAN

### Current NotificationService (`notification_service.py`)

**Line 68-993:** One massive class doing EVERYTHING

**Producer Side (Generation & Queuing):**
- Lines 152-344: Public API methods (send_achievement, send_meal_reminder, etc.)
- Lines 348-404: `_queue_notification()` → writes to Redis
- Lines 745-779: `_get_user_preferences()` → checks if should send

**Consumer Side (Delivery):**
- Lines 432-455: `process_notification_queue()` → infinite loop
- Lines 457-483: `_process_priority_queue()` → reads from Redis
- Lines 514-545: `_send_notification()` → actual delivery
- Lines 547-693: `_send_via_provider()` → **if/elif chain (BAD)**

**Template Generation:**
- Lines 824-855: `_generate_email_html()` → **hardcoded HTML in Python string (BAD)**
- No template files
- No template factory
- No template versioning

**Channel Selection:**
- Lines 547-561: if/elif chain
```python
if provider == NotificationProvider.PUSH:
    return await _mock_send_provider(...)
elif provider == NotificationProvider.EMAIL:
    return await _mock_send_provider(...)
```
- **No Strategy Pattern**
- **No Channel Factory**

**Redis Client:**
- Lines 73-78: Creates own Redis client
- Should use `get_redis_client()` singleton

### Current NotificationWorker (`notification_worker.py`)

**Line 22-70:** `NotificationWorker.run()` - IS a periodic event publisher!
- Runs in 30-second loop
- Checks time conditions (9 PM, Sunday 8 PM, 8 AM, every 5 min)
- Calls NotificationService producer methods

**Line 257-271:** `run_notification_queue_processor()` - consumer function
- Creates NotificationService
- Calls `process_notification_queue()`

**Architecture Pattern:**
```
NotificationWorker (producer mode)
├── Checks: Is it 9 PM? Sunday 8 PM? Meal reminder time?
├── Calls: notification_service.send_daily_summary(...)
└── Effect: Queues to Redis

NotificationProcessor (consumer mode)
├── Runs: notification_service.process_notification_queue()
├── Reads: From Redis queues
└── Sends: Via channels
```

**Key Insight:** Worker is time-based event publisher, just like EventPublisher but triggered by schedule instead of user action!

---

## INDUSTRY RESEARCH FINDINGS

### 1. Producer-Consumer Pattern (Celery, BullMQ, Sidekiq)

**All frameworks follow same pattern:**

**Producer:**
- Decides eligibility (should notification be sent?)
- Generates content (templates, context)
- Queues message
- Returns immediately (non-blocking)

**Consumer:**
- Polls/listens for messages
- Delivers via appropriate channel
- Handles retries
- Logs results

**Message Queue:**
- Decouples producer timing from consumer timing
- Enables horizontal scaling (multiple consumers)
- Persistence (survives crashes)
- Priority queues

### 2. Template Pattern (Algorithm Structure)

**Purpose:** Define notification generation algorithm once, customize steps per channel

**Pattern:**
```python
class NotificationGenerator(ABC):
    def generate(self, ...):  # Template method
        recipient = self.validate_prerequisites()
        context = self.fetch_context_data()
        template = self.get_template()
        content = template.render(context)
        enriched = self.enrich_notification(content)
        validated = self.validate_content(enriched)
        return self.apply_user_preferences(validated)

    @abstractmethod
    def validate_prerequisites(self): pass

    @abstractmethod
    def enrich_notification(self, content): pass

    @abstractmethod
    def validate_content(self, notification): pass
```

**Implementations:**
- `EmailGenerator`: adds unsubscribe link, validates email length
- `SMSGenerator`: truncates to 160 chars, validates phone opt-in
- `PushGenerator`: adds action buttons, validates token exists

**Benefits:**
- Algorithm defined once
- Each channel customizes specific steps
- DRY principle
- Easy to add new channels

### 3. Strategy Pattern (Channel Delivery)

**Purpose:** Encapsulate delivery algorithms, make them interchangeable

**Pattern:**
```python
class INotificationChannel(ABC):
    @abstractmethod
    async def send(self, notification) -> DeliveryResult: pass

    @abstractmethod
    def validate(self, user) -> bool: pass

class EmailChannel(INotificationChannel):
    async def send(self, notification):
        return await self.sendgrid.send(...)

    def validate(self, user):
        return user.email and user.email_verified

class SMSChannel(INotificationChannel):
    async def send(self, notification):
        return await self.twilio.send(...)

    def validate(self, user):
        return user.phone and user.sms_opt_in

class PushChannel(INotificationChannel):
    async def send(self, notification):
        return await self.fcm.send(...)

    def validate(self, user):
        return user.device_tokens
```

**ChannelStrategyFactory:**
```python
def create_strategies(user, notification_type):
    """Returns ordered list to try"""
    strategies = []

    # Primary: user preference
    if user.preferred_channel == "EMAIL":
        strategies.append(EmailChannel())

    # Fallback: based on type
    if notification_type == "URGENT":
        strategies.extend([SMSChannel(), PushChannel()])

    return strategies
```

**Consumer tries each strategy:**
```python
strategies = factory.create_strategies(user, type)
for strategy in strategies:
    result = await strategy.send(notification)
    if result.success:
        break  # Success!
```

**Benefits:**
- Open/Closed Principle (add channels without modifying existing)
- Easy testing (mock individual strategies)
- Clean fallback logic
- Encapsulation

### 4. Factory Pattern (Template & Channel Creation)

**TemplateFactory:**
```python
class TemplateFactory:
    def create_template(self, type: NotificationType, channel: ChannelType):
        # Load from files or database
        template_path = f"templates/{type}_{channel}.html"
        return Template.from_file(template_path)
```

**ChannelStrategyFactory:**
```python
class ChannelStrategyFactory:
    def create_strategies(self, user, type):
        # Create appropriate strategies based on:
        # - User preferences
        # - Notification type urgency
        # - Available channels for user
        return [EmailChannel(...), SMSChannel(...)]
```

**Benefits:**
- Centralized creation logic
- Easy to add new types
- Dependency injection friendly
- Testable

### 5. Periodic vs Real-Time Publishers

**Both are Event Publishers, just different triggers:**

| Aspect | Real-Time | Periodic |
|--------|-----------|----------|
| Trigger | User action | Time schedule |
| Example | Meal logged → achievement | 9 PM → daily summary |
| Latency | Seconds | Hours |
| Pattern | Observer pattern | Cron pattern |

**Architecture:**
```
User Action → EventPublisher → NotificationObserver → NotificationProducer
Time Check → PeriodicEventPublisher → NotificationProducer

Both feed same queue:
NotificationProducer → Redis → NotificationConsumer → Channels
```

**Key Insight:** Worker IS a PeriodicEventPublisher, should be treated as such!

---

## PROPOSED ARCHITECTURE

### Complete Flow

```
┌──────────────────────────────────────────────────────────┐
│                  EVENT PUBLISHERS                         │
├──────────────────────────────────────────────────────────┤
│  Real-Time (EventPublisher)                              │
│    User logs meal → publish("meal_logged")               │
│         ↓                                                │
│    NotificationObserver.update()                         │
│         ↓                                                │
│    Check achievements → NotificationProducer             │
│                                                          │
│  Periodic (PeriodicEventPublisher / Worker)              │
│    Time check (9PM, Sunday 8PM, every 5min)              │
│         ↓                                                │
│    Directly calls NotificationProducer                   │
└──────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│           NOTIFICATION PRODUCER (Generation)              │
├──────────────────────────────────────────────────────────┤
│  send_achievement(user_id, type, message)                │
│  send_meal_reminder(user_id, ...)                        │
│  send_daily_summary(user_id, data)                       │
│                                                          │
│  Flow per notification:                                  │
│  1. Check user preferences (enabled?)                    │
│  2. Check rate limits                                    │
│  3. Get template (TemplateFactory)                       │
│  4. Generate content (NotificationGenerator)             │
│  5. Queue to Redis                                       │
│                                                          │
│  NEVER sends - only queues!                              │
└──────────────────────────────────────────────────────────┘
                           ↓
                   Redis Queues
           (high, normal, low priority)
                           ↓
┌──────────────────────────────────────────────────────────┐
│          NOTIFICATION CONSUMER (Delivery)                 │
├──────────────────────────────────────────────────────────┤
│  process_queue() - infinite loop                         │
│                                                          │
│  Flow per message:                                       │
│  1. Poll Redis queue (batch)                             │
│  2. Get user                                             │
│  3. Create strategies (ChannelStrategyFactory)           │
│  4. Try each strategy until success                      │
│  5. Log delivery result                                  │
│  6. Handle failures (retry or DLQ)                       │
│                                                          │
│  NEVER decides eligibility - only delivers!              │
└──────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│              CHANNEL STRATEGIES                           │
├──────────────────────────────────────────────────────────┤
│  EmailChannel → SendGrid                                 │
│  SMSChannel → Twilio                                     │
│  PushChannel → FCM                                       │
│  WhatsAppChannel → Twilio WhatsApp                       │
└──────────────────────────────────────────────────────────┘
```

### File Structure

```
backend/app/
├── domain/
│   └── notifications/
│       ├── notification.py       # Domain models
│       └── template.py           # Template domain
│
├── infrastructure/
│   ├── events/
│   │   ├── event_publisher.py              # ✅ Real-time
│   │   └── periodic_event_publisher.py     # NEW (refactored worker)
│   │
│   ├── observers/
│   │   ├── websocket_observer.py           # ✅ Exists
│   │   └── notification_observer.py        # ✅ Exists
│   │
│   └── notifications/
│       ├── producers/
│       │   ├── notification_producer.py    # NEW - Queuing only
│       │   └── generators/
│       │       ├── base_generator.py       # Template Pattern
│       │       ├── email_generator.py
│       │       ├── sms_generator.py
│       │       └── push_generator.py
│       │
│       ├── consumers/
│       │   └── notification_consumer.py    # NEW - Delivery only
│       │
│       ├── channels/
│       │   ├── base_channel.py             # Strategy interface
│       │   ├── email_channel.py
│       │   ├── sms_channel.py
│       │   ├── push_channel.py
│       │   └── whatsapp_channel.py
│       │
│       └── factories/
│           ├── template_factory.py
│           └── channel_factory.py
│
└── templates/                              # NEW - Template files
    └── notifications/
        ├── achievement_email.html
        ├── achievement_push.json
        ├── meal_reminder_email.html
        └── ...
```

---

## IMPLEMENTATION PHASES

### Phase 1: Infrastructure (Interfaces & Base Classes)
- Domain models
- INotificationChannel interface
- NotificationGenerator base class
- Template domain model

### Phase 2: Template Management
- Template files (Jinja2)
- Template renderer
- Template factory

### Phase 3: Producer
- Email/SMS/Push generators
- NotificationProducer
- Update NotificationObserver

### Phase 4: Consumer
- Email/SMS/Push/WhatsApp channels
- ChannelStrategyFactory
- NotificationConsumer

### Phase 5: Periodic Publisher
- Refactor worker → PeriodicEventPublisher
- Update Docker

### Phase 6: Dependency Injection
- Update dependencies.py
- Update main.py

### Phase 7: Migration & Cleanup
- Migrate existing usage
- Remove old NotificationService
- Testing

---

## CRITICAL DESIGN PRINCIPLES

1. **Single Responsibility**
   - Producer: Generate + Queue
   - Consumer: Deliver + Retry
   - Never mixed!

2. **Open/Closed**
   - New channels: Add strategy, no modification
   - New templates: Add file, no code change
   - New notification types: Extend, don't modify

3. **Dependency Inversion**
   - Depend on INotificationChannel, not concrete classes
   - Depend on NotificationGenerator, not specific generators
   - Factories inject dependencies

4. **Template Method**
   - Algorithm structure in base
   - Specific steps in subclasses
   - Reusable, extensible

5. **Strategy**
   - Encapsulated delivery
   - Interchangeable at runtime
   - Testable in isolation

---

## QUESTIONS TO DISCUSS

1. **Template Storage:** Files only, or database for runtime editing?
2. **Queue Library:** Raw Redis, or use Celery/BullMQ/Sidekiq?
3. **Retry Strategy:** Exponential backoff 2^n minutes, or fixed delays?
4. **Dead Letter Queue:** Separate Redis key, or different store?
5. **Template Versioning:** Database tracking, or Git only?
6. **Channel Fallback:** Try all, or respect user preference strictly?
7. **Implementation Order:** Agree on phase sequence?

---

## NO OVERENGINEERING VERIFICATION

✅ **Every pattern has clear purpose:**
- Template Pattern → Reuse generation algorithm
- Strategy Pattern → Interchangeable delivery
- Factory Pattern → Centralized creation
- Producer/Consumer → Independent scaling

✅ **Follow existing codebase patterns:**
- Repository pattern (already used)
- Dependency injection (already used)
- Redis singleton (already exists)
- Clean architecture layers (already established)

✅ **Industry standard:**
- Celery does this
- BullMQ does this
- Sidekiq does this
- Not inventing new patterns!

✅ **Solves real problems:**
- Current: One class doing everything (SRP violation)
- Current: Hardcoded templates (can't edit without deploy)
- Current: if/elif chains (OCP violation)
- Current: No separation (can't scale independently)

---

This is thorough, detailed, based on facts, and follows industry best practices without overengineering.
