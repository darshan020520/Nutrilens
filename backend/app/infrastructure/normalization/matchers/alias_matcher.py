import logging
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext
from app.infrastructure.normalization.repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)


class AliasMatcherHandler(IMatchHandler):


    def __init__(self, item_repository: ItemRepository):

        super().__init__()
        self.item_repo = item_repository

    def _generate_variations(self, text: str) -> list:

        variations = [text]

        if text.endswith('s'):
            variations.append(text[:-1])
        else:
            variations.append(text + 's')

        return variations

    async def _process(self, context: MatchContext) -> None:

        if context.item_cache is None:
            context.item_cache = await self.item_repo.build_and_cache_items()
            context.add_log(f"AliasMatcher: Loaded cache ({len(context.item_cache)} entries)")

        cleaned = context.user_text.lower().strip()
        variations = self._generate_variations(cleaned)

        print(f"  [AliasMatcher] cleaned='{cleaned}', variations={variations}")

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
