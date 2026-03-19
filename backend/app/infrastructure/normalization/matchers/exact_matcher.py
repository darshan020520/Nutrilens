"""Exact Matcher - Matches items using exact name/alias comparison"""
import logging
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext
from app.infrastructure.normalization.repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)


class ExactMatcherHandler(IMatchHandler):

    def __init__(self, item_repository: ItemRepository):

        super().__init__()
        self.item_repo = item_repository

    def _clean_text(self, text: str) -> str:

        return text.lower().strip()

    async def _process(self, context: MatchContext) -> None:

        if context.item_cache is None:
            context.item_cache = await self.item_repo.build_and_cache_items()
            context.add_log(f"ExactMatcher: Loaded cache ({len(context.item_cache)} entries)")

        cleaned = self._clean_text(context.user_text)

        print(f"  [ExactMatcher] user_text='{context.user_text}' -> cleaned='{cleaned}' -> in_cache={cleaned in context.item_cache}")

        if cleaned in context.item_cache:
            item_id = context.item_cache[cleaned]
            context.mark_matched(
                item_id=item_id,
                item_name=cleaned,
                confidence=1.0,
                strategy="exact",
                reasoning=f"Exact match found in cache"
            )
            print(f"  [ExactMatcher] MATCHED -> item_id={item_id}")
        else:
            # Show a few cache keys that are close for debugging
            similar = [k for k in list(context.item_cache.keys())[:500] if cleaned.replace(" ", "_") == k or cleaned.replace("_", " ") == k]
            if similar:
                print(f"  [ExactMatcher] MISS but underscore variant exists in cache: {similar}")
            context.add_log(f"ExactMatcher: No match for '{cleaned}'")
