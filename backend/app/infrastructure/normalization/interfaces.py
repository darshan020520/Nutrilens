"""Abstract interfaces for normalization and LLM architecture"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# =============================================================================
# EMBEDDING INTERFACES
# =============================================================================

class IEmbeddingService(ABC):
    """
    Interface for embedding service providers

    Allows swapping embedding providers (OpenAI, Anthropic, Cohere, etc.)
    Each provider implements this interface with their specific API
    """

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for single text

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors in same order as input
        """
        pass


class IEmbeddingAdapter(ABC):
    """
    Interface for embedding adapters

    Allows swapping embedding providers (OpenAI, Cohere, etc.)
    without changing business logic
    """

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for single text

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors in same order as input
        """
        pass


# =============================================================================
# LLM ARCHITECTURE INTERFACES
# =============================================================================

class IPromptRegistry(ABC):
    """
    Interface for prompt storage and retrieval.

    Responsibilities:
    - Fetch prompt templates from storage (MongoDB, PostgreSQL, etc.)
    - Render templates with provided variables
    - Return config (model, temperature, max_tokens) alongside messages

    The registry knows WHAT to ask but not HOW to ask or WHO is asking.
    """

    @abstractmethod
    async def get_rendered_prompt(
        self,
        slug: str,
        variables: Dict[str, Any]
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """
        Fetch and render a prompt template.

        Args:
            slug: Unique identifier for the prompt (e.g., "verify_match", "estimate_nutrition")
            variables: Values to inject into the template (e.g., {"user_text": "red capsicum"})

        Returns:
            Tuple of:
            - messages: List of rendered messages [{"role": "user", "content": "..."}]
            - config: Dict with model settings {"model": "gpt-4o-mini", "temperature": 0, "max_tokens": 500}

        Raises:
            KeyError: If slug not found in registry
        """
        pass


class ITokenGovernor(ABC):
    """
    Interface for token budget management.

    Implements pessimistic reservation pattern:
    1. RESERVE: Lock max possible tokens BEFORE LLM call (atomic)
    2. LLM call happens
    3. REFUND: Return unused tokens AFTER call completes

    This prevents race conditions where concurrent requests could exceed budget.
    The governor knows about budgets but not about prompts or LLM providers.
    """

    @abstractmethod
    async def reserve(self, user_id: int, amount: int, limit: int) -> bool:
        """
        Atomically reserve tokens for a user.

        Uses pessimistic locking - reserves the full estimated amount upfront.
        If reservation would exceed limit, returns False without reserving.

        Args:
            user_id: User ID
            amount: Number of tokens to reserve (input + max_output estimate)
            limit: User's daily token limit

        Returns:
            True if reservation successful, False if would exceed budget
        """
        pass

    @abstractmethod
    async def refund(self, user_id: int, amount: int) -> None:
        """
        Refund unused tokens after LLM call completes.

        Called with: reserved_amount - actual_tokens_used

        Args:
            user_id: User ID
            amount: Number of tokens to refund (must be >= 0)
        """
        pass


class ILLMAdapter(ABC):
    """
    Interface for LLM execution.

    The adapter is intentionally "dumb" - it only knows HOW to execute:
    - Takes pre-rendered messages (doesn't know where they came from)
    - Takes config (doesn't decide model/temperature)
    - Returns result + token count (doesn't track budgets)

    This allows swapping OpenAI for Anthropic, Azure, etc. without
    changing any business logic.

    Exceptions propagate to global handler - no try/except for LLM errors.
    """

    @abstractmethod
    async def execute(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        config: Dict[str, Any]
    ) -> Tuple[T, int]:
        """
        Execute LLM call and return structured response.

        Args:
            messages: Pre-rendered messages [{"role": "user", "content": "..."}]
            response_model: Pydantic model for structured output (used by Instructor)
            config: Model settings {"model": "gpt-4o-mini", "temperature": 0, "max_tokens": 500, "retries": 2}

        Returns:
            Tuple of:
            - result: Parsed Pydantic model instance
            - tokens_used: Actual total tokens consumed (input + output)

        Raises:
            LLMServiceError: If LLM API call fails
        """
        pass