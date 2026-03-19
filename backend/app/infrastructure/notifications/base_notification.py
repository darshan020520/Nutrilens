from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime


class BaseNotification(ABC):
    
    def __init__(self, user_id: int, metadata: Dict[str, Any]):
        """
        Initialize notification with user and event metadata.

        Args:
            user_id: Recipient user ID
            metadata: Event-specific data for notification context
        """
        self.user_id = user_id
        self.metadata = metadata

    def create(self) -> Dict[str, Any]:
        

        channels = self.determine_channels()


        priority = self.calculate_priority()


        context = self.build_notification_context()


        common_metadata = self._add_common_metadata()


        return {
            "user_id": self.user_id,
            "type": self.get_notification_type(),
            "priority": priority,
            "channels": channels,
            "context": context,
            "metadata": common_metadata,
            "created_at": datetime.utcnow().isoformat()
        }


    @abstractmethod
    def get_notification_type(self) -> str:
        pass

    @abstractmethod
    def determine_channels(self) -> List[str]:
        pass

    @abstractmethod
    def calculate_priority(self) -> str:
        pass

    @abstractmethod
    def build_notification_context(self) -> Dict[str, Any]:
        pass


    def _add_common_metadata(self) -> Dict[str, Any]:
        return {
            "retry_count": 0,
            "max_retries": 5,
            "source": "notification_system",
            "version": "1.0"
        }
