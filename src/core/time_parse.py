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
    # 7:30pm, 3:30 pm, 10:00am - HH:MM with AM/PM (must check before plain HH:MM)
    "hh_mm_ampm": re.compile(r"\b(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)\b", re.IGNORECASE),
    # 14h30, 9h, 14h - European format (French, Portuguese, etc)
    "hh_h_mm": re.compile(r"\b(\d{1,2})h(\d{2})?\b", re.IGNORECASE),
    # 1500Z, 0745, 2200 - military/24h format (4 digits, optionally Z suffix)
    "military": re.compile(r"\b([01]\d|2[0-3])([0-5]\d)(?:Z|z)?\b"),
    # 14:30, 2:30, 02:30 - plain 24h or ambiguous
    "hh_mm": re.compile(r"\b(\d{1,2}):(\d{2})\b"),
    # 2pm, 2 pm, 2PM, 1p.m. - hour only with AM/PM
    "h_ampm": re.compile(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b", re.IGNORECASE),
    # 5-7pm, 7-10am - range with trailing am/pm
    "range_ampm": re.compile(r"\b(\d{1,2})-(\d{1,2})\s*(am|pm)\b", re.IGNORECASE),
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

    First checks if text contains time reference using ML classifier.
    Then uses regex patterns to extract actual time values.
    Returns empty list if no times found or if classifier says no time.

    Args:
        text: Message text to parse.

    Returns:
        List of parsed time references.
    """
    # Early exit if ML classifier says no time reference
    if not contains_time_reference(text):
        return []

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

    # Track positions already matched to avoid duplicates
    matched_positions: set[int] = set()

    # 1. Parse HH:MM + am/pm format first (highest priority)
    # Examples: 7:30pm, 3:30 pm, 10:00am, 2:30 p.m.
    for match in PATTERNS["hh_mm_ampm"].finditer(text):
        hour = int(match.group(1))
        minute = int(match.group(2))
        ampm = match.group(3).lower().replace(".", "")  # normalize p.m. -> pm

        if 1 <= hour <= 12 and 0 <= minute <= 59:
            # Convert to 24-hour
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0

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
            matched_positions.add(match.start())

    # 2. Parse European HHhMM format (14h30, 9h)
    for match in PATTERNS["hh_h_mm"].finditer(text):
        if match.start() in matched_positions:
            continue

        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            results.append(
                ParsedTime(
                    original_text=match.group(0),
                    hour=hour,
                    minute=minute,
                    timezone_hint=tz_hint,
                    is_tomorrow=is_tomorrow,
                    confidence=0.9,
                )
            )
            matched_positions.add(match.start())

    # 3. Parse military time (1500Z, 0745, 2200)
    for match in PATTERNS["military"].finditer(text):
        if match.start() in matched_positions:
            continue

        hour = int(match.group(1))
        minute = int(match.group(2))

        results.append(
            ParsedTime(
                original_text=match.group(0),
                hour=hour,
                minute=minute,
                timezone_hint=tz_hint,
                is_tomorrow=is_tomorrow,
                confidence=0.9,
            )
        )
        matched_positions.add(match.start())

    # 4. Parse plain HH:MM format (skip positions already matched)
    for match in PATTERNS["hh_mm"].finditer(text):
        if match.start() in matched_positions:
            continue  # Already matched with am/pm

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
            matched_positions.add(match.start())

    # 5. Parse H am/pm format (hour only, skip overlapping)
    for match in PATTERNS["h_ampm"].finditer(text):
        if match.start() in matched_positions:
            continue  # Already matched as HH:MM+ampm

        hour = int(match.group(1))
        ampm = match.group(2).lower().replace(".", "")

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
            matched_positions.add(match.start())

    # 6. Parse ranges like 5-7pm, 7-10am
    for match in PATTERNS["range_ampm"].finditer(text):
        if match.start() in matched_positions:
            continue

        start_h = int(match.group(1))
        end_h = int(match.group(2))
        ampm = match.group(3).lower()

        # Convert both hours to 24h
        for h in [start_h, end_h]:
            hour = h
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
                        confidence=0.85,
                    )
                )
        matched_positions.add(match.start())

    # 7. Parse "at H" format (lower confidence since ambiguous)
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

    # LLM extraction fallback: classifier detected time but regex found nothing
    if not results:
        results = _try_llm_extraction(text, tz_hint)

    return results


def _try_llm_extraction(text: str, tz_hint: str | None) -> list[ParsedTime]:
    """Try LLM extraction when regex fails.

    Args:
        text: Message text to parse.
        tz_hint: Optional timezone hint.

    Returns:
        List of parsed times from LLM, empty if fails.
    """
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    try:
        from src.core.llm_fallback import extract_times_with_llm

        # Run async function in sync context
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already in async context - need thread pool
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extract_times_with_llm(text, tz_hint))
                return future.result(timeout=15.0)
        else:
            # No event loop - safe to use asyncio.run
            return asyncio.run(extract_times_with_llm(text, tz_hint))

    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")
        return []


def contains_time_reference(text: str) -> bool:
    """Check if text likely contains a time reference.

    Uses ML classifier trained on corpus data for accurate detection.
    Falls back to simple patterns if classifier unavailable.

    Args:
        text: Message text to check.

    Returns:
        True if text contains a time reference.
    """
    try:
        from src.core.time_classifier import contains_time_ml

        return contains_time_ml(text)
    except Exception:
        # Fallback to simple regex if classifier unavailable
        quick_patterns = [
            r"\d{1,2}:\d{2}",  # HH:MM
            r"\d{1,2}\s*(am|pm)",  # H am/pm
            r"\bat\s+\d{1,2}\b",  # at H
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
