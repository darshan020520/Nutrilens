"""
Auth Repository

Handles database operations for authentication.
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from loguru import logger

from app.models.database import User, NotificationPreference
from app.repositories.interfaces.auth_repository import IAuthRepository


class AuthRepository(IAuthRepository):
    """
    Repository for authentication data access.

    Handles user lookups, creation, and updates for authentication flows.
    """

    def __init__(self, db: Session):
        """
        Initialize auth repository.

        Args:
            db: Database session
        """
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        EXTRACTED FROM:
        - auth.py (service):59
        - auth.py (API):24

        Args:
            email: User email

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        EXTRACTED FROM: auth.py (service):88

        Args:
            user_id: User ID

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, email: str, hashed_password: str) -> User:
        """
        Create a new user.

        EXTRACTED FROM: auth.py (service):67-73

        Args:
            email: User email
            hashed_password: Hashed password

        Returns:
            Created user with ID populated
        """
        user = User(
            email=email,
            hashed_password=hashed_password
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_last_login(self, user_id: int) -> Optional[User]:
        """
        Update user's last login timestamp.

        EXTRACTED FROM: auth.py (API):47-48

        Args:
            user_id: User ID

        Returns:
            Updated User object with fresh last_login, None if user not found
        """
        user = self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user
        return None

    def create_notification_preferences(self, user_id: int) -> NotificationPreference:
        """
        Create default notification preferences for new user.

        EXTRACTED FROM: auth.py (service):113-131

        Args:
            user_id: User ID

        Returns:
            Created notification preferences

        Raises:
            Exception: If preferences creation fails
        """
        try:
            # Check if preferences already exist
            existing = self.db.query(NotificationPreference).filter(
                NotificationPreference.user_id == user_id
            ).first()

            if existing:
                logger.info(f"Notification preferences already exist for user {user_id}")
                return existing

            # Create default preferences
            preferences = NotificationPreference(
                user_id=user_id,
                enabled_providers=["email"],  # Start with email
                enabled_types=["inventory_alert", "achievement"],  # Essential notifications
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
        """
        Get all active users.

        Used by notification worker to send scheduled notifications
        to all active users (daily summaries, weekly reports, inventory alerts).

        Returns:
            List of User objects where is_active=True
        """
        return self.db.query(User).filter(User.is_active == True).all()
