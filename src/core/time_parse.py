"""Time parsing utilities.

Simple rules-based time parsing for common patterns.
LLM is only used as fallback when these rules fail.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from src.core.models import ParsedTime
from src.settings import get_settings


@lru_cache(maxsize=1)
def _get_confidence_config() -> dict[str, float]:
    """Get time parsing confidence values from config."""
    settings = get_settings()
    conf = settings.config.time_parsing.confidence
    return {
        "hhmm_ampm": conf.hhmm_ampm,
        "european_hhmm": conf.european_hhmm,
        "military": conf.military,
        "plain_hhmm": conf.plain_hhmm,
        "h_ampm": conf.h_ampm,
        "range": conf.range,
        "at_h": conf.at_h,
    }


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
    # --- Russian patterns ---
    # "в 5 утра", "в 7 вечера", "в 3 дня", "в 2 ночи" - hour with time of day
    "ru_time_of_day": re.compile(r"\bв\s+(\d{1,2})\s*(утра|вечера|дня|ночи)\b", re.IGNORECASE),
    # "в 10-30", "в 14-45" - Russian format with dash
    "ru_v_hh_mm": re.compile(r"\bв\s+(\d{1,2})-(\d{2})\b"),
    # "в 10", "в 15" - Russian "at X" (hour only)
    "ru_v_h": re.compile(r"\bв\s+(\d{1,2})\b"),
    # "завтра" - tomorrow in Russian
    "ru_tomorrow": re.compile(r"\bзавтра\b", re.IGNORECASE),
    # "сегодня" - today in Russian
    "ru_today": re.compile(r"\bсегодня\b", re.IGNORECASE),
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
    conf = _get_confidence_config()

    # Check for tomorrow prefix (English and Russian)
    is_tomorrow = bool(PATTERNS["tomorrow"].search(text) or PATTERNS["ru_tomorrow"].search(text))

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
                    confidence=conf["hhmm_ampm"],
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
                    confidence=conf["european_hhmm"],
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
                confidence=conf["military"],
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
                    confidence=conf["plain_hhmm"],
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
                    confidence=conf["h_ampm"],
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
                        confidence=conf["range"],
                    )
                )
        matched_positions.add(match.start())

    # 7. Parse Russian "в X утра/вечера/дня/ночи" format (time of day)
    # Examples: в 5 утра, в 7 вечера, в 3 дня, в 2 ночи
    for match in PATTERNS["ru_time_of_day"].finditer(text):
        if match.start() in matched_positions:
            continue

        hour = int(match.group(1))
        time_of_day = match.group(2).lower()

        # Convert to 24-hour based on time of day
        if time_of_day == "утра":
            # Morning: keep as-is (1-11), 12 утра = 0
            if hour == 12:
                hour = 0
        elif time_of_day == "ночи":
            # Night: 1-4 ночи stays as-is, 12 ночи = 0
            if hour == 12:
                hour = 0
        elif time_of_day == "дня":
            # Afternoon: 12 дня = 12, 1-5 дня = +12
            if hour != 12 and hour < 6:
                hour += 12
        elif time_of_day == "вечера" and hour != 12:
            # Evening: 5-11 вечера = +12 (if < 12)
            hour += 12

        if 0 <= hour <= 23:
            results.append(
                ParsedTime(
                    original_text=match.group(0),
                    hour=hour,
                    minute=0,
                    timezone_hint=tz_hint,
                    is_tomorrow=is_tomorrow,
                    confidence=conf["h_ampm"],  # Same confidence as H am/pm
                )
            )
            matched_positions.add(match.start())

    # 8. Parse Russian "в X-XX" format (hour-minute with dash)
    # Examples: в 10-30, в 14-45
    for match in PATTERNS["ru_v_hh_mm"].finditer(text):
        if match.start() in matched_positions:
            continue

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
                    confidence=conf["plain_hhmm"],
                )
            )
            matched_positions.add(match.start())

    # 9. Parse Russian "в X" format (hour only)
    # Examples: в 10, в 15
    # Lower priority - only if no time_of_day match at same position
    if not results:  # Only if no other times found
        for match in PATTERNS["ru_v_h"].finditer(text):
            if match.start() in matched_positions:
                continue

            hour = int(match.group(1))
            if 0 <= hour <= 23:
                results.append(
                    ParsedTime(
                        original_text=match.group(0),
                        hour=hour,
                        minute=0,
                        timezone_hint=tz_hint,
                        is_tomorrow=is_tomorrow,
                        confidence=conf["at_h"],  # Same confidence as "at H"
                    )
                )
                matched_positions.add(match.start())

    # 10. Parse English "at H" format (lower confidence since ambiguous)
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
                        confidence=conf["at_h"],
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

            from src.settings import get_settings

            timeout = get_settings().config.llm.sync_bridge_timeout
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, extract_times_with_llm(text, tz_hint))
                return future.result(timeout=timeout)
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
