"""Base Handler - Interface and base implementation for Chain of Responsibility"""
from abc import ABC, abstractmethod
from typing import Optional
import logging
from app.infrastructure.normalization.chain.match_context import MatchContext

logger = logging.getLogger(__name__)


class IMatchHandler(ABC):
    """
    Interface for match handlers in Chain of Responsibility

    Chain of Responsibility Principles:
    1. Common interface for all handlers (this interface)
    2. Each handler has reference to next handler
    3. Each handler decides whether to process and/or pass to next
    4. Shared context object flows through chain
    5. Handlers are loosely coupled - don't know about each other

    References:
    - https://refactoring.guru/design-patterns/chain-of-responsibility
    - https://www.geeksforgeeks.org/system-design/chain-responsibility-design-pattern/
    """

    def __init__(self):
        """Initialize handler with no next handler"""
        self._next_handler: Optional[IMatchHandler] = None

    def set_next(self, handler: 'IMatchHandler') -> 'IMatchHandler':
        """
        Set the next handler in the chain

        Args:
            handler: Next handler to call

        Returns:
            The handler that was set (for chaining)
        """
        self._next_handler = handler
        return handler

    async def handle(self, context: MatchContext) -> MatchContext:
        """
        Handle the request and optionally pass to next handler

        This is the Template Method that defines the chain flow:
        1. Process the request (implemented by subclass)
        2. Decide whether to continue chain
        3. Pass to next handler if exists and should continue

        Args:
            context: Shared context object

        Returns:
            Modified context object
        """
        # Process request in subclass
        await self._process(context)

        # Pass to next handler if chain should continue
        if context.should_continue() and self._next_handler:
            return await self._next_handler.handle(context)

        return context

    @abstractmethod
    async def _process(self, context: MatchContext) -> None:
        """
        Process the request (implemented by concrete handlers)

        This method should:
        - Read from context to make decisions
        - Perform handler-specific logic
        - Write results back to context
        - Use context.mark_matched() if successful match found
        - Use context.add_log() to record processing steps

        Args:
            context: Shared context object to read/modify
        """
        pass