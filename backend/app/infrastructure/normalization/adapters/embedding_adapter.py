"""Embedding Adapter - Generic adapter with caching for any embedding service

This adapter is provider-agnostic. It wraps any IEmbeddingService implementation
(OpenAI, Anthropic, Cohere, etc.) and adds caching functionality.
"""
from typing import List
import logging
from app.infrastructure.normalization.interfaces import IEmbeddingAdapter, IEmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingAdapter(IEmbeddingAdapter):
    """
    Generic embedding adapter with caching

    Responsibilities:
    - Wrap any embedding service provider (OpenAI, Anthropic, etc.)
    - Cache embeddings in Redis to avoid redundant API calls
    - Return cached embeddings when available

    This adapter is provider-agnostic - it depends on IEmbeddingService interface,
    not on any specific provider implementation.
    """

    def __init__(self, embedding_service: IEmbeddingService, cache_adapter):
        """
        Args:
            embedding_service: Any service implementing IEmbeddingService
            cache_adapter: RedisCacheAdapter instance
        """
        self.embedding_service = embedding_service
        self.cache = cache_adapter

    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding with caching

        Args:
            text: Text to embed

        Returns:
            List of 1536 floats
        """
        # Check cache first
        cached = await self.cache.get_embedding(text)
        if cached:
            logger.debug(f"Embedding cache hit for: {text}")
            return cached

        # Generate new embedding
        embedding = await self.embedding_service.get_embedding(text)

        # Cache for 24 hours
        await self.cache.set_embedding(text, embedding)

        return embedding

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts with caching

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings in same order
        """
        results = []
        uncached_indices = []
        uncached_texts = []

        # Check cache for each text
        for idx, text in enumerate(texts):
            cached = await self.cache.get_embedding(text)
            if cached:
                results.append(cached)
            else:
                results.append(None)
                uncached_indices.append(idx)
                uncached_texts.append(text)

        # Generate embeddings for uncached texts
        if uncached_texts:
            new_embeddings = await self.embedding_service.get_embeddings_batch(uncached_texts)

            # Cache and insert new embeddings
            for idx, text, embedding in zip(uncached_indices, uncached_texts, new_embeddings):
                await self.cache.set_embedding(text, embedding)
                results[idx] = embedding

        return results
