"""Slack outbound connector.

Sends messages to Slack via the Web API (chat.postMessage).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.core.models import OutboundMessage, Platform
from src.settings import get_settings

logger = logging.getLogger(__name__)

# Slack Web API base URL
SLACK_API_BASE = "https://slack.com/api"


class SlackOutbound:
    """Slack outbound message sender."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """Initialize the Slack outbound connector.

        Args:
            http_client: Optional httpx client for dependency injection.
        """
        self.settings = get_settings()
        self._http_client = http_client
        self._owns_client = False

    @property
    def bot_token(self) -> str:
        """Get the Slack bot token."""
        return self.settings.slack_bot_token or ""

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
        """Send a message to Slack.

        Args:
            message: OutboundMessage to send.

        Returns:
            Slack API response on success, None on failure.
        """
        if message.platform != Platform.SLACK:
            logger.error(f"SlackOutbound received non-Slack message: {message.platform}")
            return None

        # Build request payload
        payload: dict[str, Any] = {
            "channel": message.chat_id,
            "text": message.text,
        }

        # Add thread_ts for reply (Slack uses thread_ts, not reply_to_message_id)
        if message.reply_to_message_id:
            payload["thread_ts"] = message.reply_to_message_id

        # Slack supports mrkdwn by default, but we can be explicit
        if message.parse_mode == "markdown":
            payload["mrkdwn"] = True

        return await self._call_api("chat.postMessage", payload)

    async def _call_api(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Call the Slack Web API.

        Args:
            method: API method name (e.g., "chat.postMessage").
            payload: Request payload.

        Returns:
            API response on success, None on failure.
        """
        url = f"{SLACK_API_BASE}/{method}"
        client = await self.get_http_client()

        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        try:
            response = await client.post(url, json=payload, headers=headers)
            data = response.json()

            if not response.is_success:
                logger.error(
                    f"Slack API HTTP error {response.status_code}: {data} "
                    f"(payload: channel={payload.get('channel')})"
                )
                return None

            # Slack API returns ok=true/false in response body
            if not data.get("ok"):
                error = data.get("error", "unknown_error")
                logger.error(
                    f"Slack API error: {error} "
                    f"(payload: channel={payload.get('channel')}, "
                    f"thread_ts={payload.get('thread_ts')})"
                )
                return None

            return data

        except httpx.HTTPError as e:
            logger.error(f"Slack HTTP error: {e!r} (payload: {payload})")
            return None


# Global outbound instance
_outbound: SlackOutbound | None = None


def get_slack_outbound() -> SlackOutbound:
    """Get the global Slack outbound instance."""
    global _outbound
    if _outbound is None:
        _outbound = SlackOutbound()
    return _outbound


async def close_slack_outbound() -> None:
    """Close the global Slack outbound instance."""
    global _outbound
    if _outbound:
        await _outbound.close()
        _outbound = None


async def send_messages(messages: list[OutboundMessage]) -> int:
    """Send multiple messages to Slack.

    Args:
        messages: List of OutboundMessage to send.

    Returns:
        Number of successfully sent messages.
    """
    outbound = get_slack_outbound()
    success_count = 0

    for message in messages:
        if message.platform == Platform.SLACK:
            result = await outbound.send_message(message)
            if result:
                success_count += 1

    return success_count
