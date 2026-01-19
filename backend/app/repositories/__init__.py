"""
Repository Layer

This layer handles ALL database access.
Services MUST use repositories, never access db directly.
"""

# Import all repository implementations
from app.repositories.tracking_repository import TrackingRepository
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.consumption_analytics_repository import ConsumptionAnalyticsRepository
from app.repositories.user_profile_repository import UserProfileRepository

__all__ = [
    "TrackingRepository",
    "InventoryRepository",
    "ConsumptionAnalyticsRepository",
    "UserProfileRepository",
]
