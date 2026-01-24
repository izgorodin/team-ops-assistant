"""Timezone state manager.

Manages user timezone state with confidence tracking.
Implements the StateManager[str] protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.models import Platform, StateResult, TimezoneSource
from src.core.timezone_identity import get_effective_confidence
from src.settings import get_settings

if TYPE_CHECKING:
    from src.storage.mongo import MongoStorage


class TimezoneStateManager:
    """Manages user timezone state.

    Wraps the existing timezone identity infrastructure with
    the StateManager protocol interface.

    Implements StateManager[str] protocol where T=str (IANA timezone).
    """

    def __init__(self, storage: MongoStorage | None = None) -> None:
        """Initialize the timezone state manager.

        Args:
            storage: MongoDB storage instance. If None, will be lazy-loaded.
        """
        self._storage = storage
        self._settings = get_settings()

    @property
    def storage(self) -> MongoStorage:
        """Get storage instance, lazy-loading if needed."""
        if self._storage is None:
            from src.storage.mongo import MongoStorage

            self._storage = MongoStorage()
        return self._storage

    async def get_state(
        self,
        platform: Platform,
        user_id: str,
        chat_id: str,
    ) -> StateResult[str]:
        """Get current timezone for a user.

        Follows disambiguation policy:
        1. User's verified timezone (if confidence >= threshold)
        2. Chat default timezone
        3. None (unknown)

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            chat_id: Chat/channel ID.

        Returns:
            StateResult containing timezone value, confidence, and source.
        """
        config = self._settings.config.confidence

        try:
            # Use self.storage to trigger lazy-loading if needed
            # Try user's verified timezone first (with decay applied)
            user_state = await self.storage.get_user_tz_state(platform, user_id)
            if user_state and user_state.tz_iana:
                # Apply confidence decay based on time since last update
                effective_conf = get_effective_confidence(user_state, config)
                if effective_conf >= config.threshold:
                    return StateResult[str](
                        value=user_state.tz_iana,
                        confidence=effective_conf,  # Return decayed confidence
                        source=user_state.source.value,
                    )

            # Try chat default timezone
            chat_state = await self.storage.get_chat_state(platform, chat_id)
            if chat_state and chat_state.default_tz:
                return StateResult[str](
                    value=chat_state.default_tz,
                    confidence=config.chat_default,
                    source="chat_default",
                )
        except Exception:
            # Storage unavailable, return unknown
            pass

        # Unknown
        return StateResult[str](
            value=None,
            confidence=0.0,
            source="unknown",
        )

    async def update_state(
        self,
        platform: Platform,
        user_id: str,
        value: str,
        source: str,
        confidence: float,
    ) -> None:
        """Update timezone for a user.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            value: IANA timezone identifier.
            source: Where this value came from.
            confidence: Confidence in this value.
        """
        from datetime import datetime

        from src.core.models import UserTzState

        # Map source string to TimezoneSource enum
        try:
            source_enum = TimezoneSource(source)
        except ValueError:
            source_enum = TimezoneSource.DEFAULT

        now = datetime.utcnow()
        state = UserTzState(
            platform=platform,
            user_id=user_id,
            tz_iana=value,
            confidence=confidence,
            source=source_enum,
            updated_at=now,
            last_verified_at=now if source_enum == TimezoneSource.WEB_VERIFIED else None,
        )

        await self.storage.upsert_user_tz_state(state)
