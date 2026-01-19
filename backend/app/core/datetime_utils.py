"""
Datetime utilities for consistent timezone handling across the application.

All datetime operations should use UTC to avoid timezone-related bugs.
"""
from datetime import datetime, timezone
from typing import Optional


class DateTimeHelper:
    """Helper class for consistent UTC datetime operations"""

    @staticmethod
    def now_utc() -> datetime:
        """
        Get current UTC datetime.

        Returns:
            Current datetime in UTC timezone

        Usage:
            Instead of: datetime.now() or datetime.utcnow()
            Use: DateTimeHelper.now_utc()
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def days_until(future_date: Optional[datetime]) -> Optional[int]:
        """
        Calculate days until a future date from now (UTC).

        Args:
            future_date: Target datetime (can be None)

        Returns:
            Number of days until future_date, or None if future_date is None
            Negative if future_date is in the past

        Example:
            expiry = datetime(2025, 12, 30, tzinfo=timezone.utc)
            days = DateTimeHelper.days_until(expiry)  # e.g., 3
        """
        if not future_date:
            return None
        return (future_date - DateTimeHelper.now_utc()).days

    @staticmethod
    def days_since(past_date: Optional[datetime]) -> Optional[int]:
        """
        Calculate days since a past date from now (UTC).

        Args:
            past_date: Past datetime (can be None)

        Returns:
            Number of days since past_date, or None if past_date is None
            Negative if past_date is in the future

        Example:
            purchase = datetime(2025, 12, 20, tzinfo=timezone.utc)
            days = DateTimeHelper.days_since(purchase)  # e.g., 7
        """
        if not past_date:
            return None
        return (DateTimeHelper.now_utc() - past_date).days
