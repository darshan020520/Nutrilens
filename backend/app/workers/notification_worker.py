# backend/app/workers/notification_worker.py
"""
Notification Worker - Scheduler for triggering scheduled notifications via EventPublisher.

Uses APScheduler for industry-standard cron-based scheduling.
All events flow through EventPublisher → NotificationObserver → Redis.
"""

import asyncio
import logging
import signal
import sys
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.models.database import engine
from app.infrastructure.events.event_publisher import EventPublisher
from app.services.consumption_service_v2 import ConsumptionServiceV2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationWorker:
    """
    Notification scheduler using APScheduler.

    Triggers scheduled notifications via EventPublisher.
    All events flow: EventPublisher → NotificationObserver → Redis → NotificationConsumer
    """

    def __init__(self, event_publisher: EventPublisher):
        """
        Initialize notification worker with scheduler.

        Args:
            event_publisher: EventPublisher instance to publish events
        """
        self.event_publisher = event_publisher
        self.session_factory = sessionmaker(bind=engine)
        self.scheduler = AsyncIOScheduler()
        self.should_stop = False

        # Handle graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.should_stop = True
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)

    async def run(self):
        """
        Start APScheduler with cron jobs for scheduled notifications.

        Schedule:
        - Daily summaries: Every day at 9 PM UTC
        - Weekly reports: Every Sunday at 8 PM UTC
        - Meal reminders: Every 5 minutes
        - Inventory alerts: Every day at 8 AM UTC
        """
        logger.info("Starting NotificationWorker with APScheduler...")

        # Schedule daily summaries (every day at 9 PM UTC)
        self.scheduler.add_job(
            self._trigger_daily_summaries,
            trigger=CronTrigger(hour=21, minute=0),
            id='daily_summaries',
            name='Daily Summaries',
            replace_existing=True
        )
        logger.info("Scheduled: Daily summaries at 9 PM UTC")

        # Schedule weekly reports (every Sunday at 8 PM UTC)
        # self.scheduler.add_job(
        #     self._trigger_weekly_reports,
        #     trigger=CronTrigger(day_of_week='sun', hour=20, minute=0),
        #     id='weekly_reports',
        #     name='Weekly Reports',
        #     replace_existing=True
        # )
        logger.info("Scheduled: Weekly reports on Sunday at 8 PM UTC")

        # Schedule meal reminders (every 5 minutes)
        self.scheduler.add_job(
            self._trigger_meal_reminders,
            trigger=CronTrigger(minute='*/5'),
            id='meal_reminders',
            name='Meal Reminders',
            replace_existing=True
        )
        logger.info("Scheduled: Meal reminders every 5 minutes")

        # Schedule inventory alerts (every day at 8 AM UTC)
        self.scheduler.add_job(
            self._trigger_inventory_alerts,
            trigger=CronTrigger(hour=8, minute=0),
            id='inventory_alerts',
            name='Inventory Alerts',
            replace_existing=True
        )
        logger.info("Scheduled: Inventory alerts at 8 AM UTC")

        # Start scheduler
        self.scheduler.start()
        logger.info("APScheduler started successfully")

        # Keep worker alive
        try:
            while not self.should_stop:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=True)
            logger.info("NotificationWorker stopped.")
    
    
    async def _trigger_meal_reminders(self):
        """
        Trigger meal reminder events via EventPublisher.

        Checks for upcoming meals (30 minutes from now) and publishes events.
        """
        db = self.session_factory()
        try:
            from app.repositories.meal_log_repository import MealLogRepository

            # Find meals that need reminders (30 minutes from now)
            reminder_time = datetime.utcnow() + timedelta(minutes=30)
            reminder_window_start = reminder_time - timedelta(minutes=2)
            reminder_window_end = reminder_time + timedelta(minutes=2)

            meal_log_repo = MealLogRepository(db)
            upcoming_meals = await meal_log_repo.get_upcoming_meals_in_time_window(
                start_datetime=reminder_window_start,
                end_datetime=reminder_window_end
            )

            reminder_count = 0

            for meal in upcoming_meals:
                try:
                    time_until = int((meal.planned_datetime - datetime.utcnow()).total_seconds() / 60)

                    if 25 <= time_until <= 35:
                        # Publish event via EventPublisher
                        # Map to observer expectations:
                            # - time_until (not time_until_minutes)
                            # - scheduled_time (formatted from planned_datetime)
                            await self.event_publisher.publish(
                                event_type="scheduled_meal_reminder",
                                data={
                                    "user_id": meal.user_id,
                                    "meal_type": meal.meal_type,
                                    "recipe_name": meal.recipe.title if meal.recipe else "Your meal",
                                    "time_until": time_until,
                                    "scheduled_time": meal.planned_datetime.strftime("%I:%M %p"),
                                }
                            )
                            reminder_count += 1
                            logger.info(f"Meal reminder event published for user {meal.user_id}")

                except Exception as e:
                    logger.error(f"Error publishing meal reminder for meal {meal.id}: {str(e)}")

            if reminder_count > 0:
                logger.info(f"Published {reminder_count} meal reminder events")

        except Exception as e:
            logger.error(f"Error in _trigger_meal_reminders: {str(e)}")
        finally:
            db.close()
    
    async def _trigger_daily_summaries(self):
        """
        Trigger daily summary events via EventPublisher.

        Generates daily summaries for all active users and publishes events.
        """
        db = self.session_factory()
        try:
            from app.repositories.auth_repository import AuthRepository
            from app.repositories.tracking_repository import TrackingRepository
            from app.repositories.inventory_repository import InventoryRepository
            from app.repositories.consumption_analytics_repository import ConsumptionAnalyticsRepository
            from app.services.consumption_service_v2 import ConsumptionServiceV2
            from app.dependencies import get_llm_orchestrator

            # Build ConsumptionServiceV2 directly — Depends() only works in route handlers
            llm_orchestrator = await get_llm_orchestrator()
            consumption_service = ConsumptionServiceV2(
                tracking_repo=TrackingRepository(db),
                inventory_repo=InventoryRepository(db),
                analytics_repo=ConsumptionAnalyticsRepository(db),
                db=db,
                llm_orchestrator=llm_orchestrator,
            )

            auth_repo = AuthRepository(db)
            active_users = auth_repo.get_all_active()

            for user in active_users:
                try:
                    summary = consumption_service.get_today_summary(user.id)

                    if summary.get("success"):
                        # Publish event via EventPublisher
                        # Map service keys to observer expectations:
                        # - total_calories → calories_consumed
                        # - total_macros.protein_g → protein_g
                        await self.event_publisher.publish(
                            event_type="scheduled_daily_summary",
                            data={
                                "user_id": user.id,
                                "date": summary.get("date"),
                                "meals_consumed": summary.get("meals_consumed", 0),
                                "compliance_rate": summary.get("compliance_rate", 0.0),
                                "calories_consumed": summary.get("total_calories", 0),
                                "protein_g": summary.get("total_macros", {}).get("protein_g", 0),
                            }
                        )
                        logger.info(f"Daily summary event published for user {user.id}")

                except Exception as e:
                    logger.error(f"Error publishing daily summary for user {user.id}: {str(e)}")

            logger.info(f"Published daily summary events for {len(active_users)} users")

        except Exception as e:
            logger.error(f"Error in _trigger_daily_summaries: {str(e)}")
        finally:
            db.close()
    
    # async def _trigger_weekly_reports(self):
    #     """
    #     Trigger weekly report events via EventPublisher.

    #     Generates weekly analytics for all active users and publishes events.
    #     """
    #     db = self.session_factory()
    #     try:
    #         from app.repositories.auth_repository import AuthRepository

    #         consumption_service = ConsumptionService(db)
    #         auth_repo = AuthRepository(db)
    #         active_users = auth_repo.get_all_active()

    #         for user in active_users:
    #             try:
    #                 analytics = consumption_service.generate_consumption_analytics(
    #                     user_id=user.id,
    #                     days=7
    #                 )

    #                 if analytics.get("success"):
    #                     # Extract data from analytics
    #                     analytics_data = analytics.get("analytics", {})
    #                     daily_compliance = analytics_data.get("daily_compliance", {})

    #                     # Calculate date range
    #                     end_date = datetime.utcnow().date()
    #                     start_date = end_date - timedelta(days=7)

    #                     # Publish event via EventPublisher
    #                     # Map service data to observer expectations:
    #                     # - Calculate start_date and end_date
    #                     # - Extract average_compliance from nested analytics
    #                     # - Map total_meals_analyzed → total_meals
    #                     # - Set weight_change and achievements_unlocked to 0 (TODO: integrate services)
    #                     await self.event_publisher.publish(
    #                         event_type="scheduled_weekly_report",
    #                         data={
    #                             "user_id": user.id,
    #                             "start_date": start_date.isoformat(),
    #                             "end_date": end_date.isoformat(),
    #                             "total_meals": analytics.get("total_meals_analyzed", 0),
    #                             "average_compliance": daily_compliance.get("average_compliance", 0.0),
    #                             "weight_change": 0.0,  # TODO: Integrate weight tracking service
    #                             "achievements_unlocked": 0,  # TODO: Integrate achievement service
    #                         }
    #                     )
    #                     logger.info(f"Weekly report event published for user {user.id}")

    #             except Exception as e:
    #                 logger.error(f"Error publishing weekly report for user {user.id}: {str(e)}")

    #         logger.info(f"Published weekly report events for {len(active_users)} users")

    #     except Exception as e:
    #         logger.error(f"Error in _trigger_weekly_reports: {str(e)}")
    #     finally:
    #         db.close()

    async def _trigger_inventory_alerts(self):
        """
        Trigger inventory alert events via EventPublisher.

        Uses InventoryManagementService to get expiring and restock data,
        then publishes events for notification system.
        """
        db = self.session_factory()
        try:
            from app.services.inventory_management_service import InventoryManagementService
            from app.repositories.inventory_repository import InventoryRepository
            from app.repositories.tracking_repository import TrackingRepository
            from app.repositories.auth_repository import AuthRepository

            # Initialize repositories and service
            inventory_repo = InventoryRepository(db)
            tracking_repo = TrackingRepository(db)
            inventory_service = InventoryManagementService(inventory_repo, tracking_repo, db)
            auth_repo = AuthRepository(db)

            active_users = auth_repo.get_all_active()
            alert_count = 0

            for user in active_users:
                try:
                    # Get expiring items (same as /tracking/v2/expiring-items)
                    expiring_result = await inventory_service.check_expiring_items(
                        user_id=user.id,
                        filter_mode="both",
                        days_threshold=3
                    )

                    # Get restock items (same as /tracking/v2/restock-list)
                    restock_result = await inventory_service.generate_restock_list(
                        user_id=user.id
                    )

                    # Filter for URGENT items only (matching old TrackingAgent behavior)
                    expiring_items = []
                    if expiring_result.get("success"):
                        urgent_expiring = [
                            item for item in expiring_result.get("expiring_items", [])
                            if item.get("priority") == "urgent"
                        ]

                        # Map to observer's expected format
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

                        # Map to observer's expected format
                        low_stock_items = [
                            {
                                "name": item["item_name"],
                                "quantity": item["current_quantity"],
                                "urgency": "high"
                            }
                            for item in urgent_restock
                        ]

                    # Only publish if there are alerts
                    if len(expiring_items) > 0 or len(low_stock_items) > 0:
                        await self.event_publisher.publish(
                            event_type="scheduled_inventory_check",
                            data={
                                "user_id": user.id,
                                "expiring_items": expiring_items,
                                "days_until_expiry": 3,
                                "low_stock_items": low_stock_items,
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

async def run_notification_consumer():
    """
    Run NotificationConsumer to process queued notifications.

    Uses BRPOP (blocking pop) for efficient Redis queue consumption.
    """
    from app.infrastructure.notifications.consumers import NotificationConsumer

    logger.info("Starting NotificationConsumer...")
    consumer = NotificationConsumer()

    try:
        await consumer.start()
    except Exception as e:
        logger.error(f"NotificationConsumer crashed: {e}")
        raise


async def main():
    """
    Main entry point - supports producer, consumer, or both.

    Producer: APScheduler-based worker that triggers events via EventPublisher
    Consumer: NotificationConsumer that processes queued notifications
    """

    # Check if command line argument provided
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

        if mode == "producer":
            logger.info("Starting in PRODUCER mode (APScheduler worker)")

            from app.infrastructure.observers.notification_observer import NotificationObserver
            from app.models.database import SessionLocal

            event_publisher = EventPublisher()
            notification_observer = NotificationObserver(session_factory=SessionLocal)
            event_publisher.attach(notification_observer)

            worker = NotificationWorker(event_publisher)
            await worker.run()

        elif mode == "consumer":
            logger.info("Starting in CONSUMER mode (NotificationConsumer)")
            await run_notification_consumer()

        else:
            logger.error(f"Unknown mode: {mode}")
            logger.info("Usage: python -m app.workers.notification_worker [producer|consumer]")
            logger.info("  producer - Run APScheduler worker that triggers notifications")
            logger.info("  consumer - Run NotificationConsumer that sends notifications")
            logger.info("  (no arg) - Run both together")
            sys.exit(1)
    else:
        # No argument - run both
        logger.info("Starting in BOTH mode (producer + consumer)")

        from app.infrastructure.observers.notification_observer import NotificationObserver
        from app.models.database import SessionLocal

        event_publisher = EventPublisher()
        notification_observer = NotificationObserver(session_factory=SessionLocal)
        event_publisher.attach(notification_observer)

        # Start both worker and consumer
        worker = NotificationWorker(event_publisher)
        await asyncio.gather(
            worker.run(),
            run_notification_consumer()
        )

if __name__ == "__main__":
    asyncio.run(main())
