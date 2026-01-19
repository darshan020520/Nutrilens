"""Exact Matcher - Matches items using exact name/alias comparison"""
import logging
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext
from app.infrastructure.normalization.repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)


class ExactMatcherHandler(IMatchHandler):
    """
    Handler for exact matching using item cache

    Responsibilities:
    - Load item cache into context if not present
    - Clean and normalize text
    - Check exact match in cache (name + aliases)
    - Mark context as matched if found

    Chain Position: First matcher in chain (after cache loading)
    Chain Behavior: Stops chain if match found, continues otherwise
    """

    def __init__(self, item_repository: ItemRepository):
        """
        Args:
            item_repository: ItemRepository for loading item cache
        """
        super().__init__()
        self.item_repo = item_repository

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for matching"""
        return text.lower().strip()

    async def _process(self, context: MatchContext) -> None:
        """
        Try to match text exactly against item cache

        Args:
            context: Shared context containing user_text and item_cache
        """
        # Load cache if not present
        if context.item_cache is None:
            context.item_cache = await self.item_repo.build_and_cache_items()
            context.add_log(f"ExactMatcher: Loaded cache ({len(context.item_cache)} entries)")

        # Clean text
        cleaned = self._clean_text(context.user_text)

        # Check direct match
        if cleaned in context.item_cache:
            item_id = context.item_cache[cleaned]
            context.mark_matched(
                item_id=item_id,
                item_name=cleaned,  # Will be replaced with actual name from DB if needed
                confidence=1.0,
                strategy="exact",
                reasoning=f"Exact match found in cache"
            )
            context.add_log(f"ExactMatcher: Match found for '{cleaned}' -> item_id {item_id}")
            logger.debug(f"Exact match: '{context.user_text}' -> item_id {item_id}")
        else:
            context.add_log(f"ExactMatcher: No match for '{cleaned}'")
            logger.debug(f"Exact match failed for '{context.user_text}'")
