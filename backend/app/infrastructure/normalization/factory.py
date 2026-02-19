import logging
from sqlalchemy.orm import Session

from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter

from app.infrastructure.normalization.matchers.exact_matcher import ExactMatcherHandler
from app.infrastructure.normalization.matchers.alias_matcher import AliasMatcherHandler
from app.infrastructure.normalization.matchers.vector_matcher import VectorMatcherHandler
from app.infrastructure.normalization.matchers.llm_matcher import LLMMatcherHandler

from app.infrastructure.normalization.chain.matcher_chain import MatcherChain
from app.infrastructure.normalization.converters.unit_converter import UnitConverter
from app.infrastructure.normalization.batch.batch_normalizer import BatchNormalizer
from app.infrastructure.normalization.repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)


async def create_normalizer(
    db: Session,
    redis_client,
    llm_orchestrator,
    embedding_adapter,
    item_repo: ItemRepository = None
) -> BatchNormalizer:

    logger.debug("Creating BatchNormalizer instance...")

    cache_adapter = RedisCacheAdapter(redis_client=redis_client)

    if item_repo is None:
        item_repo = ItemRepository(
            db=db,
            cache_adapter=cache_adapter
        )
        await item_repo.build_and_cache_items()

    exact_handler = ExactMatcherHandler(item_repository=item_repo)
    alias_handler = AliasMatcherHandler(item_repository=item_repo)
    vector_handler = VectorMatcherHandler(
        embedding_adapter=embedding_adapter,
        item_repository=item_repo,
        threshold=0.85
    )
    llm_handler = LLMMatcherHandler(
        llm_orchestrator=llm_orchestrator,
        confidence_threshold=0.7
    )

    matcher_chain = MatcherChain(
        handlers=[exact_handler, alias_handler, vector_handler, llm_handler]
    )

    unit_converter = UnitConverter(llm_orchestrator=llm_orchestrator)

    normalizer = BatchNormalizer(
        llm_orchestrator=llm_orchestrator,
        matcher_chain=matcher_chain,
        unit_converter=unit_converter
    )

    logger.debug("BatchNormalizer instance created")

    return normalizer