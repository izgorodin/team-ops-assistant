"""Telegram polling mode for local development.

Uses getUpdates API instead of webhooks. This allows testing
without a public URL.

Usage:
    python -m src.app --polling
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx

from src.connectors.telegram.inbound import normalize_telegram_update
from src.connectors.telegram.outbound import send_messages
from src.settings import get_settings

if TYPE_CHECKING:
    from src.core.orchestrator import MessageOrchestrator

logger = logging.getLogger(__name__)


class TelegramPoller:
    """Polls Telegram getUpdates API for local development."""

    def __init__(self, orchestrator: MessageOrchestrator) -> None:
        """Initialize the poller.

        Args:
            orchestrator: Message orchestrator for processing updates.
        """
        self.orchestrator = orchestrator
        self.settings = get_settings()
        self._running = False
        self._offset: int | None = None
        self._client: httpx.AsyncClient | None = None

    @property
    def api_base(self) -> str:
        """Get the Telegram API base URL with token."""
        return f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    async def start(self) -> None:
        """Start polling for updates."""
        self._running = True
        self._client = httpx.AsyncClient(timeout=60.0)

        # Delete webhook first (required for getUpdates to work)
        await self._delete_webhook()

        logger.info("Starting Telegram polling mode (local development)")
        logger.info("Send a message to your bot to test!")

        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._process_update(update)
            except httpx.HTTPError as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)  # Back off on errors
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Unexpected polling error: {e}")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop polling."""
        self._running = False
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Telegram polling stopped")

    async def _delete_webhook(self) -> None:
        """Delete any existing webhook (required for polling to work)."""
        if not self._client:
            return

        try:
            response = await self._client.post(f"{self.api_base}/deleteWebhook")
            data = response.json()
            if data.get("ok"):
                logger.info("Webhook deleted, polling mode active")
            else:
                logger.warning(f"Failed to delete webhook: {data}")
        except Exception as e:
            logger.warning(f"Error deleting webhook: {e}")

    async def _get_updates(self) -> list[dict[str, Any]]:
        """Get updates from Telegram.

        Returns:
            List of update objects.
        """
        if not self._client:
            return []

        params: dict[str, Any] = {
            "timeout": 30,  # Long polling timeout
            "allowed_updates": ["message"],  # Only get messages
        }
        if self._offset is not None:
            params["offset"] = self._offset

        response = await self._client.get(
            f"{self.api_base}/getUpdates",
            params=params,
        )
        data = response.json()

        if not data.get("ok"):
            logger.error(f"getUpdates error: {data}")
            return []

        updates = data.get("result", [])

        # Update offset to acknowledge processed updates
        if updates:
            self._offset = updates[-1]["update_id"] + 1

        return updates

    async def _process_update(self, update: dict[str, Any]) -> None:
        """Process a single update.

        Args:
            update: Telegram update object.
        """
        logger.debug(f"Processing update: {update.get('update_id')}")

        # Normalize the update
        event = normalize_telegram_update(update)
        if event is None:
            logger.debug("Update ignored (not a text message)")
            return

        logger.info(f"Received: '{event.text}' from {event.display_name}")

        try:
            # Process through orchestrator
            result = await self.orchestrator.route(event)

            # Send response messages
            if result.should_respond and result.messages:
                sent = await send_messages(result.messages)
                logger.info(f"Sent {sent} message(s)")
            else:
                logger.debug("No response needed")

        except Exception as e:
            logger.exception(f"Error processing update: {e}")
