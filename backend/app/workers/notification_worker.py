# backend/app/workers/notification_worker.py
"""
Single notification worker that handles both real-time and scheduled notifications
"""

import asyncio
import logging
import signal
import sys
import json 
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy import and_, func

from app.models.database import engine, User, MealLog
from app.services.notification_service import NotificationService, NotificationPriority
from app.services.consumption_services import ConsumptionService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationWorker:
    """Single worker that processes all notifications"""
    
    def __init__(self):
        self.should_stop = False
        self.session_factory = sessionmaker(bind=engine)
        self.last_daily_summary = None
        self.last_weekly_report = None
        self.last_meal_reminder_check = None
        
        # Handle graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.should_stop = True
    
    async def run(self):
        """Main worker loop - handles all notification types"""
        logger.info("Starting complete notification worker...")
        
        while not self.should_stop:
            db = self.session_factory()
            try:
                notification_service = NotificationService(db)
                consumption_service = ConsumptionService(db)
                

                
                # Handle scheduled notifications
                await self._process_scheduled_notifications(notification_service, consumption_service)
                
                # NEW: Handle meal reminders
                await self._process_meal_reminders(notification_service, db)
                
            except Exception as e:
                logger.error(f"Worker error: {str(e)}")
            finally:
                db.close()
            
            # Sleep for 30 seconds between cycles
            await asyncio.sleep(30)
        
        logger.info("Notification worker stopped.")
    
    
    async def _process_scheduled_notifications(self, notification_service, consumption_service):
        """Handle time-based scheduled notifications - ONLY TRIGGER THEM"""
        current_time = datetime.utcnow()
        current_hour = current_time.hour
        current_date = current_time.date()
        
        try:
            # Daily summaries at 9 PM (only once per day)
            if (current_hour == 21 and 
                (self.last_daily_summary is None or self.last_daily_summary != current_date)):
                
                # TRIGGER the notifications - NotificationService will queue them
                await self._trigger_daily_summaries(notification_service, consumption_service)
                self.last_daily_summary = current_date
                logger.info("Daily summaries triggered")
            
            # Weekly reports on Sunday at 8 PM (only once per week)
            if (current_time.weekday() == 6 and  # Sunday
                current_hour == 20 and
                (self.last_weekly_report is None or 
                 (current_date - self.last_weekly_report).days >= 7)):
                
                # TRIGGER the notifications - NotificationService will queue them
                await self._trigger_weekly_reports(notification_service, consumption_service)
                self.last_weekly_report = current_date
                logger.info("Weekly reports triggered")
                
        except Exception as e:
            logger.error(f"Error processing scheduled notifications: {str(e)}")

    
    async def _process_meal_reminders(self, notification_service, db):
        """Process meal reminders - ONLY TRIGGER THEM"""
        current_time = datetime.utcnow()
        current_minute = current_time.minute
        
        # Only check meal reminders every 5 minutes to avoid spam
        if (current_minute % 5 == 0 and 
            (self.last_meal_reminder_check is None or 
             (current_time - self.last_meal_reminder_check).total_seconds() >= 300)):
            
            try:
                await self._trigger_meal_reminders(notification_service, db)
                self.last_meal_reminder_check = current_time
                
            except Exception as e:
                logger.error(f"Error processing meal reminders: {str(e)}")
    
    async def _trigger_meal_reminders(self, notification_service, db):
        """TRIGGER meal reminders - NotificationService will queue them"""
        try:
            # Find meals that need reminders (30 minutes from now)
            reminder_time = datetime.utcnow() + timedelta(minutes=30)
            reminder_window_start = reminder_time - timedelta(minutes=2)
            reminder_window_end = reminder_time + timedelta(minutes=2)
            
            upcoming_meals = db.query(MealLog).options(
                joinedload(MealLog.recipe),
                joinedload(MealLog.user)
            ).filter(
                and_(
                    MealLog.planned_datetime >= reminder_window_start,
                    MealLog.planned_datetime <= reminder_window_end,
                    MealLog.consumed_datetime.is_(None),
                    MealLog.was_skipped == False
                )
            ).all()
            
            reminder_count = 0
            
            for meal in upcoming_meals:
                try:
                    if meal.user and meal.user.is_active:
                        time_until = int((meal.planned_datetime - datetime.utcnow()).total_seconds() / 60)
                        
                        if 25 <= time_until <= 35:
                            # CALL THE API METHOD - This will queue the notification properly
                            await notification_service.send_meal_reminder(
                                user_id=meal.user_id,
                                meal_type=meal.meal_type,
                                recipe_name=meal.recipe.title if meal.recipe else "Your meal",
                                time_until=time_until,
                                priority=NotificationPriority.NORMAL
                            )
                            reminder_count += 1
                            logger.info(f"Meal reminder triggered for user {meal.user_id}")
                            
                except Exception as e:
                    logger.error(f"Error triggering meal reminder for meal {meal.id}: {str(e)}")
            
            if reminder_count > 0:
                logger.info(f"Triggered {reminder_count} meal reminders")
                
        except Exception as e:
            logger.error(f"Error in _trigger_meal_reminders: {str(e)}")
    
    async def _trigger_daily_summaries(self, notification_service, consumption_service):
        """TRIGGER daily summaries for all active users"""
        try:
            db = self.session_factory()
            try:
                active_users = db.query(User).filter(User.is_active == True).all()
                
                for user in active_users:
                    summary = consumption_service.get_today_summary(user.id)
                    
                    if summary.get("success"):
                        # CALL THE API METHOD - This will queue the notification properly
                        await notification_service.send_daily_summary(
                            user_id=user.id,
                            summary_data=summary
                        )
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error triggering daily summaries: {str(e)}")
    
    async def _trigger_weekly_reports(self, notification_service, consumption_service):
        """TRIGGER weekly reports for all active users"""
        try:
            db = self.session_factory()
            try:
                active_users = db.query(User).filter(User.is_active == True).all()
                
                for user in active_users:
                    analytics = consumption_service.generate_consumption_analytics(
                        user_id=user.id,
                        days=7
                    )
                    
                    if analytics.get("success"):
                        # CALL THE API METHOD - This will queue the notification properly
                        await notification_service.send_weekly_report(
                            user_id=user.id,
                            report_data=analytics["analytics"]
                        )
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error triggering weekly reports: {str(e)}")

async def run_notification_queue_processor():
    """Separate process to handle Redis queue processing"""
    session_factory = sessionmaker(bind=engine)
    
    while True:
        db = session_factory()
        try:
            notification_service = NotificationService(db)
            # This runs continuously and processes the Redis queues
            await notification_service.process_notification_queue()
        except Exception as e:
            logger.error(f"Notification processor crashed: {str(e)}")
            await asyncio.sleep(10)  # Wait before restart
        finally:
            db.close()

async def main():
    """Main entry point"""
    worker = NotificationWorker()
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
