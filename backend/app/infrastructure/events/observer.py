from abc import ABC, abstractmethod
from typing import Dict


class IObserver(ABC):

    @abstractmethod
    async def update(self, event: Dict) -> None:

        pass
