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

    def __init__(self, client: AsyncOpenAI):
        self.client = instructor.from_openai(client)

    async def execute(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[T],
        config: Dict[str, Any]
    ) -> Tuple[T, int]:

        model = config.get("model", "gpt-4o-mini")
        temperature = config.get("temperature", 0)
        max_tokens = config.get("max_tokens", 1000)
        max_retries = config.get("retries", 2)

        try:

            result, completion = await self.client.chat.completions.create_with_completion(
                model=model,
                response_model=response_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                max_retries=max_retries
            )

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
