"""Timezone identity and confidence model.

Manages user timezone state, confidence scoring, and verification.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from src.core.models import Platform, TimezoneSource, UserTzState, VerifyToken
from src.settings import ConfidenceConfig, get_settings

if TYPE_CHECKING:
    from src.storage.mongo import MongoStorage


def get_effective_confidence(state: UserTzState, config: ConfidenceConfig) -> float:
    """Calculate effective confidence with time decay.

    Confidence decays over time since the state was last updated.
    This encourages periodic re-verification of stale data.

    Args:
        state: User timezone state with stored confidence and updated_at.
        config: Confidence configuration with decay_per_day.

    Returns:
        Effective confidence after applying decay. Always >= 0.0.
    """
    if config.decay_per_day <= 0:
        return state.confidence

    # Calculate days since last update
    now = datetime.now(UTC)
    # Handle naive datetime from state (utcnow() returns naive)
    updated_at = state.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)

    delta = now - updated_at
    days = delta.days + (delta.seconds / 86400)  # Include partial days

    # Apply decay
    decayed = state.confidence - (config.decay_per_day * days)

    # Floor at 0.0
    return max(decayed, 0.0)


class TimezoneIdentityManager:
    """Manages user timezone identity and confidence."""

    def __init__(self, storage: MongoStorage) -> None:
        """Initialize the timezone identity manager.

        Args:
            storage: MongoDB storage instance.
        """
        self.storage = storage
        self.settings = get_settings()

    async def get_user_timezone(self, platform: Platform, user_id: str) -> UserTzState | None:
        """Get user's timezone state.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.

        Returns:
            UserTzState if found, None otherwise.
        """
        return await self.storage.get_user_tz_state(platform, user_id)

    async def get_effective_timezone(
        self,
        platform: Platform,
        user_id: str,
        chat_id: str,
        explicit_tz: str | None = None,
    ) -> tuple[str | None, float]:
        """Get the effective timezone for a user following disambiguation policy.

        Policy order:
        1. Explicit timezone from message
        2. User's verified timezone (if effective confidence >= threshold)
        3. Chat default timezone
        4. None (caller should ask user to verify)

        Note: Effective confidence applies time decay to stored confidence.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            chat_id: Chat/channel ID.
            explicit_tz: Timezone explicitly mentioned in message.

        Returns:
            Tuple of (timezone, confidence). Timezone is None if unknown.
        """
        config = self.settings.config.confidence

        # 1. Explicit timezone from message
        if explicit_tz:
            return explicit_tz, 1.0

        # 2. User's verified timezone (with decay)
        user_state = await self.get_user_timezone(platform, user_id)
        if user_state and user_state.tz_iana:
            effective_conf = get_effective_confidence(user_state, config)
            if effective_conf >= config.threshold:
                return user_state.tz_iana, effective_conf

        # 3. Chat default timezone
        chat_state = await self.storage.get_chat_state(platform, chat_id)
        if chat_state and chat_state.default_tz:
            return chat_state.default_tz, config.chat_default

        # 4. Unknown
        return None, 0.0

    async def update_user_timezone(
        self,
        platform: Platform,
        user_id: str,
        tz_iana: str,
        source: TimezoneSource,
        confidence: float | None = None,
    ) -> UserTzState:
        """Update user's timezone.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            tz_iana: IANA timezone identifier.
            source: How the timezone was determined.
            confidence: Override confidence (uses source default if None).

        Returns:
            Updated UserTzState.
        """
        config = self.settings.config.confidence

        # Determine confidence based on source
        if confidence is None:
            if source == TimezoneSource.WEB_VERIFIED:
                confidence = config.verified
            elif source == TimezoneSource.CITY_PICK:
                confidence = config.city_pick
            elif source == TimezoneSource.MESSAGE_EXPLICIT:
                confidence = config.message_explicit
            elif source == TimezoneSource.INFERRED:
                confidence = config.inferred
            else:
                confidence = config.chat_default

        now = datetime.utcnow()
        state = UserTzState(
            platform=platform,
            user_id=user_id,
            tz_iana=tz_iana,
            confidence=confidence,
            source=source,
            updated_at=now,
            last_verified_at=now if source == TimezoneSource.WEB_VERIFIED else None,
        )

        await self.storage.upsert_user_tz_state(state)
        return state

    def should_prompt_verification(self, user_state: UserTzState | None) -> bool:
        """Check if we should prompt the user to verify their timezone.

        Uses effective (decayed) confidence to account for stale data.

        Args:
            user_state: Current user timezone state.

        Returns:
            True if user should be prompted to verify.
        """
        if user_state is None:
            return True

        if user_state.tz_iana is None:
            return True

        config = self.settings.config.confidence
        effective_conf = get_effective_confidence(user_state, config)
        return effective_conf < config.threshold


def generate_verify_token(
    platform: Platform, user_id: str, chat_id: str, expires_hours: int | None = None
) -> str:
    """Generate a verification token for timezone verification.

    Args:
        platform: User's platform.
        user_id: User's platform-specific ID.
        chat_id: Chat where the request originated.
        expires_hours: Token validity in hours. If None, uses
            config.ui.verification_token_hours (default: 24).
            Backwards compatible: explicit values work as before.

    Returns:
        Signed verification token.
    """
    settings = get_settings()
    if expires_hours is None:
        expires_hours = settings.config.ui.verification_token_hours
    secret = settings.verify_token_secret

    # Create token payload
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
    nonce = secrets.token_urlsafe(8)

    # Payload format: platform|user_id|chat_id|expires_timestamp|nonce
    payload = f"{platform.value}|{user_id}|{chat_id}|{int(expires_at.timestamp())}|{nonce}"

    # Sign with HMAC
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]

    return f"{payload}|{signature}"


def parse_verify_token(token: str) -> VerifyToken | None:
    """Parse and validate a verification token.

    Args:
        token: Token string to parse.

    Returns:
        VerifyToken if valid, None if invalid or expired.
    """
    settings = get_settings()
    secret = settings.verify_token_secret

    try:
        parts = token.split("|")
        if len(parts) != 6:
            return None

        platform_str, user_id, chat_id, expires_str, nonce, signature = parts

        # Verify signature
        payload = f"{platform_str}|{user_id}|{chat_id}|{expires_str}|{nonce}"
        expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]

        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Check expiry
        expires_at = datetime.utcfromtimestamp(int(expires_str))
        if datetime.utcnow() > expires_at:
            return None

        return VerifyToken(
            platform=Platform(platform_str),
            user_id=user_id,
            chat_id=chat_id,
            created_at=datetime.utcnow(),  # Not stored in token
            expires_at=expires_at,
        )
    except (ValueError, KeyError):
        return None


def get_verify_url(token: str, base_url: str = "") -> str:
    """Get the full verification URL for a token.

    Args:
        token: Verification token.
        base_url: Base URL of the application.

    Returns:
        Full verification URL.
    """
    return f"{base_url}/verify?token={token}"
