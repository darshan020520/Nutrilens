"""Matcher Chain - Coordinates matching strategies using Chain of Responsibility"""
from typing import Optional, Tuple, List
import logging
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext

logger = logging.getLogger(__name__)


class MatcherChain:
    """
    Chain of Responsibility for item matching

    Implements proper Chain of Responsibility pattern:
    - Builds chain of handlers (ExactMatcher -> AliasMatcher -> VectorMatcher -> LLMMatcher)
    - Creates shared context object
    - Passes context through chain
    - Returns match result from context

    Responsibilities:
    - Build handler chain with set_next()
    - Create MatchContext for each request
    - Start chain execution
    - Extract result from context
    """

    def __init__(self, handlers: List[IMatchHandler]):
        """
        Args:
            handlers: List of IMatchHandler instances in order
                     [ExactMatcherHandler, AliasMatcherHandler, VectorMatcherHandler, LLMMatcherHandler]
        """
        if not handlers:
            raise ValueError("MatcherChain requires at least one handler")

        # Build the chain by linking handlers
        self.first_handler = handlers[0]
        for i in range(len(handlers) - 1):
            handlers[i].set_next(handlers[i + 1])

        logger.info(f"MatcherChain initialized with {len(handlers)} handlers")

    async def match(self, text: str, user_id: int) -> Optional[Tuple]:
        """
        Execute chain to match text.

        Args:
            text: User input text to match
            user_id: User ID for token budget tracking (used by LLM handler)

        Returns:
            - 4-tuple (item_id, item_name, strategy, confidence) if matched
            - 5-tuple (None, normalized_name, "unknown_item", confidence, category) if unknown item detected
            - None if no match and not a valid food item
        """
        # Create shared context with user_id
        context = MatchContext(user_text=text, user_id=user_id)

        # Start chain execution
        result_context = await self.first_handler.handle(context)

        # CASE 1: Item matched in database
        if result_context.matched:
            logger.info(
                f"Match found: '{text}' -> item_id {result_context.item_id} "
                f"via {result_context.match_strategy} (confidence: {result_context.confidence:.3f})"
            )
            return (
                result_context.item_id,
                result_context.item_name,
                result_context.match_strategy,
                result_context.confidence
            )

        # CASE 2: Unknown item detected (not in database, but is a valid food item)
        if result_context.unknown_item_detected:
            logger.info(
                f"Unknown item detected: '{text}' -> '{result_context.unknown_item_name}' "
                f"(category: {result_context.unknown_item_category}, confidence: {result_context.unknown_item_confidence:.3f})"
            )
            return (
                None,  # No item_id
                result_context.unknown_item_name,
                "unknown_item",  # Special strategy
                result_context.unknown_item_confidence,
                result_context.unknown_item_category  # 5th element
            )

        # CASE 3: No match and not a valid food item (garbage input)
        logger.debug(f"No match found for: '{text}'")
        return None
