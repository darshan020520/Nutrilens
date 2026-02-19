# Simple Inventory Alert Solution - FINAL

## The Problem
- 3 functions send inventory notifications (expiring, low stock, restock)
- All triggered by API calls (when user visits pages)
- Results in spam and duplicate notifications

## The Simple Solution

### Create ONE dedicated notification function
- Separate from UI data functions
- Called once per day by notification worker (8 AM)
- Uses restock list data (already has everything)
- Redis deduplication built-in

---

## Implementation (3 Simple Steps)

### Step 1: Add New Function to tracking_agent.py

```python
async def check_and_send_inventory_alert(self) -> Dict:
    """
    Dedicated function for sending inventory alerts - called by notification worker
    Separate from UI data functions - purely for notifications
    """
    try:
        # Get comprehensive restock data (already includes everything)
        restock_data = self.generate_restock_list()

        if not restock_data.get("success"):
            return {"success": False, "error": "Failed to generate restock data"}

        # Check Redis deduplication
        from app.core.config import settings
        import redis

        redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        today = datetime.utcnow().strftime("%Y-%m-%d")
        alert_key = f"inventory_alert:{self.user_id}:unified:{today}"

        if redis_client.exists(alert_key):
            logger.info(f"⏭️  Inventory alert SKIPPED - already sent today for user {self.user_id}")
            return {"success": True, "skipped": True, "reason": "already_sent_today"}

        # Check if user has any inventory (skip if never added items)
        has_inventory = self.db.query(UserInventory).filter(
            UserInventory.user_id == self.user_id
        ).first() is not None

        if not has_inventory:
            logger.info(f"⏭️  Inventory alert SKIPPED - user has no inventory")
            return {"success": True, "skipped": True, "reason": "no_inventory"}

        # Check if there are urgent items
        urgent_count = restock_data.get("urgent_count", 0)

        if urgent_count == 0:
            logger.info(f"⏭️  Inventory alert SKIPPED - no urgent items")
            return {"success": True, "skipped": True, "reason": "no_urgent_items"}

        # Send unified notification
        urgent_items = restock_data["restock_list"]["urgent"][:3]  # Top 3
        item_names = [item["item_name"] for item in urgent_items]

        await self.notification_service.send_inventory_alert(
            user_id=self.user_id,
            alert_type="inventory_urgent",
            items=item_names,
            priority=NotificationPriority.HIGH
        )

        # Mark as sent
        redis_client.setex(alert_key, 86400, "1")

        logger.info(f"✅ Unified inventory alert sent for {urgent_count} urgent items")

        return {
            "success": True,
            "sent": True,
            "urgent_count": urgent_count,
            "items": item_names
        }

    except Exception as e:
        logger.error(f"Error in check_and_send_inventory_alert: {str(e)}")
        return {"success": False, "error": str(e)}
```

### Step 2: Add Scheduler to notification_worker.py

Add to `__init__`:
```python
self.last_inventory_check = None
```

Add to `_process_scheduled_notifications()`:
```python
# Inventory alerts at 8 AM (only once per day)
if (current_hour == 8 and
    (self.last_inventory_check is None or self.last_inventory_check != current_date)):

    await self._trigger_inventory_alerts(db)
    self.last_inventory_check = current_date
    logger.info("Inventory alerts triggered")
```

Add new method:
```python
async def _trigger_inventory_alerts(self, db):
    """TRIGGER inventory alerts for all active users"""
    try:
        from app.agents.tracking_agent import TrackingAgent

        active_users = db.query(User).filter(User.is_active == True).all()

        alert_count = 0

        for user in active_users:
            try:
                tracking_agent = TrackingAgent(db, user.id)
                result = await tracking_agent.check_and_send_inventory_alert()

                if result.get("sent"):
                    alert_count += 1

            except Exception as e:
                logger.error(f"Error checking inventory for user {user.id}: {str(e)}")

        if alert_count > 0:
            logger.info(f"Sent inventory alerts to {alert_count} users")

    except Exception as e:
        logger.error(f"Error in _trigger_inventory_alerts: {str(e)}")
```

### Step 3: Remove Notification Sending from UI Functions

**In `check_expiring_items()` - Remove lines 787-813:**
```python
# Notification removed - now handled by daily scheduled check
logger.info(f"Found {len(urgent_items)} urgent expiring items")
```

**In `calculate_inventory_status()` - Remove lines 1098-1125:**
```python
# Notification removed - now handled by daily scheduled check
logger.info(f"Found {len(critical_item_names)} critical items")
```

**In `generate_restock_list()` - Keep as is:**
- No changes needed (doesn't send notifications currently)

---

## Result

### Before:
- ❌ 3 functions send notifications
- ❌ Triggered by API calls (spam)
- ❌ Duplicate/conflicting alerts
- ❌ User visits page → notification spam

### After:
- ✅ 1 dedicated notification function
- ✅ Triggered once per day (8 AM)
- ✅ Single unified alert
- ✅ User visits page → just gets data (no notifications)

---

## Benefits

1. **Clean Separation:**
   - UI functions = data only
   - Notification function = alerts only

2. **No Spam:**
   - Once per day maximum
   - Redis deduplication

3. **Comprehensive:**
   - Uses restock list (has all data: planned meals + history + inventory + expiry)

4. **No Over-Engineering:**
   - Just adds one simple function
   - Removes notification logic from 2 functions
   - Net result: cleaner, simpler code

5. **Easy to Test:**
   - Call `check_and_send_inventory_alert()` directly
   - Check Redis deduplication
   - Verify notification sent

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│          INVENTORY NOTIFICATION FLOW (SIMPLIFIED)            │
└─────────────────────────────────────────────────────────────┘

Every 30 seconds:
    notification_worker.run()
        │
        ▼
    Is it 8 AM?
        │
        ├─── NO ──▶ Continue checking
        │
        ▼ YES
    _trigger_inventory_alerts()
        │
        ▼
    For each active user:
        │
        ▼
    check_and_send_inventory_alert()
        │
        ▼
    generate_restock_list()  (get comprehensive data)
        │
        ▼
    Check Redis deduplication
        │
        ├─── Already sent today ──▶ Skip
        │
        ▼
    Check if user has inventory
        │
        ├─── No inventory ──▶ Skip
        │
        ▼
    Check if urgent items exist
        │
        ├─── No urgent items ──▶ Skip
        │
        ▼
    Send unified notification
        │
        ▼
    Set Redis flag (24h TTL)
        │
        ▼
    ✅ Done - User gets ONE notification per day
```

### User Experience:

**8:00 AM:** User receives notification
"Urgent: Need 3 items for planned meals: Chicken, Rice, Tomatoes"

**8:05 AM:** User opens inventory dashboard
→ API calls return data
→ NO additional notifications

**10:00 AM:** User opens expiring items page
→ API call returns data
→ NO additional notifications

**Result:** User informed once, can check details anytime without spam ✅

---

## Testing Commands

```bash
# Test the new function directly
docker exec nutrilens-api-1 python -c "
from app.agents.tracking_agent import TrackingAgent
from app.models.database import SessionLocal
import asyncio

db = SessionLocal()
agent = TrackingAgent(db, user_id=223)
result = asyncio.run(agent.check_and_send_inventory_alert())
print(result)
"

# Check Redis key
docker exec nutrilens-redis-1 redis-cli GET "inventory_alert:223:unified:2025-11-07"

# Monitor worker logs
docker logs nutrilens-notification-worker-1 -f | grep "inventory"
```

---

**END OF SIMPLE SOLUTION**
