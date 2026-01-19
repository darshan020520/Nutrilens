"""
LLM Orchestrator - The single entry point for all LLM calls.

Coordinates the four-step flow:
1. FETCH: Get rendered prompt from registry
2. RESERVE: Lock tokens via governor (pessimistic)
3. EXECUTE: Call LLM via adapter
4. REFUND: Return unused tokens via governor

Usage:
    orchestrator = LLMOrchestrator(registry, governor, adapter)
    result = await orchestrator.run(
        user_id=123,
        slug="verify_match",
        variables={"user_text": "red capsicum", "candidates": "[...]"},
        response_model=VerifyMatchResult
    )
"""
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

# Default daily token limit (can be overridden per user)
DEFAULT_DAILY_TOKEN_LIMIT = getattr(settings, "daily_token_limit", 100000)


def count_tokens(messages: List[Dict[str, str]], model: str) -> int:
    """
    Count input tokens for messages using tiktoken.

    Args:
        messages: List of message dicts [{"role": "...", "content": "..."}]
        model: Model name for encoding selection

    Returns:
        Estimated token count
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback for unknown models
        encoding = tiktoken.get_encoding("cl100k_base")

    token_count = 0
    for message in messages:
        # Every message follows <|start|>{role}\n{content}<|end|>
        token_count += 4  # overhead per message
        for key, value in message.items():
            token_count += len(encoding.encode(str(value)))
    token_count += 2  # priming for assistant reply

    return token_count


class LLMOrchestrator:
    """
    Orchestrates LLM calls through registry, governor, and adapter.

    This is the ONLY entry point for LLM calls in the application.
    All components are injected via constructor (dependency injection).
    """

    def __init__(
        self,
        registry: IPromptRegistry,
        governor: ITokenGovernor,
        adapter: ILLMAdapter
    ):
        """
        Args:
            registry: Prompt storage (MongoDB implementation)
            governor: Token budget manager (Redis implementation)
            adapter: LLM executor (OpenAI implementation)
        """
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
        """
        Execute an LLM call with full orchestration.

        Args:
            user_id: User ID for token budget tracking
            slug: Prompt identifier (e.g., "verify_match")
            variables: Template variables to inject into prompt
            response_model: Pydantic model for structured output
            daily_limit: User's daily token limit (default from settings)

        Returns:
            Parsed Pydantic model instance

        Raises:
            TokenBudgetExceeded: If user's token budget is exhausted
            KeyError: If prompt slug not found in registry
            LLMServiceError: If LLM API call fails
        """
        # STEP 1: FETCH - Get rendered prompt from registry
        messages, config = await self.registry.get_rendered_prompt(slug, variables)

        model = config.get("model", "gpt-4o-mini")
        max_tokens = config.get("max_tokens", 1000)

        # STEP 2: RESERVE - Calculate and lock tokens
        input_tokens = count_tokens(messages, model)
        reservation = input_tokens + max_tokens  # Pessimistic: assume max output

        logger.debug(
            f"Orchestrator: slug={slug}, input_tokens={input_tokens}, "
            f"max_output={max_tokens}, reservation={reservation}"
        )

        allowed = await self.governor.reserve(user_id, reservation, daily_limit)
        if not allowed:
            logger.warning(f"Token budget exceeded for user {user_id}")
            raise TokenBudgetExceeded(
                message="Daily token budget exceeded",
                used=0,  # Governor doesn't return current usage on failure
                limit=daily_limit
            )

        # STEP 3: EXECUTE - Call LLM (with refund on failure)
        try:
            result, actual_tokens = await self.adapter.execute(
                messages=messages,
                response_model=response_model,
                config=config
            )

            # STEP 4: REFUND - Return unused tokens
            refund_amount = reservation - actual_tokens
            if refund_amount > 0:
                await self.governor.refund(user_id, refund_amount)
                logger.debug(
                    f"Orchestrator: actual_tokens={actual_tokens}, refunded={refund_amount}"
                )

            return result

        except Exception as e:
            # Full refund on failure - don't charge for failed calls
            await self.governor.refund(user_id, reservation)
            logger.error(f"LLM call failed, refunded {reservation} tokens: {e}")
            raise
