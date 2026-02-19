# CRITICAL: Inventory Alert Architecture Violation

## Problem

The `NotificationWorker._trigger_inventory_alerts()` method calls `TrackingAgent.check_and_send_inventory_alert()`, which **directly sends notifications** via the old NotificationService instead of publishing events through EventPublisher.

This completely bypasses the new clean architecture!

## Current Flow (WRONG)

```
APScheduler
    ↓
NotificationWorker._trigger_inventory_alerts()
    ↓
TrackingAgent.check_and_send_inventory_alert()
    ↓
NotificationService.send_inventory_alert() ❌ BYPASSES EventPublisher!
    ↓
Redis Queue
    ↓
NotificationConsumer
```

## Should Be

```
APScheduler
    ↓
NotificationWorker._trigger_inventory_alerts()
    ↓
TrackingAgent.check_inventory_status() (NEW METHOD - just returns data)
    ↓
EventPublisher.publish("scheduled_inventory_check", data)
    ↓
NotificationObserver._handle_inventory_check()
    ↓
Creates 2 notifications: expiry_alert + low_stock_alert
    ↓
Redis Queue
    ↓
NotificationConsumer
```

## Root Cause

`TrackingAgent.check_and_send_inventory_alert()` was created BEFORE the EventPublisher architecture and directly calls NotificationService.

## Solution

### Option 1: Create New TrackingAgent Method (RECOMMENDED)

Create a new method that ONLY returns data without sending notifications:

```python
# backend/app/agents/tracking_agent.py

async def get_inventory_alert_data(self) -> Dict:
    """
    Get inventory alert data for event publishing.
    Does NOT send notifications - just returns data.

    Returns:
        {
            "success": True,
            "expiring_items": [
                {"name": "Milk", "expiry_date": "2026-01-12", "days_left": 3},
                ...
            ],
            "days_until_expiry": 3,
            "low_stock_items": [
                {"name": "Eggs", "quantity": 2, "urgency": "high"},
                ...
            ]
        }
    """
    try:
        # Get expiring items
        expiring_result = await self.check_expiring_items(filter_mode="both", days_threshold=3)
        expiring_items = []

        if expiring_result.get("success"):
            urgent_expiring = [item for item in expiring_result.get("expiring_items", [])
                              if item.get("priority") == "urgent"]

            expiring_items = [
                {
                    "name": item["item_name"],
                    "expiry_date": item["expiry_date"],
                    "days_left": item["days_until_expiry"]
                }
                for item in urgent_expiring
            ]

        # Get low stock items
        restock_data = self.generate_restock_list()
        low_stock_items = []

        if restock_data.get("success"):
            urgent_items = restock_data.get("restock_list", {}).get("urgent", [])

            low_stock_items = [
                {
                    "name": item["item_name"],
                    "quantity": item.get("current_quantity", 0),
                    "urgency": "high"
                }
                for item in urgent_items
            ]

        return {
            "success": True,
            "expiring_items": expiring_items,
            "days_until_expiry": 3,
            "low_stock_items": low_stock_items
        }

    except Exception as e:
        logger.error(f"Error getting inventory alert data: {str(e)}")
        return {"success": False, "error": str(e)}
```

### Option 2: Refactor Existing Method (BREAKING CHANGE)

Rename `check_and_send_inventory_alert()` to `check_inventory_status()` and remove the notification sending:

```python
# backend/app/agents/tracking_agent.py

async def check_inventory_status(self) -> Dict:
    """
    Check inventory status and return data (does NOT send notifications).

    Replaces: check_and_send_inventory_alert()
    Breaking change: Removes direct notification sending
    """
    # ... same logic but return data instead of sending notifications
```

Then create a migration script to update any existing code that calls the old method.

## Recommended Action

**Use Option 1** - Create a new method and deprecate the old one:

1. Create `get_inventory_alert_data()` method
2. Update `NotificationWorker._trigger_inventory_alerts()` to use new method
3. Mark `check_and_send_inventory_alert()` as deprecated
4. Plan migration to remove old method in future release

This allows backward compatibility while moving to clean architecture.

## Worker Code Update

```python
# backend/app/workers/notification_worker.py

async def _trigger_inventory_alerts(self):
    """
    Trigger inventory alert events via EventPublisher.

    Checks inventory status for all active users and publishes events.
    """
    db = self.session_factory()
    try:
        from app.agents.tracking_agent import TrackingAgent

        active_users = db.query(User).filter(User.is_active == True).all()
        alert_count = 0

        for user in active_users:
            try:
                tracking_agent = TrackingAgent(db, user.id)

                # Use NEW method that only returns data
                inventory_data = await tracking_agent.get_inventory_alert_data()

                if inventory_data.get("success"):
                    # Only publish if there are alerts
                    has_expiring = len(inventory_data.get("expiring_items", [])) > 0
                    has_low_stock = len(inventory_data.get("low_stock_items", [])) > 0

                    if has_expiring or has_low_stock:
                        # Publish event via EventPublisher
                        await self.event_publisher.publish(
                            event_type="scheduled_inventory_check",
                            data={
                                "user_id": user.id,
                                "expiring_items": inventory_data.get("expiring_items", []),
                                "days_until_expiry": inventory_data.get("days_until_expiry", 3),
                                "low_stock_items": inventory_data.get("low_stock_items", []),
                            }
                        )
                        alert_count += 1
                        logger.info(f"Inventory alert event published for user {user.id}")

            except Exception as e:
                logger.error(f"Error publishing inventory alert for user {user.id}: {str(e)}")

        if alert_count > 0:
            logger.info(f"Published inventory alert events for {alert_count} users")

    except Exception as e:
        logger.error(f"Error in _trigger_inventory_alerts: {str(e)}")
    finally:
        db.close()
```

## Impact Analysis

### Files to Modify:
1. `backend/app/agents/tracking_agent.py` - Add `get_inventory_alert_data()` method
2. `backend/app/workers/notification_worker.py` - Update `_trigger_inventory_alerts()` to use new method

### Files to Check for Old Method Usage:
```bash
grep -r "check_and_send_inventory_alert" backend/
```

Need to ensure no other code is calling the old method directly.

### Breaking Changes:
None if we use Option 1 (create new method alongside old one).

### Migration Path:
1. Create new method
2. Update worker to use new method
3. Test end-to-end flow
4. Mark old method as deprecated
5. Plan removal in v2.0

## Testing Required

1. **Unit Test**: `TrackingAgent.get_inventory_alert_data()` returns correct structure
2. **Integration Test**: Worker → EventPublisher → Observer → Redis → Consumer flow
3. **E2E Test**: Scheduled task triggers and sends inventory alerts correctly

## Priority

**CRITICAL** - This must be fixed before the new architecture is considered complete. Otherwise, inventory alerts will continue using old architecture and bypassing EventPublisher.
