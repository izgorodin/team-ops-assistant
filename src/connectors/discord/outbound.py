"""Discord outbound connector.

Sends messages to Discord channels via the REST API (v10).

Discord API docs: https://discord.com/developers/docs/resources/channel#create-message
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.models import OutboundMessage, Platform
from src.settings import get_settings

logger = logging.getLogger(__name__)

# Discord API base URL
DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordOutbound:
    """Discord outbound message sender.

    Uses Discord REST API v10 to send messages to channels.
    Requires a bot token with MESSAGE_CONTENT intent and Send Messages permission.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize the Discord outbound connector.

        Args:
            http_client: Optional httpx client for dependency injection.
        """
        self.settings = get_settings()
        self._http_client = http_client
        self._owns_client = False

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bot {self.settings.discord_bot_token}",
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
        """Send a message to a Discord channel.

        Args:
            message: OutboundMessage to send.

        Returns:
            Discord API response on success, None on failure.
        """
        if message.platform != Platform.DISCORD:
            logger.error(f"DiscordOutbound received non-Discord message: {message.platform}")
            return None

        url = f"{DISCORD_API_BASE}/channels/{message.chat_id}/messages"
        payload: dict[str, Any] = {"content": message.text}

        # Add message reference for replies
        if message.reply_to_message_id:
            payload["message_reference"] = {"message_id": message.reply_to_message_id}

        client = await self.get_http_client()

        try:
            response = await client.post(url, json=payload)
            data = response.json()

            if not response.is_success:
                error_msg = data.get("message", "Unknown error")
                error_code = data.get("code", 0)
                logger.error(
                    f"Discord API error {response.status_code} (code {error_code}): {error_msg} "
                    f"(channel={message.chat_id})"
                )
                return None

            return data

        except httpx.HTTPError as e:
            logger.error(f"Discord HTTP error: {e!r} (channel={message.chat_id})")
            return None


# Global outbound instance
_outbound: DiscordOutbound | None = None


def get_discord_outbound() -> DiscordOutbound:
    """Get the global Discord outbound instance."""
    global _outbound
    if _outbound is None:
        _outbound = DiscordOutbound()
    return _outbound


async def close_discord_outbound() -> None:
    """Close the global Discord outbound instance."""
    global _outbound
    if _outbound:
        await _outbound.close()
        _outbound = None


async def send_messages(messages: list[OutboundMessage]) -> int:
    """Send multiple messages to Discord.

    Args:
        messages: List of OutboundMessage to send.

    Returns:
        Number of successfully sent messages.
    """
    outbound = get_discord_outbound()
    success_count = 0

    for message in messages:
        if message.platform == Platform.DISCORD:
            result = await outbound.send_message(message)
            if result:
                success_count += 1

    return success_count
