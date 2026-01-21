"""Contract tests for Telegram connector."""

from __future__ import annotations

import pytest

from src.connectors.telegram.inbound import (
    EXAMPLE_UPDATE,
    normalize_telegram_update,
)
from src.core.models import Platform


class TestTelegramNormalization:
    """Contract tests for Telegram message normalization."""

    def test_normalize_basic_message(self) -> None:
        """Test normalization of a basic text message."""
        event = normalize_telegram_update(EXAMPLE_UPDATE)

        assert event is not None
        assert event.platform == Platform.TELEGRAM
        assert event.text == "Let's meet at 3pm PST tomorrow"
        assert event.user_id == "12345678"
        assert event.chat_id == "-100123456789"
        assert event.username == "johndoe"
        assert event.display_name == "John Doe"

    def test_event_id_format(self) -> None:
        """Test that event ID is formatted correctly for deduplication."""
        event = normalize_telegram_update(EXAMPLE_UPDATE)

        assert event is not None
        assert event.event_id == "-100123456789_42"

    def test_normalize_message_without_text(self) -> None:
        """Test that messages without text are ignored."""
        update = {
            "update_id": 123,
            "message": {
                "message_id": 1,
                "from": {"id": 123},
                "chat": {"id": 456},
                # No "text" field
            },
        }

        event = normalize_telegram_update(update)
        assert event is None

    def test_normalize_non_message_update(self) -> None:
        """Test that non-message updates are ignored."""
        update = {
            "update_id": 123,
            "edited_message": {
                "message_id": 1,
                "text": "edited",
            },
        }

        event = normalize_telegram_update(update)
        assert event is None

    def test_normalize_with_reply(self) -> None:
        """Test normalization of a reply message."""
        update = {
            "update_id": 123,
            "message": {
                "message_id": 42,
                "from": {"id": 123, "first_name": "Test"},
                "chat": {"id": 456},
                "text": "Reply text",
                "date": 1704067200,
                "reply_to_message": {"message_id": 41},
            },
        }

        event = normalize_telegram_update(update)

        assert event is not None
        assert event.reply_to_message_id == "41"

    def test_normalize_preserves_raw_payload(self) -> None:
        """Test that raw payload is preserved for debugging."""
        event = normalize_telegram_update(EXAMPLE_UPDATE)

        assert event is not None
        assert event.raw_payload == EXAMPLE_UPDATE

    def test_display_name_fallbacks(self) -> None:
        """Test display name construction with various user data."""
        # First name only
        update1 = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 1, "first_name": "John"},
                "chat": {"id": 1},
                "text": "test",
                "date": 0,
            },
        }
        event1 = normalize_telegram_update(update1)
        assert event1 is not None
        assert event1.display_name == "John"

        # Last name only
        update2 = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 1, "last_name": "Doe"},
                "chat": {"id": 1},
                "text": "test",
                "date": 0,
            },
        }
        event2 = normalize_telegram_update(update2)
        assert event2 is not None
        assert event2.display_name == "Doe"

        # Username fallback
        update3 = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "from": {"id": 1, "username": "johndoe"},
                "chat": {"id": 1},
                "text": "test",
                "date": 0,
            },
        }
        event3 = normalize_telegram_update(update3)
        assert event3 is not None
        assert event3.display_name == "johndoe"


class TestTelegramPayloadFixtures:
    """Tests using realistic Telegram payload fixtures."""

    @pytest.fixture
    def group_message(self) -> dict:
        """Fixture for a group chat message."""
        return {
            "update_id": 987654321,
            "message": {
                "message_id": 100,
                "from": {
                    "id": 111222333,
                    "is_bot": False,
                    "first_name": "Alice",
                    "username": "alice_dev",
                },
                "chat": {
                    "id": -1001234567890,
                    "title": "Development Team",
                    "type": "supergroup",
                },
                "date": 1704153600,
                "text": "Standup at 9am EST",
            },
        }

    @pytest.fixture
    def private_message(self) -> dict:
        """Fixture for a private chat message."""
        return {
            "update_id": 987654322,
            "message": {
                "message_id": 50,
                "from": {
                    "id": 444555666,
                    "is_bot": False,
                    "first_name": "Bob",
                    "last_name": "Smith",
                },
                "chat": {
                    "id": 444555666,
                    "first_name": "Bob",
                    "last_name": "Smith",
                    "type": "private",
                },
                "date": 1704153700,
                "text": "When is the call?",
            },
        }

    def test_group_message_normalization(self, group_message: dict) -> None:
        """Test normalization of group message fixture."""
        event = normalize_telegram_update(group_message)

        assert event is not None
        assert event.platform == Platform.TELEGRAM
        assert event.chat_id == "-1001234567890"
        assert event.user_id == "111222333"
        assert event.text == "Standup at 9am EST"

    def test_private_message_normalization(self, private_message: dict) -> None:
        """Test normalization of private message fixture."""
        event = normalize_telegram_update(private_message)

        assert event is not None
        assert event.chat_id == "444555666"
        assert event.display_name == "Bob Smith"
