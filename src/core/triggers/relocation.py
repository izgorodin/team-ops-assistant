"""Relocation trigger detector.

Detects phrases indicating user has moved to a different location.
Implements the TriggerDetector protocol.
"""

from __future__ import annotations

import re

from src.core.models import DetectedTrigger, NormalizedEvent

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
]


class RelocationDetector:
    """Detects relocation intent in messages.

    When user says "moved to London" or "переехал в Москву",
    this detector fires and signals that timezone should be re-verified.

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

        for pattern, pattern_name in RELOCATION_PATTERNS:
            match = pattern.search(text)
            if match:
                city = _clean_city(match.group(1).strip())
                return [
                    DetectedTrigger(
                        trigger_type="relocation",
                        confidence=0.9,  # High confidence for explicit statements
                        original_text=match.group(0),
                        data={
                            "city": city,
                            "pattern": pattern_name,
                        },
                    )
                ]

        return []
