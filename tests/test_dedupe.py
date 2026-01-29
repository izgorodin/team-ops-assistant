"""Tests for DedupeManager deduplication and throttling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.dedupe import DedupeManager
from src.core.models import Platform


class TestDedupeManagerInit:
    """Tests for DedupeManager initialization."""

    def test_init_creates_empty_throttle_cache(self) -> None:
        """DedupeManager should start with empty throttle cache."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        assert manager._throttle_cache == {}
        assert manager.storage is mock_storage

    def test_init_loads_settings(self) -> None:
        """DedupeManager should load settings on init."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        assert manager.settings is not None


class TestIsDuplicate:
    """Tests for is_duplicate method."""

    @pytest.mark.asyncio
    async def test_returns_true_for_duplicate(self) -> None:
        """Should return True when storage reports duplicate."""
        mock_storage = MagicMock()
        mock_storage.check_dedupe_event = AsyncMock(return_value=True)
        manager = DedupeManager(mock_storage)

        result = await manager.is_duplicate(Platform.TELEGRAM, "event123")

        assert result is True
        mock_storage.check_dedupe_event.assert_called_once_with(Platform.TELEGRAM, "event123")

    @pytest.mark.asyncio
    async def test_returns_false_for_new_event(self) -> None:
        """Should return False when event is not in storage."""
        mock_storage = MagicMock()
        mock_storage.check_dedupe_event = AsyncMock(return_value=False)
        manager = DedupeManager(mock_storage)

        result = await manager.is_duplicate(Platform.DISCORD, "new_event")

        assert result is False


class TestMarkProcessed:
    """Tests for mark_processed method."""

    @pytest.mark.asyncio
    async def test_creates_dedupe_event(self) -> None:
        """Should create DedupeEvent and insert into storage."""
        mock_storage = MagicMock()
        mock_storage.insert_dedupe_event = AsyncMock()
        manager = DedupeManager(mock_storage)

        await manager.mark_processed(Platform.TELEGRAM, "event123", "chat456")

        mock_storage.insert_dedupe_event.assert_called_once()
        event = mock_storage.insert_dedupe_event.call_args[0][0]
        assert event.platform == Platform.TELEGRAM
        assert event.event_id == "event123"
        assert event.chat_id == "chat456"
        assert event.created_at is not None


class TestIsThrottled:
    """Tests for is_throttled method."""

    def test_not_throttled_for_new_chat(self) -> None:
        """New chat should not be throttled."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        result = manager.is_throttled(Platform.TELEGRAM, "new_chat")

        assert result is False

    def test_throttled_when_recent_response(self) -> None:
        """Should be throttled when response was sent recently."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        # Record a response
        manager.record_response(Platform.TELEGRAM, "chat123")

        # Should be throttled immediately after
        result = manager.is_throttled(Platform.TELEGRAM, "chat123")

        assert result is True

    def test_not_throttled_after_cooldown(self) -> None:
        """Should not be throttled after cooldown period."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)
        config = manager.settings.config.dedupe

        # Set a past response time beyond throttle window
        past_time = datetime.now(UTC) - timedelta(seconds=config.throttle_seconds + 1)
        manager._throttle_cache["telegram:chat123"] = past_time

        result = manager.is_throttled(Platform.TELEGRAM, "chat123")

        assert result is False

    def test_throttle_keys_include_platform(self) -> None:
        """Different platforms should have separate throttle keys."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        # Record response for Telegram
        manager.record_response(Platform.TELEGRAM, "chat123")

        # Discord same chat_id should NOT be throttled
        result = manager.is_throttled(Platform.DISCORD, "chat123")

        assert result is False


class TestRecordResponse:
    """Tests for record_response method."""

    def test_records_current_time(self) -> None:
        """Should record current time for the chat."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        before = datetime.now(UTC)
        manager.record_response(Platform.TELEGRAM, "chat123")
        after = datetime.now(UTC)

        recorded = manager._throttle_cache["telegram:chat123"]
        assert before <= recorded <= after

    def test_updates_existing_entry(self) -> None:
        """Should update time for existing chat entry."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        old_time = datetime.now(UTC) - timedelta(minutes=5)
        manager._throttle_cache["telegram:chat123"] = old_time

        manager.record_response(Platform.TELEGRAM, "chat123")

        new_time = manager._throttle_cache["telegram:chat123"]
        assert new_time > old_time


class TestCleanupThrottleCache:
    """Tests for cleanup_throttle_cache method."""

    def test_removes_expired_entries(self) -> None:
        """Should remove entries older than cleanup threshold."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)
        config = manager.settings.config.dedupe

        # Add an old entry (way past cleanup threshold)
        old_time = datetime.now(UTC) - timedelta(
            seconds=config.throttle_seconds * config.cache_cleanup_multiplier * 2
        )
        manager._throttle_cache["telegram:old_chat"] = old_time

        # Add a recent entry
        manager._throttle_cache["telegram:new_chat"] = datetime.now(UTC)

        manager.cleanup_throttle_cache()

        assert "telegram:old_chat" not in manager._throttle_cache
        assert "telegram:new_chat" in manager._throttle_cache

    def test_keeps_recent_entries(self) -> None:
        """Should keep entries within cleanup threshold."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        # Add a recent entry
        manager._throttle_cache["telegram:chat"] = datetime.now(UTC)

        manager.cleanup_throttle_cache()

        assert "telegram:chat" in manager._throttle_cache

    def test_handles_empty_cache(self) -> None:
        """Should handle empty cache gracefully."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)

        # Should not raise
        manager.cleanup_throttle_cache()

        assert manager._throttle_cache == {}


class TestPeriodicCleanup:
    """Tests for periodic cleanup trigger in record_response."""

    def test_triggers_cleanup_at_multiplier_interval(self) -> None:
        """Should trigger cleanup when cache size is multiple of cleanup_multiplier."""
        mock_storage = MagicMock()
        manager = DedupeManager(mock_storage)
        config = manager.settings.config.dedupe

        # Fill cache to just under multiplier
        for i in range(config.cache_cleanup_multiplier - 1):
            manager._throttle_cache[f"telegram:chat{i}"] = datetime.now(UTC)

        with patch.object(manager, "cleanup_throttle_cache") as mock_cleanup:
            # This should trigger cleanup (cache size becomes multiplier)
            manager.record_response(Platform.TELEGRAM, f"chat{config.cache_cleanup_multiplier}")

            mock_cleanup.assert_called_once()
