# Final Revised Notification Architecture Plan

**Date:** 2026-01-02
**After thorough code review**

---

## EXISTING CODE STATE (Facts)

### 1. WebSocket Manager
**File:** `services/websocket_manager.py`
- **Line 432:** Singleton instance: `websocket_manager = ConnectionManager()`
- **Line 29-30:** Stores connections: `{user_id: [WebSocket, WebSocket]}`
- **Line 169:** `broadcast_to_user(user_id, message)` - sends to specific user
- **Line 56-61:** Creates its own Redis client (WRONG - should use `get_redis_client()`)

### 2. Redis Client
**File:** `core/redis_client.py`
- **Line 17-42:** Singleton `get_redis_client()` - CORRECT way
- **Used by:** Normalizer, some services
- **NOT used by:** WebSocket manager, NotificationService (they create their own - WRONG)

### 3. Dependencies
**File:** `dependencies.py`
- **Line 323-325:** `get_notification_service(db: Session = Depends(get_db))`
- **Line 382-393:** `get_meal_event_publisher()` - Singleton with websocket_manager=None, event_bus=None
- **Line 397-415:** Orchestrator gets: meal_tracking, notification_service, event_publisher, db

### 4. MealTrackingService
**File:** `services/meal_tracking_service.py`
- **Line 41:** Takes `notification_service` in constructor
- **Line 55:** Stores it: `self.notification_service = notification_service`
- **FACT:** Never actually uses it (grep shows only assignment)

### 5. Current MealEventPublisher
**File:** `events/meal_events.py`
- **Line 32:** `__init__(self, websocket_manager=None, event_bus=None)`
- **Line 390-391:** Always created with None, None
- **Line 72-77:** Sends to WebSocket AND event_bus (but event_bus is always None)
- **Problem:** event_bus is dead code

---

## REVISED ARCHITECTURE (Clean)

### Component 1: EventPublisher (NEW - replaces MealEventPublisher)

**File:** `infrastructure/events/event_publisher.py`

**Purpose:** Core Observer pattern - notify observers of events

**Code:**
```python
from typing import List, Dict
from infrastructure.events.observer import IObserver

class EventPublisher:
    """
    Publisher in Observer pattern.
    Maintains list of observers, notifies them when events occur.
    """

    def __init__(self):
        self._observers: List[IObserver] = []

    def attach(self, observer: IObserver) -> None:
        """Register an observer"""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: IObserver) -> None:
        """Remove an observer"""
        self._observers.remove(observer)

    async def publish(self, event_type: str, data: Dict) -> None:
        """
        Notify all observers about event.

        Args:
            event_type: "meal_logged", "meal_skipped", etc.
            data: Event data (user_id, meal info, daily_totals, etc.)
        """
        from datetime import datetime

        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        # Notify all observers (don't let one failure stop others)
        for observer in self._observers:
            try:
                await observer.update(event)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"Observer {observer.__class__.__name__} failed: {e}"
                )
```

**Why this code:**
- Simple list of observers
- try/except prevents one observer breaking others
- No transformation of data, just wraps in event structure
- No interface (EventPublisher) - not needed yet (YAGNI)

**Dependencies:** None (just IObserver interface)

**Created:** Once at startup (singleton)

---

### Component 2: IObserver (Interface)

**File:** `infrastructure/events/observer.py`

**Purpose:** Contract all observers must implement

**Code:**
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
                "data": {...}  # Event-specific data
            }
        """
        pass
```

**Why this code:**
- ABC with one method
- Push model (event data given to observer)
- Simple, no over-engineering

---

### Component 3: WebSocketObserver (Concrete Observer)

**File:** `infrastructure/observers/websocket_observer.py`

**Purpose:** Broadcast events to WebSocket clients

**Code:**
```python
from typing import Dict
from infrastructure.events.observer import IObserver
from services.websocket_manager import ConnectionManager


class WebSocketObserver(IObserver):
    """
    Observer that broadcasts events to WebSocket clients.
    Wraps existing ConnectionManager.
    """

    def __init__(self, websocket_manager: ConnectionManager):
        """
        Args:
            websocket_manager: Existing singleton WebSocket manager
        """
        self.ws_manager = websocket_manager

    async def update(self, event: Dict) -> None:
        """
        Broadcast event to user's WebSocket connections.

        Args:
            event: Event dict from EventPublisher
        """
        # Extract user_id
        user_id = event["data"].get("user_id")
        if not user_id:
            return

        # Broadcast to all user's WebSocket connections
        await self.ws_manager.broadcast_to_user(
            user_id=user_id,
            message=event  # Send entire event dict
        )
```

**Why this code:**
- Wrapper around existing websocket_manager
- Extracts user_id from event
- Calls existing broadcast_to_user() method
- No new logic, just adapts interface

**Dependencies:** `websocket_manager` (existing singleton from `websocket.py`)

**Created:** Once at startup

---

### Component 4: NotificationObserver (Concrete Observer)

**File:** `infrastructure/observers/notification_observer.py`

**Purpose:** Check achievements, queue notifications

**Code:**
```python
from typing import Dict
from infrastructure.events.observer import IObserver
from services.achievement_service import AchievementService
from services.notification_service import NotificationService


class NotificationObserver(IObserver):
    """
    Observer that checks for achievements and queues notifications.
    Coordinates between AchievementService and NotificationService.
    """

    def __init__(
        self,
        achievement_service: AchievementService,
        notification_service: NotificationService
    ):
        """
        Args:
            achievement_service: Service that checks achievements
            notification_service: Service that queues notifications to Redis
        """
        self.achievement_service = achievement_service
        self.notification_service = notification_service

    async def update(self, event: Dict) -> None:
        """
        React to events by checking achievements and queuing notifications.

        Args:
            event: Event dict from EventPublisher
        """
        # Only handle meal_logged events
        if event["type"] != "meal_logged":
            return

        # Extract data
        user_id = event["data"]["user_id"]
        daily_totals = event["data"].get("daily_totals", {})

        # Check for achievements
        achievements = await self.achievement_service.check_achievements(
            user_id=user_id,
            daily_totals=daily_totals
        )

        # Queue notification for each achievement
        for achievement in achievements:
            await self.notification_service.send_achievement(
                user_id=user_id,
                achievement_type=achievement["type"],
                message=achievement["message"],
                priority="high"
            )
```

**Why this code:**
- Filters for "meal_logged" events only
- Delegates achievement checking to AchievementService
- Delegates queuing to existing NotificationService
- Just coordination, no business logic

**Dependencies:**
- AchievementService (NEW - see Component 5)
- NotificationService (EXISTING - from notification_service.py)

**Created:** Once at startup

---

### Component 5: AchievementService (NEW Service)

**File:** `services/achievement_service.py`

**Purpose:** Check if user unlocked achievements with Redis deduplication

**Code:**
```python
import logging
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.database import MealLog
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository
from app.core.redis_client import get_redis_client  # Use singleton

logger = logging.getLogger(__name__)


class AchievementService:
    """
    Service for checking user achievements.

    Responsibilities:
    - Check streak achievements (7-day, 14-day, 30-day)
    - Check daily completion (3 meals logged)
    - Check nutrition targets (protein goal)
    - Redis deduplication (send each achievement once per day)
    """

    def __init__(
        self,
        user_profile_repo: IUserProfileRepository
    ):
        """
        Args:
            user_profile_repo: Repository for user preferences/goals
        """
        self.user_profile_repo = user_profile_repo
        self.redis = get_redis_client()  # Use singleton Redis client

    async def check_achievements(
        self,
        user_id: int,
        daily_totals: Dict,
        db: Session  # Passed when called, not stored
    ) -> List[Dict]:
        """
        Check all achievements for user.

        Args:
            user_id: User ID
            daily_totals: Today's nutrition totals
            db: Database session

        Returns:
            List of achievements: [{"type": "streak_7day", "message": "..."}]
        """
        achievements = []
        today = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Check streak achievements
            streak_achievement = await self._check_streak(user_id, today, db)
            if streak_achievement:
                achievements.append(streak_achievement)

            # Check daily completion
            daily_achievement = await self._check_daily_completion(user_id, today, db)
            if daily_achievement:
                achievements.append(daily_achievement)

            # Check nutrition target
            nutrition_achievement = await self._check_nutrition_target(
                user_id, daily_totals, today
            )
            if nutrition_achievement:
                achievements.append(nutrition_achievement)

        except Exception as e:
            logger.error(f"Error checking achievements for user {user_id}: {e}")

        return achievements

    async def _check_streak(
        self, user_id: int, today: str, db: Session
    ) -> Dict | None:
        """Check streak achievements (7-day, 14-day, 30-day)"""

        # Count meal logs in last 7 days
        recent_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.consumed_datetime >= datetime.utcnow() - timedelta(days=7),
                MealLog.consumed_datetime.isnot(None)
            )
        ).count()

        if recent_logs >= 21:  # 3 meals * 7 days
            streak_days = recent_logs // 3

            # Determine achievement type
            if streak_days >= 30:
                achievement_type = "streak_30day"
                message = "Incredible! 30-day meal streak - habit mastery!"
            elif streak_days >= 14:
                achievement_type = "streak_14day"
                message = "Amazing! 14-day meal streak - you're on fire!"
            elif streak_days >= 7:
                achievement_type = "streak_7day"
                message = "7-day meal logging streak! Building lasting habits!"
            else:
                return None

            # Check Redis deduplication
            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if self.redis.exists(dedup_key):
                return None  # Already sent today

            # Mark as sent (24h TTL)
            self.redis.setex(dedup_key, 86400, "1")

            return {"type": achievement_type, "message": message}

        return None

    async def _check_daily_completion(
        self, user_id: int, today: str, db: Session
    ) -> Dict | None:
        """Check if user logged 3+ meals today"""

        today_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                func.date(MealLog.consumed_datetime) == datetime.utcnow().date(),
                MealLog.consumed_datetime.isnot(None)
            )
        ).count()

        if today_logs >= 3:
            achievement_type = "daily_completion"

            # Check deduplication
            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if self.redis.exists(dedup_key):
                return None

            # Mark as sent
            self.redis.setex(dedup_key, 86400, "1")

            return {
                "type": achievement_type,
                "message": "Perfect day! All meals logged - crushing your goals!"
            }

        return None

    async def _check_nutrition_target(
        self, user_id: int, daily_totals: Dict, today: str
    ) -> Dict | None:
        """Check if user hit protein target"""

        protein_consumed = daily_totals.get("protein_g", 0)

        # Get user's protein target from their goal
        goal = await self.user_profile_repo.get_active_goal(user_id)
        protein_target = goal.protein_target if goal else 50  # Default 50g

        if protein_consumed >= protein_target:
            achievement_type = "nutrition_target"

            # Check deduplication
            dedup_key = f"achievement_sent:{user_id}:{achievement_type}:{today}"
            if self.redis.exists(dedup_key):
                return None

            # Mark as sent
            self.redis.setex(dedup_key, 86400, "1")

            return {
                "type": achievement_type,
                "message": f"Protein goal achieved! Hit {int(protein_consumed)}g target!"
            }

        return None
```

**Why this code:**
- Extracted from tracking_agent.py (same logic)
- Uses singleton `get_redis_client()` (CORRECT)
- Doesn't store DB session (gets it when needed)
- Redis deduplication same as before
- Gets protein target from user goal (not hardcoded)

**Dependencies:**
- IUserProfileRepository (existing)
- Redis via `get_redis_client()` (existing singleton)
- Database session (passed when called, not stored)

**Created:** Once at startup

---

## DEPENDENCY INJECTION CHANGES

**File:** `dependencies.py`

### Add these functions:

```python
# Singleton instances
_event_publisher = None
_websocket_observer = None
_notification_observer = None


def get_event_publisher() -> EventPublisher:
    """Get singleton EventPublisher with observers attached"""
    global _event_publisher, _websocket_observer, _notification_observer

    if _event_publisher is None:
        from infrastructure.events.event_publisher import EventPublisher
        from infrastructure.observers.websocket_observer import WebSocketObserver
        from infrastructure.observers.notification_observer import NotificationObserver
        from app.api.websocket import websocket_manager  # Existing singleton

        # Create publisher
        _event_publisher = EventPublisher()

        # Create and attach WebSocketObserver
        _websocket_observer = WebSocketObserver(websocket_manager)
        _event_publisher.attach(_websocket_observer)

        # Create and attach NotificationObserver
        _notification_observer = NotificationObserver(
            achievement_service=get_achievement_service_singleton(),
            notification_service_singleton=get_notification_service_singleton()
        )
        _event_publisher.attach(_notification_observer)

    return _event_publisher


def get_achievement_service_singleton() -> AchievementService:
    """Get singleton AchievementService"""
    global _achievement_service
    if _achievement_service is None:
        from services.achievement_service import AchievementService
        # Note: user_profile_repo needs DB, so we create it per-request
        # For now, create without it, pass DB when calling check_achievements
        _achievement_service = AchievementService(
            user_profile_repo=None  # Will need to fix this
        )
    return _achievement_service


def get_notification_service_singleton() -> NotificationService:
    """Get singleton NotificationService (for observers)"""
    # Observers need ONE instance, not per-request
    global _notification_service_singleton
    if _notification_service_singleton is None:
        # NotificationService only needs Redis, not DB
        # But current implementation takes DB - need to fix
        _notification_service_singleton = NotificationService(db=None)
    return _notification_service_singleton
```

**PROBLEM IDENTIFIED:**
- NotificationService takes DB in constructor
- AchievementService needs user_profile_repo which needs DB
- But singletons can't hold DB sessions

**SOLUTION:** We need to refactor before implementing:
1. NotificationService shouldn't need DB for queuing
2. AchievementService should get DB when check_achievements() is called

---

## BLOCKING ISSUES FOUND

### Issue 1: NotificationService takes DB

**Current:** Line 323-325 in dependencies.py
```python
def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db)
```

**In NotificationService.__init__:**
```python
def __init__(self, db: Session):
    self.db = db  # Used for logging notifications to database
```

**Problem:** Observer needs singleton NotificationService, but it can't hold DB session

**Solution:** NotificationService should NOT take DB in constructor
- For queuing: Only needs Redis (no DB)
- For logging: Get DB when needed, or log async in consumer

### Issue 2: AchievementService needs user_profile_repo

**user_profile_repo needs DB session**

**Solution:** Pass DB to check_achievements() method, not constructor

---

## WHAT TO DO NEXT

**Option A: Fix NotificationService first**
- Remove DB from constructor
- Move logging to consumer
- THEN implement Observer pattern

**Option B: Simplified approach**
- NotificationObserver gets DB via Depends when orchestrator calls it
- But this breaks Observer pattern (observer shouldn't need per-request deps)

**My recommendation: Option A - Fix NotificationService first**

**Steps:**
1. Refactor NotificationService to not need DB in constructor
2. Move notification logging to consumer process
3. THEN implement Observer pattern cleanly

---

## QUESTIONS FOR YOU

1. **Should we fix NotificationService first** (remove DB dependency) **before** implementing Observer pattern?

2. **Or** should we keep current NotificationService and have NotificationObserver call it per-request (not singleton)?

3. **AchievementService** - how should it get DB? Pass in check_achievements() method?

Once we decide, I'll create the exact implementation plan with no blockers.