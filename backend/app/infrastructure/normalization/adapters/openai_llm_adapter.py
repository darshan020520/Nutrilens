"""
OpenAI LLM Adapter - Executes LLM calls using OpenAI API.

Implements ILLMAdapter. This adapter is intentionally "dumb":
- Takes pre-rendered messages (doesn't know where they came from)
- Uses config as-is (doesn't decide model/temperature)
- Returns result + token count (doesn't track budgets)

Does NOT know about:
- Users or budgets (Governor's job)
- Prompt templates (Registry's job)
- Domain concepts like "verify_match" or "convert_to_grams"
"""
import logging
from typing import Dict, Any, List, Tuple, Type, TypeVar
from pydantic import BaseModel
import instructor
from openai import AsyncOpenAI
from app.infrastructure.normalization.interfaces import ILLMAdapter
from app.core.exceptions import LLMServiceError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAILLMAdapter(ILLMAdapter):
    """
    OpenAI implementation of ILLMAdapter.

    Uses Instructor library for structured outputs with Pydantic models.
    Receives singleton AsyncOpenAI client via dependency injection.
    """

    def __init__(self, client: AsyncOpenAI):
        """
        Args:
            client: Singleton AsyncOpenAI client (from llm_clients.py)
        """
        self.client = instructor.from_openai(client)

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
            response_model: Pydantic model for structured output
            config: Model settings from registry

        Returns:
            Tuple of:
            - result: Parsed Pydantic model instance
            - tokens_used: Actual total tokens consumed (input + output)

        Raises:
            LLMServiceError: If LLM API call fails
        """
        # Extract config values with defaults
        model = config.get("model", "gpt-4o-mini")
        temperature = config.get("temperature", 0)
        max_tokens = config.get("max_tokens", 1000)
        max_retries = config.get("retries", 2)

        try:
            # Use create_with_completion to get both result and raw response
            result, completion = await self.client.chat.completions.create_with_completion(
                model=model,
                response_model=response_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=max_retries
            )

            # Extract actual token usage from completion
            tokens_used = completion.usage.total_tokens if completion.usage else 0

            logger.debug(
                f"LLM call: model={model}, schema={response_model.__name__}, tokens={tokens_used}"
            )

            return result, tokens_used

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise LLMServiceError(
                message=f"LLM call failed: {str(e)}",
                original_error=e
            )
