# backend/app/services/notification_service.py
"""
Complete Production-Ready Notification Service for NutriLens AI
Handles push notifications, email, SMS with Redis queuing and retry logic
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import logging
import json
import redis
import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.database import (
    User, UserProfile, MealLog, UserInventory, 
    AgentInteraction, NotificationPreference, NotificationLog
)
from app.core.config import settings

logger = logging.getLogger(__name__)



async def _mock_send_provider(notification_data: Dict, provider_name: str) -> bool:
    """Mock provider function for testing - prints data and returns success"""
    print("\n" + "="*60)
    print(f"📧 MOCK [{provider_name.upper()}] NOTIFICATION SENT")
    print("="*60)
    print(f"User ID      : {notification_data.get('user_id')}")
    print(f"Type         : {notification_data.get('type')}")
    print(f"Priority     : {notification_data.get('priority')}")
    print(f"Title        : {notification_data.get('title')}")
    print(f"Body         : {notification_data.get('body')}")
    print(f"Data         : {notification_data.get('data', {})}")
    print(f"Created At   : {notification_data.get('created_at')}")
    print("="*60)
    print(f"✅ {provider_name.upper()} notification sent successfully (MOCKED)")
    print("="*60 + "\n")
    return True

class NotificationType(str, Enum):
    MEAL_REMINDER = "meal_reminder"
    INVENTORY_ALERT = "inventory_alert"
    PROGRESS_UPDATE = "progress_update"
    ACHIEVEMENT = "achievement"
    EXPIRY_ALERT = "expiry_alert"
    LOW_STOCK_ALERT = "low_stock_alert"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_REPORT = "weekly_report"

class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationProvider(str, Enum):
    PUSH = "push"  # Firebase Cloud Messaging
    EMAIL = "email"  # SMTP/SendGrid
    SMS = "sms"    # Twilio
    WHATSAPP = "whatsapp"  # Twilio WhatsApp API

class NotificationService:
    """Complete notification service with multiple providers and retry logic"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True
        )
        self.max_retries = 3
        self.retry_delays = [60, 300, 900]  # 1min, 5min, 15min
        
        # Initialize notification providers
        self.providers = {
            NotificationProvider.PUSH: self._init_push_provider(),
            NotificationProvider.EMAIL: self._init_email_provider(),
            NotificationProvider.SMS: self._init_sms_provider(),
            NotificationProvider.WHATSAPP: self._init_whatsapp_provider()
        }
    
    def _init_push_provider(self):
        """Initialize Firebase Cloud Messaging"""
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            
            if not firebase_admin._apps:
                # Initialize Firebase Admin SDK
                cred = credentials.Certificate(settings.firebase_credentials_path)
                firebase_admin.initialize_app(cred)
            
            return messaging
        except ImportError:
            logger.warning("Firebase Admin SDK not installed - push notifications disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            return None
    
    def _init_email_provider(self):
        """Initialize email provider (SendGrid/SMTP)"""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail
            
            return sendgrid.SendGridAPIClient(api_key=settings.sendgrid_api_key)
        except ImportError:
            logger.warning("SendGrid not installed - email notifications disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize SendGrid: {str(e)}")
            return None
    
    def _init_sms_provider(self):
        """Initialize SMS provider (Twilio)"""
        try:
            from twilio.rest import Client
            
            return Client(settings.twilio_account_sid, settings.twilio_auth_token)
        except ImportError:
            logger.warning("Twilio not installed - SMS notifications disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Twilio: {str(e)}")
            return None
    
    def _init_whatsapp_provider(self):
        """Initialize WhatsApp provider (Twilio WhatsApp API)"""
        try:
            from twilio.rest import Client
            
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            return client
        except ImportError:
            logger.warning("Twilio not installed - WhatsApp notifications disabled")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize WhatsApp provider: {str(e)}")
            return None
    
    # ===== PUBLIC API METHODS =====
    
    async def send_meal_reminder(
        self,
        user_id: int,
        meal_type: str,
        recipe_name: str,
        time_until: int,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Send meal reminder notification"""
        
        notification_data = {
            "type": NotificationType.MEAL_REMINDER,
            "user_id": user_id,
            "priority": priority,
            "data": {
                "meal_type": meal_type,
                "recipe_name": recipe_name,
                "time_until": time_until
            },
            "title": f"{meal_type.capitalize()} Reminder",
            "body": f"Time to prepare {recipe_name}! Starting in {time_until} minutes.",
            "action_url": f"/meals/{meal_type}",
            "created_at": datetime.utcnow().isoformat()
        }
        
        
        return await self._queue_notification(notification_data)
    
    async def send_inventory_alert(
        self,
        user_id: int,
        alert_type: str,
        items: List[str],
        priority: NotificationPriority = NotificationPriority.HIGH
    ) -> bool:
        """Send inventory alert notification"""

        print("sending alert to inventory for user")
        
        if alert_type == "low_stock":
            title = "Low Stock Alert"
            body = f"Running low on: {', '.join(items[:3])}"
            if len(items) > 3:
                body += f" and {len(items) - 3} more items"
        elif alert_type == "expiring":
            title = "Expiry Alert"
            body = f"Items expiring soon: {', '.join(items[:3])}"
            if len(items) > 3:
                body += f" and {len(items) - 3} more items"
        else:
            return False
        
        notification_data = {
            "type": NotificationType.INVENTORY_ALERT,
            "user_id": user_id,
            "priority": priority,
            "data": {
                "alert_type": alert_type,
                "items": items,
                "item_count": len(items)
            },
            "title": title,
            "body": body,
            "action_url": "/inventory",
            "created_at": datetime.utcnow().isoformat()
        }

        print("notification data befor adding to queue", notification_data)
        
        return await self._queue_notification(notification_data)
    
    async def send_progress_update(
        self,
        user_id: int,
        compliance_rate: float,
        calories_consumed: float,
        calories_remaining: float,
        priority: NotificationPriority = NotificationPriority.LOW
    ) -> bool:
        """Send daily progress update"""
        
        # Generate encouraging message based on progress
        if compliance_rate >= 90:
            message = f"Amazing! {compliance_rate:.0f}% meal compliance today!"
        elif compliance_rate >= 70:
            message = f"Good progress! {compliance_rate:.0f}% compliance - keep it up!"
        else:
            message = f"Stay on track! {compliance_rate:.0f}% compliance so far today"
        
        notification_data = {
            "type": NotificationType.PROGRESS_UPDATE,
            "user_id": user_id,
            "priority": priority,
            "data": {
                "compliance_rate": compliance_rate,
                "calories_consumed": calories_consumed,
                "calories_remaining": calories_remaining
            },
            "title": "Daily Progress Update",
            "body": f"{message} | {calories_consumed:.0f} cal consumed | {calories_remaining:.0f} cal remaining",
            "action_url": "/dashboard",
            "created_at": datetime.utcnow().isoformat()
        }
        
        return await self._queue_notification(notification_data)
    
    async def send_achievement(
        self,
        user_id: int,
        achievement_type: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> bool:
        """Send achievement notification"""
        
        notification_data = {
            "type": NotificationType.ACHIEVEMENT,
            "user_id": user_id,
            "priority": priority,
            "data": {
                "achievement_type": achievement_type,
                "achievement_message": message
            },
            "title": "Achievement Unlocked!",
            "body": message,
            "action_url": "/achievements",
            "created_at": datetime.utcnow().isoformat()
        }

        print("SENDING TO QUEUE", notification_data)
        
        return await self._queue_notification(notification_data)
    
    async def send_daily_summary(
        self,
        user_id: int,
        summary_data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.LOW
    ) -> bool:
        """Send daily summary notification"""
        
        meals_consumed = summary_data.get("meals_consumed", 0)
        compliance_rate = summary_data.get("compliance_rate", 0)
        
        notification_data = {
            "type": NotificationType.DAILY_SUMMARY,
            "user_id": user_id,
            "priority": priority,
            "data": summary_data,
            "title": "Daily Summary",
            "body": f"Today: {meals_consumed} meals logged, {compliance_rate:.0f}% compliance",
            "action_url": "/summary",
            "created_at": datetime.utcnow().isoformat()
        }
        
        return await self._queue_notification(notification_data)
    
    async def send_weekly_report(
        self,
        user_id: int,
        report_data: Dict[str, Any],
        priority: NotificationPriority = NotificationPriority.LOW
    ) -> bool:
        """Send weekly report notification"""
        
        avg_compliance = report_data.get("average_compliance", 0)
        total_meals = report_data.get("total_meals_consumed", 0)
        
        notification_data = {
            "type": NotificationType.WEEKLY_REPORT,
            "user_id": user_id,
            "priority": priority,
            "data": report_data,
            "title": "Weekly Progress Report",
            "body": f"This week: {total_meals} meals logged, {avg_compliance:.0f}% average compliance",
            "action_url": "/reports/weekly",
            "created_at": datetime.utcnow().isoformat()
        }
        
        return await self._queue_notification(notification_data)
    
    # ===== QUEUE MANAGEMENT =====
    
    async def _queue_notification(self, notification_data: Dict) -> bool:
        """Queue notification for processing"""
        try:
            # Get user preferences
            preferences = self._get_user_preferences(notification_data["user_id"])

            print("get notification prefrences", preferences)
            
            # Check if user wants this type of notification
            notification_type = notification_data["type"]
            if not self._should_send_notification(preferences, notification_type):
                logger.info(f"Notification {notification_type} disabled for user {notification_data['user_id']}")
                return True  # Return True as this is expected behavior
            
            # Apply user timing preferences
            if not self._is_allowed_time(preferences, notification_data["priority"]):
                # Schedule for later
                return await self._schedule_notification(notification_data, preferences)
            
            # Add to Redis queue based on priority
            queue_name = f"notifications:{notification_data['priority']}"

            
            # Add retry count and attempt tracking
            notification_data["retry_count"] = 0
            notification_data["max_retries"] = self.max_retries
            notification_data["queued_at"] = datetime.utcnow().isoformat()
            
            # Push to Redis queue
            print("notification data befor pushing to queue", notification_data)


            result = self.redis_client.lpush(queue_name, json.dumps(notification_data))


            
            logger.info(f"Queued {notification_type} notification for user {notification_data['user_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue notification: {str(e)}")
            return False
    
    async def _schedule_notification(self, notification_data: Dict, preferences: Dict) -> bool:
        """Schedule notification for later delivery"""
        try:
            # Calculate next allowed time
            next_allowed_time = self._calculate_next_allowed_time(preferences)
            
            # Add to scheduled notifications with delay
            delay_seconds = (next_allowed_time - datetime.utcnow()).total_seconds()
            
            scheduled_data = {
                **notification_data,
                "scheduled_for": next_allowed_time.isoformat(),
                "original_created_at": notification_data["created_at"]
            }
            
            # Use Redis sorted set for scheduled notifications
            score = next_allowed_time.timestamp()
            self.redis_client.zadd("notifications:scheduled", {json.dumps(scheduled_data): score})
            
            logger.info(f"Scheduled notification for user {notification_data['user_id']} at {next_allowed_time}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to schedule notification: {str(e)}")
            return False
    
    async def process_notification_queue(self):
        """Main queue processor - runs continuously"""
        logger.info("Starting notification queue processor")

        print("STARTING NOTIFICATION QUEUE")
        
        while True:
            try:
                print("STARTING _process_priority_queue")
                await asyncio.gather(
                    self._process_priority_queue("urgent"),
                    self._process_priority_queue("high"),
                    self._process_priority_queue("normal"),
                    self._process_priority_queue("low"),
                    self._process_scheduled_notifications(),
                    self._cleanup_old_notifications()
                )
                
                # Sleep between processing cycles
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error in notification queue processor: {str(e)}")
                await asyncio.sleep(10)  # Wait longer on error
    
    async def _process_priority_queue(self, priority: str):
        """Process notifications from a specific priority queue"""
        queue_name = f"notifications:{priority}"
        
        try:
            # Process up to 10 notifications per cycle for this priority
            batch_size = 10 if priority in ["urgent", "high"] else 5
            
            for _ in range(batch_size):
                # Get notification from queue (blocking with timeout)
                result = self.redis_client.brpop(queue_name, timeout=1)
                
                if not result:
                    break  # No more notifications in this queue
                
                _, notification_json = result
                notification_data = json.loads(notification_json)
                
                # Process the notification
                success = await self._send_notification(notification_data)
                
                if not success:
                    # Handle retry logic
                    await self._handle_failed_notification(notification_data)
                
        except Exception as e:
            logger.error(f"Error processing {priority} queue: {str(e)}")
    
    async def _process_scheduled_notifications(self):
        """Process scheduled notifications that are due"""
        try:
            current_time = datetime.utcnow().timestamp()
            
            # Get notifications that are due (score <= current_time)
            due_notifications = self.redis_client.zrangebyscore(
                "notifications:scheduled", 
                0, 
                current_time,
                withscores=True
            )
            
            for notification_json, _ in due_notifications:
                try:
                    notification_data = json.loads(notification_json)
                    
                    # Remove from scheduled set
                    self.redis_client.zrem("notifications:scheduled", notification_json)
                    
                    # Add back to regular queue
                    await self._queue_notification(notification_data)
                    
                except Exception as e:
                    logger.error(f"Error processing scheduled notification: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error processing scheduled notifications: {str(e)}")
    
    async def _send_notification(self, notification_data: Dict) -> bool:
        """Send notification using appropriate provider"""
        try:
            user_id = notification_data["user_id"]
            notification_type = notification_data["type"]
            
            # Get user preferences to determine which providers to use
            preferences = self._get_user_preferences(user_id)
            enabled_providers = preferences.get("enabled_providers", [NotificationProvider.PUSH])
            
            # Try each enabled provider until one succeeds
            for provider in enabled_providers:
                try:
                    success = await self._send_via_provider(notification_data, provider)
                    
                    if success:
                        print("proceeding to log the notification")
                        # Log successful notification
                        self._log_notification(notification_data, provider, "sent")
                        return True
                        
                except Exception as e:
                    logger.warning(f"Provider {provider} failed for user {user_id}: {str(e)}")
                    continue
            
            # All providers failed
            logger.error(f"All providers failed for notification to user {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            return False
    
    async def _send_via_provider(self, notification_data: Dict, provider: NotificationProvider) -> bool:
        """Send notification via specific provider"""


        if provider == NotificationProvider.PUSH:
            return await _mock_send_provider(notification_data, "PUSH")
        elif provider == NotificationProvider.EMAIL:
            return await _mock_send_provider(notification_data, "EMAIL")
        elif provider == NotificationProvider.SMS:
            return await _mock_send_provider(notification_data, "SMS")
        elif provider == NotificationProvider.WHATSAPP:
            return await _mock_send_provider(notification_data, "WHATSAPP")
        else:
            logger.error(f"Unknown provider: {provider}")
            return False
    
    async def _send_push_notification(self, notification_data: Dict) -> bool:
        """Send push notification via Firebase Cloud Messaging"""
        try:
            if not self.providers[NotificationProvider.PUSH]:
                return False
            
            user_id = notification_data["user_id"]
            
            # Get user's FCM token
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.fcm_token:
                logger.warning(f"No FCM token for user {user_id}")
                return False
            
            # Create FCM message
            message = self.providers[NotificationProvider.PUSH].Message(
                notification=self.providers[NotificationProvider.PUSH].Notification(
                    title=notification_data["title"],
                    body=notification_data["body"]
                ),
                data={
                    "type": notification_data["type"],
                    "action_url": notification_data.get("action_url", ""),
                    "user_data": json.dumps(notification_data.get("data", {}))
                },
                token=user.fcm_token
            )
            
            # Send message
            response = self.providers[NotificationProvider.PUSH].send(message)
            logger.info(f"Push notification sent to user {user_id}: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            return False
    
    async def _send_email_notification(self, notification_data: Dict) -> bool:
        """Send email notification via SendGrid"""
        try:
            if not self.providers[NotificationProvider.EMAIL]:
                return False
            
            user_id = notification_data["user_id"]
            
            # Get user email
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.email:
                logger.warning(f"No email for user {user_id}")
                return False
            
            # Create email content
            from sendgrid.helpers.mail import Mail
            
            html_content = self._generate_email_html(notification_data)
            
            message = Mail(
                from_email=settings.FROM_EMAIL,
                to_emails=user.email,
                subject=notification_data["title"],
                html_content=html_content
            )
            
            # Send email
            response = self.providers[NotificationProvider.EMAIL].send(message)
            logger.info(f"Email sent to user {user_id}: {response.status_code}")
            return response.status_code == 202
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
            return False
    
    async def _send_sms_notification(self, notification_data: Dict) -> bool:
        """Send SMS notification via Twilio"""
        try:
            if not self.providers[NotificationProvider.SMS]:
                return False
            
            user_id = notification_data["user_id"]
            
            # Get user phone number
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.phone_number:
                logger.warning(f"No phone number for user {user_id}")
                return False
            
            # Create SMS message
            message_body = f"{notification_data['title']}\n{notification_data['body']}"
            
            message = self.providers[NotificationProvider.SMS].messages.create(
                body=message_body,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=user.phone_number
            )
            
            logger.info(f"SMS sent to user {user_id}: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS notification: {str(e)}")
            return False
    
    async def _send_whatsapp_notification(self, notification_data: Dict) -> bool:
        """Send WhatsApp notification via Twilio"""
        try:
            if not self.providers[NotificationProvider.WHATSAPP]:
                return False
            
            user_id = notification_data["user_id"]
            
            # Get user WhatsApp number
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user or not user.whatsapp_number:
                logger.warning(f"No WhatsApp number for user {user_id}")
                return False
            
            # Create WhatsApp message
            message_body = f"*{notification_data['title']}*\n{notification_data['body']}"
            
            message = self.providers[NotificationProvider.WHATSAPP].messages.create(
                body=message_body,
                from_=f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
                to=f"whatsapp:{user.whatsapp_number}"
            )
            
            logger.info(f"WhatsApp sent to user {user_id}: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp notification: {str(e)}")
            return False
    
    async def _handle_failed_notification(self, notification_data: Dict):
        """Handle failed notification with retry logic"""
        try:
            retry_count = notification_data.get("retry_count", 0)
            max_retries = notification_data.get("max_retries", self.max_retries)
            
            if retry_count < max_retries:
                # Calculate retry delay
                delay_seconds = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                
                # Update retry count
                notification_data["retry_count"] = retry_count + 1
                notification_data["next_retry_at"] = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()
                
                # Schedule retry
                retry_time = datetime.utcnow().timestamp() + delay_seconds
                self.redis_client.zadd("notifications:retries", {json.dumps(notification_data): retry_time})
                
                logger.info(f"Scheduled retry {retry_count + 1}/{max_retries} for user {notification_data['user_id']} in {delay_seconds}s")
            else:
                # Max retries exceeded - log as failed
                self._log_notification(notification_data, None, "failed")
                logger.error(f"Notification failed permanently for user {notification_data['user_id']} after {max_retries} retries")
                
        except Exception as e:
            logger.error(f"Error handling failed notification: {str(e)}")
    
    async def _cleanup_old_notifications(self):
        """Clean up old notification logs and queues"""
        try:
            # Clean up old scheduled notifications (older than 7 days)
            week_ago = (datetime.utcnow() - timedelta(days=7)).timestamp()
            self.redis_client.zremrangebyscore("notifications:scheduled", 0, week_ago)
            
            # Clean up old retry notifications (older than 1 day)
            day_ago = (datetime.utcnow() - timedelta(days=1)).timestamp()
            self.redis_client.zremrangebyscore("notifications:retries", 0, day_ago)
            
            # Clean up old notification logs from database (older than 30 days)
            month_ago = datetime.utcnow() - timedelta(days=30)
            self.db.query(NotificationLog).filter(
                NotificationLog.created_at < month_ago
            ).delete()
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {str(e)}")
    
    # ===== HELPER METHODS =====
    
    def _get_user_preferences(self, user_id: int) -> Dict:
        """Get user notification preferences"""
        try:
            # Try to get from database
            prefs = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id
            ).first()
            
            if prefs:
                return {
                    "enabled_providers": prefs.enabled_providers or [NotificationProvider.PUSH],
                    "enabled_types": prefs.enabled_types or [t.value for t in NotificationType],
                    "quiet_hours_start": prefs.quiet_hours_start or 22,  # 10 PM
                    "quiet_hours_end": prefs.quiet_hours_end or 7,       # 7 AM
                    "timezone": prefs.timezone or "UTC"
                }
            else:
                # Return defaults
                return {
                    "enabled_providers": [NotificationProvider.PUSH],
                    "enabled_types": [t.value for t in NotificationType],
                    "quiet_hours_start": 22,
                    "quiet_hours_end": 7,
                    "timezone": "UTC"
                }
                
        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}")
            return {
                "enabled_providers": [NotificationProvider.PUSH],
                "enabled_types": [t.value for t in NotificationType],
                "quiet_hours_start": 22,
                "quiet_hours_end": 7,
                "timezone": "UTC"
            }
    
    def _should_send_notification(self, preferences: Dict, notification_type: str) -> bool:
        """Check if user wants this type of notification"""
        enabled_types = preferences.get("enabled_types", [])
        return notification_type in enabled_types
    
    def _is_allowed_time(self, preferences: Dict, priority: str) -> bool:
        """Check if current time is allowed for notifications"""
        try:
            # Urgent notifications always go through
            if priority == NotificationPriority.URGENT:
                return True
            
            current_hour = datetime.utcnow().hour
            quiet_start = preferences.get("quiet_hours_start", 22)
            quiet_end = preferences.get("quiet_hours_end", 7)
            
            # Handle quiet hours spanning midnight
            if quiet_start > quiet_end:
                # e.g., 22:00 to 07:00
                is_quiet_time = current_hour >= quiet_start or current_hour < quiet_end
            else:
                # e.g., 02:00 to 06:00
                is_quiet_time = quiet_start <= current_hour < quiet_end
            
            return not is_quiet_time
            
        except Exception as e:
            logger.error(f"Error checking allowed time: {str(e)}")
            return True  # Default to allowing notifications
    
    def _calculate_next_allowed_time(self, preferences: Dict) -> datetime:
        """Calculate next allowed time for notifications"""
        quiet_end = preferences.get("quiet_hours_end", 7)
        
        now = datetime.utcnow()
        next_allowed = now.replace(hour=quiet_end, minute=0, second=0, microsecond=0)
        
        # If quiet end time has passed today, use tomorrow
        if next_allowed <= now:
            next_allowed += timedelta(days=1)
        
        return next_allowed
    
    def _generate_email_html(self, notification_data: Dict) -> str:
        """Generate HTML content for email notifications"""
        
        title = notification_data["title"]
        body = notification_data["body"]
        action_url = notification_data.get("action_url", "")
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2E8B57;">{title}</h2>
                <p>{body}</p>
                
                {f'<a href="{action_url}" style="display: inline-block; background-color: #2E8B57; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 20px;">View in App</a>' if action_url else ''}
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
                <p style="font-size: 12px; color: #666;">
                    This email was sent by NutriLens AI. 
                    <a href="#" style="color: #2E8B57;">Manage your notification preferences</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _log_notification(self, notification_data: Dict, provider: Optional[str], status: str):
        """Log notification attempt to database"""
        try:
            log_entry = NotificationLog(
                user_id=notification_data["user_id"],
                notification_type=notification_data["type"],
                provider=provider,
                status=status,
                title=notification_data["title"],
                body=notification_data["body"],
                data=notification_data.get("data", {}),
                retry_count=notification_data.get("retry_count", 0),
                created_at=datetime.utcnow()
            )
            
            self.db.add(log_entry)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error logging notification: {str(e)}")
    
    # ===== UTILITY METHODS =====
    
    def get_notification_stats(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Get notification statistics for a user"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            logs = self.db.query(NotificationLog).filter(
                and_(
                    NotificationLog.user_id == user_id,
                    NotificationLog.created_at >= start_date
                )
            ).all()
            
            total_sent = len([log for log in logs if log.status == "sent"])
            total_failed = len([log for log in logs if log.status == "failed"])
            
            by_type = {}
            for log in logs:
                if log.notification_type not in by_type:
                    by_type[log.notification_type] = {"sent": 0, "failed": 0}
                by_type[log.notification_type][log.status] += 1
            
            return {
                "period_days": days,
                "total_notifications": len(logs),
                "total_sent": total_sent,
                "total_failed": total_failed,
                "success_rate": round((total_sent / len(logs)) * 100, 1) if logs else 0,
                "by_type": by_type
            }
            
        except Exception as e:
            logger.error(f"Error getting notification stats: {str(e)}")
            return {"error": str(e)}
    
    def update_user_preferences(
        self,
        user_id: int,
        enabled_providers: Optional[List[str]] = None,
        enabled_types: Optional[List[str]] = None,
        quiet_hours_start: Optional[int] = None,
        quiet_hours_end: Optional[int] = None,
        timezone: Optional[str] = None
    ) -> bool:
        """Update user notification preferences"""
        try:
            # Get or create preferences
            prefs = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id
            ).first()
            
            if not prefs:
                prefs = NotificationPreference(user_id=user_id)
                self.db.add(prefs)
            
            # Update preferences
            if enabled_providers is not None:
                prefs.enabled_providers = enabled_providers
            if enabled_types is not None:
                prefs.enabled_types = enabled_types
            if quiet_hours_start is not None:
                prefs.quiet_hours_start = quiet_hours_start
            if quiet_hours_end is not None:
                prefs.quiet_hours_end = quiet_hours_end
            if timezone is not None:
                prefs.timezone = timezone
            
            prefs.updated_at = datetime.utcnow()
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {str(e)}")
            self.db.rollback()
            return False
    
    async def send_test_notification(self, user_id: int, provider: str) -> bool:
        """Send a test notification for debugging"""
        
        test_notification = {
            "type": "test",
            "user_id": user_id,
            "priority": NotificationPriority.LOW,
            "title": "Test Notification",
            "body": "This is a test notification from NutriLens AI",
            "data": {"test": True},
            "created_at": datetime.utcnow().isoformat()
        }
        
        return await self._send_via_provider(test_notification, NotificationProvider(provider))

# ===== BACKGROUND TASK RUNNER =====

async def start_notification_processor(db_session_factory):
    """Start the notification processor as a background task"""
    
    async def run_processor():
        db = db_session_factory()
        try:
            notification_service = NotificationService(db)
            await notification_service.process_notification_queue()
        except Exception as e:
            logger.error(f"Notification processor crashed: {str(e)}")
        finally:
            db.close()
    
    # Run processor with auto-restart
    while True:
        try:
            await run_processor()
        except Exception as e:
            print("Restarting notification processor after error:", str(e))
            logger.error(f"Restarting notification processor after error: {str(e)}")
            await asyncio.sleep(10)  # Wait before restart