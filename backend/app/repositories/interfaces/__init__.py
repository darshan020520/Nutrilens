"""
Repository Interfaces

Define contracts for data access.
All repositories implement these interfaces.
"""

from app.repositories.interfaces.base_repository import IRepository
from app.repositories.interfaces.tracking_repository import ITrackingRepository
from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.repositories.interfaces.consumption_analytics_repository import IConsumptionAnalyticsRepository
from app.repositories.interfaces.auth_repository import IAuthRepository
from app.repositories.interfaces.onboarding_repository import IOnboardingRepository
from app.repositories.interfaces.receipt_repository import IReceiptRepository

__all__ = [
    "IRepository",
    "ITrackingRepository",
    "IInventoryRepository",
    "IConsumptionAnalyticsRepository",
    "IAuthRepository",
    "IOnboardingRepository",
    "IReceiptRepository",
]
