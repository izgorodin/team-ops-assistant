"""Telegram outbound connector.

Sends messages to Telegram via the Bot API.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.models import OutboundMessage, Platform
from src.settings import get_settings

logger = logging.getLogger(__name__)

# Telegram Bot API base URL
TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramOutbound:
    """Telegram outbound message sender."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize the Telegram outbound connector.

        Args:
            http_client: Optional httpx client for dependency injection.
        """
        self.settings = get_settings()
        self._http_client = http_client
        self._owns_client = False

    @property
    def api_base(self) -> str:
        """Get the Telegram API base URL with token."""
        return f"{TELEGRAM_API_BASE}{self.settings.telegram_bot_token}"

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
            self._owns_client = True
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client if we own it."""
        if self._owns_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None
            self._owns_client = False

    async def send_message(self, message: OutboundMessage) -> dict[str, Any] | None:
        """Send a message to Telegram.

        Args:
            message: OutboundMessage to send.

        Returns:
            Telegram API response on success, None on failure.
        """
        if message.platform != Platform.TELEGRAM:
            logger.error(f"TelegramOutbound received non-Telegram message: {message.platform}")
            return None

        # Build request payload
        payload: dict[str, Any] = {
            "chat_id": message.chat_id,
            "text": message.text,
        }

        # Add parse mode if not plain
        if message.parse_mode == "markdown":
            payload["parse_mode"] = "MarkdownV2"
        elif message.parse_mode == "html":
            payload["parse_mode"] = "HTML"

        # Add reply_to if specified
        if message.reply_to_message_id:
            payload["reply_to_message_id"] = message.reply_to_message_id

        return await self._call_api("sendMessage", payload)

    async def _call_api(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Call the Telegram Bot API.

        Args:
            method: API method name (e.g., "sendMessage").
            payload: Request payload.

        Returns:
            API response on success, None on failure.
        """
        url = f"{self.api_base}/{method}"
        client = await self.get_http_client()

        try:
            response = await client.post(url, json=payload)

            # Always try to parse response for error details
            data = response.json()

            if not response.is_success:
                error_desc = data.get("description", "Unknown error")
                logger.error(
                    f"Telegram API error {response.status_code}: {error_desc} "
                    f"(payload: chat_id={payload.get('chat_id')}, "
                    f"reply_to={payload.get('reply_to_message_id')})"
                )
                return None

            if not data.get("ok"):
                logger.error(f"Telegram API error: {data}")
                return None

            return data.get("result")

        except httpx.HTTPError as e:
            logger.error(f"Telegram HTTP error: {e!r} (payload: {payload})")
            return None


# Global outbound instance
_outbound: TelegramOutbound | None = None


def get_telegram_outbound() -> TelegramOutbound:
    """Get the global Telegram outbound instance."""
    global _outbound
    if _outbound is None:
        _outbound = TelegramOutbound()
    return _outbound


async def close_telegram_outbound() -> None:
    """Close the global Telegram outbound instance."""
    global _outbound
    if _outbound:
        await _outbound.close()
        _outbound = None


async def send_messages(messages: list[OutboundMessage]) -> int:
    """Send multiple messages to Telegram.

    Args:
        messages: List of OutboundMessage to send.

    Returns:
        Number of successfully sent messages.
    """
    outbound = get_telegram_outbound()
    success_count = 0

    for message in messages:
        if message.platform == Platform.TELEGRAM:
            result = await outbound.send_message(message)
            if result:
                success_count += 1

    return success_count
