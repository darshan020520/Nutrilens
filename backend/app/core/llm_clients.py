"""
LLM Client Singletons - Centralized management of LLM TCP clients

This module manages singleton instances of LLM clients for the entire application.
Each provider (OpenAI, Anthropic, etc.) has ONE client instance that is:
- Created once at application startup
- Shared across all requests
- Properly closed at application shutdown

Benefits:
- Connection pooling: httpx pools are reused across requests
- Resource efficiency: No duplicate TCP connections
- Clean lifecycle: Explicit startup/shutdown management
"""
import logging
from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# SINGLETON INSTANCES (Module-level globals)
# ============================================================================

_openai_client: Optional[AsyncOpenAI] = None


# ============================================================================
# OPENAI CLIENT
# ============================================================================

async def get_openai_client() -> AsyncOpenAI:
    """
    Get or create singleton AsyncOpenAI client.

    This client is shared across ALL OpenAI API calls regardless of model.
    The model parameter is specified in each API call, not at client level.

    Supports all models:
    - gpt-4o-mini
    - gpt-4o
    - gpt-4o-2024-08-06
    - etc.

    Returns:
        AsyncOpenAI: Singleton client instance with connection pooling
    """
    global _openai_client

    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            max_retries=0,
            timeout=60.0
        )
        logger.info("✅ OpenAI AsyncClient initialized (singleton)")

    return _openai_client


# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================

async def close_llm_clients():
    """
    Close all LLM clients on application shutdown.

    This should be called in the FastAPI lifespan shutdown phase
    to ensure clean closure of HTTP connection pools.
    """
    global _openai_client

    if _openai_client is not None:
        await _openai_client.close()
        _openai_client = None
        logger.info("✅ OpenAI client closed")


# ============================================================================
# FUTURE: ANTHROPIC CLIENT
# ============================================================================

# _anthropic_client: Optional[AsyncAnthropic] = None
#
# async def get_anthropic_client() -> AsyncAnthropic:
#     """Get or create singleton Anthropic client"""
#     global _anthropic_client
#
#     if _anthropic_client is None:
#         _anthropic_client = AsyncAnthropic(
#             api_key=settings.anthropic_api_key,
#             max_retries=3,
#             timeout=60.0
#         )
#         logger.info("✅ Anthropic AsyncClient initialized (singleton)")
#
#     return _anthropic_client


# ============================================================================
# FUTURE: GROK CLIENT
# ============================================================================

# _grok_client = None
#
# async def get_grok_client():
#     """Get or create singleton Grok client"""
#     global _grok_client
#
#     if _grok_client is None:
#         _grok_client = GrokClient(api_key=settings.grok_api_key)
#         logger.info("✅ Grok client initialized (singleton)")
#
#     return _grok_client