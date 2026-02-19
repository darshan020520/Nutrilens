# Step-by-Step Execution Plan

**Date:** 2026-01-02

---

## STEP 1: Fix NotificationService - Remove DB Dependency

### What we're fixing:
**Current:** NotificationService takes DB in constructor, uses it for logging
**Target:** NotificationService only uses Redis for queuing

### Changes needed:

#### File: `services/notification_service.py`

**Change 1: Constructor**
```python
# BEFORE
def __init__(self, db: Session):
    self.db = db
    self.redis_client = redis.Redis(...)

# AFTER
def __init__(self):
    self.redis = get_redis_client()  # Use singleton
```

**Change 2: Remove logging calls**
```python
# Find all self._log_notification() calls and remove them
# Logging will happen in consumer process instead
```

**Change 3: Use singleton Redis**
```python
from app.core.redis_client import get_redis_client

# Remove lines 73-78 (creating new Redis client)
# Use get_redis_client() instead
```

### Test:
- NotificationService can be created without DB
- Queuing to Redis still works
- No errors

**Ready for Step 1?**

---

## STEP 2: Create IObserver Interface

### What we're creating:
Simple interface that all observers implement

### New file: `infrastructure/events/observer.py`

```python
from abc import ABC, abstractmethod
from typing import Dict


class IObserver(ABC):
    """Observer interface - all observers must implement update()"""

    @abstractmethod
    async def update(self, event: Dict) -> None:
        """
        Called when EventPublisher publishes an event.

        Args:
            event: {
                "type": "meal_logged",
                "timestamp": "2026-01-02T12:30:00Z",
                "data": {...}
            }
        """
        pass
```

### Test:
- Can create mock observer that implements IObserver
- Interface can be imported

**Ready for Step 2?**

---

## STEP 3: Create EventPublisher

### What we're creating:
Core Observer pattern - maintains observers, notifies them

### New file: `infrastructure/events/event_publisher.py`

```python
import logging
from typing import List, Dict
from datetime import datetime
from infrastructure.events.observer import IObserver

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publisher in Observer pattern - notifies observers of events"""

    def __init__(self):
        self._observers: List[IObserver] = []

    def attach(self, observer: IObserver) -> None:
        """Register an observer"""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: IObserver) -> None:
        """Remove an observer"""
        if observer in self._observers:
            self._observers.remove(observer)

    async def publish(self, event_type: str, data: Dict) -> None:
        """Notify all observers about event"""
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        for observer in self._observers:
            try:
                await observer.update(event)
            except Exception as e:
                logger.error(f"Observer {observer.__class__.__name__} failed: {e}")
```

### Test:
- Can create EventPublisher
- Can attach mock observers
- publish() calls update() on all observers
- Exception in one observer doesn't break others

**Ready for Step 3?**

---

## STEP 4: Create WebSocketObserver

### What we're creating:
Observer that broadcasts events to WebSocket clients

### New file: `infrastructure/observers/websocket_observer.py`

```python
import logging
from typing import Dict
from infrastructure.events.observer import IObserver

logger = logging.getLogger(__name__)


class WebSocketObserver(IObserver):
    """Observer that broadcasts events to WebSocket clients"""

    def __init__(self, websocket_manager):
        """
        Args:
            websocket_manager: Existing ConnectionManager singleton
        """
        self.ws_manager = websocket_manager

    async def update(self, event: Dict) -> None:
        """Broadcast event to user's WebSocket connections"""
        try:
            user_id = event["data"].get("user_id")
            if not user_id:
                logger.warning("Event missing user_id, cannot broadcast to WebSocket")
                return

            await self.ws_manager.broadcast_to_user(
                user_id=user_id,
                message=event
            )
        except Exception as e:
            logger.error(f"WebSocketObserver failed: {e}")
```

### Test:
- Can create WebSocketObserver with mock websocket_manager
- update() extracts user_id and calls broadcast_to_user()
- Handles missing user_id gracefully

**Ready for Step 4?**

---

## STEP 5: Create AchievementService

### What we're creating:
Service that checks achievements with Redis deduplication

### New file: `services/achievement_service.py`

```python
import logging
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.database import MealLog
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class AchievementService:
    """Service for checking user achievements with Redis deduplication"""

    def __init__(self, user_profile_repo: IUserProfileRepository):
        self.user_profile_repo = user_profile_repo
        self.redis = get_redis_client()

    async def check_achievements(
        self,
        user_id: int,
        daily_totals: Dict,
        db: Session  # Passed when called
    ) -> List[Dict]:
        """
        Check all achievements for user.

        Returns:
            List of achievements: [{"type": "streak_7day", "message": "..."}]
        """
        achievements = []
        today = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Check streak
            streak = await self._check_streak(user_id, today, db)
            if streak:
                achievements.append(streak)

            # Check daily completion
            daily = await self._check_daily_completion(user_id, today, db)
            if daily:
                achievements.append(daily)

            # Check nutrition target
            nutrition = await self._check_nutrition_target(user_id, daily_totals, today)
            if nutrition:
                achievements.append(nutrition)

        except Exception as e:
            logger.error(f"Error checking achievements: {e}")

        return achievements

    async def _check_streak(self, user_id: int, today: str, db: Session) -> Dict | None:
        """Check streak achievements"""
        # Count logs in last 7 days
        recent_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.consumed_datetime >= datetime.utcnow() - timedelta(days=7),
                MealLog.consumed_datetime.isnot(None)
            )
        ).count()

        if recent_logs >= 21:  # 3 meals * 7 days
            streak_days = recent_logs // 3

            if streak_days >= 30:
                achievement_type = "streak_30day"
                message = "30-day meal streak!"
            elif streak_days >= 14:
                achievement_type = "streak_14day"
                message = "14-day meal streak!"
            elif streak_days >= 7:
                achievement_type = "streak_7day"
                message = "7-day meal streak!"
            else:
                return None

            # Check deduplication
            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if self.redis.exists(dedup_key):
                return None

            # Mark as sent (24h TTL)
            self.redis.setex(dedup_key, 86400, "1")

            return {"type": achievement_type, "message": message}

        return None

    async def _check_daily_completion(self, user_id: int, today: str, db: Session) -> Dict | None:
        """Check if 3+ meals logged today"""
        today_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.consumed_datetime) == datetime.utcnow().date(),
                MealLog.consumed_datetime.isnot(None)
            )
        ).count()

        if today_logs >= 3:
            dedup_key = f"achievement_sent:{user_id}:daily_completion:{today}"
            if self.redis.exists(dedup_key):
                return None

            self.redis.setex(dedup_key, 86400, "1")
            return {"type": "daily_completion", "message": "All meals logged today!"}

        return None

    async def _check_nutrition_target(self, user_id: int, daily_totals: Dict, today: str) -> Dict | None:
        """Check if protein target hit"""
        protein_consumed = daily_totals.get("protein_g", 0)

        # Get target from user goal
        goal = await self.user_profile_repo.get_active_goal(user_id)
        protein_target = goal.protein_target if goal else 50

        if protein_consumed >= protein_target:
            dedup_key = f"achievement_sent:{user_id}:nutrition_target:{today}"
            if self.redis.exists(dedup_key):
                return None

            self.redis.setex(dedup_key, 86400, "1")
            return {"type": "nutrition_target", "message": f"Protein goal achieved!"}

        return None
```

### Test:
- Can create AchievementService
- check_achievements() returns list of achievement dicts
- Redis deduplication works (second call returns empty list)

**Ready for Step 5?**

---

## STEP 6: Create NotificationObserver

### What we're creating:
Observer that checks achievements and queues notifications

### New file: `infrastructure/observers/notification_observer.py`

```python
import logging
from typing import Dict
from sqlalchemy.orm import Session
from infrastructure.events.observer import IObserver
from services.achievement_service import AchievementService
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class NotificationObserver(IObserver):
    """Observer that checks achievements and queues notifications"""

    def __init__(
        self,
        achievement_service: AchievementService,
        notification_service: NotificationService,
        db_factory  # sessionmaker or get_db function
    ):
        self.achievement_service = achievement_service
        self.notification_service = notification_service
        self.db_factory = db_factory

    async def update(self, event: Dict) -> None:
        """Check achievements and queue notifications"""
        try:
            # Only handle meal_logged
            if event["type"] != "meal_logged":
                return

            user_id = event["data"]["user_id"]
            daily_totals = event["data"].get("daily_totals", {})

            # Get DB session
            db = self.db_factory()
            try:
                # Check achievements
                achievements = await self.achievement_service.check_achievements(
                    user_id=user_id,
                    daily_totals=daily_totals,
                    db=db
                )

                # Queue notification for each achievement
                for achievement in achievements:
                    await self.notification_service.send_achievement(
                        user_id=user_id,
                        achievement_type=achievement["type"],
                        message=achievement["message"],
                        priority="high"
                    )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"NotificationObserver failed: {e}")
```

### Test:
- Can create NotificationObserver
- update() with meal_logged event checks achievements
- Queues notifications for achievements

**Ready for Step 6?**

---

## STEP 7: Update Dependencies

### What we're updating:
Wire everything together in dependency injection

### File: `dependencies.py`

**Add:**
```python
# Singletons
_event_publisher = None
_websocket_observer = None
_notification_observer = None
_achievement_service = None
_notification_service_singleton = None


def get_event_publisher() -> EventPublisher:
    """Get singleton EventPublisher with observers attached"""
    global _event_publisher

    if _event_publisher is None:
        from infrastructure.events.event_publisher import EventPublisher
        from infrastructure.observers.websocket_observer import WebSocketObserver
        from infrastructure.observers.notification_observer import NotificationObserver
        from app.api.websocket import websocket_manager
        from app.models.database import SessionLocal

        # Create publisher
        _event_publisher = EventPublisher()

        # Create and attach WebSocketObserver
        ws_observer = WebSocketObserver(websocket_manager)
        _event_publisher.attach(ws_observer)

        # Create and attach NotificationObserver
        notif_observer = NotificationObserver(
            achievement_service=get_achievement_service_singleton(),
            notification_service=get_notification_service_singleton(),
            db_factory=SessionLocal  # Factory, not instance
        )
        _event_publisher.attach(notif_observer)

    return _event_publisher


def get_achievement_service_singleton() -> AchievementService:
    """Get singleton AchievementService"""
    global _achievement_service

    if _achievement_service is None:
        from services.achievement_service import AchievementService
        from app.models.database import SessionLocal

        # Create with user_profile_repo
        db = SessionLocal()
        try:
            user_profile_repo = UserProfileRepository(db)
            _achievement_service = AchievementService(user_profile_repo)
        finally:
            db.close()

    return _achievement_service


def get_notification_service_singleton() -> NotificationService:
    """Get singleton NotificationService (no DB needed)"""
    global _notification_service_singleton

    if _notification_service_singleton is None:
        from services.notification_service import NotificationService
        _notification_service_singleton = NotificationService()  # No DB

    return _notification_service_singleton
```

### Test:
- Can import get_event_publisher()
- Calling it returns same instance (singleton)
- Has 2 observers attached

**Ready for Step 7?**

---

## STEP 8: Update MealTrackingService to use EventPublisher

### What we're updating:
Replace notification_service with event_publisher

### File: `services/meal_tracking_service.py`

**Change constructor:**
```python
# BEFORE
def __init__(
    self,
    tracking_repo: ITrackingRepository,
    inventory_repo: IInventoryRepository,
    analytics_repo: IConsumptionAnalyticsRepository,
    notification_service: NotificationService
):
    self.notification_service = notification_service

# AFTER
def __init__(
    self,
    tracking_repo: ITrackingRepository,
    inventory_repo: IInventoryRepository,
    analytics_repo: IConsumptionAnalyticsRepository,
    event_publisher: EventPublisher
):
    self.event_publisher = event_publisher
```

**Add after meal logged:**
```python
async def log_meal(...):
    # ... existing code ...

    # Publish event
    await self.event_publisher.publish("meal_logged", {
        "user_id": user_id,
        "meal_log_id": meal_log.id,
        "meal_type": meal_log.meal_type,
        "recipe_name": meal_log.recipe.title if meal_log.recipe else None,
        "daily_totals": daily_totals
    })

    return result
```

### Update dependency:
```python
# In dependencies.py
def get_meal_tracking_service(
    tracking_repo: ITrackingRepository = Depends(get_tracking_repository),
    inventory_repo: IInventoryRepository = Depends(get_inventory_repository),
    analytics_repo: IConsumptionAnalyticsRepository = Depends(get_consumption_analytics_repository),
    event_publisher: EventPublisher = Depends(get_event_publisher)  # Changed
) -> MealTrackingService:
    return MealTrackingService(
        tracking_repo=tracking_repo,
        inventory_repo=inventory_repo,
        analytics_repo=analytics_repo,
        event_publisher=event_publisher  # Changed
    )
```

### Test:
- Meal logging publishes event
- WebSocketObserver broadcasts to WebSocket
- NotificationObserver checks achievements and queues

**Ready for Step 8?**

---

## STEP 9: Test End-to-End

### What we're testing:
Complete flow from API to notifications

### Test case:
1. POST /tracking/log-meal
2. MealTrackingService.log_meal() publishes event
3. WebSocketObserver broadcasts to WebSocket
4. NotificationObserver checks achievements
5. If achievement unlocked, notification queued to Redis
6. Consumer picks up and sends notification

### Verify:
- API returns 200 immediately (doesn't block)
- WebSocket clients receive event
- Redis has notification in queue (if achievement)
- No errors in logs

**Ready for Step 9?**

---

## Which step should we start with?

Tell me and I'll implement that step exactly.
