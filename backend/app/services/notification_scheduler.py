# backend/app/services/notification_scheduler.py
"""
Notification Scheduler Service - Handles all scheduled notifications
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.database import User, UserProfile, MealLog, MealPlan
from app.services.notification_service import NotificationService, NotificationPriority
from app.services.consumption_services import ConsumptionService
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationScheduler:
    """Handles scheduled notifications based on user patterns and meal plans"""
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)
        self.consumption_service = ConsumptionService(db)
    
    async def schedule_meal_reminders(self) -> None:
        """Schedule meal reminders for all active users"""
        try:
            # Get users with active meal plans
            active_users = self.db.query(User).join(MealPlan).filter(
                MealPlan.is_active == True
            ).all()
            
            for user in active_users:
                await self._schedule_user_meal_reminders(user.id)
                
        except Exception as e:
            logger.error(f"Error scheduling meal reminders: {str(e)}")
    
    async def _schedule_user_meal_reminders(self, user_id: int) -> None:
        """Schedule today's meal reminders for a specific user"""
        try:
            # Get today's planned meals
            today = datetime.utcnow().date()
            planned_meals = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    func.date(MealLog.planned_datetime) == today,
                    MealLog.consumed_datetime.is_(None),
                    MealLog.was_skipped == False
                )
            ).all()
            
            for meal in planned_meals:
                # Calculate reminder time (30 minutes before)
                reminder_time = meal.planned_datetime - timedelta(minutes=30)
                
                # Only schedule if reminder time is in the future
                if reminder_time > datetime.utcnow():
                    await self.notification_service.send_meal_reminder(
                        user_id=user_id,
                        meal_type=meal.meal_type,
                        recipe_name=meal.recipe.title if meal.recipe else "Your meal",
                        time_until=30,
                        priority=NotificationPriority.NORMAL
                    )
                    
        except Exception as e:
            logger.error(f"Error scheduling meal reminders for user {user_id}: {str(e)}")
    
    async def send_daily_summaries(self) -> None:
        """Send daily summaries to all users at 9 PM"""
        try:
            # Get all active users
            active_users = self.db.query(User).filter(User.is_active == True).all()
            
            for user in active_users:
                # Get today's summary
                summary = self.consumption_service.get_today_summary(user.id)
                
                if summary.get("success"):
                    await self.notification_service.send_daily_summary(
                        user_id=user.id,
                        summary_data=summary,
                        priority=NotificationPriority.LOW
                    )
                    
        except Exception as e:
            logger.error(f"Error sending daily summaries: {str(e)}")
    
    async def send_progress_updates(self, user_id: int) -> None:
        """Send progress update after meal logging"""
        try:
            # Get today's data
            summary = self.consumption_service.get_today_summary(user_id)
            
            if summary.get("success"):
                # Calculate compliance rate
                compliance_rate = summary.get("compliance_rate", 0)
                total_calories = summary.get("total_calories", 0)
                
                # Get user profile for remaining calories
                user_profile = self.db.query(UserProfile).filter(
                    UserProfile.user_id == user_id
                ).first()
                
                target_calories = user_profile.goal_calories if user_profile else 2000
                remaining_calories = max(0, target_calories - total_calories)
                
                await self.notification_service.send_progress_update(
                    user_id=user_id,
                    compliance_rate=compliance_rate,
                    calories_consumed=total_calories,
                    calories_remaining=remaining_calories,
                    priority=NotificationPriority.LOW
                )
                
        except Exception as e:
            logger.error(f"Error sending progress update for user {user_id}: {str(e)}")
    
    async def send_weekly_reports(self) -> None:
        """Send weekly reports every Sunday at 8 PM"""
        try:
            # Get all active users
            active_users = self.db.query(User).filter(User.is_active == True).all()
            
            for user in active_users:
                # Get weekly analytics
                analytics = self.consumption_service.generate_consumption_analytics(
                    user_id=user.id,
                    days=7
                )
                
                if analytics.get("success"):
                    await self.notification_service.send_weekly_report(
                        user_id=user.id,
                        report_data=analytics["analytics"],
                        priority=NotificationPriority.LOW
                    )
                    
        except Exception as e:
            logger.error(f"Error sending weekly reports: {str(e)}")

# Scheduled Task Runner
async def run_notification_scheduler():
    """Main scheduler that runs scheduled notification tasks"""
    
    while True:
        try:
            from app.models.database import SessionLocal
            db = SessionLocal()
            
            try:
                scheduler = NotificationScheduler(db)
                current_time = datetime.utcnow()
                
                # Run meal reminders every 5 minutes
                if current_time.minute % 5 == 0:
                    await scheduler.schedule_meal_reminders()
                
                # Send daily summaries at 9 PM
                if current_time.hour == 21 and current_time.minute == 0:
                    await scheduler.send_daily_summaries()
                
                # Send weekly reports on Sunday at 8 PM
                if (current_time.weekday() == 6 and  # Sunday
                    current_time.hour == 20 and 
                    current_time.minute == 0):
                    await scheduler.send_weekly_reports()
                
            finally:
                db.close()
            
            # Sleep for 60 seconds before next check
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")
            await asyncio.sleep(60)  # Continue running even on error