import logging
from typing import Dict, Any, Type, TypeVar, List
import tiktoken
from pydantic import BaseModel

from app.infrastructure.normalization.interfaces import (
    IPromptRegistry,
    ITokenGovernor,
    ILLMAdapter
)
from app.core.exceptions import TokenBudgetExceeded
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_DAILY_TOKEN_LIMIT = getattr(settings, "daily_token_limit", 100000)


def count_tokens(messages: List[Dict[str, str]], model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    token_count = 0
    for message in messages:
        token_count += 4
        for key, value in message.items():
            token_count += len(encoding.encode(str(value)))
    token_count += 2  
    return token_count


class LLMOrchestrator:
    def __init__(
        self,
        registry: IPromptRegistry,
        governor: ITokenGovernor,
        adapter: ILLMAdapter
    ):
        self.registry = registry
        self.governor = governor
        self.adapter = adapter

    async def run(
        self,
        user_id: int,
        slug: str,
        variables: Dict[str, Any],
        response_model: Type[T],
        daily_limit: int = DEFAULT_DAILY_TOKEN_LIMIT
    ) -> T:

        messages, config = await self.registry.get_rendered_prompt(slug, variables)

        model = config.get("model", "gpt-4o-mini")
        max_tokens = config.get("max_tokens", 1000)

        input_tokens = count_tokens(messages, model)
        reservation = input_tokens + max_tokens

        logger.debug(
            f"Orchestrator: slug={slug}, input_tokens={input_tokens}, "
            f"max_output={max_tokens}, reservation={reservation}"
        )

        allowed = await self.governor.reserve(user_id, reservation, daily_limit)
        if not allowed:
            logger.warning(f"Token budget exceeded for user {user_id}")
            raise TokenBudgetExceeded(
                message="Daily token budget exceeded",
                used=0,
                limit=daily_limit
            )

        try:
            print("Messages sent to LLM:", messages)
            result, actual_tokens = await self.adapter.execute(
                messages=messages,
                response_model=response_model,
                config=config
            )

            refund_amount = reservation - actual_tokens
            if refund_amount > 0:
                await self.governor.refund(user_id, refund_amount)
                logger.debug(
                    f"Orchestrator: actual_tokens={actual_tokens}, refunded={refund_amount}"
                )

            return result

        except Exception as e:
            await self.governor.refund(user_id, reservation)
            logger.error(f"LLM call failed, refunded {reservation} tokens: {e}")
            raise
