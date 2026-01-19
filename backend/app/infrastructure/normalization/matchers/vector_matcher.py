"""Vector Matcher - Matches items using embedding similarity"""
import logging
from app.infrastructure.normalization.chain.base_handler import IMatchHandler
from app.infrastructure.normalization.chain.match_context import MatchContext
from app.infrastructure.normalization.interfaces import IEmbeddingAdapter
from app.infrastructure.normalization.repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)


class VectorMatcherHandler(IMatchHandler):
    """
    Handler for vector similarity matching

    Responsibilities:
    - Generate embedding for input text (or use cached from context)
    - Store embedding in context for reuse by LLM matcher
    - Query vector database for similar items
    - Store top candidates in context
    - Mark context as matched if best match >= threshold

    Chain Position: Third matcher in chain (after ExactMatcher, AliasMatcher)
    Chain Behavior: Stops chain if match found, continues otherwise
    """

    def __init__(
        self,
        embedding_adapter: IEmbeddingAdapter,
        item_repository: ItemRepository,
        threshold: float = 0.85
    ):
        """
        Args:
            embedding_adapter: IEmbeddingAdapter for generating embeddings
            item_repository: ItemRepository for vector search
            threshold: Minimum similarity score (0-1)
        """
        super().__init__()
        self.embedding_adapter = embedding_adapter
        self.item_repo = item_repository
        self.threshold = threshold

    async def _process(self, context: MatchContext) -> None:
        """
        Try to match text using vector similarity

        Args:
            context: Shared context containing user_text
        """
        # Generate embedding if not already in context
        if context.embedding is None:
            context.embedding = await self.embedding_adapter.get_embedding(context.user_text)
            context.add_log(f"VectorMatcher: Generated embedding for '{context.user_text}'")

        # Query vector database (get top 5 for potential LLM verification)
        results = self.item_repo.vector_search(
            embedding=context.embedding,
            limit=5
        )

        if not results:
            context.add_log("VectorMatcher: No vector results found")
            logger.debug(f"Vector search returned no results for '{context.user_text}'")
            return

        # Store candidates in context for LLM matcher
        context.vector_candidates = [
            {"item_id": item_id, "item_name": item_name, "similarity": similarity}
            for item_id, item_name, similarity in results
        ]

        # Check if best match exceeds threshold
        best_item_id, best_item_name, best_similarity = results[0]

        if best_similarity >= self.threshold:
            context.mark_matched(
                item_id=best_item_id,
                item_name=best_item_name,
                confidence=best_similarity,
                strategy="vector",
                reasoning=f"Vector similarity: {best_similarity:.3f}"
            )
            context.add_log(
                f"VectorMatcher: Match found '{context.user_text}' -> '{best_item_name}' "
                f"(similarity: {best_similarity:.3f})"
            )
            logger.debug(
                f"Vector match: '{context.user_text}' -> '{best_item_name}' "
                f"(similarity: {best_similarity:.3f})"
            )
        else:
            context.add_log(
                f"VectorMatcher: Best match below threshold '{best_item_name}' "
                f"(similarity: {best_similarity:.3f} < {self.threshold})"
            )
            logger.debug(
                f"Vector match below threshold: '{context.user_text}' -> '{best_item_name}' "
                f"(similarity: {best_similarity:.3f})"
            )
