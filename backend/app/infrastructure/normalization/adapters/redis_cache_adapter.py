"""Redis Cache Adapter - Handles all Redis caching operations"""
from typing import Optional, List, Any
import json
import logging

logger = logging.getLogger(__name__)


class RedisCacheAdapter:
    """
    Adapter for Redis caching with TTL strategies

    Cache Strategy:
    - Embeddings: 24h TTL (rarely change)
    - LLM responses: 1h TTL (relatively stable)
    - Item cache: 1h TTL (updates periodically)
    """

    def __init__(self, redis_client):
        """
        Args:
            redis_client: Redis client instance (from dependencies)
        """
        self.redis = redis_client
        self.EMBEDDING_TTL = 86400  # 24 hours
        self.LLM_TTL = 3600  # 1 hour
        self.CACHE_TTL = 3600  # 1 hour

    async def _get_from_cache(self, key: str, error_context: str) -> Optional[Any]:
        """
        Generic method to get value from Redis cache

        Args:
            key: Redis key
            error_context: Context for error logging

        Returns:
            Parsed JSON value or None
        """
        try:
            cached = await self.redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Redis get error for {error_context}: {e}")
        return None

    async def _set_in_cache(self, key: str, value: Any, ttl: int, error_context: str) -> None:
        """
        Generic method to set value in Redis cache with TTL

        Args:
            key: Redis key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds
            error_context: Context for error logging
        """
        try:
            await self.redis.setex(key, ttl, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis set error for {error_context}: {e}")

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get cached embedding for text"""
        key = f"embedding:{text.lower().strip()}"
        return await self._get_from_cache(key, "embedding")

    async def set_embedding(self, text: str, embedding: List[float]) -> None:
        """Cache embedding with 24h TTL"""
        key = f"embedding:{text.lower().strip()}"
        await self._set_in_cache(key, embedding, self.EMBEDDING_TTL, "embedding")

    async def get_llm_response(self, prompt_hash: str) -> Optional[dict]:
        """Get cached LLM response"""
        key = f"llm:{prompt_hash}"
        return await self._get_from_cache(key, "LLM")

    async def set_llm_response(self, prompt_hash: str, response: dict) -> None:
        """Cache LLM response with 1h TTL"""
        key = f"llm:{prompt_hash}"
        await self._set_in_cache(key, response, self.LLM_TTL, "LLM")

    async def get_item_cache(self) -> Optional[dict]:
        """Get cached item dictionary"""
        key = "items:cache"
        return await self._get_from_cache(key, "item cache")

    async def set_item_cache(self, cache: dict) -> None:
        """Cache item dictionary with 1h TTL"""
        key = "items:cache"
        await self._set_in_cache(key, cache, self.CACHE_TTL, "item cache")
