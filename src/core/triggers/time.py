"""Time trigger detector.

Detects time references in messages using ML classifier and regex parsing.
Determines whether the time is in user's timezone or an explicit timezone.
Implements the TriggerDetector protocol.
"""

from __future__ import annotations

import logging

from src.core.models import DetectedTrigger, NormalizedEvent
from src.core.time_parse import parse_times
from src.core.tz_context_trigger import detect_tz_context

logger = logging.getLogger(__name__)

# Threshold for using LLM fallback for TZ resolution
_LLM_TZ_RESOLUTION_CONFIDENCE_THRESHOLD = 0.7


class TimeDetector:
    """Detects time references in messages.

    Uses the existing time parsing infrastructure:
    1. ML classifier for quick detection
    2. Regex patterns for extraction
    3. TZ context trigger to determine source timezone
    4. LLM fallback for edge cases

    Implements TriggerDetector protocol.
    """

    async def detect(
        self,
        event: NormalizedEvent,
        user_tz: str | None = None,
        use_llm_fallback: bool = True,
    ) -> list[DetectedTrigger]:
        """Detect time references in a normalized event.

        Args:
            event: The normalized event to analyze.
            user_tz: User's verified timezone (for fallback when no explicit TZ).
            use_llm_fallback: Whether to use LLM for uncertain TZ resolution.

        Returns:
            List of detected time triggers. Empty if no times found.
        """
        # Use existing time parsing infrastructure
        parsed_times = await parse_times(event.text)

        if not parsed_times:
            return []

        # Check if message has explicit TZ context
        tz_trigger = detect_tz_context(event.text)

        # Convert ParsedTime to DetectedTrigger
        triggers: list[DetectedTrigger] = []
        for pt in parsed_times:
            # Determine source timezone:
            # 1. If explicit TZ in message (Мск, PST, "по Тбилиси") → use that
            # 2. Otherwise → use user's verified timezone
            source_tz = pt.timezone_hint
            # Explicit TZ is determined solely by whether a TZ was parsed from the message.
            # tz_trigger is kept for LLM gating but not for is_explicit_tz determination.
            is_explicit_tz = source_tz is not None

            # If TZ trigger fired but regex couldn't extract TZ, use LLM
            needs_llm_resolution = (
                use_llm_fallback
                and tz_trigger.triggered
                and source_tz is None
                and tz_trigger.confidence >= _LLM_TZ_RESOLUTION_CONFIDENCE_THRESHOLD
            )

            if needs_llm_resolution:
                # LLM fallback for TZ resolution
                resolved = await self._resolve_tz_with_llm(event.text, user_tz)
                if resolved is not None:
                    source_tz = resolved["source_tz"]
                    is_explicit_tz = not resolved["is_user_tz"]

            # If still no explicit TZ, fall back to user's timezone
            if source_tz is None:
                source_tz = user_tz

            triggers.append(
                DetectedTrigger(
                    trigger_type="time",
                    confidence=pt.confidence,
                    original_text=pt.original_text,
                    data={
                        "hour": pt.hour,
                        "minute": pt.minute,
                        "timezone_hint": pt.timezone_hint,
                        "source_tz": source_tz,
                        "is_explicit_tz": is_explicit_tz,
                        "is_user_tz": not is_explicit_tz,
                        "is_tomorrow": pt.is_tomorrow,
                        "tz_trigger_type": tz_trigger.trigger_type,
                        "tz_trigger_confidence": tz_trigger.confidence,
                    },
                )
            )

        return triggers

    async def _resolve_tz_with_llm(
        self,
        text: str,
        user_tz: str | None,
    ) -> dict[str, object] | None:
        """Use LLM to resolve timezone from message.

        Args:
            text: Message text.
            user_tz: User's verified timezone.

        Returns:
            Dict with source_tz and is_user_tz, or None if resolution fails.
        """
        try:
            from src.core.llm_fallback import resolve_timezone_context

            result = await resolve_timezone_context(
                message=text,
                user_tz=user_tz,
            )

            # Only use LLM result if confidence is reasonable
            if result.confidence >= 0.5:
                logger.debug(
                    f"LLM TZ resolution: {result.source_tz} "
                    f"(is_user_tz={result.is_user_tz}, conf={result.confidence})"
                )
                return {
                    "source_tz": result.source_tz,
                    "is_user_tz": result.is_user_tz,
                }

            logger.debug(f"LLM TZ resolution low confidence: {result.confidence}")
            return None

        except Exception as e:
            logger.warning(f"LLM TZ resolution failed: {e}")
            return None
