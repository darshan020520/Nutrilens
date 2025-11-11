"""
LLM Client Wrapper - Unified interface for Claude and OpenAI

Provides a unified interface for calling different LLM providers with:
- Automatic retry logic
- Cost tracking
- Rate limiting
- Error handling
- Response caching

Supported providers:
- Anthropic Claude (Haiku, Sonnet, Opus)
- OpenAI (GPT-3.5, GPT-4)

Author: NutriLens AI Team
Created: 2025-11-10
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
import time
from dataclasses import dataclass
import hashlib
import json

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class ModelType(str, Enum):
    """Available models with their characteristics"""
    # Anthropic
    CLAUDE_HAIKU = "claude-haiku-3.5"
    CLAUDE_SONNET = "claude-sonnet-4.5"
    CLAUDE_OPUS = "claude-opus-4"

    # OpenAI
    GPT_35_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4O = "gpt-4o"


# Pricing per 1M tokens (input/output) - for internal logging only
MODEL_PRICING = {
    ModelType.CLAUDE_HAIKU: (0.25, 1.25),  # $0.25/$1.25 per 1M tokens
    ModelType.CLAUDE_SONNET: (3.0, 15.0),  # $3/$15 per 1M tokens
    ModelType.CLAUDE_OPUS: (15.0, 75.0),  # $15/$75 per 1M tokens
    ModelType.GPT_35_TURBO: (0.5, 1.5),  # $0.50/$1.50 per 1M tokens
    ModelType.GPT_4: (30.0, 60.0),  # $30/$60 per 1M tokens
    ModelType.GPT_4_TURBO: (10.0, 30.0),  # $10/$30 per 1M tokens
    ModelType.GPT_4O: (2.5, 10.0),  # $2.50/$10.00 per 1M tokens (May 2024 pricing)
}


@dataclass
class LLMResponse:
    """Response from LLM with metadata"""
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    cached: bool = False


class LLMClient:
    """
    Unified LLM client supporting multiple providers

    Features:
    - Automatic provider selection based on model
    - Retry logic with exponential backoff
    - Cost tracking
    - Optional response caching
    - Rate limiting

    Usage:
        client = LLMClient(
            anthropic_api_key="...",
            openai_api_key="..."
        )

        response = await client.complete(
            prompt="Explain protein",
            model="claude-haiku-3.5",
            max_tokens=500
        )
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        enable_cache: bool = True,
        cache_ttl_seconds: int = 300
    ):
        """
        Initialize LLM client

        Args:
            anthropic_api_key: Anthropic API key
            openai_api_key: OpenAI API key
            enable_cache: Enable response caching
            cache_ttl_seconds: Cache TTL in seconds
        """
        self.anthropic_api_key = anthropic_api_key
        self.openai_api_key = openai_api_key
        self.enable_cache = enable_cache
        self.cache_ttl_seconds = cache_ttl_seconds

        # Simple in-memory cache (use Redis in production)
        self._cache: Dict[str, tuple[LLMResponse, float]] = {}

        # Initialize API clients lazily
        self._anthropic_client = None
        self._openai_client = None

        logger.info(f"LLM Client initialized (cache: {enable_cache})")

    def _get_anthropic_client(self):
        """Lazy load Anthropic client"""
        if self._anthropic_client is None:
            try:
                import anthropic
                self._anthropic_client = anthropic.AsyncAnthropic(
                    api_key=self.anthropic_api_key
                )
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.error("anthropic package not installed. Install: pip install anthropic")
                raise
            except Exception as e:
                logger.error(f"Error initializing Anthropic client: {str(e)}")
                raise

        return self._anthropic_client

    def _get_openai_client(self):
        """Lazy load OpenAI client"""
        if self._openai_client is None:
            try:
                import openai
                self._openai_client = openai.AsyncOpenAI(
                    api_key=self.openai_api_key
                )
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.error("openai package not installed. Install: pip install openai")
                raise
            except Exception as e:
                logger.error(f"Error initializing OpenAI client: {str(e)}")
                raise

        return self._openai_client

    def _get_cache_key(self, prompt: str, model: str, **kwargs) -> str:
        """Generate cache key from request parameters"""
        cache_data = {
            "prompt": prompt,
            "model": model,
            **kwargs
        }
        return hashlib.md5(json.dumps(cache_data, sort_keys=True).encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[LLMResponse]:
        """Get cached response if available and not expired"""
        if not self.enable_cache:
            return None

        if cache_key in self._cache:
            response, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self.cache_ttl_seconds:
                logger.info(f"Cache hit for {cache_key[:8]}")
                response.cached = True
                return response
            else:
                # Expired, remove
                del self._cache[cache_key]

        return None

    def _cache_response(self, cache_key: str, response: LLMResponse):
        """Cache response"""
        if self.enable_cache:
            self._cache[cache_key] = (response, time.time())

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD"""
        try:
            model_type = ModelType(model)
            input_price, output_price = MODEL_PRICING[model_type]

            input_cost = (input_tokens / 1_000_000) * input_price
            output_cost = (output_tokens / 1_000_000) * output_price

            return input_cost + output_cost
        except (ValueError, KeyError):
            logger.warning(f"Unknown model pricing: {model}")
            return 0.0

    async def complete(
        self,
        prompt: str,
        model: str = "claude-haiku-3.5",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system: Optional[str] = None,
        retry_count: int = 3
    ) -> str:
        """
        Complete a prompt using specified LLM

        Args:
            prompt: User prompt
            model: Model name (claude-haiku-3.5, gpt-4, etc)
            max_tokens: Maximum tokens to generate
            temperature: Temperature (0-1)
            system: System prompt
            retry_count: Number of retries on failure

        Returns:
            Generated text (string)

        Raises:
            Exception if all retries fail
        """
        # Check cache
        cache_key = self._get_cache_key(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system
        )

        cached = self._get_cached_response(cache_key)
        if cached:
            return cached.text

        # Determine provider
        provider = self._get_provider(model)

        # Retry loop
        for attempt in range(retry_count):
            try:
                start_time = time.time()

                if provider == LLMProvider.ANTHROPIC:
                    response = await self._call_anthropic(
                        prompt=prompt,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system=system
                    )
                elif provider == LLMProvider.OPENAI:
                    response = await self._call_openai(
                        prompt=prompt,
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system=system
                    )
                else:
                    raise ValueError(f"Unknown provider: {provider}")

                # Add latency
                latency_ms = int((time.time() - start_time) * 1000)
                response.latency_ms = latency_ms

                # Cache response
                self._cache_response(cache_key, response)

                logger.info(
                    f"LLM call successful: {model} ({latency_ms}ms, "
                    f"{response.input_tokens}/{response.output_tokens} tokens, "
                    f"${response.cost_usd:.4f})"
                )

                return response.text

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{retry_count}): {str(e)}")
                if attempt == retry_count - 1:
                    raise
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)

    def _get_provider(self, model: str) -> LLMProvider:
        """Determine provider from model name"""
        if "claude" in model.lower():
            return LLMProvider.ANTHROPIC
        elif "gpt" in model.lower():
            return LLMProvider.OPENAI
        else:
            raise ValueError(f"Cannot determine provider for model: {model}")

    async def _call_anthropic(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system: Optional[str]
    ) -> LLMResponse:
        """Call Anthropic API"""
        client = self._get_anthropic_client()

        messages = [{"role": "user", "content": prompt}]

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages
        }

        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)

        # Extract text
        text = response.content[0].text

        # Calculate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self._calculate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            text=text,
            model=model,
            provider=LLMProvider.ANTHROPIC.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=0  # Will be set by caller
        )

    async def _call_openai(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system: Optional[str]
    ) -> LLMResponse:
        """Call OpenAI API"""
        client = self._get_openai_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Use JSON mode for structured output if system prompt mentions JSON
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        # Enable JSON mode if system prompt requests JSON
        if system and "json" in system.lower():
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)

        # Extract text
        text = response.choices[0].message.content

        # Calculate cost
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost = self._calculate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            text=text,
            model=model,
            provider=LLMProvider.OPENAI.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=0  # Will be set by caller
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return {
            "cache_size": len(self._cache),
            "cache_enabled": self.enable_cache,
            "anthropic_available": self.anthropic_api_key is not None,
            "openai_available": self.openai_api_key is not None
        }
