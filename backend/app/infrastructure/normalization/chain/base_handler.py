from abc import ABC, abstractmethod
from typing import Optional
import logging
from app.infrastructure.normalization.chain.match_context import MatchContext

logger = logging.getLogger(__name__)


class IMatchHandler(ABC):
    def __init__(self):
        self._next_handler: Optional[IMatchHandler] = None

    def set_next(self, handler: 'IMatchHandler') -> 'IMatchHandler':
        self._next_handler = handler
        return handler

    async def handle(self, context: MatchContext) -> MatchContext:

        await self._process(context)

        if context.should_continue() and self._next_handler:
            return await self._next_handler.handle(context)

        return context

    @abstractmethod
    async def _process(self, context: MatchContext) -> None:
        pass