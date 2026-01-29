"""Discord inbound connector.

Handles incoming Discord MESSAGE_CREATE events and normalizes them to NormalizedEvent.
Uses the Discord API v10 webhook/interaction format.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.core.models import NormalizedEvent, Platform

logger = logging.getLogger(__name__)


def normalize_discord_message(payload: dict[str, Any]) -> NormalizedEvent | None:
    """Normalize a Discord MESSAGE_CREATE event to a NormalizedEvent.

    Args:
        payload: Discord message payload (MESSAGE_CREATE event data).

    Returns:
        NormalizedEvent if this is a processable message, None otherwise.
    """
    message_id = payload.get("id", "")
    channel_id = payload.get("channel_id", "")
    content = payload.get("content", "")

    if not message_id or not channel_id or not content:
        logger.debug("Ignoring Discord message missing required fields")
        return None

    author = payload.get("author", {})
    user_id = author.get("id", "")
    if not user_id:
        logger.warning("Discord message missing author ID")
        return None

    # Skip bot messages
    if author.get("bot", False):
        logger.debug("Ignoring Discord bot message")
        return None

    # Build display name
    display_name = author.get("global_name") or author.get("username", "Unknown")
    username = author.get("username")

    # Parse timestamp
    timestamp_str = payload.get("timestamp", "")
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        timestamp = datetime.now(UTC)

    # Check for reply
    referenced = payload.get("referenced_message")
    reply_to_message_id = referenced.get("id") if referenced else None

    return NormalizedEvent(
        platform=Platform.DISCORD,
        event_id=f"{channel_id}_{message_id}",
        message_id=message_id,
        chat_id=channel_id,
        user_id=user_id,
        username=username,
        display_name=display_name,
        text=content,
        timestamp=timestamp,
        reply_to_message_id=reply_to_message_id,
        raw_payload=payload,
    )


# Example Discord MESSAGE_CREATE payload for testing/documentation
EXAMPLE_MESSAGE_CREATE = {
    "id": "123456789012345678",
    "type": 0,
    "content": "Let's meet at 3pm PST tomorrow",
    "channel_id": "987654321098765432",
    "guild_id": "111222333444555666",
    "author": {
        "id": "777888999000111222",
        "username": "johndoe",
        "discriminator": "0",
        "global_name": "John Doe",
        "avatar": "abc123",
        "bot": False,
    },
    "timestamp": "2024-01-01T15:30:00.000000+00:00",
    "edited_timestamp": None,
    "tts": False,
    "mention_everyone": False,
    "mentions": [],
    "mention_roles": [],
    "attachments": [],
    "embeds": [],
    "pinned": False,
    "referenced_message": None,
}


# Contract test expectations
NORMALIZATION_EXPECTATIONS = [
    {
        "input": EXAMPLE_MESSAGE_CREATE,
        "expected": {
            "platform": "discord",
            "event_id": "987654321098765432_123456789012345678",
            "chat_id": "987654321098765432",
            "user_id": "777888999000111222",
            "username": "johndoe",
            "display_name": "John Doe",
            "text": "Let's meet at 3pm PST tomorrow",
        },
    },
    {
        "input": {"id": "", "content": "test"},
        "expected": None,  # Should return None for invalid input
    },
    {
        "input": {
            "id": "123",
            "channel_id": "456",
            "content": "hello",
            "author": {"id": "789", "username": "bot", "bot": True},
        },
        "expected": None,  # Should skip bot messages
    },
]
