from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

from app.models.database import User, NotificationPreference
from app.repositories.interfaces.auth_repository import IAuthRepository


class AuthRepository(IAuthRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def create(self, email: str, hashed_password: str) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_last_login(self, user_id: int) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)
            return user
        return None

    async def set_email_verification_token(self, user_id: int, token: str) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.email_verification_token = token
            user.email_verification_sent_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(user)
            return user
        return None

    async def get_by_email_verification_token(self, token: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email_verification_token == token)
        )
        return result.scalars().first()

    async def mark_email_verified(self, user_id: int) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if user:
            user.email_verified = True
            user.email_verified_at = datetime.utcnow()
            user.email_verification_token = None
            user.email_verification_sent_at = None
            await self.db.commit()
            await self.db.refresh(user)
            return user
        return None

    async def create_notification_preferences(self, user_id: int) -> NotificationPreference:
        try:
            result = await self.db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == user_id
                )
            )
            existing = result.scalars().first()

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
            await self.db.commit()
            await self.db.refresh(preferences)
            logger.info(f"Created default notification preferences for user {user_id}")
            return preferences

        except Exception as e:
            logger.error(f"Error creating default notification preferences: {str(e)}")
            await self.db.rollback()
            raise

    async def get_notification_preferences(self, user_id: int) -> Optional[NotificationPreference]:
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        )
        return result.scalars().first()

    async def update_notification_preferences(self, user_id: int, updates: dict) -> Optional[NotificationPreference]:
        pref = await self.get_notification_preferences(user_id)
        if not pref:
            return None
        for key, value in updates.items():
            setattr(pref, key, value)
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def update_whatsapp_number(self, user_id: int, whatsapp_number: str) -> Optional[NotificationPreference]:
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        )
        pref = result.scalars().first()
        if not pref:
            return None
        pref.whatsapp_number = whatsapp_number
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def get_all_active(self) -> List[User]:
        result = await self.db.execute(select(User).where(User.is_active == True))
        return result.unique().scalars().all()
