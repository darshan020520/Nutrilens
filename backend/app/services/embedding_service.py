"""
Embedding Service - Converts text to vector embeddings using OpenAI
"""
import openai
from typing import List
import json
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI's API

    Features:
    - Generates 1536-dimensional vectors using text-embedding-3-small
    - Batch processing for efficiency
    - Cost-efficient operations
    """

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        """
        Initialize embedding service

        Args:
            api_key: OpenAI API key
            model: Embedding model to use (default: text-embedding-3-small)
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.dimension = 1536  # text-embedding-3-small dimension

    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for single text

        Args:
            text: Text to embed (e.g., "chicken breast protein")

        Returns:
            List of 1536 floats representing the embedding
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self.dimension

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text.lower().strip()
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding for '{text}': {e}")
            # Return zero vector on error
            return [0.0] * self.dimension

    async def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Get embeddings for multiple texts efficiently

        OpenAI allows up to 2048 inputs per request, but we use smaller batches
        for better error handling

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call (default: 100)

        Returns:
            List of embeddings in same order as input texts
        """
        if not texts:
            return []

        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Filter empty strings and clean
            batch_clean = [text.lower().strip() if text else "" for text in batch]

            try:
                # Call OpenAI API
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch_clean
                )

                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.info(f"Generated {len(batch_embeddings)} embeddings (batch {i//batch_size + 1})")
            except Exception as e:
                logger.error(f"Error in batch {i//batch_size + 1}: {e}")
                # Add zero vectors for failed batch
                all_embeddings.extend([[0.0] * self.dimension] * len(batch))

        return all_embeddings

    def embedding_to_db_string(self, embedding: List[float]) -> str:
        """
        Convert embedding to string format for database storage

        Args:
            embedding: List of floats

        Returns:
            JSON string representation
        """
        return json.dumps(embedding)

    def db_string_to_embedding(self, db_string: str) -> List[float]:
        """
        Convert database string back to embedding

        Args:
            db_string: JSON string from database

        Returns:
            List of floats
        """
        if not db_string:
            return [0.0] * self.dimension
        return json.loads(db_string)
