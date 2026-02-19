import logging
from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

_openai_client: Optional[AsyncOpenAI] = None

async def get_openai_client() -> AsyncOpenAI:
    global _openai_client

    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            max_retries=0,
            timeout=60.0
        )
        logger.info("✅ OpenAI AsyncClient initialized (singleton)")

    return _openai_client

async def close_llm_clients():
    global _openai_client

    if _openai_client is not None:
        await _openai_client.close()
        _openai_client = None
        logger.info("✅ OpenAI client closed")