# Data Mapping Fixes Required

## Issue 1: Daily Summary - Service vs Observer Mismatch

### Service Returns (`ConsumptionService.get_today_summary`)
```python
{
    "success": True,
    "date": "2026-01-09",
    "meals_consumed": 3,  # ✅ MATCHES
    "compliance_rate": 75.0,  # ✅ MATCHES
    "total_calories": 1800,  # ❌ MISMATCH - Observer expects "calories_consumed"
    "total_macros": {
        "calories": 1800,
        "protein_g": 120,  # ❌ MISMATCH - Observer expects this at top level
        "carbs_g": 200,
        "fat_g": 60,
        ...
    },
    ...
}
```

### Observer Expects (`notification_observer.py:236-240`)
```python
{
    "user_id": 123,
    "date": "2026-01-09",  # ✅
    "meals_consumed": 3,  # ✅
    "compliance_rate": 75.0,  # ✅
    "calories_consumed": 1800,  # ❌ Service has "total_calories"
    "protein_g": 120,  # ❌ Service has "total_macros.protein_g"
}
```

### Fix for Worker (`notification_worker.py:198-212`)
```python
if summary.get("success"):
    await self.event_publisher.publish(
        event_type="scheduled_daily_summary",
        data={
            "user_id": user.id,
            "date": summary.get("date"),
            "meals_consumed": summary.get("meals_consumed", 0),
            "compliance_rate": summary.get("compliance_rate", 0.0),
            "calories_consumed": summary.get("total_calories", 0),  # ✅ Map total_calories → calories_consumed
            "protein_g": summary.get("total_macros", {}).get("protein_g", 0),  # ✅ Extract from total_macros
        }
    )
```

---

## Issue 2: Weekly Report - No Direct Data Available

### Service Returns (`ConsumptionService.generate_consumption_analytics`)
```python
{
    "success": True,
    "period_days": 7,
    "total_meals_analyzed": 21,
    "analytics": {
        "meal_timing_patterns": {...},
        "skip_frequency": {...},
        "portion_trends": {...},
        "favorite_recipes": {...},
        "daily_compliance": {...},  # ⚠️ This contains compliance data
        "macro_consistency": {...},
        "weekly_patterns": {...},
        "improvement_insights": {...}
    },
    "generated_at": "2026-01-09T10:30:00"
}
```

### Observer Expects (`notification_observer.py:252-257`)
```python
{
    "user_id": 123,
    "start_date": "2026-01-02",  # ❌ Service doesn't return this
    "end_date": "2026-01-09",  # ❌ Service doesn't return this
    "total_meals": 21,  # ✅ Service has "total_meals_analyzed"
    "average_compliance": 82.0,  # ❌ Need to extract from analytics.daily_compliance
    "weight_change": -1.5,  # ❌ Service doesn't track weight
    "achievements_unlocked": 2,  # ❌ Service doesn't track achievements
}
```

### Problem: Service Doesn't Provide Required Data

The `generate_consumption_analytics` method doesn't return:
1. `start_date` / `end_date` - Worker must calculate these
2. `average_compliance` - Must extract from `analytics.daily_compliance`
3. `weight_change` - Not tracked by consumption service
4. `achievements_unlocked` - Not tracked by consumption service

### Temporary Fix (Calculate Missing Data)
```python
if analytics.get("success"):
    analytics_data = analytics.get("analytics", {})

    # Calculate dates
    from datetime import datetime, timedelta
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=7)

    # Extract average compliance
    daily_compliance = analytics_data.get("daily_compliance", {})
    average_compliance = daily_compliance.get("average_compliance_rate", 0.0)

    await self.event_publisher.publish(
        event_type="scheduled_weekly_report",
        data={
            "user_id": user.id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_meals": analytics.get("total_meals_analyzed", 0),
            "average_compliance": average_compliance,
            "weight_change": 0.0,  # TODO: Integrate with weight tracking service
            "achievements_unlocked": 0,  # TODO: Integrate with achievement service
        }
    )
```

### Long-term Fix: Update ConsumptionService

Add a dedicated `get_weekly_report_data` method that returns exactly what the notification needs:
```python
def get_weekly_report_data(self, user_id: int) -> Dict[str, Any]:
    """Get data specifically for weekly report notification"""
    analytics = self.generate_consumption_analytics(user_id, days=7)

    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=7)

    daily_compliance = analytics["analytics"].get("daily_compliance", {})

    return {
        "success": True,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_meals": analytics.get("total_meals_analyzed", 0),
        "average_compliance": daily_compliance.get("average_compliance_rate", 0.0),
        "weight_change": 0.0,  # TODO: Query weight tracking
        "achievements_unlocked": 0,  # TODO: Query achievements
    }
```

---

## Issue 3: Meal Reminder - Key Name Mismatch

### Worker Sends (`notification_worker.py:159-168`)
```python
{
    "user_id": meal.user_id,
    "meal_type": meal.meal_type,  # ✅
    "recipe_name": meal.recipe.title if meal.recipe else "Your meal",  # ✅
    "time_until_minutes": time_until,  # ❌ Observer expects "time_until"
    "meal_id": meal.id  # ⚠️ Observer doesn't use this
}
```

### Observer Expects (`notification_observer.py:268-272`)
```python
{
    "user_id": 123,
    "meal_type": "lunch",  # ✅
    "recipe_name": "Grilled Chicken",  # ✅
    "time_until": 30,  # ❌ Worker sends "time_until_minutes"
    "scheduled_time": "12:30 PM",  # ❌ Worker doesn't send this
}
```

### Fix for Worker
```python
await self.event_publisher.publish(
    event_type="scheduled_meal_reminder",
    data={
        "user_id": meal.user_id,
        "meal_type": meal.meal_type,
        "recipe_name": meal.recipe.title if meal.recipe else "Your meal",
        "time_until": time_until,  # ✅ Fixed key name
        "scheduled_time": meal.planned_datetime.strftime("%I:%M %p"),  # ✅ Add scheduled time
    }
)
```

---

## Issue 4: Inventory Check - Need to Verify TrackingAgent

### Worker Sends (`notification_worker.py:278-284`)
```python
{
    "user_id": user.id,
    "alerts": result.get("alerts", [])  # ❌ Unknown structure
}
```

### Observer Expects (`notification_observer.py:285-307`)
```python
{
    "user_id": 123,
    "expiring_items": [
        {"name": "Milk", "expiry_date": "2026-01-12"},
        ...
    ],
    "days_until_expiry": 3,
    "low_stock_items": [
        {"name": "Eggs", "quantity": 2},
        ...
    ]
}
```

### Need to Check: TrackingAgent.check_and_send_inventory_alert()

Must verify what structure this method returns and map accordingly.

---

## Summary of Fixes

### Immediate Fixes Required:

1. **Daily Summary** - Map `total_calories` → `calories_consumed` and extract `protein_g` from `total_macros`
2. **Meal Reminder** - Rename `time_until_minutes` → `time_until` and add `scheduled_time`
3. **Weekly Report** - Calculate missing dates and extract compliance from nested analytics
4. **Inventory Check** - Verify TrackingAgent structure and map correctly

### Long-term Improvements:

1. Create dedicated service methods that return data in the exact shape needed by notifications
2. Add data classes/schemas to enforce contracts between producers and consumers
3. Add integration tests that verify end-to-end data flow
