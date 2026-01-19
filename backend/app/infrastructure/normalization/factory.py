"""
Normalizer Factory - Creates BatchNormalizer with all dependencies.

Creates a fresh BatchNormalizer instance per request. All components are
stateless wrappers around singleton clients (Redis, MongoDB, OpenAI).

Following Clean Architecture principles:
- Depends on interfaces (IEmbeddingAdapter, LLMOrchestrator)
- Uses Adapter Pattern for swappable providers
- Uses Chain of Responsibility for matchers
- Single Responsibility: Factory only creates and wires dependencies
"""
import logging
from sqlalchemy.orm import Session

# Infrastructure adapters
from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter

# Matcher handlers (Chain of Responsibility)
from app.infrastructure.normalization.matchers.exact_matcher import ExactMatcherHandler
from app.infrastructure.normalization.matchers.alias_matcher import AliasMatcherHandler
from app.infrastructure.normalization.matchers.vector_matcher import VectorMatcherHandler
from app.infrastructure.normalization.matchers.llm_matcher import LLMMatcherHandler

# Chain and components
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
    """
    Create a new BatchNormalizer instance with all dependencies wired.

    Creates fresh instance per request - all components are stateless.
    The heavy resources (TCP connections) are singletons managed elsewhere.

    Args:
        db: SQLAlchemy session for item repository
        redis_client: Redis client instance (singleton)
        llm_orchestrator: LLMOrchestrator for all LLM calls (token-budgeted)
        embedding_adapter: Embedding adapter for vector similarity matching
        item_repo: Optional pre-built ItemRepository (for reuse across requests)

    Returns:
        BatchNormalizer instance ready to process items
    """
    logger.debug("Creating BatchNormalizer instance...")

    # ===== Step 1: Create Cache Adapter =====
    cache_adapter = RedisCacheAdapter(redis_client=redis_client)

    # ===== Step 2: Create or Reuse Repository =====
    if item_repo is None:
        item_repo = ItemRepository(
            db=db,
            cache_adapter=cache_adapter
        )
        # Build and cache items (only needed on first creation)
        await item_repo.build_and_cache_items()

    # ===== Step 3: Create Match Handlers (Chain of Responsibility) =====
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

    # ===== Step 4: Create Matcher Chain =====
    matcher_chain = MatcherChain(
        handlers=[exact_handler, alias_handler, vector_handler, llm_handler]
    )

    # ===== Step 5: Create Unit Converter =====
    unit_converter = UnitConverter(llm_orchestrator=llm_orchestrator)

    # ===== Step 6: Create Batch Normalizer =====
    # Note: BatchNormalizer handles batch extraction directly via orchestrator
    # StructureExtractor is no longer needed as a separate component
    normalizer = BatchNormalizer(
        llm_orchestrator=llm_orchestrator,
        matcher_chain=matcher_chain,
        unit_converter=unit_converter
    )

    logger.debug("BatchNormalizer instance created")

    return normalizer