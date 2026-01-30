"""Time trigger detector.

Detects time references in messages using ML classifier and regex parsing.
Determines whether the time is in user's timezone or an explicit timezone.
Implements the TriggerDetector protocol.
"""

from __future__ import annotations

import logging
import re

from src.core.models import DetectedTrigger, NormalizedEvent
from src.core.time_parse import parse_times
from src.core.tz_context_trigger import detect_tz_context

logger = logging.getLogger(__name__)

# Pattern to extract city name from "по [city]" references (Russian)
_PO_CITY_EXTRACT_PATTERN = re.compile(
    r"по\s+([а-яёА-ЯЁ][а-яёА-ЯЁ\-]+)",
    re.IGNORECASE,
)


def _normalize_russian_city_name(city: str) -> str:
    """Normalize Russian city name by removing case endings.

    In Russian, city names are declined. "по Бобруйску" uses dative case.
    This function tries to convert to nominative case for geocoding.

    Common patterns:
    - "-ску" → "-ск" (Бобруйску → Бобруйск, Минску → Минск)
    - "-ве" → "-ва" (Москве → Москва)
    - "-ни" → "-нь" (Казани → Казань)

    Args:
        city: City name (possibly in dative/prepositional case).

    Returns:
        Normalized city name (nominative case attempt).
    """
    city_lower = city.lower()

    # Common dative endings
    if city_lower.endswith("ску"):
        return city[:-1]  # Remove final char: -sku -> -sk
    if city_lower.endswith("ку"):
        return city[:-1]  # бак → Баку stays, but "Минску" → "Минск"
    if city_lower.endswith("ве"):
        return city[:-1] + "а"  # Москве → Москва
    if city_lower.endswith("ни") and len(city) > 4:
        return city[:-1] + "ь"  # Казани → Казань
    if city_lower.endswith("си") and len(city) > 4:
        return city  # Тбилиси stays as is
    if city_lower.endswith("у") and len(city) > 3:
        # Generic dative ending, try removing it
        return city[:-1]

    return city


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

            # If TZ trigger fired but regex couldn't extract TZ, try resolution
            needs_tz_resolution = (
                tz_trigger.triggered
                and source_tz is None
                and tz_trigger.confidence >= _LLM_TZ_RESOLUTION_CONFIDENCE_THRESHOLD
            )

            if needs_tz_resolution:
                # First try geocoding - fast path using geonamescache (always enabled)
                geocoded_tz = self._try_geocode_from_text(event.text)
                if geocoded_tz:
                    source_tz = geocoded_tz
                    is_explicit_tz = True
                    logger.debug(f"Geocoded TZ from text: {geocoded_tz}")
                elif use_llm_fallback:
                    # LLM fallback for TZ resolution (only if enabled)
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

    def _try_geocode_from_text(self, text: str) -> str | None:
        """Try to extract city from text and geocode it.

        Looks for "по [city]" pattern and uses geonamescache to resolve timezone.
        This is faster than LLM and works for any city in the database.

        Args:
            text: Message text.

        Returns:
            IANA timezone if city found, None otherwise.
        """
        # Extract city from "по [city]" pattern
        match = _PO_CITY_EXTRACT_PATTERN.search(text)
        if not match:
            return None

        city = match.group(1)

        # Skip short matches (likely false positives)
        if len(city) < 3:
            return None

        # Try to geocode via geonamescache (now searches alternatenames too)
        try:
            from src.core.agent_tools import _lookup_city_geonames

            # Try original form first
            result = _lookup_city_geonames(city)
            if result.startswith("FOUND:"):
                tz = result.split("→")[-1].strip()
                logger.debug(f"Geocoded '{city}' → {tz}")
                return tz

            # Normalize Russian case endings and try again
            # e.g. "bobruysku" -> "bobruysk" (dative -> nominative)
            normalized = _normalize_russian_city_name(city)
            if normalized != city:
                result = _lookup_city_geonames(normalized)
                if result.startswith("FOUND:"):
                    tz = result.split("→")[-1].strip()
                    logger.debug(f"Geocoded '{city}' (normalized: {normalized}) → {tz}")
                    return tz

        except Exception as e:
            logger.warning(f"Geocoding failed for '{city}': {e}")

        return None

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
