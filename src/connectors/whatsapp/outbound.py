"""WhatsApp Cloud API outbound connector (SKELETON).

Sends messages to WhatsApp via the Cloud API.

TODO: Complete implementation
- Implement proper authentication
- Handle rate limits
- Support message templates (required for some scenarios)
- Implement retry logic with exponential backoff
- Handle different message types (text, template, interactive)
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
    """WhatsApp Cloud API outbound message sender (SKELETON).

    This is a skeleton implementation. For full WhatsApp support:
    1. Use message templates for initiating conversations (24h window rule)
    2. Handle different message types (text, template, interactive, media)
    3. Implement proper error handling for API responses
    4. Handle rate limits and quota management
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

        TODO: Implement this method
        - POST to /{phone_number_id}/messages
        - Handle 24-hour messaging window
        - Support template messages for out-of-window sends
        """
        if message.platform != Platform.WHATSAPP:
            logger.error(f"WhatsAppOutbound received non-WhatsApp message: {message.platform}")
            return None

        # TODO: Implement WhatsApp API call
        # Example implementation:
        #
        # url = f"{self.api_base}/messages"
        # payload = {
        #     "messaging_product": "whatsapp",
        #     "recipient_type": "individual",
        #     "to": message.chat_id,  # Phone number
        #     "type": "text",
        #     "text": {"body": message.text}
        # }
        #
        # # For replies within a conversation
        # if message.reply_to_message_id:
        #     payload["context"] = {"message_id": message.reply_to_message_id}
        #
        # client = await self.get_http_client()
        # response = await client.post(url, json=payload)
        # return response.json()

        logger.warning("WhatsApp outbound not implemented - message not sent")
        return None

    async def send_template_message(
        self,
        to: str,  # noqa: ARG002
        template_name: str,  # noqa: ARG002
        language_code: str = "en_US",  # noqa: ARG002
        components: list[dict[str, Any]] | None = None,  # noqa: ARG002
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

        TODO: Implement this method
        """
        # TODO: Implement template message sending
        logger.warning("WhatsApp template messages not implemented")
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
