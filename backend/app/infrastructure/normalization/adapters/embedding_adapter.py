from typing import List
import logging
from app.infrastructure.normalization.interfaces import IEmbeddingAdapter, IEmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingAdapter(IEmbeddingAdapter):

    def __init__(self, embedding_service: IEmbeddingService, cache_adapter):
        self.embedding_service = embedding_service
        self.cache = cache_adapter

    async def get_embedding(self, text: str) -> List[float]:
        cached = await self.cache.get_embedding(text)
        if cached:
            logger.debug(f"Embedding cache hit for: {text}")
            return cached

        embedding = await self.embedding_service.get_embedding(text)

        await self.cache.set_embedding(text, embedding)

        return embedding

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:

        results = []
        uncached_indices = []
        uncached_texts = []

        for idx, text in enumerate(texts):
            cached = await self.cache.get_embedding(text)
            if cached:
                results.append(cached)
            else:
                results.append(None)
                uncached_indices.append(idx)
                uncached_texts.append(text)

  
        if uncached_texts:
            new_embeddings = await self.embedding_service.get_embeddings_batch(uncached_texts)

            for idx, text, embedding in zip(uncached_indices, uncached_texts, new_embeddings):
                await self.cache.set_embedding(text, embedding)
                results[idx] = embedding

        return results
    
    async def embedding_to_db_string(self, embedding: List[float]) -> str:

        return await self.embedding_service.embedding_to_db_string(embedding)
    
    async def db_string_to_embedding(self, embedding_str: str) -> List[float]:

        return await self.embedding_service.db_string_to_embedding(embedding_str)