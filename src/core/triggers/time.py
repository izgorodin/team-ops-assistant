"""Time trigger detector.

Detects time references in messages using regex parsing.
Determines whether the time is in user's timezone or an explicit timezone.
Implements the TriggerDetector protocol.

NO ML dependency - uses regex + geonames only (98% rule-based).
"""

from __future__ import annotations

import logging
import re

from src.core.geo import geocode_city
from src.core.models import DetectedTrigger, NormalizedEvent
from src.core.time_parse import parse_times

logger = logging.getLogger(__name__)

# Pattern to extract city name from "по [city]" references (Russian)
_PO_CITY_PATTERN = re.compile(
    r"по\s+([а-яёА-ЯЁ][а-яёА-ЯЁ\-]+)",
    re.IGNORECASE,
)


class TimeDetector:
    """Detects time references in messages.

    Uses pure regex + geonames approach (no ML):
    1. Regex patterns for time extraction (parse_times)
    2. TZ hints from regex (e.g., "3pm PST")
    3. "по [city]" pattern → geonames lookup
    4. Fallback to user's verified timezone

    Implements TriggerDetector protocol.
    """

    async def detect(
        self,
        event: NormalizedEvent,
        user_tz: str | None = None,
        use_llm_fallback: bool = True,  # noqa: ARG002 - Kept for API compatibility
    ) -> list[DetectedTrigger]:
        """Detect time references in a normalized event.

        Args:
            event: The normalized event to analyze.
            user_tz: User's verified timezone (for fallback when no explicit TZ).
            use_llm_fallback: Deprecated, kept for API compatibility.

        Returns:
            List of detected time triggers. Empty if no times found.
        """
        # Parse times using regex patterns
        parsed_times = await parse_times(event.text)

        if not parsed_times:
            return []

        # Convert ParsedTime to DetectedTrigger
        triggers: list[DetectedTrigger] = []
        for pt in parsed_times:
            # Determine source timezone:
            # 1. If explicit TZ in message (Мск, PST, etc.) → use that
            # 2. Try "по [city]" pattern → geonames lookup
            # 3. Otherwise → use user's verified timezone
            source_tz = pt.timezone_hint
            is_explicit_tz = source_tz is not None

            # If no TZ hint from regex, try geocoding "по [city]" pattern
            if source_tz is None:
                geocoded_tz = self._try_geocode_from_text(event.text)
                if geocoded_tz:
                    source_tz = geocoded_tz
                    is_explicit_tz = True
                    logger.debug(f"Geocoded TZ from text: {geocoded_tz}")

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
                    },
                )
            )

        return triggers

    def _try_geocode_from_text(self, text: str) -> str | None:
        """Try to extract city from text and geocode it.

        Looks for "по [city]" pattern and uses geo.geocode_city() to resolve.

        Args:
            text: Message text.

        Returns:
            IANA timezone if city found, None otherwise.
        """
        match = _PO_CITY_PATTERN.search(text)
        if not match:
            return None

        city = match.group(1)

        # Skip short matches (likely false positives)
        if len(city) < 3:
            return None

        # Use unified geocoding (handles Russian case normalization internally)
        result = geocode_city(city, use_llm=False)  # No LLM in detection path
        if result:
            logger.debug(f"Geocoded '{city}' → {result[0]} ({result[1]})")
            return result[1]

        return None
