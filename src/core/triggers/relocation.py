"""Relocation trigger detector.

Detects phrases indicating user has moved to a different location.
Implements the TriggerDetector protocol.

Detection strategy:
1. Regex patterns for explicit relocation phrases (EN/RU) - high confidence
2. City name detection from geonames (any language) - medium confidence

This makes the detector language-agnostic while preferring explicit phrases.
"""

from __future__ import annotations

import re

from src.core.geo import find_cities_in_text
from src.core.models import DetectedTrigger, NormalizedEvent
from src.settings import get_settings

# Common words that shouldn't be part of city names
# These get captured due to greedy (\w+\s+\w+)? pattern
TRAILING_WORDS = frozenset(
    {
        # English time words
        "last",
        "next",
        "yesterday",
        "today",
        "tomorrow",
        "soon",
        "week",
        "month",
        "year",
        "ago",
        # Russian words
        "живу",
        "жить",
        "буду",
        "работаю",
        "теперь",
    }
)


def _clean_city(raw_city: str) -> str:
    """Remove trailing non-city words from captured city name.

    The regex captures "London last" from "moved to London last week".
    This function strips common trailing words.

    Args:
        raw_city: Raw captured city string, possibly with trailing words.

    Returns:
        Cleaned city name.
    """
    words = raw_city.split()
    if len(words) > 1 and words[-1].lower() in TRAILING_WORDS:
        return " ".join(words[:-1])
    return raw_city


# Relocation patterns (English and Russian, past and future tense)
# Each pattern has a capturing group for the city name
RELOCATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # English - past tense
    (re.compile(r"(?:i\s+)?(?:just\s+)?moved?\s+to\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "moved_to"),
    (
        re.compile(r"(?:i(?:'ve)?\s+)?relocated?\s+to\s+(\w+(?:\s+\w+)?)", re.IGNORECASE),
        "relocated_to",
    ),
    (
        re.compile(r"(?:i(?:'m)?\s+)?now\s+(?:in|living\s+in)\s+(\w+(?:\s+\w+)?)", re.IGNORECASE),
        "now_in",
    ),
    # English - future tense
    (re.compile(r"(?:i(?:'m)?\s+)?moving\s+to\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "moving_to"),
    # Russian - past tense
    (re.compile(r"переехал[аи]?\s+(?:в\s+)?(\w+(?:\s+\w+)?)", re.IGNORECASE), "relocated_ru"),
    (re.compile(r"перееха[лв]\s+в\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "relocated_ru_2"),
    (re.compile(r"теперь\s+(?:в|живу\s+в)\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "now_in_ru"),
    # Russian - future tense
    (re.compile(r"перееду\s+(?:в\s+)?(\w+(?:\s+\w+)?)", re.IGNORECASE), "moving_ru"),
    (re.compile(r"переезжаю\s+(?:в\s+)?(\w+(?:\s+\w+)?)", re.IGNORECASE), "moving_ru_2"),
    # Russian - temporary relocation (next week I'm in X)
    (
        re.compile(
            r"(?:на\s+)?(?:следующ|этой|будущ)\w*\s+недел\w*\s+(?:я\s+)?(?:буду\s+)?в\s+(\w+)",
            re.IGNORECASE,
        ),
        "next_week_in_ru",
    ),
    (re.compile(r"(?:я\s+)?буду\s+в\s+(\w+)", re.IGNORECASE), "will_be_in_ru"),
    # Russian - travel/trip patterns
    (re.compile(r"(?:я\s+)?еду\s+в\s+(\w+)", re.IGNORECASE), "going_to_ru"),
    (re.compile(r"(?:я\s+)?лечу\s+в\s+(\w+)", re.IGNORECASE), "flying_to_ru"),
    (re.compile(r"(?:я\s+)?уезжаю\s+в\s+(\w+)", re.IGNORECASE), "leaving_for_ru"),
    (re.compile(r"(?:я\s+)?улетаю\s+в\s+(\w+)", re.IGNORECASE), "flying_off_ru"),
    (
        re.compile(r"(?:я\s+)?(?:сейчас\s+)?в\s+командировк\w*\s+в\s+(\w+)", re.IGNORECASE),
        "business_trip_ru",
    ),
    (re.compile(r"работаю\s+(?:из|в)\s+(\w+)", re.IGNORECASE), "working_from_ru"),
    # English - temporary relocation
    (
        re.compile(
            r"(?:next|this)\s+week\s+(?:i(?:'m|'ll)?\s+)?(?:be\s+)?in\s+(\w+(?:\s+\w+)?)",
            re.IGNORECASE,
        ),
        "next_week_in_en",
    ),
    (re.compile(r"i(?:'ll|'m)\s+be\s+in\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "will_be_in_en"),
    # English - travel/trip patterns
    (re.compile(r"(?:i(?:'m)?\s+)?going\s+to\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "going_to_en"),
    (re.compile(r"(?:i(?:'m)?\s+)?flying\s+to\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "flying_to_en"),
    (
        re.compile(r"(?:i(?:'m)?\s+)?traveling\s+to\s+(\w+(?:\s+\w+)?)", re.IGNORECASE),
        "traveling_to_en",
    ),
    (re.compile(r"(?:i(?:'m)?\s+)?visiting\s+(\w+(?:\s+\w+)?)", re.IGNORECASE), "visiting_en"),
    (
        re.compile(r"(?:i(?:'m)?\s+)?staying\s+in\s+(\w+(?:\s+\w+)?)", re.IGNORECASE),
        "staying_in_en",
    ),
    (
        re.compile(r"(?:i(?:'m)?\s+)?working\s+from\s+(\w+(?:\s+\w+)?)", re.IGNORECASE),
        "working_from_en",
    ),
]


class RelocationDetector:
    """Detects relocation intent in messages.

    When user says "moved to London" or "переехал в Москву",
    this detector fires and signals that timezone should be re-verified.

    Detection strategy:
    1. Regex patterns for explicit phrases (high confidence 0.9)
    2. City name detection as fallback (medium confidence 0.7)

    Implements TriggerDetector protocol.
    """

    async def detect(self, event: NormalizedEvent) -> list[DetectedTrigger]:
        """Detect relocation phrases in a message.

        Args:
            event: The normalized event to analyze.

        Returns:
            List with single trigger if relocation detected, empty otherwise.
        """
        text = event.text
        settings = get_settings()

        # Strategy 1: Regex patterns for explicit relocation phrases (high confidence)
        for pattern, pattern_name in RELOCATION_PATTERNS:
            match = pattern.search(text)
            if match:
                city = _clean_city(match.group(1).strip())
                return [
                    DetectedTrigger(
                        trigger_type="relocation",
                        confidence=settings.config.triggers.relocation_confidence,
                        original_text=match.group(0),
                        data={
                            "city": city,
                            "pattern": pattern_name,
                            "detection_method": "regex",
                        },
                    )
                ]

        # Strategy 2: City name detection (any language) - medium confidence
        # Only trigger if message is short (likely about location change)
        if len(text) < 100:  # Short messages more likely to be about relocation
            detected_cities = find_cities_in_text(text)
            if detected_cities:
                # Take the first (most relevant) city
                city = detected_cities[0]
                return [
                    DetectedTrigger(
                        # geo_ambiguous: City detected but intent unclear
                        # Orchestrator will use LLM to classify intent
                        trigger_type="geo_ambiguous",
                        confidence=settings.config.triggers.city_detection_confidence,
                        original_text=city.original,
                        data={
                            "city": city.normalized,
                            "timezone": city.timezone,
                            "pattern": "city_name_detection",
                            "detection_method": "geonames",
                        },
                    )
                ]

        return []
