"""
Token Governor - Manages LLM token budgets with pessimistic reservation.

Implements ITokenGovernor using Redis for atomic operations.

Flow:
1. RESERVE: Atomically check AND increment by estimated amount (before LLM call)
2. LLM call happens (handled by adapter)
3. REFUND: Decrement by unused amount (reserved - actual)

This prevents race conditions where concurrent requests could exceed budget.
"""
import logging
from app.infrastructure.normalization.interfaces import ITokenGovernor
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)


# Lua script for atomic reservation
# Returns 1 if reservation successful, 0 if would exceed limit
RESERVE_SCRIPT = """
local key = KEYS[1]
local amount = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

local current = tonumber(redis.call('GET', key) or '0')

if current + amount > limit then
    return 0
end

redis.call('INCRBY', key, amount)

-- Set TTL if not already set (first reservation of the day)
if redis.call('TTL', key) == -1 then
    redis.call('EXPIRE', key, ttl)
end

return 1
"""


class RedisTokenGovernor(ITokenGovernor):
    """
    Redis-based implementation of token budget management.

    Uses Lua scripts for atomic reserve operations to prevent race conditions.
    Refund uses simple DECRBY (no atomicity needed - worst case is slight undercount).
    """

    def __init__(self, ttl: int = 86400):
        """
        Args:
            ttl: Time-to-live for budget keys in seconds (default: 24 hours)
        """
        self.ttl = ttl
        self._reserve_script_sha: str | None = None

    def _get_key(self, user_id: int) -> str:
        """Generate Redis key for user's daily token budget."""
        return f"token_budget:{user_id}:daily"

    async def reserve(self, user_id: int, amount: int, limit: int) -> bool:
        """
        Atomically reserve tokens for a user.

        Uses Lua script to ensure check-and-increment is atomic.
        If reservation would exceed limit, returns False without modifying anything.

        Args:
            user_id: User ID
            amount: Number of tokens to reserve (input + max_output estimate)
            limit: User's daily token limit

        Returns:
            True if reservation successful, False if would exceed budget
        """
        redis_client = get_redis_client()
        key = self._get_key(user_id)

        # Register script if not already done
        if self._reserve_script_sha is None:
            self._reserve_script_sha = await redis_client.script_load(RESERVE_SCRIPT)

        result = await redis_client.evalsha(
            self._reserve_script_sha,
            1,  # number of keys
            key,
            amount,
            limit,
            self.ttl
        )

        reserved = bool(result)

        if reserved:
            logger.debug(f"Reserved {amount} tokens for user {user_id}")
        else:
            logger.warning(f"Reservation denied for user {user_id}: would exceed limit {limit}")

        return reserved

    async def refund(self, user_id: int, amount: int) -> None:
        """
        Refund unused tokens after LLM call completes.

        Called with: reserved_amount - actual_tokens_used
        If amount is 0 or negative, does nothing.

        Args:
            user_id: User ID
            amount: Number of tokens to refund
        """
        if amount <= 0:
            return

        redis_client = get_redis_client()
        key = self._get_key(user_id)

        await redis_client.decrby(key, amount)
        logger.debug(f"Refunded {amount} tokens for user {user_id}")
