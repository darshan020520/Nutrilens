"""Alias Matcher - Matches items using fuzzy alias comparison"""
import logging
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext
from app.infrastructure.normalization.repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)


class AliasMatcherHandler(IMatchHandler):
    """
    Handler for alias matching using fuzzy comparison

    Responsibilities:
    - Load item cache into context if not present
    - Try fuzzy variations (plurals, singulars, partial matches)
    - Check aliases in cache
    - Mark context as matched if found

    Chain Position: Second matcher in chain (after ExactMatcher)
    Chain Behavior: Stops chain if match found, continues otherwise
    """

    def __init__(self, item_repository: ItemRepository):
        """
        Args:
            item_repository: ItemRepository for loading item cache
        """
        super().__init__()
        self.item_repo = item_repository

    def _generate_variations(self, text: str) -> list:
        """Generate fuzzy variations of text"""
        variations = [text]

        # Add plural/singular
        if text.endswith('s'):
            variations.append(text[:-1])
        else:
            variations.append(text + 's')

        return variations

    async def _process(self, context: MatchContext) -> None:
        """
        Try to match text using aliases and fuzzy matching

        Args:
            context: Shared context containing user_text and item_cache
        """
        # Load cache if not present
        if context.item_cache is None:
            context.item_cache = await self.item_repo.build_and_cache_items()
            context.add_log(f"AliasMatcher: Loaded cache ({len(context.item_cache)} entries)")

        # Generate variations
        cleaned = context.user_text.lower().strip()
        variations = self._generate_variations(cleaned)

        # Try each variation
        for variant in variations:
            if variant in context.item_cache:
                item_id = context.item_cache[variant]
                context.mark_matched(
                    item_id=item_id,
                    item_name=variant,
                    confidence=0.95,  # Slightly lower than exact match
                    strategy="alias",
                    reasoning=f"Alias match: '{cleaned}' -> '{variant}'"
                )
                context.add_log(f"AliasMatcher: Match found '{cleaned}' -> '{variant}' -> item_id {item_id}")
                logger.debug(f"Alias match: '{context.user_text}' -> '{variant}' -> item_id {item_id}")
                return

        context.add_log(f"AliasMatcher: No match for '{cleaned}' or its variations")
        logger.debug(f"Alias match failed for '{context.user_text}'")
