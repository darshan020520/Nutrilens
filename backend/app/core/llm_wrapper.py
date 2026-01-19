"""
LLM Wrapper - HOW to ask (Instructor, retries, tracing)

Sits between Adapters and Singleton Client:
    Adapter (WHAT to ask) → Wrapper (HOW to ask) → Client (WHERE to ask)

Responsibilities:
- Instructor integration for structured outputs
- Retry logic
- Token budget enforcement (pre-flight check + post-call record)
- LangSmith tracing (added via @traceable decorator)
- Global timeout/retry policies
"""
import logging
from typing import Optional, Type, TypeVar, Union, List, Dict
from pydantic import BaseModel
import instructor
import tiktoken
from app.core.llm_clients import get_openai_client
from app.core.redis_client import check_and_increment_token_budget, get_current_token_usage
from app.core.exceptions import TokenBudgetExceeded, LLMServiceError
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Token budget settings (can be moved to config)
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
        # gpt-4o, gpt-4o-mini, gpt-4, gpt-3.5-turbo use cl100k_base
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


async def check_budget_preflight(user_id: int, estimated_tokens: int) -> None:
    """
    Pre-flight budget check before making LLM call.

    Checks if user has enough budget for the estimated tokens.
    Does NOT increment - just checks.

    Args:
        user_id: User ID
        estimated_tokens: Estimated tokens for this request

    Raises:
        TokenBudgetExceeded: If user would exceed budget
    """
    current_usage = await get_current_token_usage(user_id)

    if current_usage + estimated_tokens > DEFAULT_DAILY_TOKEN_LIMIT:
        raise TokenBudgetExceeded(
            message="Daily token budget exceeded",
            used=current_usage,
            limit=DEFAULT_DAILY_TOKEN_LIMIT
        )


async def record_tokens_atomic(user_id: int, tokens: int) -> None:
    """
    Atomically check and record token usage after successful LLM call.

    Uses Lua script to ensure atomic check-and-increment operation,
    preventing race conditions in concurrent requests.

    Args:
        user_id: User ID
        tokens: Actual tokens used (from API response)

    Raises:
        TokenBudgetExceeded: If budget exceeded (shouldn't happen if pre-flight worked)
    """
    allowed, current_usage, limit = await check_and_increment_token_budget(
        user_id=user_id,
        tokens=tokens,
        limit=DEFAULT_DAILY_TOKEN_LIMIT
    )

    if not allowed:
        raise TokenBudgetExceeded(
            message="Daily token budget exceeded",
            used=current_usage,
            limit=limit
        )


async def call_llm(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o-mini",
    response_model: Optional[Type[T]] = None,
    temperature: float = 0,
    max_retries: int = 3,
    max_tokens: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Union[T, str]:
    """
    Unified LLM call interface with token budget enforcement.

    Flow:
    1. PRE-FLIGHT: Estimate tokens, check budget (reject if over)
    2. CALL: Make LLM API call
    3. RECORD: Atomically record actual token usage

    Args:
        messages: List of message dicts [{"role": "user", "content": "..."}]
        model: Model to use (gpt-4o-mini, gpt-4o, etc.)
        response_model: Pydantic model for structured output (uses Instructor)
        temperature: Sampling temperature (0 = deterministic)
        max_retries: Retry attempts for structured outputs
        max_tokens: Optional token limit for response
        user_id: User ID for token budget tracking (optional, skips budget check if None)

    Returns:
        - If response_model: Instance of the Pydantic model
        - If no response_model: Raw string response

    Raises:
        TokenBudgetExceeded: If user's token budget is exhausted
        LLMServiceError: If LLM API call fails
    """
    # 1. PRE-FLIGHT CHECK
    if user_id is not None:
        estimated_tokens = count_tokens(messages, model)
        # Add max_tokens to estimate if provided (for response budget)
        if max_tokens:
            estimated_tokens += max_tokens
        await check_budget_preflight(user_id, estimated_tokens)

    # 2. MAKE LLM CALL
    client = await get_openai_client()

    try:
        if response_model:
            instructor_client = instructor.from_openai(client)

            logger.debug(f"LLM call: model={model}, schema={response_model.__name__}")

            # Use create_with_completion to get both result and raw response
            result, completion = await instructor_client.chat.completions.create_with_completion(
                model=model,
                response_model=response_model,
                max_retries=max_retries,
                temperature=temperature,
                messages=messages,
                **({"max_tokens": max_tokens} if max_tokens else {})
            )

            # 3. RECORD ACTUAL TOKEN USAGE
            if user_id is not None and completion.usage:
                await record_tokens_atomic(user_id, completion.usage.total_tokens)

            return result

        else:
            logger.debug(f"LLM call: model={model}, raw completion")

            response = await client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=messages,
                **({"max_tokens": max_tokens} if max_tokens else {})
            )

            # 3. RECORD ACTUAL TOKEN USAGE
            if user_id is not None and response.usage:
                await record_tokens_atomic(user_id, response.usage.total_tokens)

            return response.choices[0].message.content

    except TokenBudgetExceeded:
        raise  # Re-raise budget exceptions
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        raise LLMServiceError(message=f"LLM call failed: {str(e)}", original_error=e)
