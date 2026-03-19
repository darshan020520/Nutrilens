import logging
import json
from datetime import datetime
from typing import Dict, Any, Callable, Optional
from app.infrastructure.events.observer import IObserver
from app.infrastructure.notifications.factories.notification_factory import NotificationFactory
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class NotificationObserver(IObserver):

    QUEUE_KEYS = {
        "urgent": "notifications:queue:urgent",
        "high": "notifications:queue:high",
        "normal": "notifications:queue:normal",
        "low": "notifications:queue:low",
    }

    def __init__(self, session_factory: Optional[Callable] = None):
        # session_factory is SessionLocal (the class, not an instance).
        # A new session is opened per handler call and closed immediately after,
        # so we never hold a stale connection from startup.
        self._session_factory = session_factory
        self.redis_client = get_redis_client()
        self.factory = NotificationFactory()

    async def update(self, event: Dict) -> None:

        try:
            event_type = event.get("type")
            event_data = event.get("data", {})

            handler = self._get_event_handler(event_type)
            if handler:
                await handler(event_data)
            else:
                logger.debug(f"No notification handler for event type: {event_type}")

        except Exception as e:
            logger.error(f"NotificationObserver failed for event {event.get('type')}: {e}", exc_info=True)

    def _get_event_handler(self, event_type: str):

        handlers = {
            "meal_logged": self._handle_meal_logged,
            "meal_skipped": self._handle_meal_skipped,
            "external_meal_logged": self._handle_external_meal_logged,
            "inventory_updated": self._handle_inventory_updated,
            "receipt_uploaded": self._handle_receipt_uploaded,
            "scheduled_daily_summary": self._handle_daily_summary,
            "scheduled_weekly_report": self._handle_weekly_report,
            "scheduled_meal_reminder": self._handle_meal_reminder,
            "scheduled_inventory_check": self._handle_inventory_check,
        }
        return handlers.get(event_type)


    async def _handle_meal_logged(self, event_data: Dict) -> None:

        user_id = event_data.get("user_id")
        daily_totals = event_data.get("daily_totals", {})

        if self._session_factory:
            async with self._session_factory() as db:
                from app.dependencies import create_achievement_service
                achievement_service = create_achievement_service(db)
                achievements = await achievement_service.check_achievements(
                    user_id=user_id,
                    daily_totals=daily_totals
                )
                for achievement in achievements:
                    await self._create_and_queue_notification(
                        notification_type="achievement",
                        user_id=user_id,
                        metadata={
                            "achievement_type": achievement.get("type"),
                            "achievement_name": achievement.get("name"),
                            "description": achievement.get("description"),
                            "message": achievement.get("message"),
                        }
                    )

        if self._is_progress_milestone(daily_totals):
            today = datetime.utcnow().strftime("%Y-%m-%d")
            dedup_key = f"progress_sent:{user_id}:daily_goal:{today}"
            if not await self.redis_client.exists(dedup_key):
                await self.redis_client.setex(dedup_key, 86400, "1")
                progress_pct = round(daily_totals.get("compliance_rate", 0) * 100)
                await self._create_and_queue_notification(
                    notification_type="progress_update",
                    user_id=user_id,
                    metadata={
                        "milestone_type": "daily_goal",
                        "milestone_name": "Daily Progress",
                        "progress_percentage": progress_pct,
                        "message": f"You've reached {progress_pct}% of your daily goal!",
                    }
                )

    async def _handle_meal_skipped(self, event_data: Dict) -> None:
        user_id = event_data.get("user_id")
        meal_type = event_data.get("meal_type")

        await self._create_and_queue_notification(
            notification_type="progress_update",
            user_id=user_id,
            metadata={
                "milestone_type": "meal_skipped",
                "milestone_name": "Meal Reminder",
                "message": f"Don't forget to log your {meal_type}!",
            }
        )

    async def _handle_external_meal_logged(self, event_data: Dict) -> None:

        user_id = event_data.get("user_id")
        daily_totals = event_data.get("daily_totals", {})

        if self._session_factory:
            async with self._session_factory() as db:
                from app.dependencies import create_achievement_service
                achievement_service = create_achievement_service(db)
                achievements = await achievement_service.check_achievements(
                    user_id=user_id,
                    daily_totals=daily_totals
                )
                for achievement in achievements:
                    await self._create_and_queue_notification(
                        notification_type="achievement",
                        user_id=user_id,
                        metadata={
                            "achievement_type": achievement.get("type"),
                            "achievement_name": achievement.get("name"),
                            "description": achievement.get("description"),
                            "message": achievement.get("message"),
                        }
                    )

    async def _handle_inventory_updated(self, event_data: Dict) -> None:
        user_id = event_data.get("user_id")
        item_count = event_data.get("item_count", 0)

        await self._create_and_queue_notification(
            notification_type="inventory_alert",
            user_id=user_id,
            metadata={
                "alert_type": "inventory_updated",
                "message": f"Your inventory has been updated with {item_count} items",
                "item_count": item_count,
            }
        )

    async def _handle_receipt_uploaded(self, event_data: Dict) -> None:
        user_id = event_data.get("user_id")
        items_added = event_data.get("items_added", 0)

        await self._create_and_queue_notification(
            notification_type="inventory_alert",
            user_id=user_id,
            metadata={
                "alert_type": "receipt_processed",
                "message": f"Receipt processed! {items_added} items added to inventory",
                "item_count": items_added,
            }
        )

    async def _handle_daily_summary(self, event_data: Dict) -> None:

        user_id = event_data.get("user_id")

        await self._create_and_queue_notification(
            notification_type="daily_summary",
            user_id=user_id,
            metadata={
                "date": event_data.get("date"),
                "meals_consumed": event_data.get("meals_consumed", 0),
                "compliance_rate": event_data.get("compliance_rate", 0.0),
                "calories_consumed": event_data.get("calories_consumed", 0),
                "protein_g": event_data.get("protein_g", 0),
            }
        )

    async def _handle_weekly_report(self, event_data: Dict) -> None:
        user_id = event_data.get("user_id")

        await self._create_and_queue_notification(
            notification_type="weekly_report",
            user_id=user_id,
            metadata={
                "start_date": event_data.get("start_date"),
                "end_date": event_data.get("end_date"),
                "total_meals": event_data.get("total_meals", 0),
                "average_compliance": event_data.get("average_compliance", 0.0),
                "weight_change": event_data.get("weight_change", 0.0),
                "achievements_unlocked": event_data.get("achievements_unlocked", 0),
            }
        )

    async def _handle_meal_reminder(self, event_data: Dict) -> None:
        user_id = event_data.get("user_id")

        await self._create_and_queue_notification(
            notification_type="meal_reminder",
            user_id=user_id,
            metadata={
                "meal_type": event_data.get("meal_type"),
                "recipe_name": event_data.get("recipe_name"),
                "time_until": event_data.get("time_until", 30),
                "scheduled_time": event_data.get("scheduled_time"),
            }
        )

    async def _handle_inventory_check(self, event_data: Dict) -> None:

        user_id = event_data.get("user_id")

        expiring_items = event_data.get("expiring_items", [])
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

        low_stock_items = event_data.get("low_stock_items", [])
        if low_stock_items:
            await self._create_and_queue_notification(
                notification_type="low_stock_alert",
                user_id=user_id,
                metadata={
                    "low_stock_items": low_stock_items,
                    "item_count": len(low_stock_items),
                }
            )


    def _is_progress_milestone(self, daily_totals: Dict) -> bool:
        """Check if daily totals represent a milestone. compliance_rate is a 0-1 fraction."""
        compliance_rate = daily_totals.get("compliance_rate", 0)
        return compliance_rate >= 0.8  # 80% or more is a milestone

    async def _create_and_queue_notification(
        self,
        notification_type: str,
        user_id: int,
        metadata: Dict[str, Any]
    ) -> None:
        try:

            notification = self.factory.create_notification(
                notification_type=notification_type,
                user_id=user_id,
                metadata=metadata
            )

            notification_data = notification.create()

            await self._queue_to_redis(notification_data)

            logger.info(
                f"Queued {notification_type} notification for user {user_id} "
                f"with priority {notification_data['priority']}"
            )

        except Exception as e:
            logger.error(
                f"Failed to create/queue {notification_type} notification "
                f"for user {user_id}: {e}",
                exc_info=True
            )

    async def _queue_to_redis(self, notification_data: Dict[str, Any]) -> None:

        priority = notification_data.get("priority", "normal")
        queue_key = self.QUEUE_KEYS.get(priority, self.QUEUE_KEYS["normal"])

        notification_json = json.dumps(notification_data)

        await self.redis_client.lpush(queue_key, notification_json)

        logger.debug(f"Pushed notification to {queue_key}")
