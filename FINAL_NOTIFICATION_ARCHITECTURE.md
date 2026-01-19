# Final Notification System Architecture

**Date:** 2026-01-08
**Status:** Finalized Architecture

---

## All Event Types and Notification Types

### Event Types (Triggers)

| Event Type | Triggered By | When |
|------------|-------------|------|
| `meal_logged` | User action | When user logs a meal |
| `meal_skipped` | User action | When user skips a meal |
| `external_meal_logged` | User action | When user logs external meal |
| `inventory_updated` | User action | When inventory changes |
| `receipt_uploaded` | User action | When receipt is processed |
| `scheduled_daily_summary` | Periodic (Worker) | Every day at 9 PM |
| `scheduled_weekly_report` | Periodic (Worker) | Every Sunday at 8 PM |
| `scheduled_meal_reminder` | Periodic (Worker) | 30 minutes before meal time |
| `scheduled_inventory_check` | Periodic (Worker) | Every day at 8 AM |

### Notification Types (What Gets Created)

| Notification Type | Triggered By Event(s) | Category |
|------------------|---------------------|----------|
| `achievement` | `meal_logged`, `meal_skipped`, `external_meal_logged` | Achievement-based |
| `meal_reminder` | `scheduled_meal_reminder` | Time-based |
| `inventory_alert` | `scheduled_inventory_check`, `inventory_updated` | Inventory-based |
| `expiry_alert` | `scheduled_inventory_check` | Inventory-based |
| `low_stock_alert` | `scheduled_inventory_check` | Inventory-based |
| `progress_update` | `meal_logged` | Progress-based |
| `daily_summary` | `scheduled_daily_summary` | Summary-based |
| `weekly_report` | `scheduled_weekly_report` | Summary-based |

---

## Complete Architecture Flow

### Producer Side (Event → Queue)

```
[1] EVENT SOURCE
    ├─ User Action (meal_logged, inventory_updated, etc.)
    └─ Periodic Worker (scheduled_daily_summary, scheduled_meal_reminder, etc.)

    ↓

[2] EVENT PUBLISHER (Observer Pattern - Subject)
    event_publisher.publish(event_type, metadata)

    ↓

[3] MULTIPLE OBSERVERS (Observer Pattern - Observers)
    ├─ NotificationObserver
    │   └─ Determines which notifications to create
    │
    ├─ WebSocketObserver
    │   └─ Broadcasts real-time updates
    │
    └─ AnalyticsObserver (future)
        └─ Tracks metrics

    ↓

[4] NOTIFICATION OBSERVER LOGIC
    Based on event_type, decide:
    ├─ meal_logged → Check achievements → Create achievement notifications
    ├─ scheduled_daily_summary → Create daily_summary notification
    ├─ scheduled_meal_reminder → Create meal_reminder notification
    └─ scheduled_inventory_check → Create inventory_alert notifications

    ↓

[5] NOTIFICATION FACTORY
    factory.create_notification(event_type, metadata)
    Returns appropriate notification class instance

    ↓

[6] NOTIFICATION TEMPLATE PATTERN
    notification.create() executes:
    ├─ determine_channels() → List of channels
    ├─ calculate_priority() → Priority level
    ├─ build_notification_context() → Data for template
    └─ Returns complete notification dict

    ↓

[7] QUEUE TO REDIS
    notification_queue.enqueue(notification)
    Stores: {user_id, type, priority, channels, context, metadata}
```

---

### Consumer Side (Queue → Delivery)

```
[8] NOTIFICATION CONSUMER (Separate Container)
    Polls Redis queues by priority

    ↓

[9] GET USER PREFERENCES
    user_preferences = get_preferences(user_id)

    ↓

[10] FOR EACH PREFERRED CHANNEL
     Render template for that channel

     ↓

[11] TEMPLATE RENDERER
     renderer.render(channel, type, context, user)
     Loads: templates/{channel}/{type}.html
     Returns: {title, body}

     ↓

[12] CHANNEL STRATEGY (Strategy Pattern)
     strategy_factory.get_channel(channel)
     ├─ EmailChannel.send()
     ├─ SMSChannel.send()
     └─ PushChannel.send()

     ↓

[13] DELIVERY RESULT
      Log success/failure
      Retry if failed (exponential backoff)
```

---

## Implementation Details

### 1. Notification Observer (Decoupled Achievement Checking)

```python
# infrastructure/observers/notification_observer.py
class NotificationObserver(IObserver):
    def __init__(self, notification_factory, notification_queue, achievement_service):
        self.factory = notification_factory
        self.queue = notification_queue
        self.achievement_service = achievement_service  # Only used for specific events

    async def update(self, event: dict):
        """Route event to appropriate handler"""
        event_type = event["type"]

        # Route to specific handler based on event type
        if event_type == "meal_logged":
            await self._handle_meal_logged(event)
        elif event_type == "meal_skipped":
            await self._handle_meal_skipped(event)
        elif event_type == "scheduled_daily_summary":
            await self._handle_daily_summary(event)
        elif event_type == "scheduled_meal_reminder":
            await self._handle_meal_reminder(event)
        elif event_type == "scheduled_inventory_check":
            await self._handle_inventory_check(event)
        # ... other event types

    async def _handle_meal_logged(self, event: dict):
        """
        Meal logged can trigger:
        1. Achievement notifications (if achievements unlocked)
        2. Progress update notification (optional)
        """
        # Check achievements (ONLY for meal-related events!)
        achievements = await self.achievement_service.check_achievements(
            user_id=event["data"]["user_id"],
            daily_totals=event["data"]["daily_totals"]
        )

        # Create notification for each achievement
        for achievement in achievements:
            notification_metadata = {
                "user_id": event["data"]["user_id"],
                "achievement_type": achievement["type"],
                "message": achievement["message"]
            }

            # Factory creates notification using Template Pattern
            notification = self.factory.create_notification(
                notification_type="achievement",  # NOT hardcoded event_type!
                metadata=notification_metadata
            )

            await self.queue.enqueue(notification)

    async def _handle_daily_summary(self, event: dict):
        """Scheduled daily summary - no achievement check needed"""
        notification_metadata = {
            "user_id": event["data"]["user_id"],
            "meals_consumed": event["data"]["meals_consumed"],
            "compliance_rate": event["data"]["compliance_rate"],
            "calories_consumed": event["data"]["calories_consumed"],
            "protein_g": event["data"]["protein_g"]
        }

        notification = self.factory.create_notification(
            notification_type="daily_summary",
            metadata=notification_metadata
        )

        await self.queue.enqueue(notification)

    async def _handle_meal_reminder(self, event: dict):
        """Scheduled meal reminder - no achievement check needed"""
        notification_metadata = {
            "user_id": event["data"]["user_id"],
            "meal_type": event["data"]["meal_type"],
            "recipe_name": event["data"]["recipe_name"],
            "time_until": event["data"]["time_until"]
        }

        notification = self.factory.create_notification(
            notification_type="meal_reminder",
            metadata=notification_metadata
        )

        await self.queue.enqueue(notification)

    async def _handle_inventory_check(self, event: dict):
        """
        Scheduled inventory check can trigger:
        1. Low stock alerts
        2. Expiry alerts
        """
        user_id = event["data"]["user_id"]

        # Check for low stock items
        low_stock_items = event["data"].get("low_stock_items", [])
        if low_stock_items:
            notification = self.factory.create_notification(
                notification_type="low_stock_alert",
                metadata={
                    "user_id": user_id,
                    "items": low_stock_items
                }
            )
            await self.queue.enqueue(notification)

        # Check for expiring items
        expiring_items = event["data"].get("expiring_items", [])
        if expiring_items:
            notification = self.factory.create_notification(
                notification_type="expiry_alert",
                metadata={
                    "user_id": user_id,
                    "items": expiring_items
                }
            )
            await self.queue.enqueue(notification)
```

**Key Points:**
- ✅ Achievement checking ONLY for meal-related events
- ✅ Not hardcoded - routes based on event_type
- ✅ Factory called with notification_type (not event_type)
- ✅ Clean separation of concerns

---

### 2. Notification Factory

```python
# infrastructure/notifications/factories/notification_factory.py
class NotificationFactory:
    """
    Factory Pattern: Creates appropriate notification class based on type
    """

    def __init__(self):
        # Map notification types to classes
        self._notification_classes = {
            "achievement": AchievementNotification,
            "meal_reminder": MealReminderNotification,
            "daily_summary": DailySummaryNotification,
            "weekly_report": WeeklyReportNotification,
            "inventory_alert": InventoryAlertNotification,
            "expiry_alert": ExpiryAlertNotification,
            "low_stock_alert": LowStockAlertNotification,
            "progress_update": ProgressUpdateNotification
        }

    def create_notification(self, notification_type: str, metadata: dict):
        """
        Create notification instance based on type

        Args:
            notification_type: Type of notification (achievement, meal_reminder, etc.)
            metadata: Data for the notification

        Returns:
            Dictionary with complete notification data ready for queue
        """
        if notification_type not in self._notification_classes:
            raise ValueError(f"Unknown notification type: {notification_type}")

        # Get the appropriate class
        notification_class = self._notification_classes[notification_type]

        # Create instance
        notification = notification_class(metadata)

        # Execute template method to build complete notification
        return notification.create()
```

---

### 3. Base Notification (Template Pattern)

```python
# infrastructure/notifications/base_notification.py
from abc import ABC, abstractmethod
from datetime import datetime

class BaseNotification(ABC):
    """
    Template Pattern: Defines algorithm for creating notifications

    The algorithm:
    1. Determine available channels for this notification type
    2. Calculate priority/severity
    3. Build notification context (data for template rendering)
    4. Add common metadata
    5. Return complete notification dict
    """

    def __init__(self, metadata: dict):
        self.metadata = metadata
        self.user_id = metadata["user_id"]

    def create(self):
        """
        Template Method: Defines the algorithm structure

        Returns complete notification dict ready for queue:
        {
            "user_id": int,
            "type": str,
            "priority": str,
            "channels": List[str],  # Available channels (not user preference yet!)
            "context": dict,  # Data for template rendering
            "metadata": dict  # Common metadata
        }
        """
        # Step 1: Determine available channels for this notification type
        channels = self.determine_channels()

        # Step 2: Calculate priority/severity
        priority = self.calculate_priority()

        # Step 3: Build notification context (data for template)
        context = self.build_notification_context()

        # Step 4: Add common metadata
        metadata = self._add_common_metadata()

        # Step 5: Return complete notification
        return {
            "user_id": self.user_id,
            "type": self.get_notification_type(),
            "priority": priority,
            "channels": channels,  # What channels THIS notification supports
            "context": context,  # Data for template rendering
            "metadata": metadata,
            "created_at": datetime.utcnow().isoformat()
        }

    # ===== ABSTRACT METHODS - Subclasses MUST implement =====

    @abstractmethod
    def get_notification_type(self) -> str:
        """Return notification type identifier"""
        pass

    @abstractmethod
    def determine_channels(self) -> list:
        """
        Which channels are AVAILABLE for this notification type?

        Examples:
        - Achievement: Can go via push, email (not SMS - too long)
        - Meal Reminder: Can go via push, SMS (quick reminder)
        - Daily Summary: Only email (too long for push/SMS)

        NOTE: This is NOT user preference - just what's technically possible
        Consumer will filter by user preference later
        """
        pass

    @abstractmethod
    def calculate_priority(self) -> str:
        """
        Calculate priority/severity: "low", "normal", "high", "urgent"

        Examples:
        - Achievement: "high" (exciting!)
        - Meal Reminder: "normal"
        - Daily Summary: "low" (can wait)
        """
        pass

    @abstractmethod
    def build_notification_context(self) -> dict:
        """
        Build context data for template rendering

        This is the data that will be passed to Jinja2 template

        NOTE: For future database-stored templates, this context
        will fill placeholders in the template

        Returns:
            Dictionary of variables for template
        """
        pass

    # ===== COMMON METHOD - Same for all notifications =====

    def _add_common_metadata(self):
        """Add metadata common to all notifications"""
        return {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat()
        }
```

---

### 4. Concrete Notification Examples

```python
# infrastructure/notifications/achievement_notification.py
class AchievementNotification(BaseNotification):
    """Achievement notification when user unlocks achievement"""

    def get_notification_type(self):
        return "achievement"

    def determine_channels(self):
        """
        Achievements can go via:
        - Push (immediate, exciting)
        - Email (with nice formatting)
        NOT SMS (message too long, not urgent enough)
        """
        return ["push", "email"]

    def calculate_priority(self):
        """Achievements are exciting - high priority"""
        return "high"

    def build_notification_context(self):
        """
        Context for template rendering

        Template will have access to:
        - achievement_type: Type of achievement
        - message: Achievement message

        Future: When templates in DB, these will fill {{achievement_type}}, {{message}}
        """
        return {
            "achievement_type": self.metadata["achievement_type"],
            "message": self.metadata["message"]
        }


# infrastructure/notifications/meal_reminder_notification.py
class MealReminderNotification(BaseNotification):
    """Meal reminder notification"""

    def get_notification_type(self):
        return "meal_reminder"

    def determine_channels(self):
        """
        Meal reminders can go via:
        - Push (immediate, quick)
        - SMS (reaches user even without app open)
        NOT Email (too slow for time-sensitive reminder)
        """
        return ["push", "sms"]

    def calculate_priority(self):
        """Reminders are timely but not critical"""
        return "normal"

    def build_notification_context(self):
        """Context for template"""
        return {
            "meal_type": self.metadata["meal_type"],
            "recipe_name": self.metadata["recipe_name"],
            "time_until": self.metadata["time_until"]
        }


# infrastructure/notifications/daily_summary_notification.py
class DailySummaryNotification(BaseNotification):
    """Daily summary notification"""

    def get_notification_type(self):
        return "daily_summary"

    def determine_channels(self):
        """
        Daily summaries can ONLY go via:
        - Email (long content, formatted tables, charts)
        NOT Push/SMS (too much data, need formatting)
        """
        return ["email"]

    def calculate_priority(self):
        """Summaries can wait - low priority"""
        return "low"

    def build_notification_context(self):
        """Context for template"""
        return {
            "meals_consumed": self.metadata["meals_consumed"],
            "compliance_rate": self.metadata["compliance_rate"],
            "calories_consumed": self.metadata["calories_consumed"],
            "protein_g": self.metadata["protein_g"]
        }


# infrastructure/notifications/inventory_alert_notification.py
class LowStockAlertNotification(BaseNotification):
    """Low stock alert notification"""

    def get_notification_type(self):
        return "low_stock_alert"

    def determine_channels(self):
        """Can go via push and email"""
        return ["push", "email"]

    def calculate_priority(self):
        """Stock alerts are important but not urgent"""
        return "normal"

    def build_notification_context(self):
        """Context for template"""
        return {
            "alert_type": "low_stock",
            "items": self.metadata["items"],
            "item_count": len(self.metadata["items"])
        }
```

---

### 5. What Goes in Redis Queue

```python
# Example notification in queue:
{
    "user_id": 123,
    "type": "achievement",
    "priority": "high",
    "channels": ["push", "email"],  # Available channels (NOT user preference)
    "context": {
        "achievement_type": "nutrition_target",
        "message": "Protein goal achieved! Hit 50g target!"
    },
    "metadata": {
        "version": "1.0",
        "created_at": "2026-01-08T10:30:00Z"
    },
    "created_at": "2026-01-08T10:30:00Z"
}
```

**Key Points:**
- ✅ User ID (not recipient object)
- ✅ Type identifier (for template loading)
- ✅ Priority (for queue routing)
- ✅ Available channels (what notification supports)
- ✅ Context (data for template - future-proof for DB templates)
- ✅ Metadata (common info)
- ❌ NO rendered templates (consumer does that)
- ❌ NO user preferences (consumer checks that)

---

### 6. Consumer Side

```python
# infrastructure/notifications/consumers/notification_consumer.py
class NotificationConsumer:
    def __init__(self, redis_client, user_repo, template_renderer, channel_factory):
        self.redis = redis_client
        self.user_repo = user_repo
        self.renderer = template_renderer
        self.channel_factory = channel_factory

    async def process_notification(self, notification: dict):
        """
        Process one notification from queue

        Steps:
        1. Get user preferences
        2. Filter channels by user preference
        3. For each preferred channel, render and send
        """
        user_id = notification["user_id"]

        # 1. Get user and preferences
        user = self.user_repo.get(user_id)
        preferences = self.user_repo.get_preferences(user_id)

        # 2. Determine which channel to use
        # notification["channels"] = What notification supports
        # preferences.primary_channel = What user prefers
        available_channels = set(notification["channels"])
        preferred_channel = preferences.primary_channel

        # Use preferred channel if available, else first available
        if preferred_channel in available_channels:
            channel_to_use = preferred_channel
        else:
            channel_to_use = notification["channels"][0]

        # 3. Render template for that channel
        rendered = self.renderer.render(
            channel=channel_to_use,
            notification_type=notification["type"],
            context=notification["context"],
            user=user
        )
        # Returns: {"title": "...", "body": "..."}

        # 4. Get strategy and send
        strategy = self.channel_factory.get_channel(channel_to_use)
        result = await strategy.send(user, rendered)

        return result


# infrastructure/notifications/templates/template_renderer.py
class TemplateRenderer:
    """
    Renders templates at delivery time (consumer side)

    For now: Loads from template files
    Future: Load from database with placeholders
    """

    def __init__(self):
        from jinja2 import Environment, FileSystemLoader
        self.jinja_env = Environment(
            loader=FileSystemLoader("templates/notifications")
        )

    def render(self, channel: str, notification_type: str, context: dict, user):
        """
        Render template for specific channel

        Args:
            channel: "email", "sms", "push"
            notification_type: "achievement", "meal_reminder", etc.
            context: Data from notification (for template variables)
            user: User object (for recipient_name, email, etc.)

        Returns:
            {"title": str, "body": str}
        """
        # 1. Build template file path
        extensions = {"email": ".html", "sms": ".txt", "push": ".json"}
        template_path = f"{channel}/{notification_type}{extensions[channel]}"

        # 2. Load template
        template = self.jinja_env.get_template(template_path)

        # 3. Merge context with user data
        render_context = {
            **context,
            "user_name": user.username or "User",
            "user_email": user.email,
            "unsubscribe_url": f"https://app.nutrilens.com/unsubscribe/{user.id}"
        }

        # 4. Render
        rendered_body = template.render(render_context)

        # 5. Extract title (if any)
        title = context.get("message", notification_type.replace("_", " ").title())

        # 6. Channel-specific post-processing
        if channel == "sms":
            rendered_body = rendered_body[:160]  # SMS limit

        return {
            "title": title,
            "body": rendered_body
        }
```

---

## Summary

### ✅ What We're Doing Right:

1. **Observer Pattern** - One event triggers multiple observers
2. **Factory Pattern** - Creates right notification type
3. **Template Pattern** - Structured algorithm even if simple now (future-proof!)
4. **Strategy Pattern** - Interchangeable channel delivery
5. **Decoupled Achievement** - Only checked for meal events
6. **Not Hardcoded** - Observer routes by event_type, factory by notification_type
7. **Future-Proof Context** - Context structure ready for DB templates
8. **Consumer Renders** - Templates rendered at delivery time
9. **User Preferences in Consumer** - Latest preferences checked

### 🎯 Key Architecture Decisions:

| Decision | Choice | Reason |
|----------|--------|--------|
| Achievement checking | Only in meal-related event handlers | Not all events need it |
| Factory input | notification_type (not event_type) | One event can create multiple notification types |
| Template Pattern | Use it even if simple | Structure for future, clear algorithm |
| Template rendering | Consumer side | Industry standard, allows template updates |
| User preferences | Consumer checks | Latest preferences, more flexible |
| Queue payload | Context + metadata | Future-proof for DB templates |

---

This architecture is clean, scalable, and follows industry best practices!
