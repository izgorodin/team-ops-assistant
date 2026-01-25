"""Rate limiter for request throttling.

Implements sliding window rate limiting for per-user and per-chat limits.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from time import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.settings import RateLimitConfig

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding window rate limiter.

    Tracks request timestamps in memory and enforces rate limits
    based on a configurable window size.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize rate limiter with configuration.

        Args:
            config: Rate limit configuration with requests and window_seconds.
        """
        self.config = config
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed under the rate limit.

        Args:
            key: Unique identifier for the rate limit bucket (e.g., user_id, chat_id).

        Returns:
            True if request is allowed, False if rate limited.
        """
        now = time()
        cutoff = now - self.config.window_seconds

        # Remove expired entries
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

        if len(self._requests[key]) >= self.config.requests:
            return False

        self._requests[key].append(now)
        return True

    def get_retry_after(self, key: str) -> int:
        """Get seconds until a request would be allowed.

        Args:
            key: Unique identifier for the rate limit bucket.

        Returns:
            Seconds until rate limit resets (0 if not rate limited).
        """
        if not self._requests[key]:
            return 0

        now = time()
        cutoff = now - self.config.window_seconds
        valid_requests = [t for t in self._requests[key] if t > cutoff]

        if len(valid_requests) < self.config.requests:
            return 0

        oldest = min(valid_requests)
        return max(0, int(self.config.window_seconds - (now - oldest)))

    def reset(self, key: str) -> None:
        """Reset rate limit for a key.

        Args:
            key: Unique identifier for the rate limit bucket.
        """
        self._requests.pop(key, None)

    def clear(self) -> None:
        """Clear all rate limit data."""
        self._requests.clear()


class RateLimitManager:
    """Manages multiple rate limiters for different limit types.

    Provides per-user and per-chat rate limiting with a unified interface.
    """

    def __init__(
        self,
        user_config: RateLimitConfig,
        chat_config: RateLimitConfig,
        enabled: bool = True,
    ) -> None:
        """Initialize rate limit manager.

        Args:
            user_config: Configuration for per-user rate limiting.
            chat_config: Configuration for per-chat rate limiting.
            enabled: Whether rate limiting is enabled.
        """
        self.enabled = enabled
        self._user_limiter = RateLimiter(user_config)
        self._chat_limiter = RateLimiter(chat_config)

    def check_rate_limit(
        self, platform: str, user_id: str, chat_id: str
    ) -> tuple[bool, str | None]:
        """Check if request passes all rate limits.

        Args:
            platform: Platform identifier (e.g., "telegram", "discord").
            user_id: User identifier.
            chat_id: Chat identifier.

        Returns:
            Tuple of (is_allowed, limit_type) where limit_type is None if allowed,
            or "user" / "chat" indicating which limit was exceeded.
        """
        if not self.enabled:
            return True, None

        user_key = f"{platform}:{user_id}"
        chat_key = f"{platform}:{chat_id}"

        # Check per-user limit first
        if not self._user_limiter.is_allowed(user_key):
            retry_after = self._user_limiter.get_retry_after(user_key)
            logger.info(f"Rate limited: user {user_key}, retry after {retry_after}s")
            return False, "user"

        # Check per-chat limit
        if not self._chat_limiter.is_allowed(chat_key):
            retry_after = self._chat_limiter.get_retry_after(chat_key)
            logger.info(f"Rate limited: chat {chat_key}, retry after {retry_after}s")
            return False, "chat"

        return True, None

    def get_user_retry_after(self, platform: str, user_id: str) -> int:
        """Get retry-after for user rate limit.

        Args:
            platform: Platform identifier.
            user_id: User identifier.

        Returns:
            Seconds until rate limit resets.
        """
        return self._user_limiter.get_retry_after(f"{platform}:{user_id}")

    def get_chat_retry_after(self, platform: str, chat_id: str) -> int:
        """Get retry-after for chat rate limit.

        Args:
            platform: Platform identifier.
            chat_id: Chat identifier.

        Returns:
            Seconds until rate limit resets.
        """
        return self._chat_limiter.get_retry_after(f"{platform}:{chat_id}")

    def clear(self) -> None:
        """Clear all rate limit data."""
        self._user_limiter.clear()
        self._chat_limiter.clear()


# Global rate limit manager instance
_rate_limit_manager: RateLimitManager | None = None


def get_rate_limit_manager() -> RateLimitManager:
    """Get or create the global rate limit manager.

    Returns:
        Global RateLimitManager instance.
    """
    global _rate_limit_manager
    if _rate_limit_manager is None:
        from src.settings import get_settings

        settings = get_settings()
        config = settings.config.rate_limits
        _rate_limit_manager = RateLimitManager(
            user_config=config.per_user,
            chat_config=config.per_chat,
            enabled=config.enabled,
        )
    return _rate_limit_manager


def reset_rate_limit_manager() -> None:
    """Reset the global rate limit manager (for testing)."""
    global _rate_limit_manager
    _rate_limit_manager = None
