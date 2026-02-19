"""
Helpers for IST-based datetime handling in meal planning/tracking flows.

Datetimes in meal tables are stored as naive values, so these helpers
normalize incoming timezone-aware values into IST naive datetimes.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Return timezone-aware current datetime in IST."""
    return datetime.now(IST)


def now_ist_naive() -> datetime:
    """Return current IST datetime without timezone info."""
    return now_ist().replace(tzinfo=None)


def today_ist() -> date:
    """Return current calendar date in IST."""
    return now_ist().date()


def to_ist_naive(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to IST naive; keep naive input as-is."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(IST).replace(tzinfo=None)


def start_of_day_naive(target_date: date) -> datetime:
    return datetime.combine(target_date, time.min)


def end_of_day_naive(target_date: date) -> datetime:
    return datetime.combine(target_date, time.max)
