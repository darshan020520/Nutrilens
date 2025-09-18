# backend/app/services/notification_service.py
"""
Push notification service for real-time updates
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.database import User, MealLog, UserInventory, UserProfile
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for managing push notifications"""
    
    def __init__(self, db: Session):
        self.db = db
        self.notification_queue = asyncio.Queue()
    
    async def send_meal_reminder(
        self,
        user_id: int,
        meal_type: str,
        recipe_name: str,
        time_until: int
    ) -> bool:
        """Send meal reminder notification"""
        
        notification = {
            "user_id": user_id,
            "type": "meal_reminder",
            "title": f"{meal_type.capitalize()} Reminder",
            "body": f"Time to prepare {recipe_name}! Starting in {time_until} minutes.",
            "data": {
                "meal_type": meal_type,
                "recipe": recipe_name,
                "time_until": time_until
            },
            "priority": "high" if time_until <= 15 else "normal"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def send_inventory_alert(
        self,
        user_id: int,
        alert_type: str,
        items: List[str]
    ) -> bool:
        """Send inventory alert notification"""
        
        if alert_type == "low_stock":
            title = "Low Stock Alert"
            body = f"Running low on: {', '.join(items[:3])}"
        elif alert_type == "expiring":
            title = "Expiry Alert"
            body = f"Items expiring soon: {', '.join(items[:3])}"
        else:
            return False
        
        notification = {
            "user_id": user_id,
            "type": "inventory_alert",
            "title": title,
            "body": body,
            "data": {
                "alert_type": alert_type,
                "items": items
            },
            "priority": "normal"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def send_progress_update(
        self,
        user_id: int,
        compliance_rate: float,
        calories_consumed: float,
        calories_remaining: float
    ) -> bool:
        """Send daily progress update"""
        
        notification = {
            "user_id": user_id,
            "type": "progress_update",
            "title": "Daily Progress",
            "body": f"Compliance: {compliance_rate:.0f}% | {calories_consumed:.0f} cal consumed | {calories_remaining:.0f} cal remaining",
            "data": {
                "compliance_rate": compliance_rate,
                "calories_consumed": calories_consumed,
                "calories_remaining": calories_remaining
            },
            "priority": "low"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def send_achievement(
        self,
        user_id: int,
        achievement_type: str,
        message: str
    ) -> bool:
        """Send achievement notification"""
        
        notification = {
            "user_id": user_id,
            "type": "achievement",
            "title": "Achievement Unlocked! 🏆",
            "body": message,
            "data": {
                "achievement_type": achievement_type
            },
            "priority": "normal"
        }
        
        await self.notification_queue.put(notification)
        return True
    
    async def process_notification_queue(self):
        """Process notifications from queue"""
        
        while True:
            try:
                notification = await self.notification_queue.get()
                
                # In production, integrate with push notification service
                # (Firebase Cloud Messaging, AWS SNS, OneSignal, etc.)
                
                # For now, log the notification
                logger.info(f"Notification for user {notification['user_id']}: {notification['title']}")
                
                # Store in database for history
                from app.models.database import AgentInteraction
                
                interaction = AgentInteraction(
                    user_id=notification["user_id"],
                    agent_type="notification",
                    interaction_type=notification["type"],
                    response_text=notification["body"],
                    context_data=notification["data"],
                    created_at=datetime.utcnow()
                )
                
                self.db.add(interaction)
                self.db.commit()
                
            except Exception as e:
                logger.error(f"Error processing notification: {str(e)}")
                await asyncio.sleep(1)
    
    def check_achievements(self, user_id: int) -> List[Dict]:
        """Check for new achievements"""
        
        achievements = []
        
        # Check streak achievement
        week_ago = datetime.utcnow() - timedelta(days=7)
        meal_logs = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.planned_datetime >= week_ago,
                MealLog.consumed_datetime.isnot(None)
            )
        ).all()
        
        if len(meal_logs) >= 21:  # 3 meals x 7 days
            achievements.append({
                "type": "week_streak",
                "message": "7-day perfect streak! All meals logged this week!"
            })
        
        # Check calorie goal achievement
        from app.models.database import UserProfile
        
        profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        if profile and profile.goal_calories:
            today_logs = self.db.query(MealLog).filter(
                and_(
                    MealLog.user_id == user_id,
                    func.date(MealLog.consumed_datetime) == datetime.utcnow().date()
                )
            ).all()
            
            total_calories = sum(
                log.recipe.macros_per_serving.get("calories", 0) * log.portion_multiplier
                for log in today_logs
                if log.recipe and log.recipe.macros_per_serving
            )
            
            if abs(total_calories - profile.goal_calories) < profile.goal_calories * 0.05:
                achievements.append({
                    "type": "perfect_calories",
                    "message": "Perfect calorie target! Within 5% of your goal!"
                })
        
        return achievements