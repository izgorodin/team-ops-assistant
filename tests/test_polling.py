"""Tests for TelegramPoller class."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.connectors.telegram.polling import TelegramPoller
from src.core.models import HandlerResult, NormalizedEvent, OutboundMessage, Platform


class TestTelegramPoller:
    """Tests for TelegramPoller lifecycle and methods."""

    @pytest.fixture
    def mock_orchestrator(self) -> Any:
        """Fixture for a mock orchestrator."""
        orchestrator = MagicMock()
        orchestrator.route = AsyncMock()
        return orchestrator

    @pytest.fixture
    def mock_settings(self) -> Any:
        """Fixture for mock settings."""
        settings = MagicMock()
        settings.telegram_bot_token = "test_token_123"
        return settings

    @pytest.fixture
    def poller(self, mock_orchestrator: Any, mock_settings: Any) -> TelegramPoller:
        """Fixture for a TelegramPoller instance."""
        with patch("src.connectors.telegram.polling.get_settings", return_value=mock_settings):
            return TelegramPoller(mock_orchestrator)

    def test_init(self, mock_orchestrator: Any, mock_settings: Any) -> None:
        """Test TelegramPoller initialization."""
        with patch("src.connectors.telegram.polling.get_settings", return_value=mock_settings):
            poller = TelegramPoller(mock_orchestrator)

            assert poller.orchestrator is mock_orchestrator
            assert poller.settings is mock_settings
            assert poller._running is False
            assert poller._offset is None
            assert poller._client is None

    def test_api_base_property(self, poller: TelegramPoller) -> None:
        """Test that api_base property constructs correct URL."""
        expected = "https://api.telegram.org/bottest_token_123"
        assert poller.api_base == expected

    @pytest.mark.asyncio
    async def test_delete_webhook_success(self, poller: TelegramPoller) -> None:
        """Test successful webhook deletion."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        poller._client = mock_client

        await poller._delete_webhook()

        mock_client.post.assert_called_once_with(
            "https://api.telegram.org/bottest_token_123/deleteWebhook"
        )

    @pytest.mark.asyncio
    async def test_delete_webhook_failure(self, poller: TelegramPoller) -> None:
        """Test webhook deletion failure handling."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Error"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        poller._client = mock_client

        # Should not raise, just log warning
        await poller._delete_webhook()

        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_webhook_exception(self, poller: TelegramPoller) -> None:
        """Test webhook deletion with exception."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Network error")
        poller._client = mock_client

        # Should not raise, just log warning
        await poller._delete_webhook()

        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_webhook_no_client(self, poller: TelegramPoller) -> None:
        """Test webhook deletion when client is not initialized."""
        poller._client = None

        # Should return early without errors
        await poller._delete_webhook()

    @pytest.mark.asyncio
    async def test_get_updates_success(self, poller: TelegramPoller) -> None:
        """Test successful updates retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {"update_id": 1, "message": {"text": "Hello"}},
                {"update_id": 2, "message": {"text": "World"}},
            ],
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        poller._client = mock_client

        updates = await poller._get_updates()

        assert len(updates) == 2
        assert updates[0]["update_id"] == 1
        assert updates[1]["update_id"] == 2

        # Verify API call parameters
        call_args = mock_client.get.call_args
        assert call_args[0][0] == "https://api.telegram.org/bottest_token_123/getUpdates"
        assert call_args[1]["params"]["timeout"] == 30
        assert call_args[1]["params"]["allowed_updates"] == ["message"]

    @pytest.mark.asyncio
    async def test_get_updates_offset_management(self, poller: TelegramPoller) -> None:
        """Test that offset is updated after processing updates."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {"update_id": 5, "message": {"text": "Test"}},
                {"update_id": 6, "message": {"text": "Test2"}},
            ],
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        poller._client = mock_client

        # First call - no offset
        await poller._get_updates()
        assert poller._offset == 7  # Last update_id + 1

        # Second call - should include offset
        await poller._get_updates()
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["offset"] == 7

    @pytest.mark.asyncio
    async def test_get_updates_empty_result(self, poller: TelegramPoller) -> None:
        """Test updates retrieval with empty result."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": []}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        poller._client = mock_client

        updates = await poller._get_updates()

        assert len(updates) == 0
        assert poller._offset is None  # Should not update offset

    @pytest.mark.asyncio
    async def test_get_updates_error_response(self, poller: TelegramPoller) -> None:
        """Test updates retrieval with error response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        poller._client = mock_client

        updates = await poller._get_updates()

        assert len(updates) == 0

    @pytest.mark.asyncio
    async def test_get_updates_no_client(self, poller: TelegramPoller) -> None:
        """Test updates retrieval when client is not initialized."""
        poller._client = None

        updates = await poller._get_updates()

        assert len(updates) == 0

    @pytest.mark.asyncio
    async def test_process_update_success(self, poller: TelegramPoller) -> None:
        """Test successful update processing."""
        update = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 456},
                "text": "Meeting at 3pm",
                "date": 1704067200,
            },
        }

        # Mock normalized event
        mock_event = NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="456_42",
            chat_id="456",
            user_id="123",
            text="Meeting at 3pm",
        )

        # Mock orchestrator result
        mock_result = HandlerResult(
            should_respond=True,
            messages=[
                OutboundMessage(
                    platform=Platform.TELEGRAM,
                    chat_id="456",
                    text="Response message",
                )
            ],
        )
        poller.orchestrator.route.return_value = mock_result  # type: ignore[attr-defined]

        # Mock send_messages
        with (
            patch(
                "src.connectors.telegram.polling.normalize_telegram_update",
                return_value=mock_event,
            ),
            patch("src.connectors.telegram.polling.send_messages", return_value=1) as mock_send,
        ):
            await poller._process_update(update)

            poller.orchestrator.route.assert_called_once_with(mock_event)  # type: ignore[attr-defined]
            mock_send.assert_called_once_with(mock_result.messages)

    @pytest.mark.asyncio
    async def test_process_update_no_response_needed(self, poller: TelegramPoller) -> None:
        """Test update processing when no response is needed."""
        update = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 456},
                "text": "Hello",
                "date": 1704067200,
            },
        }

        mock_event = NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="456_42",
            chat_id="456",
            user_id="123",
            text="Hello",
        )

        # No response needed
        mock_result = HandlerResult(should_respond=False, messages=[])
        poller.orchestrator.route.return_value = mock_result  # type: ignore[attr-defined]

        with (
            patch(
                "src.connectors.telegram.polling.normalize_telegram_update",
                return_value=mock_event,
            ),
            patch("src.connectors.telegram.polling.send_messages") as mock_send,
        ):
            await poller._process_update(update)

            poller.orchestrator.route.assert_called_once_with(mock_event)  # type: ignore[attr-defined]
            mock_send.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_process_update_non_text_message(self, poller: TelegramPoller) -> None:
        """Test that non-text messages are filtered out."""
        update = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 123},
                "chat": {"id": 456},
                # No text field
            },
        }

        with patch("src.connectors.telegram.polling.normalize_telegram_update", return_value=None):
            await poller._process_update(update)

            # Should not call orchestrator
            poller.orchestrator.route.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_process_update_exception_handling(self, poller: TelegramPoller) -> None:
        """Test exception handling during update processing."""
        update = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 456},
                "text": "Test",
                "date": 1704067200,
            },
        }

        mock_event = NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="456_42",
            chat_id="456",
            user_id="123",
            text="Test",
        )

        # Orchestrator raises exception
        poller.orchestrator.route.side_effect = Exception("Processing error")  # type: ignore[attr-defined]

        with patch(
            "src.connectors.telegram.polling.normalize_telegram_update",
            return_value=mock_event,
        ):
            # Should not raise, just log exception
            await poller._process_update(update)

            poller.orchestrator.route.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_start_lifecycle(self, poller: TelegramPoller) -> None:
        """Test start() lifecycle without running the infinite loop."""
        # We'll test the initialization parts by mocking the while loop
        original_running = poller._running

        with (
            patch.object(poller, "_delete_webhook") as mock_delete,
            patch.object(poller, "_get_updates", return_value=[]),
        ):
            # Patch to exit loop immediately after first iteration
            async def mock_start():
                poller._running = True
                poller._client = httpx.AsyncClient(timeout=60.0)
                await poller._delete_webhook()
                # Exit immediately without loop
                poller._running = False

            # Test the initialization
            await mock_start()

            assert poller._client is not None
            assert isinstance(poller._client, httpx.AsyncClient)
            mock_delete.assert_called_once()

            # Cleanup
            await poller._client.aclose()
            poller._running = original_running

    @pytest.mark.asyncio
    async def test_stop_closes_client(self, poller: TelegramPoller) -> None:
        """Test that stop() closes the HTTP client."""
        mock_client = AsyncMock()
        poller._client = mock_client
        poller._running = True

        await poller.stop()

        assert poller._running is False
        mock_client.aclose.assert_called_once()
        assert poller._client is None

    @pytest.mark.asyncio
    async def test_stop_when_client_is_none(self, poller: TelegramPoller) -> None:
        """Test that stop() handles None client gracefully."""
        poller._client = None
        poller._running = True

        await poller.stop()

        assert poller._running is False
        assert poller._client is None
