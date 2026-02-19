"""Item Repository - Data access for items with vector search"""
from typing import List, Tuple, Dict
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ItemRepository:
    """
    Repository for item data access

    Responsibilities:
    - Load all items from database
    - Build item cache (name -> id, aliases -> id)
    - Execute vector similarity search
    - Cache results in Redis
    """

    def __init__(self, db: Session, cache_adapter):
        """
        Args:
            db: SQLAlchemy session
            cache_adapter: RedisCacheAdapter instance
        """
        self.db = db
        self.cache = cache_adapter

    async def get_item_by_id(self, item_id: int):
        """
        Get item by ID

        Args:
            item_id: Item ID

        Returns:
            Item if found, None otherwise
        """
        from app.models.database import Item
        return self.db.query(Item).filter(Item.id == item_id).first()

    async def build_and_cache_items(self) -> Dict[str, int]:
        """
        Build item cache from database and store in Redis

        Returns:
            Dict mapping {item_name/alias: item_id}
        """
        # Check Redis cache first
        cached = await self.cache.get_item_cache()
        if cached:
            logger.info(f"Item cache loaded from Redis ({len(cached)} entries)")
            return cached

        # Load from database
        from app.models.database import Item

        items = self.db.query(Item).all()
        cache_dict = {}

        for item in items:
            # Add name
            cache_dict[item.canonical_name.lower().strip()] = item.id

            # Add aliases
            if item.aliases:
                for alias in item.aliases:
                    cache_dict[alias.lower().strip()] = item.id

        # Store in Redis
        await self.cache.set_item_cache(cache_dict)

        logger.info(f"Item cache built from database ({len(cache_dict)} entries)")
        return cache_dict

    def vector_search(
        self,
        embedding: List[float],
        limit: int = 5
    ) -> List[Tuple[int, str, float]]:
        """
        Search items by vector similarity

        Args:
            embedding: Query embedding vector
            limit: Max results to return

        Returns:
            List of (item_id, item_name, similarity_score)
        """
        # Debug: Check if embedding is valid
        if not embedding or len(embedding) != 1536:
            logger.error(f"Invalid embedding: length={len(embedding) if embedding else 0}")
            return []

        # Debug: Check if embedding is zero vector
        if all(v == 0.0 for v in embedding):
            logger.error("Embedding is a zero vector - embedding generation likely failed")
            return []

        logger.info(f"Vector search: embedding length={len(embedding)}, first 5 values={embedding[:5]}")

        # Convert embedding to PostgreSQL array format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Vector similarity query using pgvector
        # Note: Space before ::vector is required for SQLAlchemy parameter binding
        # Both column and parameter need casting since embedding is stored as TEXT
        query = text("""
            SELECT
                id,
                canonical_name,
                1 - (embedding::vector(1536) <=> :embedding ::vector(1536)) as similarity
            FROM items
            WHERE embedding IS NOT NULL
            ORDER BY embedding::vector(1536) <=> :embedding ::vector(1536)
            LIMIT :limit
        """)

        result = self.db.execute(query, {"embedding": embedding_str, "limit": limit})
        rows = result.fetchall()

        return [(row[0], row[1], row[2]) for row in rows]
