"""
Notification generators using Template Pattern.

Base generator defines algorithm structure, subclasses customize specific steps.
"""

from .base_generator import NotificationGenerator

__all__ = ["NotificationGenerator"]
