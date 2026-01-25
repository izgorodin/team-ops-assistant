"""WhatsApp Cloud API outbound connector.

Sends messages to WhatsApp via the Cloud API.

WhatsApp Cloud API docs: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages

Note: WhatsApp has a 24-hour messaging window. Template messages are needed
for initiating conversations or messaging outside this window.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.models import OutboundMessage, Platform
from src.settings import get_settings

logger = logging.getLogger(__name__)

# WhatsApp Cloud API base URL
WHATSAPP_API_BASE = "https://graph.facebook.com/v18.0"


class WhatsAppOutbound:
    """WhatsApp Cloud API outbound message sender.

    Uses WhatsApp Cloud API to send text messages.
    Note: For initiating conversations or messaging outside the 24h window,
    template messages are required (use send_template_message).
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize the WhatsApp outbound connector.

        Args:
            http_client: Optional httpx client for dependency injection.
        """
        self.settings = get_settings()
        self._http_client = http_client
        self._owns_client = False

    @property
    def api_base(self) -> str:
        """Get the WhatsApp API base URL for this phone number."""
        return f"{WHATSAPP_API_BASE}/{self.settings.whatsapp_phone_number_id}"

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.settings.whatsapp_access_token}",
                    "Content-Type": "application/json",
                },
            )
            self._owns_client = True
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            self._owns_client = False

    async def send_message(self, message: OutboundMessage) -> dict[str, Any] | None:
        """Send a text message via WhatsApp.

        Args:
            message: OutboundMessage to send.

        Returns:
            WhatsApp API response on success, None on failure.
        """
        if message.platform != Platform.WHATSAPP:
            logger.error(f"WhatsAppOutbound received non-WhatsApp message: {message.platform}")
            return None

        url = f"{self.api_base}/messages"
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.chat_id,  # Phone number
            "type": "text",
            "text": {"body": message.text},
        }

        # For replies within a conversation
        if message.reply_to_message_id:
            payload["context"] = {"message_id": message.reply_to_message_id}

        client = await self.get_http_client()

        try:
            response = await client.post(url, json=payload)
            data = response.json()

            if not response.is_success:
                error = data.get("error", {})
                error_msg = error.get("message", "Unknown error")
                error_code = error.get("code", 0)
                logger.error(
                    f"WhatsApp API error {response.status_code} (code {error_code}): {error_msg} "
                    f"(to={message.chat_id})"
                )
                return None

            return data

        except httpx.HTTPError as e:
            logger.error(f"WhatsApp HTTP error: {e!r} (to={message.chat_id})")
            return None

    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en_US",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Send a template message via WhatsApp.

        Template messages are required for initiating conversations
        or messaging outside the 24-hour window.

        Args:
            to: Recipient phone number.
            template_name: Name of the approved template.
            language_code: Template language code.
            components: Template components (header, body, buttons).

        Returns:
            WhatsApp API response on success, None on failure.
        """
        url = f"{self.api_base}/messages"
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }

        if components:
            payload["template"]["components"] = components

        client = await self.get_http_client()

        try:
            response = await client.post(url, json=payload)
            data = response.json()

            if not response.is_success:
                error = data.get("error", {})
                error_msg = error.get("message", "Unknown error")
                logger.error(f"WhatsApp template error: {error_msg} (to={to})")
                return None

            return data

        except httpx.HTTPError as e:
            logger.error(f"WhatsApp HTTP error: {e!r} (to={to})")
            return None


# Global outbound instance
_outbound: WhatsAppOutbound | None = None


def get_whatsapp_outbound() -> WhatsAppOutbound:
    """Get the global WhatsApp outbound instance."""
    global _outbound
    if _outbound is None:
        _outbound = WhatsAppOutbound()
    return _outbound


async def close_whatsapp_outbound() -> None:
    """Close the global WhatsApp outbound instance."""
    global _outbound
    if _outbound:
        await _outbound.close()
        _outbound = None


async def send_messages(messages: list[OutboundMessage]) -> int:
    """Send multiple messages to WhatsApp.

    Args:
        messages: List of OutboundMessage to send.

    Returns:
        Number of successfully sent messages.
    """
    outbound = get_whatsapp_outbound()
    success_count = 0

    for message in messages:
        if message.platform == Platform.WHATSAPP:
            result = await outbound.send_message(message)
            if result:
                success_count += 1

    return success_count
