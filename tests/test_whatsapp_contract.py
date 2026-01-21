"""Contract tests for WhatsApp connector (skeleton)."""

from __future__ import annotations

import pytest

from src.connectors.whatsapp.inbound import (
    EXAMPLE_WEBHOOK_PAYLOAD,
    NORMALIZATION_EXPECTATIONS,
    normalize_whatsapp_webhook,
)
from src.core.models import Platform


class TestWhatsAppNormalization:
    """Contract tests for WhatsApp webhook normalization."""

    def test_normalize_basic_webhook(self) -> None:
        """Test normalization of a basic WhatsApp webhook."""
        events = normalize_whatsapp_webhook(EXAMPLE_WEBHOOK_PAYLOAD)

        assert len(events) == 1
        event = events[0]

        assert event.platform == Platform.WHATSAPP
        assert event.text == "Let's meet at 3pm PST tomorrow"
        assert event.user_id == "15559876543"
        assert event.chat_id == "15559876543"
        assert event.display_name == "John Doe"
        assert event.event_id == "wamid.ABC123xyz"

    def test_normalize_non_whatsapp_webhook(self) -> None:
        """Test that non-WhatsApp webhooks are ignored."""
        payload = {"object": "page"}  # Facebook Page webhook

        events = normalize_whatsapp_webhook(payload)
        assert len(events) == 0

    def test_normalize_non_text_message(self) -> None:
        """Test that non-text messages are skipped."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messages": [
                                    {
                                        "id": "123",
                                        "from": "456",
                                        "type": "image",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        events = normalize_whatsapp_webhook(payload)
        assert len(events) == 0

    def test_normalize_multiple_messages(self) -> None:
        """Test normalization of webhook with multiple messages."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "contacts": [
                                    {"wa_id": "111", "profile": {"name": "Alice"}},
                                    {"wa_id": "222", "profile": {"name": "Bob"}},
                                ],
                                "messages": [
                                    {
                                        "id": "msg1",
                                        "from": "111",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                        "timestamp": "1704067200",
                                    },
                                    {
                                        "id": "msg2",
                                        "from": "222",
                                        "type": "text",
                                        "text": {"body": "Hi there"},
                                        "timestamp": "1704067201",
                                    },
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        events = normalize_whatsapp_webhook(payload)

        assert len(events) == 2
        assert events[0].display_name == "Alice"
        assert events[1].display_name == "Bob"

    def test_normalize_with_reply_context(self) -> None:
        """Test normalization of message with reply context."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "contacts": [{"wa_id": "123", "profile": {"name": "Test"}}],
                                "messages": [
                                    {
                                        "id": "reply_msg",
                                        "from": "123",
                                        "type": "text",
                                        "text": {"body": "Reply"},
                                        "timestamp": "1704067200",
                                        "context": {"id": "original_msg_id"},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        events = normalize_whatsapp_webhook(payload)

        assert len(events) == 1
        assert events[0].reply_to_message_id == "original_msg_id"


class TestWhatsAppContractExpectations:
    """Tests validating the normalization expectations."""

    @pytest.mark.parametrize(
        "expectation",
        NORMALIZATION_EXPECTATIONS,
        ids=lambda e: f"expect_{len(e.get('expected', []))}_events",
    )
    def test_normalization_expectations(self, expectation: dict) -> None:
        """Test each documented normalization expectation."""
        input_payload = expectation["input"]
        expected = expectation["expected"]

        result = normalize_whatsapp_webhook(input_payload)

        if not expected:
            assert len(result) == 0
        else:
            assert len(result) == len(expected)
            for i, exp in enumerate(expected):
                for key, value in exp.items():
                    if key == "platform":
                        assert result[i].platform.value == value
                    else:
                        assert getattr(result[i], key) == value


class TestWhatsAppPayloadFixtures:
    """Tests using realistic WhatsApp payload fixtures."""

    @pytest.fixture
    def status_update_webhook(self) -> dict:
        """Fixture for a message status update webhook."""
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "statuses": [
                                    {
                                        "id": "wamid.XYZ",
                                        "status": "delivered",
                                        "timestamp": "1704067300",
                                        "recipient_id": "15559876543",
                                    }
                                ]
                            },
                        }
                    ]
                }
            ],
        }

    def test_status_update_produces_no_events(self, status_update_webhook: dict) -> None:
        """Test that status updates don't produce events."""
        events = normalize_whatsapp_webhook(status_update_webhook)
        assert len(events) == 0

    @pytest.fixture
    def international_phone_message(self) -> dict:
        """Fixture for message from international number."""
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "contacts": [
                                    {
                                        "wa_id": "4915123456789",
                                        "profile": {"name": "Hans"},
                                    }
                                ],
                                "messages": [
                                    {
                                        "id": "wamid.DE123",
                                        "from": "4915123456789",
                                        "type": "text",
                                        "text": {"body": "Meeting at 14:00 CET"},
                                        "timestamp": "1704067200",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

    def test_international_phone_normalization(self, international_phone_message: dict) -> None:
        """Test normalization with international phone number."""
        events = normalize_whatsapp_webhook(international_phone_message)

        assert len(events) == 1
        assert events[0].user_id == "4915123456789"
        assert events[0].display_name == "Hans"
        assert "14:00 CET" in events[0].text
