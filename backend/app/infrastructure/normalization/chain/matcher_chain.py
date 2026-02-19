from typing import Optional, Tuple, List
import logging
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext

logger = logging.getLogger(__name__)


class MatcherChain:

    def __init__(self, handlers: List[IMatchHandler]):
        if not handlers:
            raise ValueError("MatcherChain requires at least one handler")

        self.first_handler = handlers[0]
        for i in range(len(handlers) - 1):
            handlers[i].set_next(handlers[i + 1])

        logger.info(f"MatcherChain initialized with {len(handlers)} handlers")

    async def match(self, text: str, user_id: int) -> Optional[Tuple]:

        context = MatchContext(user_text=text, user_id=user_id)

        result_context = await self.first_handler.handle(context)

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

        logger.debug(f"No match found for: '{text}'")
        return None
