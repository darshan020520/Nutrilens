"""
Redis Client - Centralized Redis connection management

Provides singleton Redis client for entire application.
All modules (normalizer, notifications, caching, etc.) use this.
"""
import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Global Redis client instance (singleton)
_redis_client = None


def get_redis_client() -> redis.Redis:
    """
    Get Redis client instance (singleton pattern)

    Creates ONE async connection pool for entire application lifecycle.
    All modules share this connection pool.

    Returns:
        redis.asyncio.Redis: Configured async Redis client with decode_responses=True
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
            socket_keepalive=True,
            health_check_interval=30
        )
        logger.info(
            f"Async Redis client initialized: {settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
        )

    return _redis_client


def close_redis_client():
    """Close Redis connection on application shutdown"""
    global _redis_client

    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")


def ping_redis() -> bool:
    """Check if Redis is accessible"""
    try:
        client = get_redis_client()
        return client.ping()
    except Exception as e:
        logger.error(f"Redis ping failed: {e}")
        return False


# Lua script for atomic token budget check and increment
# Returns: [allowed (0/1), current_usage, limit]
TOKEN_BUDGET_LUA_SCRIPT = """
local key = KEYS[1]
local tokens_to_add = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local current = tonumber(redis.call('GET', key) or '0')

if current + tokens_to_add > limit then
    return {0, current, limit}
end

local new_total = redis.call('INCRBY', key, tokens_to_add)

-- Set expiry if not already set
local current_ttl = redis.call('TTL', key)
if current_ttl == -1 then
    redis.call('EXPIRE', key, ttl)
end

return {1, new_total, limit}
"""

# Cached script SHA
_token_budget_script_sha = None


async def check_and_increment_token_budget(
    user_id: int,
    tokens: int,
    limit: int,
    ttl: int = 86400
) -> tuple[bool, int, int]:
    """
    Atomically check token budget and increment if allowed.

    Uses Lua script to ensure atomic check-and-increment operation,
    preventing race conditions in concurrent requests.

    Args:
        user_id: User ID
        tokens: Number of tokens to add
        limit: Maximum allowed tokens
        ttl: Time-to-live in seconds (default 24 hours)

    Returns:
        Tuple of (allowed: bool, current_usage: int, limit: int)
    """
    global _token_budget_script_sha

    redis_client = get_redis_client()
    key = f"token_budget:{user_id}:daily"

    # Register script if not already done
    if _token_budget_script_sha is None:
        _token_budget_script_sha = await redis_client.script_load(TOKEN_BUDGET_LUA_SCRIPT)

    result = await redis_client.evalsha(
        _token_budget_script_sha,
        1,  # number of keys
        key,
        tokens,
        limit,
        ttl
    )

    allowed = bool(result[0])
    current_usage = int(result[1])
    budget_limit = int(result[2])

    return allowed, current_usage, budget_limit


async def get_current_token_usage(user_id: int) -> int:
    """
    Get current token usage for a user without incrementing.

    Used for pre-flight budget check before making LLM calls.

    Args:
        user_id: User ID

    Returns:
        Current token usage count (0 if no usage recorded)
    """
    redis_client = get_redis_client()
    key = f"token_budget:{user_id}:daily"

    usage = await redis_client.get(key)
    return int(usage) if usage else 0
