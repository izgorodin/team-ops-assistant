"""Time parsing utilities.

Simple rules-based time parsing for common patterns.
LLM is only used as fallback when these rules fail.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from src.core.models import ParsedTime

# Common timezone abbreviations mapping to IANA
TIMEZONE_ABBREVIATIONS: dict[str, str] = {
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
    "mst": "America/Denver",
    "mdt": "America/Denver",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",
    "est": "America/New_York",
    "edt": "America/New_York",
    "gmt": "Europe/London",
    "bst": "Europe/London",
    "cet": "Europe/Berlin",
    "cest": "Europe/Berlin",
    "jst": "Asia/Tokyo",
    "aest": "Australia/Sydney",
    "aedt": "Australia/Sydney",
    "utc": "UTC",
}

# City names mapping to IANA
CITY_TIMEZONES: dict[str, str] = {
    "los angeles": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "sf": "America/Los_Angeles",
    "seattle": "America/Los_Angeles",
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "boston": "America/New_York",
    "chicago": "America/Chicago",
    "denver": "America/Denver",
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "amsterdam": "Europe/Amsterdam",
    "tokyo": "Asia/Tokyo",
    "sydney": "Australia/Sydney",
    "melbourne": "Australia/Sydney",
}

# Regex patterns for time parsing
PATTERNS = {
    # 14:30, 2:30, 02:30
    "hh_mm": re.compile(r"\b(\d{1,2}):(\d{2})\b"),
    # 2pm, 2 pm, 2PM, 14pm (will validate hour)
    "h_ampm": re.compile(r"\b(\d{1,2})\s*(am|pm|AM|PM)\b"),
    # at 10, at 2
    "at_h": re.compile(r"\bat\s+(\d{1,2})\b"),
    # tomorrow prefix
    "tomorrow": re.compile(r"\btomorrow\b", re.IGNORECASE),
    # timezone/city hints
    "tz_hint": re.compile(
        r"\b(" + "|".join(re.escape(k) for k in TIMEZONE_ABBREVIATIONS) + r")\b",
        re.IGNORECASE,
    ),
    "city_hint": re.compile(
        r"\b(" + "|".join(re.escape(k) for k in CITY_TIMEZONES) + r")\b",
        re.IGNORECASE,
    ),
}


def parse_times(text: str) -> list[ParsedTime]:
    """Parse time references from message text.

    Uses simple regex patterns to extract times. Returns empty list if no times found.
    Caller should use LLM fallback if this returns empty but text seems time-related.

    Args:
        text: Message text to parse.

    Returns:
        List of parsed time references.
    """
    results: list[ParsedTime] = []
    text_lower = text.lower()

    # Check for tomorrow prefix
    is_tomorrow = bool(PATTERNS["tomorrow"].search(text))

    # Extract timezone/city hints
    tz_hint: str | None = None

    tz_match = PATTERNS["tz_hint"].search(text)
    if tz_match:
        abbrev = tz_match.group(1).lower()
        tz_hint = TIMEZONE_ABBREVIATIONS.get(abbrev)

    if not tz_hint:
        city_match = PATTERNS["city_hint"].search(text_lower)
        if city_match:
            city = city_match.group(1).lower()
            tz_hint = CITY_TIMEZONES.get(city)

    # Parse HH:MM format
    for match in PATTERNS["hh_mm"].finditer(text):
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            results.append(
                ParsedTime(
                    original_text=match.group(0),
                    hour=hour,
                    minute=minute,
                    timezone_hint=tz_hint,
                    is_tomorrow=is_tomorrow,
                    confidence=0.95,
                )
            )

    # Parse H am/pm format
    for match in PATTERNS["h_ampm"].finditer(text):
        hour = int(match.group(1))
        ampm = match.group(2).lower()

        # Validate and convert to 24-hour
        if 1 <= hour <= 12:
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0

            results.append(
                ParsedTime(
                    original_text=match.group(0),
                    hour=hour,
                    minute=0,
                    timezone_hint=tz_hint,
                    is_tomorrow=is_tomorrow,
                    confidence=0.9,
                )
            )

    # Parse "at H" format (lower confidence since ambiguous)
    if not results:  # Only if no other times found
        for match in PATTERNS["at_h"].finditer(text):
            hour = int(match.group(1))
            if 0 <= hour <= 23:
                results.append(
                    ParsedTime(
                        original_text=match.group(0),
                        hour=hour,
                        minute=0,
                        timezone_hint=tz_hint,
                        is_tomorrow=is_tomorrow,
                        confidence=0.7,
                    )
                )

    return results


def contains_time_reference(text: str) -> bool:
    """Check if text likely contains a time reference.

    Quick check to decide whether to invoke parsing/LLM.

    Args:
        text: Message text to check.

    Returns:
        True if text might contain a time reference.
    """
    # Quick patterns that suggest time content
    quick_patterns = [
        r"\d{1,2}:\d{2}",  # HH:MM
        r"\d{1,2}\s*(am|pm)",  # H am/pm
        r"\bat\s+\d{1,2}\b",  # at H
        r"\bmeeting\b",  # meeting context
        r"\bcall\b",  # call context
        r"\btomorrow\b",  # tomorrow
        r"\btoday\b",  # today
    ]

    text_lower = text.lower()
    return any(re.search(p, text_lower, re.IGNORECASE) for p in quick_patterns)


def get_highest_confidence_time(times: Sequence[ParsedTime]) -> ParsedTime | None:
    """Get the time with highest parsing confidence.

    Args:
        times: List of parsed times.

    Returns:
        The time with highest confidence, or None if list is empty.
    """
    if not times:
        return None
    return max(times, key=lambda t: t.confidence)
