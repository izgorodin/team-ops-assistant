"""Tests for rate limiter.

Tests rate limiting functionality for per-user and per-chat limits.
"""

from __future__ import annotations

from time import sleep
from unittest.mock import patch

from src.core.rate_limiter import RateLimiter, RateLimitManager
from src.settings import RateLimitConfig


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_allows_requests_under_limit(self) -> None:
        """Requests under the limit should be allowed."""
        config = RateLimitConfig(requests=3, window_seconds=60)
        limiter = RateLimiter(config)

        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True

    def test_blocks_requests_at_limit(self) -> None:
        """Requests at the limit should be blocked."""
        config = RateLimitConfig(requests=3, window_seconds=60)
        limiter = RateLimiter(config)

        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False  # 4th request blocked

    def test_different_keys_have_separate_limits(self) -> None:
        """Different keys should have independent rate limits."""
        config = RateLimitConfig(requests=2, window_seconds=60)
        limiter = RateLimiter(config)

        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False

        # user2 should still be allowed
        assert limiter.is_allowed("user2") is True
        assert limiter.is_allowed("user2") is True

    def test_requests_allowed_after_window_expires(self) -> None:
        """Requests should be allowed after window expires."""
        config = RateLimitConfig(requests=2, window_seconds=1)
        limiter = RateLimiter(config)

        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False

        # Wait for window to expire
        sleep(1.1)

        assert limiter.is_allowed("user1") is True

    def test_get_retry_after_returns_zero_when_allowed(self) -> None:
        """get_retry_after should return 0 when not rate limited."""
        config = RateLimitConfig(requests=3, window_seconds=60)
        limiter = RateLimiter(config)

        limiter.is_allowed("user1")
        assert limiter.get_retry_after("user1") == 0

    def test_get_retry_after_returns_time_when_limited(self) -> None:
        """get_retry_after should return remaining time when rate limited."""
        config = RateLimitConfig(requests=2, window_seconds=10)
        limiter = RateLimiter(config)

        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")  # This should fail

        retry_after = limiter.get_retry_after("user1")
        assert 8 <= retry_after <= 10  # Should be close to window_seconds

    def test_reset_clears_limit_for_key(self) -> None:
        """reset should clear rate limit for a specific key."""
        config = RateLimitConfig(requests=2, window_seconds=60)
        limiter = RateLimiter(config)

        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        assert limiter.is_allowed("user1") is False

        limiter.reset("user1")
        assert limiter.is_allowed("user1") is True

    def test_clear_clears_all_limits(self) -> None:
        """clear should clear all rate limit data."""
        config = RateLimitConfig(requests=2, window_seconds=60)
        limiter = RateLimiter(config)

        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        limiter.is_allowed("user2")
        limiter.is_allowed("user2")

        assert limiter.is_allowed("user1") is False
        assert limiter.is_allowed("user2") is False

        limiter.clear()

        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user2") is True


class TestRateLimitManager:
    """Tests for RateLimitManager class."""

    def test_allows_when_under_both_limits(self) -> None:
        """Requests should be allowed when under both limits."""
        manager = RateLimitManager(
            user_config=RateLimitConfig(requests=5, window_seconds=60),
            chat_config=RateLimitConfig(requests=10, window_seconds=60),
            enabled=True,
        )

        is_allowed, limit_type = manager.check_rate_limit("telegram", "user1", "chat1")
        assert is_allowed is True
        assert limit_type is None

    def test_blocks_when_user_limit_exceeded(self) -> None:
        """Requests should be blocked when user limit is exceeded."""
        manager = RateLimitManager(
            user_config=RateLimitConfig(requests=2, window_seconds=60),
            chat_config=RateLimitConfig(requests=10, window_seconds=60),
            enabled=True,
        )

        manager.check_rate_limit("telegram", "user1", "chat1")
        manager.check_rate_limit("telegram", "user1", "chat1")
        is_allowed, limit_type = manager.check_rate_limit("telegram", "user1", "chat1")

        assert is_allowed is False
        assert limit_type == "user"

    def test_blocks_when_chat_limit_exceeded(self) -> None:
        """Requests should be blocked when chat limit is exceeded."""
        manager = RateLimitManager(
            user_config=RateLimitConfig(requests=10, window_seconds=60),
            chat_config=RateLimitConfig(requests=2, window_seconds=60),
            enabled=True,
        )

        # Different users in same chat
        manager.check_rate_limit("telegram", "user1", "chat1")
        manager.check_rate_limit("telegram", "user2", "chat1")
        is_allowed, limit_type = manager.check_rate_limit("telegram", "user3", "chat1")

        assert is_allowed is False
        assert limit_type == "chat"

    def test_disabled_allows_all_requests(self) -> None:
        """Disabled rate limiter should allow all requests."""
        manager = RateLimitManager(
            user_config=RateLimitConfig(requests=1, window_seconds=60),
            chat_config=RateLimitConfig(requests=1, window_seconds=60),
            enabled=False,
        )

        for _ in range(10):
            is_allowed, limit_type = manager.check_rate_limit("telegram", "user1", "chat1")
            assert is_allowed is True
            assert limit_type is None

    def test_user_limit_checked_before_chat_limit(self) -> None:
        """User limit should be checked before chat limit."""
        manager = RateLimitManager(
            user_config=RateLimitConfig(requests=1, window_seconds=60),
            chat_config=RateLimitConfig(requests=1, window_seconds=60),
            enabled=True,
        )

        manager.check_rate_limit("telegram", "user1", "chat1")
        is_allowed, limit_type = manager.check_rate_limit("telegram", "user1", "chat1")

        # Should hit user limit first since both are at 1
        assert is_allowed is False
        assert limit_type == "user"

    def test_get_user_retry_after(self) -> None:
        """get_user_retry_after should return correct value."""
        manager = RateLimitManager(
            user_config=RateLimitConfig(requests=1, window_seconds=10),
            chat_config=RateLimitConfig(requests=10, window_seconds=60),
            enabled=True,
        )

        manager.check_rate_limit("telegram", "user1", "chat1")
        manager.check_rate_limit("telegram", "user1", "chat1")  # Should fail

        retry_after = manager.get_user_retry_after("telegram", "user1")
        assert 8 <= retry_after <= 10

    def test_get_chat_retry_after(self) -> None:
        """get_chat_retry_after should return correct value."""
        manager = RateLimitManager(
            user_config=RateLimitConfig(requests=10, window_seconds=60),
            chat_config=RateLimitConfig(requests=1, window_seconds=10),
            enabled=True,
        )

        manager.check_rate_limit("telegram", "user1", "chat1")
        manager.check_rate_limit("telegram", "user2", "chat1")  # Should fail on chat limit

        retry_after = manager.get_chat_retry_after("telegram", "chat1")
        assert 8 <= retry_after <= 10


class TestGetRateLimitManager:
    """Tests for get_rate_limit_manager function."""

    def test_returns_singleton(self) -> None:
        """get_rate_limit_manager should return the same instance."""
        from src.core.rate_limiter import get_rate_limit_manager, reset_rate_limit_manager

        reset_rate_limit_manager()

        manager1 = get_rate_limit_manager()
        manager2 = get_rate_limit_manager()

        assert manager1 is manager2

        reset_rate_limit_manager()

    def test_uses_config_values(self) -> None:
        """Manager should use values from configuration."""
        from src.core.rate_limiter import get_rate_limit_manager, reset_rate_limit_manager

        reset_rate_limit_manager()

        with patch("src.settings.get_settings") as mock_settings:
            mock_config = type(
                "Config",
                (),
                {
                    "rate_limits": type(
                        "RateLimits",
                        (),
                        {
                            "enabled": True,
                            "per_user": RateLimitConfig(requests=5, window_seconds=30),
                            "per_chat": RateLimitConfig(requests=10, window_seconds=60),
                        },
                    )()
                },
            )()
            mock_settings.return_value = type("Settings", (), {"config": mock_config})()

            manager = get_rate_limit_manager()
            assert manager.enabled is True
            assert manager._user_limiter.config.requests == 5
            assert manager._chat_limiter.config.window_seconds == 60

        reset_rate_limit_manager()
