"""Tests for dynamic timezone list feature.

When a user sets their timezone, it should be added to the chat's active_timezones.
Time conversion should use merged list: config timezones + chat's detected timezones.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.chat_timezones import add_timezone_to_chat, merge_timezones
from src.core.models import ChatState, Platform
from src.storage.mongo import MongoStorage


class TestChatActiveTimezones:
    """Tests for tracking active timezones in a chat."""

    @pytest.fixture
    def mock_storage(self) -> MongoStorage:
        """Create a mock storage instance."""
        storage = MagicMock(spec=MongoStorage)
        storage.db = MagicMock()
        return storage

    async def test_add_timezone_to_chat_creates_new_chat_state(
        self, mock_storage: MongoStorage
    ) -> None:
        """Should create ChatState if chat doesn't exist."""
        mock_storage.get_chat_state = AsyncMock(return_value=None)
        mock_storage.upsert_chat_state = AsyncMock()

        await add_timezone_to_chat(mock_storage, Platform.TELEGRAM, "chat_123", "Europe/Moscow")

        mock_storage.upsert_chat_state.assert_called_once()
        call_args = mock_storage.upsert_chat_state.call_args[0][0]
        assert isinstance(call_args, ChatState)
        assert "Europe/Moscow" in call_args.active_timezones

    async def test_add_timezone_to_chat_appends_to_existing(
        self, mock_storage: MongoStorage
    ) -> None:
        """Should append to existing active_timezones."""
        existing = ChatState(
            platform=Platform.TELEGRAM,
            chat_id="chat_123",
            active_timezones=["America/New_York"],
        )
        mock_storage.get_chat_state = AsyncMock(return_value=existing)
        mock_storage.upsert_chat_state = AsyncMock()

        await add_timezone_to_chat(mock_storage, Platform.TELEGRAM, "chat_123", "Europe/Moscow")

        call_args = mock_storage.upsert_chat_state.call_args[0][0]
        assert "America/New_York" in call_args.active_timezones
        assert "Europe/Moscow" in call_args.active_timezones

    async def test_add_timezone_to_chat_no_duplicates(self, mock_storage: MongoStorage) -> None:
        """Should not add duplicate timezones."""
        existing = ChatState(
            platform=Platform.TELEGRAM,
            chat_id="chat_123",
            active_timezones=["Europe/Moscow"],
        )
        mock_storage.get_chat_state = AsyncMock(return_value=existing)
        mock_storage.upsert_chat_state = AsyncMock()

        await add_timezone_to_chat(mock_storage, Platform.TELEGRAM, "chat_123", "Europe/Moscow")

        call_args = mock_storage.upsert_chat_state.call_args[0][0]
        assert call_args.active_timezones.count("Europe/Moscow") == 1


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
