from abc import ABC, abstractmethod
from app.domain.notifications import NotificationMessage, DeliveryResult
from app.models.database import User


class INotificationChannel(ABC):

    @abstractmethod
    async def send(self, notification: NotificationMessage, user: User) -> DeliveryResult:
        pass

    @abstractmethod
    def validate(self, user: User) -> bool:
        pass

    @abstractmethod
    def get_channel_type(self) -> str:
        pass
