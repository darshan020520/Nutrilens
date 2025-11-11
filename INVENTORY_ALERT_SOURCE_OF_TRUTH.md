# Current Source of Truth for Inventory Alerts - Analysis

**Date:** 2025-11-07
**Purpose:** Identify the exact source of truth for inventory alerts in the current system

---

## CURRENT STATE: Multiple Sources (Fragmented)

Currently, we have **THREE separate sources** triggering inventory alerts, with **NO unified source of truth**:

### 1. Expiring Items Alert

**Location:** [tracking_agent.py:787-813](backend/app/agents/tracking_agent.py:787-813)

**Trigger:** API call to `GET /api/tracking/expiring-items`

**Method:** `check_expiring_items()`

**Logic:**
```python
# Query inventory items with expiry dates
inventory_items = db.query(UserInventory).filter(
    UserInventory.user_id == user_id,
    UserInventory.quantity_grams > 0,
    UserInventory.expiry_date.isnot(None)
).all()

# Filter by urgency
urgent_items = [item for item in expiring_items if item["priority"] == "urgent"]

# Send notification if urgent items exist
if urgent_items:
    await notification_service.send_inventory_alert(
        user_id=user_id,
        alert_type="expiring",
        items=[item["item_name"] for item in urgent_items],
        priority=NotificationPriority.HIGH
    )
```

**Data Source:**
- Inventory items with expiry dates
- Filters items expiring ≤1 day (urgent)
- Smart: Checks if item will be consumed before expiry (via `_get_upcoming_consumption_patterns()`)

**Notification Trigger:** User opens expiring items page → Alert sent

**Status:** ✅ Now has deduplication (after our fixes)

---

### 2. Low Stock Alert

**Location:** [tracking_agent.py:1098-1125](backend/app/agents/tracking_agent.py:1098-1125)

**Trigger:** API call to `GET /api/tracking/inventory-status`

**Method:** `calculate_inventory_status()`

**Logic:**
```python
# Calculate required items based on PAST consumption (last 14 days)
recent_logs = db.query(MealLog).filter(
    MealLog.user_id == user_id,
    MealLog.consumed_datetime >= two_weeks_ago,
    MealLog.recipe_id.isnot(None)
).all()

# Calculate weekly requirement
for log in recent_logs:
    for ingredient in log.recipe.ingredients:
        required_items[item_id] += quantity

# Extrapolate to weekly
weekly_multiplier = 7 / days_of_data
required_items[item_id] = required_items[item_id] * weekly_multiplier * 1.2

# Compare against current inventory
current_inventory = db.query(UserInventory).filter(
    UserInventory.user_id == user_id,
    UserInventory.quantity_grams > 0
).all()

# Find critical items (< 20% stock)
critical_items = [item where (current / required) < 0.20]

# Send notification if critical items exist
if critical_item_names:
    await notification_service.send_inventory_alert(
        user_id=user_id,
        alert_type="low_stock",
        items=critical_item_names,
        priority=NotificationPriority.HIGH
    )
```

**Data Source:**
- ONLY historical consumption (past 14 days)
- Does NOT consider upcoming planned meals
- Extrapolates weekly needs from historical data

**Notification Trigger:** User opens inventory status page → Alert sent

**Status:** ✅ Now has deduplication (after our fixes)

**Issue:** ❌ Doesn't consider planned meals or grocery list

---

### 3. Shopping List (Restock List) - NO ALERTS CURRENTLY

**Location:** [tracking_agent.py:1149-1360](backend/app/agents/tracking_agent.py:1149-1360)

**Trigger:** API call to `GET /api/tracking/restock-list`

**Method:** `generate_restock_list()`

**Logic:**
```python
# STEP 1: Get upcoming planned meals (next 7 days)
upcoming_items = self._get_upcoming_consumption_patterns(seven_days_from_now)

# STEP 2: Get historical consumption (last 30 days)
recent_logs = db.query(MealLog).filter(
    MealLog.consumed_datetime >= two_weeks_ago
).all()

# Calculate historical weekly requirement
historical_weekly = usage_data["total_used"] * weekly_multiplier * 1.2

# STEP 3: Smart recommendation
recommended_stock = max(upcoming_requirement, historical_weekly)

# STEP 4: Calculate shortage
shortage = max(recommended_stock - current_stock, 0)

# STEP 5: Prioritize
if current_stock < upcoming_requirement:
    priority = "urgent"  # Can't cook planned meals
elif stock_percentage < 20:
    priority = "urgent"  # Critically low
elif stock_percentage < 50:
    priority = "soon"
elif stock_percentage < 70 and usage_count >= 3:
    priority = "routine"
```

**Data Source:**
- ✅ Upcoming planned meals (next 7 days)
- ✅ Historical consumption (last 30 days)
- ✅ Current inventory
- ✅ Smart prioritization logic

**Notification Trigger:** ❌ **NONE** - User must manually check the list

**Status:** ⚠️ **Most comprehensive data but NO notifications**

---

## COMPARISON TABLE

| Aspect | Expiring Items | Low Stock Alert | Shopping List (Restock) |
|--------|---------------|-----------------|------------------------|
| **API Endpoint** | `/api/tracking/expiring-items` | `/api/tracking/inventory-status` | `/api/tracking/restock-list` |
| **Method** | `check_expiring_items()` | `calculate_inventory_status()` | `generate_restock_list()` |
| **Data Sources** | Inventory + expiry dates | Historical consumption only | Historical + Planned meals + Inventory |
| **Considers Planned Meals?** | ✅ Yes (smart filter) | ❌ No | ✅ Yes |
| **Considers History?** | ❌ No | ✅ Yes (14 days) | ✅ Yes (30 days) |
| **Considers Inventory?** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Prioritization** | Urgent only (≤1 day) | Critical only (<20%) | Urgent/Soon/Routine/Bulk |
| **Sends Notification?** | ✅ Yes | ✅ Yes | ❌ **NO** |
| **Deduplication?** | ✅ Yes (after our fix) | ✅ Yes (after our fix) | N/A (no notifications) |
| **Comprehensiveness** | Low (expiry only) | Medium (historical only) | ⭐ **HIGH (all data)** |

---

## THE ANSWER: Shopping List Should Be the Source of Truth

### Why Shopping List is Superior:

1. **Most Comprehensive Data:**
   - ✅ Includes upcoming planned meals (what user needs)
   - ✅ Includes historical patterns (what user typically uses)
   - ✅ Includes current inventory (what user has)

2. **Smart Prioritization:**
   - Urgent: Can't cook planned meals OR critically low (<20%)
   - Soon: Running low (<50%)
   - Routine: Medium stock (<70%) for frequently used items
   - Bulk: Opportunities for bulk buying

3. **Already Implemented Logic:**
   - Lines 1305-1320: Comprehensive priority calculation
   - Lines 1249-1263: Smart recommendation combining planned + historical
   - Lines 1272-1285: Stock percentage and days supply calculations

4. **Single Source of Truth:**
   - No need to maintain 3 separate alert systems
   - No conflicting notifications
   - Clear, unified user experience

---

## CURRENT PROBLEM: No Single Source of Truth

### User Experience Issues:

**Scenario 1: User Opens Inventory Dashboard**

```
Step 1: User clicks "Inventory Status"
→ calculate_inventory_status() runs
→ Checks historical consumption only
→ Finds 10 critical items
→ 🔔 Notification: "Critical: 10 items low!"

Step 2: User clicks "Expiring Items"
→ check_expiring_items() runs
→ Finds 3 urgent expiring items
→ 🔔 Notification: "Urgent: 3 items expiring!"

Step 3: User clicks "Shopping List"
→ generate_restock_list() runs
→ Shows 15 urgent items (including planned meals)
→ ❌ NO notification

Result: User gets 2 notifications from incomplete data sources,
        but the most comprehensive source sends no notification!
```

### Development Issues:

- **3 separate codebases** doing similar calculations
- **3 separate maintenance burdens** when logic needs updating
- **Inconsistent results** between different views
- **User confusion** about which list to trust

---

## RECOMMENDED SOLUTION

### Make Shopping List the Single Source of Truth

**Step 1: Use Shopping List for ALL inventory notifications**

```python
# Current (FRAGMENTED):
check_expiring_items() → sends notification
calculate_inventory_status() → sends notification
generate_restock_list() → NO notification

# Proposed (UNIFIED):
generate_restock_list() → SINGLE notification based on priorities
check_expiring_items() → returns data only, NO notification
calculate_inventory_status() → returns data only, NO notification
```

**Step 2: Implement unified notification logic**

```python
async def check_and_send_inventory_alerts(user_id: int):
    """
    Single function to check inventory and send unified alert
    Called once per day via scheduled worker
    """

    # Generate comprehensive shopping list
    restock_data = generate_restock_list(user_id)

    # Check deduplication
    today = datetime.utcnow().strftime("%Y-%m-%d")
    alert_key = f"inventory_alert:{user_id}:unified:{today}"

    if redis.exists(alert_key):
        return  # Already alerted today

    # Check if user tracks inventory
    has_inventory = check_has_inventory(user_id)
    if not has_inventory:
        return  # User doesn't track inventory

    # Determine alert based on priorities
    urgent_count = restock_data.get("urgent_count", 0)
    soon_count = restock_data.get("soon_count", 0)

    if urgent_count > 0:
        # Critical alert: Can't cook planned meals or critically low
        urgent_items = restock_data["restock_list"]["urgent"][:3]

        # Distinguish between "can't cook" vs "critically low"
        cant_cook_items = [
            item for item in urgent_items
            if item.get("reason") == "Needed for planned meals" and
               item.get("current_quantity", 0) < item.get("upcoming_requirement", 0)
        ]

        if cant_cook_items:
            message = f"Urgent: Missing {len(cant_cook_items)} items for planned meals"
        else:
            message = f"Critical: {urgent_count} items critically low"

        await notification_service.send_inventory_alert(
            user_id=user_id,
            alert_type="inventory_urgent",
            items=[item["item_name"] for item in urgent_items],
            message=message,
            priority=NotificationPriority.HIGH
        )

        redis.setex(alert_key, 86400, "1")

    elif soon_count >= 5:
        # Medium priority: Multiple items running low
        await notification_service.send_inventory_alert(
            user_id=user_id,
            alert_type="inventory_low",
            items=[],  # Don't list all items in notification
            message=f"Running low on {soon_count} frequently used items",
            priority=NotificationPriority.NORMAL
        )

        redis.setex(alert_key, 86400, "1")
```

**Step 3: Schedule daily inventory check**

```python
# In notification_worker.py, add:

async def _process_inventory_alerts(self, notification_service, db):
    """Process daily inventory alerts at 8 AM"""
    current_time = datetime.utcnow()
    current_hour = current_time.hour
    current_date = current_time.date()

    if (current_hour == 8 and
        (self.last_inventory_check is None or
         self.last_inventory_check != current_date)):

        # Get all active users
        active_users = db.query(User).filter(User.is_active == True).all()

        for user in active_users:
            try:
                await check_and_send_inventory_alerts(user.id)
            except Exception as e:
                logger.error(f"Error checking inventory for user {user.id}: {e}")

        self.last_inventory_check = current_date
```

---

## BENEFITS OF UNIFIED APPROACH

### For Users:

✅ **Single, clear notification** - No confusion
✅ **Smart prioritization** - Knows what's truly urgent
✅ **Planned meal aware** - Won't spam if they already have grocery list
✅ **Once per day** - No notification spam
✅ **Actionable** - Links directly to shopping list

### For Development:

✅ **Single source of truth** - One place to maintain logic
✅ **Consistent results** - All views use same calculation
✅ **Easier testing** - Test one function instead of three
✅ **Better data quality** - Comprehensive data analysis

### For System:

✅ **Less redundant code** - Remove duplicate logic
✅ **Better performance** - One comprehensive calculation instead of three
✅ **Clearer architecture** - Clear separation of concerns

---

## IMPLEMENTATION PLAN

### Phase 1: Enable Notifications from Shopping List (Immediate)

**File:** `backend/app/agents/tracking_agent.py`

Add notification logic to `generate_restock_list()`:

```python
# At end of generate_restock_list() method (after line 1356):

# Send notification if urgent items exist
if len(restock_list["urgent"]) > 0:
    await self._send_restock_alert(restock_list)
```

Add new helper method:

```python
async def _send_restock_alert(self, restock_list: Dict):
    """Send unified inventory alert based on restock priorities"""

    # Check deduplication
    from app.core.config import settings
    import redis

    redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    alert_key = f"inventory_alert:{self.user_id}:restock:{today}"

    if redis_client.exists(alert_key):
        logger.info(f"⏭️  Restock alert SKIPPED - already sent today")
        return

    # Check if user has inventory
    has_inventory = self.db.query(UserInventory).filter(
        UserInventory.user_id == self.user_id
    ).first()

    if not has_inventory:
        logger.info(f"⏭️  Restock alert SKIPPED - user has no inventory")
        return

    # Send notification for urgent items
    urgent_items = restock_list.get("urgent", [])[:3]  # Top 3

    if urgent_items:
        item_names = [item["item_name"] for item in urgent_items]
        urgent_count = len(restock_list.get("urgent", []))

        await self.notification_service.send_inventory_alert(
            user_id=self.user_id,
            alert_type="restock_urgent",
            items=item_names,
            priority=NotificationPriority.HIGH
        )

        redis_client.setex(alert_key, 86400, "1")
        logger.info(f"✅ Restock alert sent for {urgent_count} urgent items")
```

### Phase 2: Disable Notifications from Other Sources (Week 1)

**Modify:** `check_expiring_items()` and `calculate_inventory_status()`

Remove notification sending logic, keep data calculation only:

```python
# In check_expiring_items() - REMOVE lines 787-813 (notification sending)
# Keep everything else (data calculation)

# In calculate_inventory_status() - REMOVE lines 1098-1125 (notification sending)
# Keep everything else (data calculation)
```

**Reason:** Shopping list already includes expiring items in its urgent calculation

### Phase 3: Add Scheduled Daily Check (Week 2)

Add to `notification_worker.py` as described above.

---

## SUMMARY

### Current State:
- ❌ **NO single source of truth**
- ❌ Three separate alert systems
- ❌ Conflicting notifications
- ❌ Shopping list has best data but sends NO notifications
- ❌ Other sources have incomplete data but DO send notifications

### Recommended State:
- ✅ **Shopping List = Single Source of Truth**
- ✅ One unified alert system
- ✅ Comprehensive data (planned + historical + inventory)
- ✅ Smart prioritization (urgent/soon/routine)
- ✅ Once per day notification
- ✅ Deduplication built-in

### Answer to Your Question:

**"What is the current source of truth for inventory alerts?"**

**Answer:** There is NO single source of truth currently. We have THREE fragmented sources:

1. **Expiring Items** - Sends alerts (but limited data)
2. **Low Stock** - Sends alerts (but limited data)
3. **Shopping List** - NO alerts (but has ALL the data) ⭐

**The Shopping List SHOULD BE the source of truth** because it already has:
- ✅ All the data (planned + historical + inventory)
- ✅ Smart prioritization logic
- ✅ Comprehensive calculations
- ❌ Just missing the notification trigger (easy to add)

---

**END OF ANALYSIS**
