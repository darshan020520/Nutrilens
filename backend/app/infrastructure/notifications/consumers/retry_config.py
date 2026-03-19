"""
Retry configuration for notification delivery.

Uses exponential backoff strategy (industry standard).
"""

from datetime import datetime, timedelta
from typing import Optional


class RetryConfig:

    BASE_DELAY_SECONDS = 60
    MAX_DELAY_SECONDS = 900
    MAX_RETRIES = 5

    @staticmethod
    def calculate_delay(attempt: int) -> int:
        """
        Calculate retry delay using exponential backoff.

        Formula: delay = BASE_DELAY × 2^(attempt - 1)
        With cap at MAX_DELAY_SECONDS

        Args:
            attempt: Retry attempt number (1, 2, 3, 4, 5)

        Returns:
            Delay in seconds

        Examples:
            >>> RetryConfig.calculate_delay(1)
            60    # 1 minute

            >>> RetryConfig.calculate_delay(2)
            120   # 2 minutes

            >>> RetryConfig.calculate_delay(3)
            240   # 4 minutes

            >>> RetryConfig.calculate_delay(4)
            480   # 8 minutes

            >>> RetryConfig.calculate_delay(5)
            900   # 15 minutes (would be 16, but capped)

        Timeline:
            00:00 - Original send → Fail
            01:00 - Retry 1 (after 1 min) → Fail
            03:00 - Retry 2 (after 2 min) → Fail
            07:00 - Retry 3 (after 4 min) → Fail
            15:00 - Retry 4 (after 8 min) → Fail
            30:00 - Retry 5 (after 15 min) → Fail
            Move to Dead Letter Queue

            Total time: 30 minutes
            Total attempts: 6
        """
        if attempt < 1:
            return 0

        # Exponential backoff: 2^(attempt - 1)
        delay = RetryConfig.BASE_DELAY_SECONDS * (2 ** (attempt - 1))

        # Cap at maximum delay
        return min(delay, RetryConfig.MAX_DELAY_SECONDS)

    @staticmethod
    def calculate_next_retry_time(attempt: int, from_time: Optional[datetime] = None) -> datetime:
        """
        Calculate the next retry timestamp.

        Args:
            attempt: Retry attempt number
            from_time: Calculate from this time (default: now)

        Returns:
            Datetime when retry should be attempted

        Example:
            >>> next_retry = RetryConfig.calculate_next_retry_time(attempt=2)
            >>> # Returns: current_time + 2 minutes
        """
        if from_time is None:
            from_time = datetime.utcnow()

        delay_seconds = RetryConfig.calculate_delay(attempt)
        return from_time + timedelta(seconds=delay_seconds)

    @staticmethod
    def should_retry(retry_count: int) -> bool:
        """
        Check if notification should be retried.

        Args:
            retry_count: Current retry count

        Returns:
            True if should retry, False if max retries exceeded

        Example:
            >>> RetryConfig.should_retry(3)
            True

            >>> RetryConfig.should_retry(5)
            False  # Max retries (5) reached
        """
        return retry_count < RetryConfig.MAX_RETRIES

    @staticmethod
    def get_retry_summary() -> dict:
        """
        Get summary of retry configuration for logging/debugging.

        Returns:
            Dictionary with retry configuration details

        Example:
            >>> RetryConfig.get_retry_summary()
            {
                'base_delay_seconds': 60,
                'max_delay_seconds': 900,
                'max_retries': 5,
                'total_attempts': 6,
                'retry_schedule': [60, 120, 240, 480, 900],
                'total_time_seconds': 1800,
                'total_time_formatted': '30 minutes'
            }
        """
        retry_schedule = [RetryConfig.calculate_delay(i) for i in range(1, RetryConfig.MAX_RETRIES + 1)]
        total_time = sum(retry_schedule)

        return {
            "base_delay_seconds": RetryConfig.BASE_DELAY_SECONDS,
            "max_delay_seconds": RetryConfig.MAX_DELAY_SECONDS,
            "max_retries": RetryConfig.MAX_RETRIES,
            "total_attempts": RetryConfig.MAX_RETRIES + 1,  # Include original attempt
            "retry_schedule": retry_schedule,
            "total_time_seconds": total_time,
            "total_time_formatted": f"{total_time // 60} minutes"
        }


# Example usage and testing
if __name__ == "__main__":
    print("Retry Configuration Summary:")
    print("=" * 60)

    summary = RetryConfig.get_retry_summary()
    print(f"Base delay: {summary['base_delay_seconds']}s ({summary['base_delay_seconds'] // 60}min)")
    print(f"Max delay: {summary['max_delay_seconds']}s ({summary['max_delay_seconds'] // 60}min)")
    print(f"Max retries: {summary['max_retries']}")
    print(f"Total attempts: {summary['total_attempts']}")
    print(f"Total time: {summary['total_time_formatted']}")
    print("\nRetry Schedule:")
    print("-" * 60)

    cumulative_time = 0
    print(f"00:00 - Original send attempt")

    for attempt, delay in enumerate(summary['retry_schedule'], 1):
        cumulative_time += delay
        hours = cumulative_time // 3600
        minutes = (cumulative_time % 3600) // 60
        time_str = f"{hours:02d}:{minutes:02d}" if hours > 0 else f"{minutes:02d}:{cumulative_time % 60:02d}"

        print(f"{time_str} - Retry {attempt} (after {delay}s / {delay // 60}min delay)")

    print(f"\nAfter {summary['max_retries']} retries → Move to Dead Letter Queue")
