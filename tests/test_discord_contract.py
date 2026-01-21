"""Contract tests for Discord connector (skeleton)."""

from __future__ import annotations

import pytest

from src.connectors.discord.inbound import (
    EXAMPLE_MESSAGE_CREATE,
    NORMALIZATION_EXPECTATIONS,
    normalize_discord_message,
)
from src.core.models import Platform


class TestDiscordNormalization:
    """Contract tests for Discord message normalization."""

    def test_normalize_basic_message(self) -> None:
        """Test normalization of a basic Discord message."""
        event = normalize_discord_message(EXAMPLE_MESSAGE_CREATE)

        assert event is not None
        assert event.platform == Platform.DISCORD
        assert event.text == "Let's meet at 3pm PST tomorrow"
        assert event.user_id == "777888999000111222"
        assert event.chat_id == "987654321098765432"
        assert event.username == "johndoe"
        assert event.display_name == "John Doe"

    def test_event_id_format(self) -> None:
        """Test that event ID is formatted for deduplication."""
        event = normalize_discord_message(EXAMPLE_MESSAGE_CREATE)

        assert event is not None
        assert event.event_id == "987654321098765432_123456789012345678"

    def test_normalize_missing_fields(self) -> None:
        """Test that messages with missing fields are rejected."""
        # Missing ID
        result = normalize_discord_message({"content": "test"})
        assert result is None

        # Missing channel_id
        result = normalize_discord_message({"id": "123", "content": "test"})
        assert result is None

        # Missing content
        result = normalize_discord_message({"id": "123", "channel_id": "456"})
        assert result is None

    def test_normalize_skips_bot_messages(self) -> None:
        """Test that bot messages are skipped."""
        payload = {
            "id": "123",
            "channel_id": "456",
            "content": "Bot message",
            "author": {"id": "789", "username": "testbot", "bot": True},
        }

        event = normalize_discord_message(payload)
        assert event is None

    def test_normalize_with_reply(self) -> None:
        """Test normalization with reply reference."""
        payload = {
            **EXAMPLE_MESSAGE_CREATE,
            "referenced_message": {"id": "111111111111111111"},
        }

        event = normalize_discord_message(payload)

        assert event is not None
        assert event.reply_to_message_id == "111111111111111111"


class TestDiscordContractExpectations:
    """Tests validating the normalization expectations."""

    @pytest.mark.parametrize(
        "expectation", NORMALIZATION_EXPECTATIONS, ids=lambda e: str(e.get("expected"))
    )
    def test_normalization_expectations(self, expectation: dict) -> None:
        """Test each documented normalization expectation."""
        input_payload = expectation["input"]
        expected = expectation["expected"]

        result = normalize_discord_message(input_payload)

        if expected is None:
            assert result is None
        else:
            assert result is not None
            for key, value in expected.items():
                if key == "platform":
                    assert result.platform.value == value
                else:
                    assert getattr(result, key) == value


class TestDiscordPayloadFixtures:
    """Tests using realistic Discord payload fixtures."""

    @pytest.fixture
    def guild_message(self) -> dict:
        """Fixture for a guild (server) message."""
        return {
            "id": "1234567890123456789",
            "type": 0,
            "content": "Team sync at 2pm Pacific",
            "channel_id": "9876543210987654321",
            "guild_id": "1111222233334444555",
            "author": {
                "id": "5555666677778888999",
                "username": "developer",
                "discriminator": "0",
                "global_name": "Dev User",
                "bot": False,
            },
            "timestamp": "2024-01-15T10:30:00.000000+00:00",
        }

    @pytest.fixture
    def dm_message(self) -> dict:
        """Fixture for a DM (direct message)."""
        return {
            "id": "9999888877776666555",
            "type": 0,
            "content": "Can we chat at 4pm?",
            "channel_id": "1111111111111111111",
            # No guild_id for DMs
            "author": {
                "id": "2222222222222222222",
                "username": "friend",
                "discriminator": "1234",
                "bot": False,
            },
            "timestamp": "2024-01-15T11:00:00.000000+00:00",
        }

    def test_guild_message_normalization(self, guild_message: dict) -> None:
        """Test normalization of guild message."""
        event = normalize_discord_message(guild_message)

        assert event is not None
        assert event.platform == Platform.DISCORD
        assert event.text == "Team sync at 2pm Pacific"
        assert event.display_name == "Dev User"

    def test_dm_message_normalization(self, dm_message: dict) -> None:
        """Test normalization of DM."""
        event = normalize_discord_message(dm_message)

        assert event is not None
        # DMs should still work without guild_id
        assert event.chat_id == "1111111111111111111"
        # Falls back to username when no global_name
        assert event.display_name == "friend"
