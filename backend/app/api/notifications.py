# backend/app/api/notifications.py
"""
Simple notification preferences API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pydantic import BaseModel

from app.models.database import get_db, User, NotificationPreference
from app.services.notification_service import NotificationService
from app.services.auth import get_current_user_dependency as get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Simple Pydantic schemas
class NotificationPreferenceUpdate(BaseModel):
    enabled_providers: Optional[List[str]] = None
    enabled_types: Optional[List[str]] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None

class NotificationPreferenceResponse(BaseModel):
    id: int
    user_id: int
    enabled_providers: List[str]
    enabled_types: List[str]
    quiet_hours_start: int
    quiet_hours_end: int
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's notification preferences"""
    
    preferences = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id
    ).first()
    
    if not preferences:
        # Create default preferences
        preferences = NotificationPreference(
            user_id=current_user.id,
            enabled_providers=["email"],  # Start with email as most reliable
            enabled_types=["inventory_alert", "achievement"],
            quiet_hours_start=22,
            quiet_hours_end=7
        )
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    
    return preferences

@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def update_notification_preferences(
    preferences_update: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification preferences"""
    
    preferences = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == current_user.id
    ).first()
    
    if not preferences:
        # Create if doesn't exist
        preferences = NotificationPreference(user_id=current_user.id)
        db.add(preferences)
    
    # Update only provided fields
    update_data = preferences_update.dict(exclude_unset=True)
    
    # Basic validation
    valid_providers = ["push", "email", "sms", "whatsapp"]
    valid_types = ["meal_reminder", "inventory_alert", "achievement", "daily_summary", "weekly_report"]
    
    if "enabled_providers" in update_data:
        for provider in update_data["enabled_providers"]:
            if provider not in valid_providers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid provider: {provider}. Valid: {valid_providers}"
                )
    
    if "enabled_types" in update_data:
        for notification_type in update_data["enabled_types"]:
            if notification_type not in valid_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid type: {notification_type}. Valid: {valid_types}"
                )
    
    # Update preferences
    for key, value in update_data.items():
        setattr(preferences, key, value)
    
    db.commit()
    db.refresh(preferences)
    
    return preferences

@router.post("/test/{provider}")
async def test_notification(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a test notification"""
    
    valid_providers = ["push", "email", "sms", "whatsapp"]
    if provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Valid: {valid_providers}"
        )
    
    notification_service = NotificationService(db)
    
    try:
        success = await notification_service.send_test_notification(
            user_id=current_user.id,
            provider=provider
        )
        
        return {
            "success": success,
            "message": f"Test notification {'sent' if success else 'failed'} via {provider}"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending test notification: {str(e)}"
        )

@router.get("/stats")
async def get_notification_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get basic notification statistics"""
    
    notification_service = NotificationService(db)
    stats = notification_service.get_notification_stats(current_user.id, days=7)
    
    return stats