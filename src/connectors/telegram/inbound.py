"""Telegram inbound connector.

Handles incoming Telegram webhook updates and normalizes them to NormalizedEvent.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.core.models import NormalizedEvent, Platform

logger = logging.getLogger(__name__)


def normalize_telegram_update(update: dict[str, Any]) -> NormalizedEvent | None:
    """Normalize a Telegram update to a NormalizedEvent.

    Args:
        update: Raw Telegram update payload.

    Returns:
        NormalizedEvent if this is a processable message, None otherwise.
    """
    # Only handle message updates for now
    message = update.get("message")
    if not message:
        # Could be edited_message, channel_post, etc.
        logger.debug("Ignoring non-message update")
        return None

    # Extract message text
    text = message.get("text", "")
    if not text:
        # Photo, sticker, etc. without text
        logger.debug("Ignoring message without text")
        return None

    # Extract chat info
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    if not chat_id:
        logger.warning("Message missing chat ID")
        return None

    # Extract user info
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", ""))
    if not user_id:
        logger.warning("Message missing user ID")
        return None

    username = from_user.get("username")
    display_name = _build_display_name(from_user)

    # Build event ID for deduplication
    message_id = str(message.get("message_id", ""))
    event_id = f"{chat_id}_{message_id}"

    # Extract timestamp
    timestamp = datetime.fromtimestamp(message.get("date", 0), tz=UTC)

    # Check for reply
    reply_to = message.get("reply_to_message", {})
    reply_to_message_id = str(reply_to.get("message_id", "")) if reply_to else None

    return NormalizedEvent(
        platform=Platform.TELEGRAM,
        event_id=event_id,
        message_id=message_id,
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        display_name=display_name,
        text=text,
        timestamp=timestamp,
        reply_to_message_id=reply_to_message_id,
        raw_payload=update,
    )


def _build_display_name(user: dict[str, Any]) -> str:
    """Build a display name from Telegram user data.

    Args:
        user: Telegram user object.

    Returns:
        Display name string.
    """
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")

    if first_name and last_name:
        return f"{first_name} {last_name}"
    elif first_name:
        return first_name
    elif last_name:
        return last_name
    else:
        return user.get("username", "Unknown")


# Example Telegram update payload for testing/documentation
EXAMPLE_UPDATE = {
    "update_id": 123456789,
    "message": {
        "message_id": 42,
        "from": {
            "id": 12345678,
            "is_bot": False,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "language_code": "en",
        },
        "chat": {
            "id": -100123456789,
            "title": "Team Chat",
            "type": "supergroup",
        },
        "date": 1704067200,
        "text": "Let's meet at 3pm PST tomorrow",
    },
}
