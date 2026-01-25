"""Contract tests for Slack connector."""

from __future__ import annotations

import pytest

from src.connectors.slack.inbound import (
    EXAMPLE_EVENT,
    EXAMPLE_URL_VERIFICATION,
    handle_url_verification,
    normalize_slack_event,
)
from src.core.models import Platform


class TestSlackNormalization:
    """Contract tests for Slack message normalization."""

    def test_normalize_basic_message(self) -> None:
        """Test normalization of a basic text message."""
        event = normalize_slack_event(EXAMPLE_EVENT)

        assert event is not None
        assert event.platform == Platform.SLACK
        assert event.text == "Let's meet at 3pm PST tomorrow"
        assert event.user_id == "U123ABC456"
        assert event.chat_id == "C123ABC456"

    def test_event_id_format(self) -> None:
        """Test that event ID is formatted correctly for deduplication."""
        event = normalize_slack_event(EXAMPLE_EVENT)

        assert event is not None
        assert event.event_id == "C123ABC456_1704067200.000001"

    def test_message_id_is_timestamp(self) -> None:
        """Test that message_id uses Slack's ts field."""
        event = normalize_slack_event(EXAMPLE_EVENT)

        assert event is not None
        assert event.message_id == "1704067200.000001"

    def test_normalize_message_without_text(self) -> None:
        """Test that messages without text are ignored."""
        payload = {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "channel": "C123",
                "user": "U123",
                "ts": "123.456",
                # No "text" field
            },
        }

        event = normalize_slack_event(payload)
        assert event is None

    def test_normalize_non_message_event(self) -> None:
        """Test that non-message events are ignored."""
        payload = {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "reaction_added",
                "user": "U123",
                "reaction": "thumbsup",
            },
        }

        event = normalize_slack_event(payload)
        assert event is None

    def test_normalize_message_with_subtype_ignored(self) -> None:
        """Test that messages with subtypes (bot_message, etc.) are ignored."""
        payload = {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "subtype": "bot_message",
                "channel": "C123",
                "bot_id": "B123",
                "text": "Bot message",
                "ts": "123.456",
            },
        }

        event = normalize_slack_event(payload)
        assert event is None

    def test_normalize_with_thread_reply(self) -> None:
        """Test normalization of a thread reply message."""
        payload = {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "channel": "C123",
                "user": "U123",
                "text": "Reply in thread",
                "ts": "1704067300.000002",
                "thread_ts": "1704067200.000001",  # Parent message ts
            },
        }

        event = normalize_slack_event(payload)

        assert event is not None
        assert event.reply_to_message_id == "1704067200.000001"

    def test_normalize_parent_message_no_reply(self) -> None:
        """Test that parent message in thread doesn't have reply_to."""
        payload = {
            "type": "event_callback",
            "team_id": "T123",
            "event": {
                "type": "message",
                "channel": "C123",
                "user": "U123",
                "text": "Starting a thread",
                "ts": "1704067200.000001",
                "thread_ts": "1704067200.000001",  # Same as ts for parent
            },
        }

        event = normalize_slack_event(payload)

        assert event is not None
        assert event.reply_to_message_id is None

    def test_normalize_preserves_raw_payload(self) -> None:
        """Test that raw payload is preserved for debugging."""
        event = normalize_slack_event(EXAMPLE_EVENT)

        assert event is not None
        assert event.raw_payload == EXAMPLE_EVENT


class TestSlackUrlVerification:
    """Tests for Slack URL verification handling."""

    def test_handle_url_verification(self) -> None:
        """Test URL verification challenge response."""
        response = handle_url_verification(EXAMPLE_URL_VERIFICATION)

        assert response is not None
        assert response["challenge"] == "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

    def test_handle_url_verification_returns_none_for_events(self) -> None:
        """Test that regular events don't trigger verification response."""
        response = handle_url_verification(EXAMPLE_EVENT)

        assert response is None

    def test_normalize_returns_none_for_url_verification(self) -> None:
        """Test that URL verification is not normalized as event."""
        event = normalize_slack_event(EXAMPLE_URL_VERIFICATION)

        assert event is None


class TestSlackPayloadFixtures:
    """Tests using realistic Slack payload fixtures."""

    @pytest.fixture
    def channel_message(self) -> dict:
        """Fixture for a public channel message."""
        return {
            "token": "verification_token",
            "team_id": "T123ABC456",
            "api_app_id": "A123ABC456",
            "event": {
                "type": "message",
                "channel": "C123ABC456",
                "user": "U111222333",
                "text": "Standup at 9am EST",
                "ts": "1704153600.000100",
                "event_ts": "1704153600.000100",
                "channel_type": "channel",
            },
            "type": "event_callback",
            "event_id": "Ev123ABC456",
            "event_time": 1704153600,
        }

    @pytest.fixture
    def dm_message(self) -> dict:
        """Fixture for a direct message."""
        return {
            "token": "verification_token",
            "team_id": "T123ABC456",
            "api_app_id": "A123ABC456",
            "event": {
                "type": "message",
                "channel": "D123ABC456",  # DM channels start with D
                "user": "U444555666",
                "text": "When is the call?",
                "ts": "1704153700.000200",
                "event_ts": "1704153700.000200",
                "channel_type": "im",
            },
            "type": "event_callback",
            "event_id": "Ev789DEF123",
            "event_time": 1704153700,
        }

    def test_channel_message_normalization(self, channel_message: dict) -> None:
        """Test normalization of channel message fixture."""
        event = normalize_slack_event(channel_message)

        assert event is not None
        assert event.platform == Platform.SLACK
        assert event.chat_id == "C123ABC456"
        assert event.user_id == "U111222333"
        assert event.text == "Standup at 9am EST"

    def test_dm_message_normalization(self, dm_message: dict) -> None:
        """Test normalization of DM message fixture."""
        event = normalize_slack_event(dm_message)

        assert event is not None
        assert event.chat_id == "D123ABC456"
        assert event.text == "When is the call?"
