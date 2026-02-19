# Implementation Decisions - Notification System Refactoring

**Date:** 2026-01-06
**Status:** Decisions Finalized

---

## DECISIONS MADE

### 1. Template Storage ✅
**Decision:** Files only (for now)
**Reason:** Will move to database later when moving all prompts to database
**Location:** `backend/templates/notifications/`
**Format:** Jinja2 templates (.html, .txt, .json)

### 2. Queue Library ✅
**Decision:** Raw Redis (continue current approach)
**Reason:** Already using Redis, no need for additional dependency
**Implementation:**
- Use existing `get_redis_client()` singleton
- Priority queues: `notifications:high`, `notifications:normal`, `notifications:low`

### 3. Channel Fallback ✅
**Decision:** Respect user preference strictly
**Reason:** Clean architecture allows easy change later if needed
**Implementation:** Send via user's preferred channel only

### 4. Dead Letter Queue ✅
**Decision:** Separate Redis key
**Implementation:** `notifications:dead_letter_queue`
**Reason:** Simple, keeps everything in Redis for now

### 5. Implementation Order ✅
**Decision:** Step by step, phase by phase
**Approach:** Build incrementally, test each phase before moving to next

---

## CONCEPTS TO DISCUSS

### 3. Retry Strategy (Exponential Backoff vs Fixed Delays)

#### What is Retry Logic?

When notification delivery fails (e.g., SendGrid API down, user's phone unreachable), we need to **retry** sending.

**Question:** How long should we wait between retries?

#### Option A: Fixed Delays

**Pattern:** Wait same amount every time
```
Attempt 1: Send → Fail
Wait 5 minutes
Attempt 2: Send → Fail
Wait 5 minutes
Attempt 3: Send → Fail
Wait 5 minutes
Give up
```

**Pros:**
- Simple to understand
- Predictable timing

**Cons:**
- If service is down for 2 minutes, we waste 3 minutes waiting
- Puts constant pressure on failing service (hammering)
- Not industry standard

#### Option B: Exponential Backoff (RECOMMENDED)

**Pattern:** Wait increasingly longer each retry
```
Attempt 1: Send → Fail
Wait 1 minute (2^0 = 1)
Attempt 2: Send → Fail
Wait 2 minutes (2^1 = 2)
Attempt 3: Send → Fail
Wait 4 minutes (2^2 = 4)
Attempt 4: Send → Fail
Wait 8 minutes (2^3 = 8)
Give up
```

**Formula:** `delay = base_delay × 2^(attempt_count - 1)`
- Base delay: 1 minute
- Attempt 1: 1 min
- Attempt 2: 2 min
- Attempt 3: 4 min
- Attempt 4: 8 min
- Attempt 5: 16 min

**Pros:**
- ✅ **Industry standard** (AWS, Google Cloud, Twilio all use this)
- ✅ **Gives service time to recover** (transient failures often recover quickly)
- ✅ **Reduces load on failing service** (not hammering)
- ✅ **Better success rate** (longer waits = more chance to recover)

**Cons:**
- Slightly more complex code

#### Real-World Example

**Scenario:** SendGrid API has a 2-minute outage

**Fixed Delays (5 min):**
```
00:00 - Attempt 1 → Fail (API down)
05:00 - Attempt 2 → Fail (API down)
10:00 - Attempt 3 → Success (API back at 02:00, but we waited until 10:00)
Total time: 10 minutes
```

**Exponential Backoff:**
```
00:00 - Attempt 1 → Fail (API down)
01:00 - Attempt 2 → Fail (API down)
03:00 - Attempt 3 → Success (API back at 02:00, we tried at 03:00)
Total time: 3 minutes
```

#### What Good Systems Do

**AWS SQS (Simple Queue Service):**
- Uses exponential backoff
- Default: 0s, 1s, 2s, 4s, 8s, 16s, 32s, ... up to 900s (15 min max)

**Google Cloud Pub/Sub:**
- Exponential backoff with jitter
- Min: 10s, Max: 600s (10 min)

**Twilio (SMS/WhatsApp):**
- Exponential backoff
- Attempts: 1m, 2m, 4m, 8m, 16m

**SendGrid (Email):**
- Exponential backoff
- Up to 72 hours of retries

**Stripe (Webhooks):**
- Exponential backoff with jitter
- Attempts over several days

#### Recommendation for NutriLens

**Pattern:** Exponential backoff with max cap
```python
def calculate_retry_delay(attempt_count: int) -> int:
    """Calculate delay in seconds for retry attempt"""
    base_delay = 60  # 1 minute
    max_delay = 900  # 15 minutes

    delay = base_delay * (2 ** (attempt_count - 1))
    return min(delay, max_delay)

# Results:
# Attempt 1: 60s (1 min)
# Attempt 2: 120s (2 min)
# Attempt 3: 240s (4 min)
# Attempt 4: 480s (8 min)
# Attempt 5: 900s (15 min) - capped
# Attempt 6: 900s (15 min) - capped
```

**Max Retries:** 5 attempts
**Total Time:** ~30 minutes before giving up
**After max retries:** Move to Dead Letter Queue for manual review

#### Advanced: Jitter (Optional - Not for now)

**What is Jitter?**
Add randomness to prevent "thundering herd" problem (many notifications retrying at exact same time)

```python
import random

def calculate_retry_delay_with_jitter(attempt_count: int) -> int:
    base_delay = calculate_retry_delay(attempt_count)
    jitter = random.uniform(0, base_delay * 0.1)  # +/- 10%
    return int(base_delay + jitter)
```

**When to use:** When you have 1000+ notifications/second
**Our case:** Not needed yet, simple exponential backoff is enough

---

### 6. Template Versioning

#### What is Template Versioning?

When you update a notification template, you want to:
1. **Keep history** - What did the old template look like?
2. **Rollback** - If new template has bug, revert to old
3. **A/B Testing** - Test new template on 10% of users
4. **Audit** - Who changed template? When? Why?

#### Option A: Git Only (RECOMMENDED for now)

**How it works:**
```
backend/templates/notifications/
├── achievement_email.html     # Current version
├── meal_reminder_email.html
└── daily_summary_email.html

# Git history:
commit abc123 - "Update achievement email template with new design"
commit def456 - "Fix typo in meal reminder template"
```

**Pros:**
- ✅ **Simple** - Just use Git
- ✅ **Free** - No database storage
- ✅ **Developer-friendly** - Use tools you already know
- ✅ **Automatic history** - Git tracks everything
- ✅ **Easy rollback** - `git revert`

**Cons:**
- ❌ Requires deploy to update templates
- ❌ Non-technical users can't edit
- ❌ No runtime A/B testing

**When to use:** MVP, small team, templates rarely change

#### Option B: Database Versioning

**Schema:**
```sql
CREATE TABLE notification_templates (
    id UUID PRIMARY KEY,
    name VARCHAR(255),           -- "achievement_email"
    version INTEGER,              -- 1, 2, 3, ...
    content TEXT,                 -- Jinja2 template
    active BOOLEAN DEFAULT true,  -- Only one version active
    created_by UUID,
    created_at TIMESTAMP,
    change_notes TEXT
);

-- Example data:
| name               | version | active | created_at | change_notes              |
|--------------------|---------|--------|------------|---------------------------|
| achievement_email  | 1       | false  | 2025-01-01 | Initial version           |
| achievement_email  | 2       | false  | 2025-02-15 | Added emoji               |
| achievement_email  | 3       | true   | 2025-03-20 | New design (current)      |
```

**Code:**
```python
class TemplateRepository:
    def get_active_template(self, name: str):
        """Get currently active version"""
        return db.query(NotificationTemplate)\
            .filter(name=name, active=True)\
            .first()

    def create_new_version(self, name: str, content: str, notes: str):
        """Create new version, keep old"""
        current = self.get_active_template(name)

        # Deactivate old
        if current:
            current.active = False

        # Create new
        new_version = NotificationTemplate(
            name=name,
            version=(current.version + 1) if current else 1,
            content=content,
            active=True,
            change_notes=notes
        )
        db.save(new_version)

    def rollback_to_version(self, name: str, version: int):
        """Rollback to specific version"""
        # Deactivate all
        db.update(NotificationTemplate)\
            .filter(name=name)\
            .set(active=False)

        # Activate specific version
        db.update(NotificationTemplate)\
            .filter(name=name, version=version)\
            .set(active=True)
```

**Pros:**
- ✅ **Runtime updates** - Change templates without deploy
- ✅ **UI for editing** - Build admin panel for non-devs
- ✅ **A/B testing** - Easy to test versions
- ✅ **Detailed audit** - Who, when, why

**Cons:**
- ❌ More complex
- ❌ Need admin UI
- ❌ Database storage

**When to use:** Scale, non-technical editors, frequent changes

#### What Good Systems Do

**SendGrid:**
- Database versioning
- Web UI to edit templates
- Version history with rollback
- A/B testing built-in

**Mailchimp:**
- Database + Git hybrid
- Templates in database
- Can export to Git for backup

**Twilio:**
- Database versioning
- REST API to manage templates
- Version history

**Stripe:**
- Git for code
- Database for content
- Webhooks notify on changes

#### Recommendation for NutriLens

**Phase 1 (NOW):** Git only
```
backend/templates/notifications/
├── achievement_email.html
├── achievement_push.json
├── meal_reminder_email.html
└── ...

# To update:
1. Edit file
2. Git commit with message
3. Deploy
```

**Phase 2 (LATER):** Database when needed
- When: Non-devs need to edit templates
- When: Frequent template changes (weekly)
- When: Need A/B testing
- Implementation: Add `notification_templates` table, build admin UI

**For now:** Keep it simple with Git!

---

## FINAL DECISIONS SUMMARY

| Decision | Choice | Reason |
|----------|--------|--------|
| Template Storage | Files only | Simple for now, database later with prompts |
| Queue Library | Raw Redis | Already using, no new dependency |
| Retry Strategy | **Exponential Backoff** | Industry standard, better recovery |
| Dead Letter Queue | Redis key (`notifications:dlq`) | Simple, consistent with queue |
| Template Versioning | **Git only** | Simple for MVP, database later if needed |
| Channel Fallback | User preference only | Clean architecture, easy to change |
| Implementation | Step by step | Incremental, test each phase |

---

## RETRY STRATEGY SPECIFICATION

### Configuration
```python
# backend/app/infrastructure/notifications/consumers/retry_config.py

class RetryConfig:
    """Retry configuration for notification delivery"""

    BASE_DELAY_SECONDS = 60      # 1 minute
    MAX_DELAY_SECONDS = 900       # 15 minutes
    MAX_RETRIES = 5               # Total attempts: 6 (1 original + 5 retries)

    @staticmethod
    def calculate_delay(attempt: int) -> int:
        """
        Calculate retry delay using exponential backoff

        Args:
            attempt: Retry attempt number (1-5)

        Returns:
            Delay in seconds

        Examples:
            attempt=1 → 60s (1 min)
            attempt=2 → 120s (2 min)
            attempt=3 → 240s (4 min)
            attempt=4 → 480s (8 min)
            attempt=5 → 900s (15 min, capped)
        """
        delay = RetryConfig.BASE_DELAY_SECONDS * (2 ** (attempt - 1))
        return min(delay, RetryConfig.MAX_DELAY_SECONDS)
```

### Implementation in Consumer
```python
# When notification fails
if not delivery_success:
    retry_count = notification_data.get("retry_count", 0)

    if retry_count < RetryConfig.MAX_RETRIES:
        # Calculate next retry time
        delay = RetryConfig.calculate_delay(retry_count + 1)
        next_retry_at = datetime.utcnow() + timedelta(seconds=delay)

        # Update metadata
        notification_data["retry_count"] = retry_count + 1
        notification_data["next_retry_at"] = next_retry_at.isoformat()

        # Schedule retry (Redis sorted set)
        redis.zadd(
            "notifications:retry_queue",
            {json.dumps(notification_data): next_retry_at.timestamp()}
        )

        logger.info(f"Scheduled retry {retry_count + 1}/{RetryConfig.MAX_RETRIES} "
                   f"for user {user_id} in {delay}s")
    else:
        # Max retries exceeded - move to DLQ
        redis.lpush("notifications:dlq", json.dumps(notification_data))
        logger.error(f"Notification failed permanently for user {user_id} "
                    f"after {RetryConfig.MAX_RETRIES} retries")
```

### Timeline Example
```
00:00 - Original send → Fail
01:00 - Retry 1 (after 1 min) → Fail
03:00 - Retry 2 (after 2 min) → Fail
07:00 - Retry 3 (after 4 min) → Fail
15:00 - Retry 4 (after 8 min) → Fail
30:00 - Retry 5 (after 15 min) → Fail
Move to DLQ

Total time: 30 minutes
Total attempts: 6 (1 original + 5 retries)
```

---

## TEMPLATE VERSIONING SPECIFICATION

### Phase 1: Git-Based Versioning (NOW)

**Directory Structure:**
```
backend/templates/notifications/
├── email/
│   ├── achievement.html
│   ├── meal_reminder.html
│   ├── daily_summary.html
│   ├── weekly_report.html
│   └── inventory_alert.html
├── sms/
│   ├── achievement.txt
│   ├── meal_reminder.txt
│   └── inventory_alert.txt
└── push/
    ├── achievement.json
    ├── meal_reminder.json
    ├── daily_summary.json
    └── inventory_alert.json
```

**Template Loading:**
```python
# backend/app/infrastructure/notifications/templates/template_loader.py

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

class TemplateLoader:
    """Loads notification templates from filesystem"""

    def __init__(self):
        template_dir = Path(__file__).parent.parent.parent.parent / "templates" / "notifications"
        self.env = Environment(loader=FileSystemLoader(template_dir))

    def load_template(self, channel: str, notification_type: str):
        """
        Load template file

        Args:
            channel: "email", "sms", "push"
            notification_type: "achievement", "meal_reminder", etc.

        Returns:
            Jinja2 Template object
        """
        extension_map = {
            "email": ".html",
            "sms": ".txt",
            "push": ".json"
        }

        template_path = f"{channel}/{notification_type}{extension_map[channel]}"
        return self.env.get_template(template_path)
```

**Version Control:**
```bash
# To update template
git log backend/templates/notifications/email/achievement.html

# Example history:
# commit def456 - "Fix typo in achievement email"
# commit abc123 - "Update achievement email design"
# commit xyz789 - "Initial achievement email template"

# To rollback
git revert abc123  # Reverts specific commit
# OR
git checkout xyz789 -- backend/templates/notifications/email/achievement.html
```

---

## NEXT STEPS

Now that all decisions are made, we can proceed with implementation!

**Phase 1 will be:**
1. Create domain models
2. Create interfaces (INotificationChannel, NotificationGenerator base)
3. Create retry configuration
4. Set up template directory structure

Ready to start? 🚀
