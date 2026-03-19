"""
Auth Repository Interface

Defines contract for authentication data access operations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from app.models.database import User, NotificationPreference


class IAuthRepository(ABC):
    """
    Interface for authentication data access.

    Provides methods for user authentication, creation, and related operations.
    """

    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.

        EXTRACTED FROM: auth.py (service):59 and auth.py (API):24

        Args:
            email: User email address

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID.

        EXTRACTED FROM: auth.py (service):88

        Args:
            user_id: User ID

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def update_last_login(self, user_id: int) -> Optional[User]:
        """
        Update user's last login timestamp to current time.

        EXTRACTED FROM: auth.py (API):47-48

        Args:
            user_id: User ID

        Returns:
            Updated User object with fresh last_login, None if user not found
        """
        pass

    @abstractmethod
    def set_email_verification_token(self, user_id: int, token: str) -> Optional[User]:
        """
        Persist a fresh email verification token for a user.

        Args:
            user_id: User ID
            token: New verification token

        Returns:
            Updated user, None if not found
        """
        pass

    @abstractmethod
    def get_by_email_verification_token(self, token: str) -> Optional[User]:
        """
        Resolve a user by email verification token.

        Args:
            token: Verification token

        Returns:
            User if found, None otherwise
        """
        pass

    @abstractmethod
    def mark_email_verified(self, user_id: int) -> Optional[User]:
        """
        Mark user email as verified and clear verification token fields.

        Args:
            user_id: User ID

        Returns:
            Updated user, None if not found
        """
        pass

    @abstractmethod
    def create_notification_preferences(self, user_id: int) -> NotificationPreference:
        """
        Create default notification preferences for a user.

        EXTRACTED FROM: auth.py (service):113-131

        Args:
            user_id: User ID

        Returns:
            Created notification preferences
        """
        pass

    @abstractmethod
    def get_notification_preferences(self, user_id: int) -> Optional[NotificationPreference]:
        """
        Get notification preferences for a user.

        Args:
            user_id: User ID

        Returns:
            NotificationPreference if found, None otherwise
        """
        pass

    @abstractmethod
    def update_notification_preferences(self, user_id: int, updates: dict) -> Optional[NotificationPreference]:
        """
        Update notification preferences for a user.

        Args:
            user_id: User ID
            updates: Dict of fields to update (enabled_providers, enabled_types,
                     quiet_hours_start, quiet_hours_end, timezone)

        Returns:
            Updated NotificationPreference, None if not found
        """
        pass

    @abstractmethod
    def update_whatsapp_number(self, user_id: int, whatsapp_number: str) -> Optional[NotificationPreference]:
        """
        Update the WhatsApp number for a user's notification preferences.

        Args:
            user_id: User ID
            whatsapp_number: WhatsApp number in E.164 format (e.g. +916264547414)

        Returns:
            Updated NotificationPreference, None if not found
        """
        pass

    @abstractmethod
    def get_all_active(self) -> List[User]:
        """
        Get all active users.

        Used by notification worker to send scheduled notifications
        to all active users (daily summaries, weekly reports, inventory alerts).

        Returns:
            List of User objects where is_active=True
        """
        pass
