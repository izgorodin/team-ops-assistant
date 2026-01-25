"""Slack inbound connector.

Handles incoming Slack Events API webhooks and normalizes them to NormalizedEvent.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.core.models import NormalizedEvent, Platform

logger = logging.getLogger(__name__)


def normalize_slack_event(payload: dict[str, Any]) -> NormalizedEvent | None:
    """Normalize a Slack Events API callback to a NormalizedEvent.

    Handles the event_callback wrapper and extracts the message event.

    Args:
        payload: Slack Events API callback payload.

    Returns:
        NormalizedEvent if this is a processable message, None otherwise.
    """
    # Handle URL verification challenge (not a real event)
    if payload.get("type") == "url_verification":
        logger.debug("Received URL verification challenge")
        return None

    # Must be an event_callback
    if payload.get("type") != "event_callback":
        logger.debug(f"Ignoring non-event_callback payload: {payload.get('type')}")
        return None

    # Extract the inner event
    event = payload.get("event", {})
    if not event:
        logger.warning("Event callback missing event field")
        return None

    # Only handle message events
    if event.get("type") != "message":
        logger.debug(f"Ignoring non-message event: {event.get('type')}")
        return None

    # Skip message subtypes that aren't regular messages
    # (bot_message, message_changed, message_deleted, etc.)
    subtype = event.get("subtype")
    if subtype is not None:
        logger.debug(f"Ignoring message with subtype: {subtype}")
        return None

    # Extract message text
    text = event.get("text", "")
    if not text:
        logger.debug("Ignoring message without text")
        return None

    # Extract channel ID
    channel_id = event.get("channel", "")
    if not channel_id:
        logger.warning("Message missing channel ID")
        return None

    # Extract user ID
    user_id = event.get("user", "")
    if not user_id:
        logger.warning("Message missing user ID")
        return None

    # Extract timestamp (Slack uses ts as message ID)
    ts = event.get("ts", "")
    if not ts:
        logger.warning("Message missing timestamp")
        return None

    # Build event ID for deduplication
    # Format: {channel}_{ts} to match Telegram pattern
    event_id = f"{channel_id}_{ts}"

    # Extract timestamp as datetime
    try:
        timestamp = datetime.utcfromtimestamp(float(ts.split(".")[0]))
    except (ValueError, TypeError):
        timestamp = datetime.utcnow()

    # Check for thread reply (thread_ts indicates a reply)
    thread_ts = event.get("thread_ts")
    reply_to_message_id = thread_ts if thread_ts and thread_ts != ts else None

    return NormalizedEvent(
        platform=Platform.SLACK,
        event_id=event_id,
        message_id=ts,
        chat_id=channel_id,
        user_id=user_id,
        username=None,  # Slack doesn't include username in event, need API call
        display_name=None,  # Same - need users.info API call
        text=text,
        timestamp=timestamp,
        reply_to_message_id=reply_to_message_id,
        raw_payload=payload,
    )


def handle_url_verification(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Handle Slack URL verification challenge.

    Slack sends this when setting up the Events API endpoint.

    Args:
        payload: The incoming request payload.

    Returns:
        Response dict with challenge if verification request, None otherwise.
    """
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge", "")
        return {"challenge": challenge}
    return None


# Example Slack Events API payload for testing/documentation
EXAMPLE_EVENT = {
    "token": "z26uFbvR1xHJEdHE1OQiO6t8",
    "team_id": "T123ABC456",
    "api_app_id": "A123ABC456",
    "event": {
        "type": "message",
        "channel": "C123ABC456",
        "user": "U123ABC456",
        "text": "Let's meet at 3pm PST tomorrow",
        "ts": "1704067200.000001",
        "event_ts": "1704067200.000001",
        "channel_type": "channel",
    },
    "type": "event_callback",
    "authed_teams": ["T123ABC456"],
    "event_id": "Ev123ABC456",
    "event_time": 1704067200,
}

# Example URL verification payload
EXAMPLE_URL_VERIFICATION = {
    "token": "z26uFbvR1xHJEdHE1OQiO6t8",
    "challenge": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "type": "url_verification",
}
