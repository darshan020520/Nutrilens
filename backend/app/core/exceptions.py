"""
Custom exceptions for application-wide error handling.

These exceptions bubble up from any layer and are caught by
global exception handlers in main.py to return proper HTTP responses.
"""


class TokenBudgetExceeded(Exception):
    """Raised when user has exceeded their token budget for LLM calls"""

    def __init__(
        self, message: str = "Token budget exceeded", used: int = 0, limit: int = 0
    ):
        self.message = message
        self.used = used
        self.limit = limit
        super().__init__(self.message)


class RateLimitExceeded(Exception):
    """Raised when request rate limit is exceeded"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)


class LLMServiceError(Exception):
    """Raised when LLM service fails (API error, timeout, etc.)"""

    def __init__(
        self, message: str = "LLM service error", original_error: Exception = None
    ):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)
