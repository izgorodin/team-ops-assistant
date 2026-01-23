"""Tests for city pick flow.

Tests the state acquisition: user picks a city → timezone saved with confidence=1.0.

Contract:
- City reply detected and handled (before time detection)
- City name matching is case-insensitive
- City pick saves timezone with confidence=1.0
- City pick sets updated_at=now (resets decay)
- Non-city replies pass through to normal handler
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.models import (
    NormalizedEvent,
    Platform,
    TimezoneSource,
    UserTzState,
)

# ============================================================================
# Unit Tests for handle_city_pick()
# ============================================================================


@pytest.mark.asyncio
async def test_city_reply_returns_timezone() -> None:
    """'London' → Europe/London returned."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    result = await handler.handle_city_pick(
        platform=Platform.TELEGRAM,
        user_id="123",
        city_name="London",
    )

    assert result == "Europe/London"


@pytest.mark.asyncio
async def test_city_reply_case_insensitive() -> None:
    """'london', 'LONDON', 'London' all work."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    # All case variations should work
    assert await handler.handle_city_pick(Platform.TELEGRAM, "1", "london") == "Europe/London"
    assert await handler.handle_city_pick(Platform.TELEGRAM, "2", "LONDON") == "Europe/London"
    assert await handler.handle_city_pick(Platform.TELEGRAM, "3", "LoNdOn") == "Europe/London"


@pytest.mark.asyncio
async def test_city_reply_with_whitespace() -> None:
    """' London ' with whitespace still works."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    assert await handler.handle_city_pick(Platform.TELEGRAM, "1", "  London  ") == "Europe/London"


@pytest.mark.asyncio
async def test_unknown_city_returns_none() -> None:
    """Unknown city returns None."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    handler = MessageHandler(storage)

    result = await handler.handle_city_pick(
        platform=Platform.TELEGRAM,
        user_id="123",
        city_name="Unknown City",
    )

    assert result is None


@pytest.mark.asyncio
async def test_city_pick_saves_with_confidence_1() -> None:
    """City pick saves timezone with confidence=1.0 (not 0.85)."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    await handler.handle_city_pick(
        platform=Platform.TELEGRAM,
        user_id="123",
        city_name="Tokyo",
    )

    # Verify upsert was called with correct state
    storage.upsert_user_tz_state.assert_called_once()
    saved_state: UserTzState = storage.upsert_user_tz_state.call_args[0][0]

    assert saved_state.tz_iana == "Asia/Tokyo"
    assert saved_state.confidence == 1.0  # KEY: confidence=1.0
    assert saved_state.source == TimezoneSource.CITY_PICK


@pytest.mark.asyncio
async def test_city_pick_sets_updated_at_now() -> None:
    """City pick sets updated_at to now (for decay calculation)."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    before = datetime.now(UTC)
    await handler.handle_city_pick(Platform.TELEGRAM, "123", "Sydney")
    after = datetime.now(UTC)

    saved_state: UserTzState = storage.upsert_user_tz_state.call_args[0][0]

    # updated_at should be between before and after
    # Note: UserTzState uses datetime.utcnow() which is naive
    assert saved_state.updated_at is not None
    # Since utcnow() returns naive datetime, compare with naive
    assert before.replace(tzinfo=None) <= saved_state.updated_at <= after.replace(tzinfo=None)


# ============================================================================
# Integration Tests for handle() with city detection
# ============================================================================


@pytest.mark.asyncio
async def test_handle_detects_city_reply() -> None:
    """handle() should detect city replies and process them."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.check_dedupe_event = AsyncMock(return_value=False)
    storage.upsert_dedupe_event = AsyncMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    event = NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id="evt123",
        chat_id="chat456",
        user_id="user789",
        text="London",  # Just the city name
    )

    result = await handler.handle(event)

    # Should respond with confirmation
    assert result.should_respond is True
    assert len(result.messages) == 1
    # Should mention timezone was saved
    assert "London" in result.messages[0].text or "Europe/London" in result.messages[0].text


@pytest.mark.asyncio
async def test_handle_ignores_non_city_text() -> None:
    """handle() should pass through non-city text to normal flow."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.check_dedupe_event = AsyncMock(return_value=False)

    handler = MessageHandler(storage)

    event = NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id="evt123",
        chat_id="chat456",
        user_id="user789",
        text="Hello, how are you?",  # Not a city
    )

    result = await handler.handle(event)

    # Should not respond (no time reference in this text)
    assert result.should_respond is False


@pytest.mark.asyncio
async def test_handle_city_with_time_prefers_time() -> None:
    """Message with both city and time should process time, not city pick."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.check_dedupe_event = AsyncMock(return_value=False)
    storage.insert_dedupe_event = AsyncMock()  # Used by mark_processed
    storage.get_user_tz_state = AsyncMock(
        return_value=UserTzState(
            platform=Platform.TELEGRAM,
            user_id="user789",
            tz_iana="America/New_York",
            confidence=1.0,
            source=TimezoneSource.WEB_VERIFIED,
            updated_at=datetime.now(UTC),
        )
    )
    storage.get_chat_state = AsyncMock(return_value=None)

    handler = MessageHandler(storage)

    event = NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id="evt123",
        chat_id="chat456",
        user_id="user789",
        text="Meeting at 3pm in London",  # Has time AND city
    )

    result = await handler.handle(event)

    # Should process as time conversion, not city pick
    # Message with spaces is not treated as city pick
    assert result.should_respond is True
    # Should have time conversion in response (mentions timezone)
    response_text = result.messages[0].text if result.messages else ""
    # Time conversion responses include timezone abbreviations or city names
    assert "New York" in response_text or "America" in response_text or ":" in response_text


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_handle_short_non_city_word_ignored() -> None:
    """Short single-word text that's not a city should be ignored."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.check_dedupe_event = AsyncMock(return_value=False)
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    event = NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id="evt123",
        chat_id="chat456",
        user_id="user789",
        text="Hello",  # Short, no spaces, but not a city
    )

    result = await handler.handle(event)

    # Should not respond (not a city, no time reference)
    assert result.should_respond is False


@pytest.mark.asyncio
async def test_handle_long_text_skips_city_check() -> None:
    """Text longer than 50 chars should skip city check."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.check_dedupe_event = AsyncMock(return_value=False)

    handler = MessageHandler(storage)

    # 60 chars of 'a' - longer than 50 char limit
    event = NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id="evt123",
        chat_id="chat456",
        user_id="user789",
        text="a" * 60,
    )

    result = await handler.handle(event)

    # Should not respond (too long for city, no time reference)
    assert result.should_respond is False


@pytest.mark.asyncio
async def test_city_pick_all_configured_cities() -> None:
    """All configured cities should be recognized."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    expected = {
        "Los Angeles": "America/Los_Angeles",
        "New York": "America/New_York",
        "London": "Europe/London",
        "Berlin": "Europe/Berlin",
        "Tokyo": "Asia/Tokyo",
        "Sydney": "Australia/Sydney",
    }

    for city_name, expected_tz in expected.items():
        result = await handler.handle_city_pick(Platform.TELEGRAM, "test", city_name)
        assert result == expected_tz, f"Failed for {city_name}"


@pytest.mark.asyncio
async def test_city_pick_response_includes_timezone() -> None:
    """Response after city pick should confirm the timezone."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.check_dedupe_event = AsyncMock(return_value=False)
    storage.upsert_dedupe_event = AsyncMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    event = NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id="evt123",
        chat_id="chat456",
        user_id="user789",
        text="Berlin",
    )

    result = await handler.handle(event)

    assert result.should_respond is True
    # Response should mention Berlin or Europe/Berlin
    response_text = result.messages[0].text
    assert "Berlin" in response_text or "Europe/Berlin" in response_text


@pytest.mark.asyncio
async def test_handle_multiword_city_detected() -> None:
    """Multi-word cities like 'New York' should be detected via handle()."""
    from src.core.handler import MessageHandler

    storage = MagicMock()
    storage.check_dedupe_event = AsyncMock(return_value=False)
    storage.upsert_dedupe_event = AsyncMock()
    storage.upsert_user_tz_state = AsyncMock()

    handler = MessageHandler(storage)

    event = NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id="evt123",
        chat_id="chat456",
        user_id="user789",
        text="New York",  # Multi-word city
    )

    result = await handler.handle(event)

    # Should respond with confirmation
    assert result.should_respond is True
    assert len(result.messages) == 1
    response_text = result.messages[0].text
    assert "New York" in response_text or "America/New_York" in response_text
