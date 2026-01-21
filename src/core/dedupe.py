"""Deduplication and throttling for message handling.

Ensures idempotent processing and prevents spam.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from src.core.models import DedupeEvent, Platform
from src.settings import get_settings

if TYPE_CHECKING:
    from src.storage.mongo import MongoStorage


class DedupeManager:
    """Manages event deduplication and response throttling."""

    def __init__(self, storage: MongoStorage) -> None:
        """Initialize the dedupe manager.

        Args:
            storage: MongoDB storage instance.
        """
        self.storage = storage
        self.settings = get_settings()
        # In-memory throttle cache (chat_key -> last_response_time)
        self._throttle_cache: dict[str, datetime] = {}

    async def is_duplicate(self, platform: Platform, event_id: str) -> bool:
        """Check if an event has already been processed.

        Args:
            platform: Event platform.
            event_id: Unique event identifier.

        Returns:
            True if event was already processed.
        """
        return await self.storage.check_dedupe_event(platform, event_id)

    async def mark_processed(self, platform: Platform, event_id: str, chat_id: str) -> None:
        """Mark an event as processed.

        Args:
            platform: Event platform.
            event_id: Unique event identifier.
            chat_id: Chat where event occurred.
        """
        event = DedupeEvent(
            platform=platform,
            event_id=event_id,
            chat_id=chat_id,
            created_at=datetime.utcnow(),
        )
        await self.storage.insert_dedupe_event(event)

    def is_throttled(self, platform: Platform, chat_id: str) -> bool:
        """Check if responses to a chat are throttled.

        Args:
            platform: Chat platform.
            chat_id: Chat identifier.

        Returns:
            True if we should not respond due to throttling.
        """
        config = self.settings.config.dedupe
        cache_key = f"{platform.value}:{chat_id}"

        last_response = self._throttle_cache.get(cache_key)
        if last_response is None:
            return False

        elapsed = (datetime.utcnow() - last_response).total_seconds()
        return elapsed < config.throttle_seconds

    def record_response(self, platform: Platform, chat_id: str) -> None:
        """Record that a response was sent to a chat.

        Args:
            platform: Chat platform.
            chat_id: Chat identifier.
        """
        cache_key = f"{platform.value}:{chat_id}"
        self._throttle_cache[cache_key] = datetime.utcnow()

    def cleanup_throttle_cache(self) -> None:
        """Clean up old entries from the throttle cache."""
        config = self.settings.config.dedupe
        cutoff = datetime.utcnow() - timedelta(seconds=config.throttle_seconds * 10)

        expired_keys = [key for key, ts in self._throttle_cache.items() if ts < cutoff]
        for key in expired_keys:
            del self._throttle_cache[key]
