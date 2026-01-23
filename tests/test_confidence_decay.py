"""Tests for confidence decay functionality.

Tests the state lifecycle: confidence decays over time, triggering re-verification.

Contract:
- get_effective_confidence(state, config) -> float
- Fresh state (today) returns full confidence
- Confidence decays by decay_per_day for each day since updated_at
- Decayed confidence never goes below 0.0
- State with effective confidence < threshold triggers verification
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.core.models import Platform, TimezoneSource, UserTzState
from src.settings import ConfidenceConfig

# ============================================================================
# Unit Tests for get_effective_confidence()
# ============================================================================


def test_fresh_state_has_full_confidence() -> None:
    """State set today has effective confidence equal to stored confidence."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.01, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC),
    )

    effective = get_effective_confidence(state, config)

    # Allow tiny floating point difference from test execution time
    assert effective == pytest.approx(1.0, abs=0.001)


def test_confidence_decays_after_one_day() -> None:
    """After 1 day with decay=0.01, confidence drops by 0.01."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.01, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC) - timedelta(days=1),
    )

    effective = get_effective_confidence(state, config)

    assert effective == pytest.approx(0.99, abs=0.001)


def test_confidence_decays_to_threshold_after_30_days() -> None:
    """After 30 days with decay=0.01, confidence drops from 1.0 to 0.7."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.01, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC) - timedelta(days=30),
    )

    effective = get_effective_confidence(state, config)

    assert effective == pytest.approx(0.7, abs=0.001)


def test_old_state_triggers_verification() -> None:
    """State >30 days old prompts re-verification (effective confidence < threshold)."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.01, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC) - timedelta(days=31),
    )

    effective = get_effective_confidence(state, config)

    assert effective < config.threshold


def test_decay_floors_at_zero() -> None:
    """Confidence never goes negative, even after very long time."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.01, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC) - timedelta(days=365),  # 1 year
    )

    effective = get_effective_confidence(state, config)

    assert effective == 0.0


def test_zero_decay_rate_preserves_confidence() -> None:
    """With decay_per_day=0, confidence never decays."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.0, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC) - timedelta(days=365),
    )

    effective = get_effective_confidence(state, config)

    assert effective == 1.0


def test_partial_confidence_decays_correctly() -> None:
    """State with confidence=0.85 decays correctly."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.01, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="America/New_York",
        confidence=0.85,  # City pick (legacy)
        source=TimezoneSource.CITY_PICK,
        updated_at=datetime.now(UTC) - timedelta(days=10),
    )

    effective = get_effective_confidence(state, config)

    # 0.85 - (0.01 * 10) = 0.75
    assert effective == pytest.approx(0.75, abs=0.001)


# ============================================================================
# Integration Tests for TimezoneIdentityManager
# ============================================================================


@pytest.mark.asyncio
async def test_get_effective_timezone_applies_decay() -> None:
    """get_effective_timezone should use decayed confidence."""
    from unittest.mock import AsyncMock, MagicMock

    from src.core.timezone_identity import TimezoneIdentityManager

    # Create mock storage
    storage = MagicMock()
    storage.get_user_tz_state = AsyncMock(
        return_value=UserTzState(
            platform=Platform.TELEGRAM,
            user_id="123",
            tz_iana="Europe/London",
            confidence=1.0,
            source=TimezoneSource.WEB_VERIFIED,
            updated_at=datetime.now(UTC) - timedelta(days=31),  # Old state
        )
    )
    storage.get_chat_state = AsyncMock(return_value=None)

    manager = TimezoneIdentityManager(storage)

    tz, confidence = await manager.get_effective_timezone(
        platform=Platform.TELEGRAM,
        user_id="123",
        chat_id="456",
    )

    # Decayed confidence = 1.0 - (0.01 * 31) = 0.69 < 0.7 threshold
    # Should return None because confidence below threshold
    assert tz is None
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_should_prompt_verification_with_decay() -> None:
    """should_prompt_verification should consider decayed confidence."""
    from unittest.mock import MagicMock

    from src.core.timezone_identity import TimezoneIdentityManager

    storage = MagicMock()
    manager = TimezoneIdentityManager(storage)

    old_state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,  # High stored confidence
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC) - timedelta(days=31),  # But old
    )

    # Should prompt because decayed confidence < threshold
    assert manager.should_prompt_verification(old_state) is True


@pytest.mark.asyncio
async def test_fresh_state_does_not_prompt_verification() -> None:
    """Fresh high-confidence state should NOT prompt verification."""
    from unittest.mock import MagicMock

    from src.core.timezone_identity import TimezoneIdentityManager

    storage = MagicMock()
    manager = TimezoneIdentityManager(storage)

    fresh_state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=1.0,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=datetime.now(UTC),  # Fresh
    )

    assert manager.should_prompt_verification(fresh_state) is False


def test_future_timestamp_clamps_to_stored_confidence() -> None:
    """Clock skew (future updated_at) should clamp to stored confidence, not exceed it."""
    from src.core.timezone_identity import get_effective_confidence

    config = ConfidenceConfig(decay_per_day=0.01, threshold=0.7)
    state = UserTzState(
        platform=Platform.TELEGRAM,
        user_id="123",
        tz_iana="Europe/London",
        confidence=0.9,
        source=TimezoneSource.WEB_VERIFIED,
        # Future timestamp (clock skew)
        updated_at=datetime.now(UTC) + timedelta(days=10),
    )

    effective = get_effective_confidence(state, config)

    # Should never exceed stored confidence
    assert effective <= state.confidence
    assert effective == 0.9  # Clamped to stored value
