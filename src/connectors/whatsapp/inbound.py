"""WhatsApp Cloud API inbound connector.

Handles incoming WhatsApp webhook events and normalizes them to NormalizedEvent.

WhatsApp Cloud API docs: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks

Note: WhatsApp webhooks require verification during setup.
See app.py for the verification endpoint implementation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.core.models import NormalizedEvent, Platform

logger = logging.getLogger(__name__)


def normalize_whatsapp_webhook(payload: dict[str, Any]) -> list[NormalizedEvent]:
    """Normalize a WhatsApp webhook payload to NormalizedEvents.

    WhatsApp webhooks can contain multiple messages in a single payload.

    Args:
        payload: WhatsApp Cloud API webhook payload.

    Returns:
        List of NormalizedEvent for each processable message.
    """
    events: list[NormalizedEvent] = []

    # WhatsApp webhook structure:
    # {
    #     "object": "whatsapp_business_account",
    #     "entry": [{
    #         "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
    #         "changes": [{
    #             "value": {
    #                 "messaging_product": "whatsapp",
    #                 "metadata": {"display_phone_number": "...", "phone_number_id": "..."},
    #                 "contacts": [{"profile": {"name": "..."}, "wa_id": "..."}],
    #                 "messages": [{...}]
    #             },
    #             "field": "messages"
    #         }]
    #     }]
    # }

    if payload.get("object") != "whatsapp_business_account":
        logger.debug("Ignoring non-WhatsApp webhook")
        return events

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue

            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])

            # Build contact lookup
            contact_map: dict[str, dict[str, Any]] = {}
            for contact in contacts:
                wa_id = contact.get("wa_id", "")
                if wa_id:
                    contact_map[wa_id] = contact

            for msg in messages:
                event = _normalize_single_message(msg, contact_map, payload)
                if event:
                    events.append(event)

    return events


def _normalize_single_message(
    msg: dict[str, Any],
    contact_map: dict[str, dict[str, Any]],
    raw_payload: dict[str, Any],
) -> NormalizedEvent | None:
    """Normalize a single WhatsApp message.

    Args:
        msg: Single message object from webhook.
        contact_map: Map of wa_id to contact info.
        raw_payload: Full webhook payload for debugging.

    Returns:
        NormalizedEvent if processable, None otherwise.
    """
    # Only handle text messages for now
    if msg.get("type") != "text":
        logger.debug(f"Ignoring WhatsApp message type: {msg.get('type')}")
        return None

    message_id = msg.get("id", "")
    from_id = msg.get("from", "")
    text_obj = msg.get("text", {})
    body = text_obj.get("body", "")

    if not message_id or not from_id or not body:
        logger.debug("WhatsApp message missing required fields")
        return None

    # Get contact info
    contact = contact_map.get(from_id, {})
    profile = contact.get("profile", {})
    display_name = profile.get("name", from_id)

    # Parse timestamp
    timestamp_str = msg.get("timestamp", "")
    try:
        timestamp = datetime.utcfromtimestamp(int(timestamp_str))
    except (ValueError, TypeError):
        timestamp = datetime.utcnow()

    # WhatsApp uses phone number as chat ID for 1:1 chats
    # For groups, would need to extract from context
    chat_id = from_id  # TODO: Handle group chats properly

    # Check for reply context
    context = msg.get("context", {})
    reply_to_message_id = context.get("id") if context else None

    return NormalizedEvent(
        platform=Platform.WHATSAPP,
        event_id=message_id,
        message_id=message_id,
        chat_id=chat_id,
        user_id=from_id,
        username=None,  # WhatsApp doesn't have usernames
        display_name=display_name,
        text=body,
        timestamp=timestamp,
        reply_to_message_id=reply_to_message_id,
        raw_payload=raw_payload,
    )


# Example WhatsApp webhook payload for testing/documentation
EXAMPLE_WEBHOOK_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "PHONE_NUMBER_ID",
                        },
                        "contacts": [
                            {
                                "profile": {"name": "John Doe"},
                                "wa_id": "15559876543",
                            }
                        ],
                        "messages": [
                            {
                                "from": "15559876543",
                                "id": "wamid.ABC123xyz",
                                "timestamp": "1704067200",
                                "text": {"body": "Let's meet at 3pm PST tomorrow"},
                                "type": "text",
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


# Contract test expectations
NORMALIZATION_EXPECTATIONS = [
    {
        "input": EXAMPLE_WEBHOOK_PAYLOAD,
        "expected": [
            {
                "platform": "whatsapp",
                "event_id": "wamid.ABC123xyz",
                "chat_id": "15559876543",
                "user_id": "15559876543",
                "display_name": "John Doe",
                "text": "Let's meet at 3pm PST tomorrow",
            }
        ],
    },
    {
        "input": {"object": "other"},
        "expected": [],  # Should ignore non-WhatsApp webhooks
    },
    {
        "input": {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {"messages": [{"type": "image", "id": "123", "from": "456"}]},
                        }
                    ]
                }
            ],
        },
        "expected": [],  # Should ignore non-text messages
    },
]
