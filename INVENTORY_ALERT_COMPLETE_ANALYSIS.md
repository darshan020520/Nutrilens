# Complete Inventory Alert Function and Logic Analysis

## 1. What `check_and_send_inventory_alert()` Actually Does

**Location:** `backend/app/agents/tracking_agent.py:1314-1393`

### Business Logic Breakdown:

```
1. Call check_expiring_items(filter_mode="both", days_threshold=3)
   └─> Returns items expiring in 3 days with "urgent" priority

2. Filter for URGENT items only
   └─> urgent_expiring = [item for item in expiring_items if priority == "urgent"]

3. If urgent_expiring items exist:
   └─> Check Redis deduplication (once per day)
   └─> Send notification via OLD NotificationService
   └─> Set Redis key with 86400s (24h) TTL

4. Call generate_restock_list()
   └─> Returns items categorized by urgency (urgent/soon/routine)

5. Get URGENT count from restock_list
   └─> urgent_count = restock_data.get("urgent_count", 0)

6. If urgent_count > 0:
   └─> Check Redis deduplication (once per day)
   └─> Send notification via OLD NotificationService
   └─> Set Redis key with 86400s (24h) TTL

7. Return summary of alerts sent
```

### Key Data Points:

**Input:** None (uses self.user_id)

**Calls These Methods:**
1. `check_expiring_items(filter_mode="both", days_threshold=3)`
2. `generate_restock_list()`

**Filters Applied:**
1. Expiring items: Only `priority == "urgent"`
2. Restock items: Only `urgent` category items

**Deduplication:**
- Redis keys: `inventory_alert:{user_id}:expiring:{date}` and `inventory_alert:{user_id}:restock:{date}`
- TTL: 86400 seconds (24 hours)
- Ensures: One alert per type per day per user

**Notification Sent Via:**
- OLD `NotificationService.send_inventory_alert()`
- Alert types: "expiring" or "low_stock"
- Priority: `NotificationPriority.HIGH`

**Output:**
```python
{
    "success": True,
    "sent": True,
    "alerts": ["expiring: 3 items", "restock: 5 items"]
}
# OR
{
    "success": True,
    "skipped": True,
    "reason": "no_urgent_items"
}
```

---

## 2. Same Logic in NEW Architecture

### Service: `InventoryManagementService`

**Location:** `backend/app/services/inventory_management_service.py`

#### Method 1: `check_expiring_items()` - Lines 258-413

**Signature:**
```python
async def check_expiring_items(
    self,
    user_id: int,
    filter_mode: str = "both",
    days_threshold: int = 3
) -> Dict[str, Any]
```

**Returns:**
```python
{
    "success": True,
    "expiring_count": 5,
    "expiring_items": [
        {
            "inventory_id": 123,
            "item_name": "Milk",
            "item_id": 456,
            "quantity_grams": 1000.0,
            "expiry_date": "2026-01-12",
            "days_remaining": 3,
            "priority": "urgent",  # or "high", "medium"
            "category": "dairy",
            "consumption_pattern": {...}
        },
        ...
    ],
    "recommendations": ["Use milk before Jan 12", ...],
    "recipe_suggestions": [...],
    "summary": {
        "urgent": 2,
        "high": 2,
        "medium": 1
    }
}
```

**Source:** Extracted from `TrackingAgent.check_expiring_items()` at line 682-821

#### Method 2: `generate_restock_list()` - Lines 414-720

**Signature:**
```python
async def generate_restock_list(self, user_id: int) -> Dict[str, Any]
```

**Returns:**
```python
{
    "success": True,
    "total_items": 15,
    "urgent_count": 5,
    "soon_count": 6,
    "routine_count": 4,
    "bulk_opportunities": 2,
    "restock_list": {
        "urgent": [
            {
                "item_id": 789,
                "item_name": "Eggs",
                "category": "protein",
                "current_quantity": 2.0,
                "recommended_quantity": 12.0,
                "priority": "urgent",
                "usage_frequency": 7,
                "days_until_depleted": 1
            },
            ...
        ],
        "soon": [...],
        "routine": [...],
        "bulk_opportunities": [...]
    },
    "estimated_cost": 125.50,
    "shopping_strategy": [...],
    "analysis_period": "30 days of consumption data"
}
```

**Source:** Extracted from `TrackingAgent.generate_restock_list()` at line 1100-1311

---

## 3. V2 Endpoints Already Using This Logic

### Endpoint 1: GET `/tracking/v2/expiring-items`

**Location:** `backend/app/api/tracking_v2.py:460-520`

**Implementation:**
```python
@router.get("/expiring-items", response_model=ExpiringItemsResponse)
async def get_expiring_items(
    days: int = Query(default=3, ge=1, le=30),
    filter_mode: str = Query(default="both", regex="^(date_only|consumption_only|both)$"),
    current_user: User = Depends(get_current_user),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service)
):
    # Use inventory service for expiry detection
    result = await inventory_service.check_expiring_items(
        user_id=current_user.id,
        filter_mode=filter_mode,
        days_threshold=days
    )

    return ExpiringItemsResponse(
        total_expiring=result.get("expiring_count", 0),
        urgent_count=summary.get("urgent", 0),
        high_priority_count=summary.get("high", 0),
        medium_priority_count=summary.get("medium", 0),
        items=result.get("expiring_items", []),
        action_recommendations=result.get("recommendations", [])
    )
```

**Confirms:** Same business logic, same service method, just returns as API response.

---

### Endpoint 2: GET `/tracking/v2/restock-list`

**Location:** `backend/app/api/tracking_v2.py:523-571`

**Implementation:**
```python
@router.get("/restock-list", response_model=RestockListResponse)
async def get_restock_list(
    current_user: User = Depends(get_current_user),
    inventory_service: InventoryManagementService = Depends(get_inventory_management_service)
):
    # Use inventory service for restock analysis
    result = await inventory_service.generate_restock_list(
        user_id=current_user.id
    )

    return RestockListResponse(
        total_items=result.get("total_items", 0),
        urgent_items=restock_list.get("urgent", []),
        soon_items=restock_list.get("soon", []),
        routine_items=restock_list.get("routine", []),
        estimated_total_cost=result.get("estimated_cost", 0),
        shopping_strategy=result.get("shopping_strategy", [])
    )
```

**Confirms:** Same business logic, same service method, just returns as API response.

---

## 4. Exact Mapping for Notification Worker

### What Notification Needs:

**From Observer:** `notification_observer.py:276-307`

```python
async def _handle_inventory_check(self, event_data: Dict) -> None:
    user_id = event_data.get("user_id")

    # Create expiry alert if items expiring
    expiring_items = event_data.get("expiring_items", [])
    # Expected format: [{"name": "Milk", "expiry_date": "2026-01-12", "days_left": 3}, ...]

    if expiring_items:
        await self._create_and_queue_notification(
            notification_type="expiry_alert",
            user_id=user_id,
            metadata={
                "expiring_items": expiring_items,
                "days_until_expiry": event_data.get("days_until_expiry", 3),
                "item_count": len(expiring_items),
            }
        )

    # Create low stock alert if items low
    low_stock_items = event_data.get("low_stock_items", [])
    # Expected format: [{"name": "Eggs", "quantity": 2, "urgency": "high"}, ...]

    if low_stock_items:
        await self._create_and_queue_notification(
            notification_type="low_stock_alert",
            user_id=user_id,
            metadata={
                "low_stock_items": low_stock_items,
                "item_count": len(low_stock_items),
            }
        )
```

### Data Transformation Required:

**From `check_expiring_items()` to `expiring_items` for notification:**

```python
# Service returns
{
    "expiring_items": [
        {
            "item_name": "Milk",
            "expiry_date": "2026-01-12",
            "days_remaining": 3,
            "priority": "urgent",
            ...
        }
    ],
    "summary": {"urgent": 2, "high": 1, "medium": 0}
}

# Filter and map to
expiring_items_for_notification = [
    {
        "name": item["item_name"],
        "expiry_date": item["expiry_date"],
        "days_left": item["days_remaining"]
    }
    for item in result["expiring_items"]
    if item["priority"] == "urgent"  # ONLY urgent items
]
```

**From `generate_restock_list()` to `low_stock_items` for notification:**

```python
# Service returns
{
    "restock_list": {
        "urgent": [
            {
                "item_name": "Eggs",
                "current_quantity": 2.0,
                "priority": "urgent",
                ...
            }
        ]
    },
    "urgent_count": 5
}

# Map to
low_stock_items_for_notification = [
    {
        "name": item["item_name"],
        "quantity": item["current_quantity"],
        "urgency": "high"  # All urgent items get "high" urgency
    }
    for item in result["restock_list"]["urgent"]
]
```

---

## 5. Complete Solution for NotificationWorker

### What Worker Should Do:

```python
async def _trigger_inventory_alerts(self):
    """
    Trigger inventory alert events via EventPublisher.

    Uses InventoryManagementService (NEW architecture) to get data,
    then publishes events via EventPublisher.
    """
    db = self.session_factory()
    try:
        from app.services.inventory_management_service import InventoryManagementService
        from app.repositories.inventory_repository import InventoryRepository
        from app.repositories.tracking_repository import TrackingRepository
        import redis

        # Initialize service with repositories (clean architecture)
        inventory_repo = InventoryRepository(db)
        tracking_repo = TrackingRepository(db)
        inventory_service = InventoryManagementService(inventory_repo, tracking_repo, db)

        # Redis for deduplication
        redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        today = datetime.utcnow().strftime("%Y-%m-%d")

        active_users = db.query(User).filter(User.is_active == True).all()
        alert_count = 0

        for user in active_users:
            try:
                # Check deduplication FIRST (infrastructure concern)
                dedup_key = f"inventory_alert:{user.id}:{today}"
                if redis_client.exists(dedup_key):
                    continue

                # 1. Get expiring items (BUSINESS LOGIC via service)
                expiring_result = await inventory_service.check_expiring_items(
                    user_id=user.id,
                    filter_mode="both",
                    days_threshold=3
                )

                # 2. Get restock items (BUSINESS LOGIC via service)
                restock_result = await inventory_service.generate_restock_list(
                    user_id=user.id
                )

                # 3. Filter and transform data for notification
                expiring_items = []
                if expiring_result.get("success"):
                    urgent_expiring = [
                        item for item in expiring_result.get("expiring_items", [])
                        if item.get("priority") == "urgent"
                    ]

                    expiring_items = [
                        {
                            "name": item["item_name"],
                            "expiry_date": item["expiry_date"],
                            "days_left": item["days_remaining"]
                        }
                        for item in urgent_expiring
                    ]

                low_stock_items = []
                if restock_result.get("success"):
                    urgent_restock = restock_result.get("restock_list", {}).get("urgent", [])

                    low_stock_items = [
                        {
                            "name": item["item_name"],
                            "quantity": item["current_quantity"],
                            "urgency": "high"
                        }
                        for item in urgent_restock
                    ]

                # 4. Only publish if there are alerts
                if len(expiring_items) > 0 or len(low_stock_items) > 0:
                    # Publish event via EventPublisher
                    await self.event_publisher.publish(
                        event_type="scheduled_inventory_check",
                        data={
                            "user_id": user.id,
                            "expiring_items": expiring_items,
                            "days_until_expiry": 3,
                            "low_stock_items": low_stock_items,
                        }
                    )

                    # Mark as sent (deduplication)
                    redis_client.setex(dedup_key, 86400, "1")
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

---

## 6. Summary

### Business Logic Location:

| Function | TrackingAgent (OLD) | NEW Architecture | Used in V2 API? |
|----------|---------------------|------------------|-----------------|
| Check expiring items | `TrackingAgent.check_expiring_items()` | `InventoryManagementService.check_expiring_items()` | ✅ YES - `/tracking/v2/expiring-items` |
| Generate restock list | `TrackingAgent.generate_restock_list()` | `InventoryManagementService.generate_restock_list()` | ✅ YES - `/tracking/v2/restock-list` |
| Send notifications | `TrackingAgent.check_and_send_inventory_alert()` | ❌ NOT MIGRATED | ❌ NO |

### Key Finding:

**The exact same business logic already exists in the new architecture and is being used by v2 API endpoints.**

We just need to:
1. Use `InventoryManagementService` instead of `TrackingAgent`
2. Apply the same filters (urgent items only)
3. Transform data to notification format
4. Publish via EventPublisher

**NO NEW LOGIC NEEDED** - just wire up existing service to notification system.

---

## 7. Files to Modify

**ONLY ONE FILE:**
- `backend/app/workers/notification_worker.py:286-325` - Replace TrackingAgent with InventoryManagementService

**NO OTHER FILES NEED CHANGES** - Service, repository, observer, consumer already correct.
