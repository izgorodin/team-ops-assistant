"""Timezone conversion utilities.

Converts times between timezones for display.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, NamedTuple
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from src.core.models import ParsedTime


class ConvertedTime(NamedTuple):
    """A time converted to a specific timezone."""

    timezone: str
    hour: int
    minute: int
    formatted: str  # e.g., "14:30 PT (UTC-8, team)"
    is_next_day: bool  # True if conversion crossed into next day
    is_prev_day: bool  # True if conversion crossed into previous day
    source: str = ""  # "team", "chat", or "" for unknown


def get_utc_offset(timezone: str) -> str:
    """Get UTC offset string for a timezone.

    Args:
        timezone: IANA timezone identifier.

    Returns:
        Offset string like "UTC+3", "UTC-8", "UTC+5:30".
    """
    now = datetime.now(ZoneInfo(timezone))
    offset = now.utcoffset()
    if offset is None:
        return "UTC"

    total_seconds = int(offset.total_seconds())
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes = remainder // 60
    sign = "+" if total_seconds >= 0 else "-"

    if minutes:
        return f"UTC{sign}{hours}:{minutes:02d}"
    return f"UTC{sign}{hours}"


def convert_to_timezone(
    parsed_time: ParsedTime,
    source_tz: str,
    target_tz: str,
    reference_date: datetime | None = None,
    source: str = "",
) -> ConvertedTime:
    """Convert a parsed time from source timezone to target timezone.

    Args:
        parsed_time: The parsed time to convert.
        source_tz: Source IANA timezone.
        target_tz: Target IANA timezone.
        reference_date: Reference date for the conversion (default: today).
        source: Source of this timezone ("team", "chat", or "").

    Returns:
        ConvertedTime with the converted time details.
    """
    if reference_date is None:
        reference_date = datetime.now(ZoneInfo(source_tz))

    # Build source datetime
    source_dt = datetime(
        year=reference_date.year,
        month=reference_date.month,
        day=reference_date.day,
        hour=parsed_time.hour,
        minute=parsed_time.minute,
        tzinfo=ZoneInfo(source_tz),
    )

    # Handle tomorrow flag
    if parsed_time.is_tomorrow:
        source_dt = source_dt + timedelta(days=1)

    # Convert to target timezone
    target_dt = source_dt.astimezone(ZoneInfo(target_tz))

    # Determine if day changed
    source_date = source_dt.date()
    target_date = target_dt.date()
    is_next_day = target_date > source_date
    is_prev_day = target_date < source_date

    # Format the time
    formatted = format_time_with_tz(
        target_dt.hour, target_dt.minute, target_tz, is_next_day, source
    )

    return ConvertedTime(
        timezone=target_tz,
        hour=target_dt.hour,
        minute=target_dt.minute,
        formatted=formatted,
        is_next_day=is_next_day,
        is_prev_day=is_prev_day,
        source=source,
    )


def convert_to_timezones(
    parsed_time: ParsedTime,
    source_tz: str,
    target_tzs: list[str],
    reference_date: datetime | None = None,
    team_tzs: set[str] | None = None,
) -> list[ConvertedTime]:
    """Convert a parsed time to multiple target timezones.

    Args:
        parsed_time: The parsed time to convert.
        source_tz: Source IANA timezone.
        target_tzs: List of target IANA timezones.
        reference_date: Reference date for the conversion.
        team_tzs: Set of team timezones (from config) to mark as "team".

    Returns:
        List of ConvertedTime for each target timezone.
    """
    results: list[ConvertedTime] = []
    team_set = team_tzs or set()

    for target_tz in target_tzs:
        if target_tz != source_tz:  # Skip if same as source
            source = "team" if target_tz in team_set else "chat"
            results.append(
                convert_to_timezone(parsed_time, source_tz, target_tz, reference_date, source)
            )

    return results


def format_time_with_tz(
    hour: int,
    minute: int,
    timezone: str,
    is_next_day: bool = False,
    source: str = "",
) -> str:
    """Format a time with timezone abbreviation, UTC offset, and source.

    Args:
        hour: Hour (0-23).
        minute: Minute (0-59).
        timezone: IANA timezone.
        is_next_day: Whether this is the next day.
        source: Source of this timezone ("team", "chat", or "").

    Returns:
        Formatted string like "14:30 CET (UTC+1, team)" or "09:00 PT (UTC-8, chat) +1 day".
    """
    time_str = f"{hour:02d}:{minute:02d}"
    tz_abbrev = get_timezone_abbreviation(timezone)
    utc_offset = get_utc_offset(timezone)

    # Build info parts: UTC offset + optional source
    info_parts = [utc_offset]
    if source:
        info_parts.append(source)
    info_str = ", ".join(info_parts)

    if is_next_day:
        return f"{time_str} {tz_abbrev} ({info_str}) +1 day"
    return f"{time_str} {tz_abbrev} ({info_str})"


def get_timezone_abbreviation(timezone: str) -> str:
    """Get a short abbreviation for a timezone.

    Args:
        timezone: IANA timezone identifier.

    Returns:
        Short abbreviation (e.g., "PST", "CET").
    """
    # Common mappings
    abbreviations: dict[str, str] = {
        "America/Los_Angeles": "PT",
        "America/New_York": "ET",
        "America/Chicago": "CT",
        "America/Denver": "MT",
        "Europe/London": "UK",
        "Europe/Berlin": "CET",
        "Europe/Paris": "CET",
        "Asia/Tokyo": "JST",
        "Australia/Sydney": "AEST",
        "UTC": "UTC",
    }

    if timezone in abbreviations:
        return abbreviations[timezone]

    # Extract city name as fallback
    if "/" in timezone:
        return timezone.split("/")[-1].replace("_", " ")

    return timezone


def format_conversion_response(
    original_text: str,
    source_tz: str,
    conversions: list[ConvertedTime],
    source_label: str = "",
) -> str:
    """Format a multi-timezone conversion response.

    Args:
        original_text: The original time text from the message.
        source_tz: Source timezone.
        conversions: List of converted times.
        source_label: Label for source timezone ("explicit", "user", or "").

    Returns:
        Formatted response string.
    """
    if not conversions:
        return ""

    source_abbrev = get_timezone_abbreviation(source_tz)
    source_offset = get_utc_offset(source_tz)

    # Build header with UTC offset and optional source label
    if source_label:
        header = f"🕐 {original_text} ({source_abbrev}, {source_offset}, {source_label}):"
    else:
        header = f"🕐 {original_text} ({source_abbrev}, {source_offset}):"

    lines = [header]

    for conv in conversions:
        lines.append(f"  → {conv.formatted}")

    return "\n".join(lines)


def format_time_conversion(
    hour: int,
    minute: int,
    source_tz: str,
    target_timezones: list[str],
    original_text: str = "",
    is_tomorrow: bool = False,
    team_tzs: set[str] | None = None,
    source_label: str = "",
) -> str:
    """Format a time conversion response from raw hour/minute.

    Convenience function that creates a ParsedTime internally
    and returns formatted conversion response.

    Args:
        hour: Hour (0-23).
        minute: Minute (0-59).
        source_tz: Source IANA timezone.
        target_timezones: List of target IANA timezones.
        original_text: Original time text from message.
        is_tomorrow: Whether the time refers to tomorrow.
        team_tzs: Set of team timezones (from config) to mark as "team".
        source_label: Label for source timezone ("explicit", "user", or "").

    Returns:
        Formatted response string.
    """
    from src.core.models import ParsedTime

    # Create ParsedTime for conversion
    parsed_time = ParsedTime(
        original_text=original_text or f"{hour:02d}:{minute:02d}",
        hour=hour,
        minute=minute,
        is_tomorrow=is_tomorrow,
    )

    # Convert to all target timezones
    conversions = convert_to_timezones(parsed_time, source_tz, target_timezones, team_tzs=team_tzs)

    # Format and return - always use normalized HH:MM format
    normalized_time = f"{hour:02d}:{minute:02d}"
    return format_conversion_response(normalized_time, source_tz, conversions, source_label)


def is_valid_iana_timezone(timezone: str) -> bool:
    """Check if a timezone string is a valid IANA timezone.

    Args:
        timezone: Timezone string to validate.

    Returns:
        True if valid IANA timezone.
    """
    try:
        ZoneInfo(timezone)
        return True
    except (KeyError, ValueError):
        return False


def get_current_time_in_timezone(timezone: str) -> datetime:
    """Get the current time in a specific timezone.

    Args:
        timezone: IANA timezone.

    Returns:
        Current datetime in that timezone.
    """
    return datetime.now(ZoneInfo(timezone))
