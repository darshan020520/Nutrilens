from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from loguru import logger

from app.models.database import User, NotificationPreference
from app.repositories.interfaces.auth_repository import IAuthRepository


class AuthRepository(IAuthRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, email: str, hashed_password: str) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_last_login(self, user_id: int) -> Optional[User]:
        user = self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user
        return None

    def set_email_verification_token(self, user_id: int, token: str) -> Optional[User]:
        user = self.get_by_id(user_id)
        if user:
            user.email_verification_token = token
            user.email_verification_sent_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user
        return None

    def get_by_email_verification_token(self, token: str) -> Optional[User]:
        return self.db.query(User).filter(User.email_verification_token == token).first()

    def mark_email_verified(self, user_id: int) -> Optional[User]:
        user = self.get_by_id(user_id)
        if user:
            user.email_verified = True
            user.email_verified_at = datetime.utcnow()
            user.email_verification_token = None
            user.email_verification_sent_at = None
            self.db.commit()
            self.db.refresh(user)
            return user
        return None

    def create_notification_preferences(self, user_id: int) -> NotificationPreference:
        try:
            existing = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id
            ).first()

            if existing:
                logger.info(f"Notification preferences already exist for user {user_id}")
                return existing

            preferences = NotificationPreference(
                user_id=user_id,
                enabled_providers=["email"],
                enabled_types=["inventory_alert", "achievement"],
                quiet_hours_start=22,
                quiet_hours_end=7
            )
            self.db.add(preferences)
            self.db.commit()
            self.db.refresh(preferences)
            logger.info(f"Created default notification preferences for user {user_id}")
            return preferences

        except Exception as e:
            logger.error(f"Error creating default notification preferences: {str(e)}")
            self.db.rollback()
            raise

    def get_all_active(self) -> List[User]:

        return self.db.query(User).filter(User.is_active == True).all()
