"""Tests for dynamic timezone list feature.

When a user sets their timezone, it should be added to the chat's active_timezones.
Time conversion should use merged list: config timezones + chat's detected timezones.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.chat_timezones import add_timezone_to_chat, merge_timezones
from src.core.models import Platform
from src.storage.mongo import MongoStorage


class TestChatActiveTimezones:
    """Tests for tracking active timezones in a chat."""

    @pytest.fixture
    def mock_storage(self) -> MongoStorage:
        """Create a mock storage instance."""
        storage = MagicMock(spec=MongoStorage)
        storage.db = MagicMock()
        return storage

    async def test_add_timezone_to_chat_delegates_to_storage(
        self, mock_storage: MongoStorage
    ) -> None:
        """Should delegate to storage's atomic add_timezone_to_chat method."""
        mock_storage.add_timezone_to_chat = AsyncMock()

        await add_timezone_to_chat(mock_storage, Platform.TELEGRAM, "chat_123", "Europe/Moscow")

        mock_storage.add_timezone_to_chat.assert_called_once_with(
            Platform.TELEGRAM, "chat_123", "Europe/Moscow"
        )


class TestMergeTimezones:
    """Tests for merging config and chat timezones."""

    def test_merge_returns_config_when_no_chat_timezones(self) -> None:
        """Should return config timezones when chat has none."""
        config_tzs = ["Europe/London", "America/New_York"]

        result = merge_timezones(config_tzs, [])

        assert result == config_tzs

    def test_merge_adds_chat_timezones(self) -> None:
        """Should add chat timezones to config list."""
        config_tzs = ["Europe/London"]
        chat_tzs = ["Europe/Moscow", "Asia/Tokyo"]

        result = merge_timezones(config_tzs, chat_tzs)

        assert "Europe/London" in result
        assert "Europe/Moscow" in result
        assert "Asia/Tokyo" in result

    def test_merge_removes_duplicates(self) -> None:
        """Should not have duplicate timezones."""
        config_tzs = ["Europe/London", "Europe/Moscow"]
        chat_tzs = ["Europe/Moscow", "Asia/Tokyo"]

        result = merge_timezones(config_tzs, chat_tzs)

        assert result.count("Europe/Moscow") == 1

    def test_merge_preserves_order_config_first(self) -> None:
        """Config timezones should come first."""
        config_tzs = ["Europe/London"]
        chat_tzs = ["Asia/Tokyo"]

        result = merge_timezones(config_tzs, chat_tzs)

        assert result[0] == "Europe/London"


class TestPipelineContextResolution:
    """Integration tests for Pipeline._resolve_context with chat timezones."""

    @pytest.fixture
    def mock_storage(self) -> MongoStorage:
        """Create a mock storage instance."""
        storage = MagicMock(spec=MongoStorage)
        storage.db = MagicMock()
        return storage

    async def test_resolve_context_merges_config_and_chat_timezones(
        self, mock_storage: MongoStorage
    ) -> None:
        """Pipeline should merge config timezones with chat's active_timezones."""
        from src.core.models import ChatState, NormalizedEvent
        from src.core.pipeline import Pipeline

        # Setup: chat has active timezones
        chat_state = ChatState(
            platform=Platform.TELEGRAM,
            chat_id="chat_123",
            active_timezones=["Europe/Moscow", "Asia/Tokyo"],
        )
        mock_storage.get_chat_state = AsyncMock(return_value=chat_state)

        # Create pipeline with storage
        pipeline = Pipeline(storage=mock_storage)

        # Create event
        event = NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="evt_001",
            chat_id="chat_123",
            user_id="user_456",
            text="3 pm",
            message_id="msg_789",
        )

        # Resolve context
        context = await pipeline._resolve_context(event, [])

        # Assert: config timezones (from settings) + chat timezones are merged
        assert "Europe/Moscow" in context.target_timezones
        assert "Asia/Tokyo" in context.target_timezones

    async def test_resolve_context_works_without_storage(self) -> None:
        """Pipeline should work with just config timezones when no storage."""
        from src.core.models import NormalizedEvent
        from src.core.pipeline import Pipeline

        # Create pipeline without storage
        pipeline = Pipeline(storage=None)

        event = NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="evt_001",
            chat_id="chat_123",
            user_id="user_456",
            text="3 pm",
            message_id="msg_789",
        )

        # Should not raise, returns config timezones only
        context = await pipeline._resolve_context(event, [])

        # Context should have at least config timezones
        assert context.target_timezones is not None
