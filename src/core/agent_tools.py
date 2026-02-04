"""Tools for the LangChain timezone agent.

These tools are used by the agent to resolve user timezone from various inputs.
Delegates to geo.py for geocoding.
"""

from __future__ import annotations

from langchain_core.tools import tool

from src.core.geo import geocode_city_str
from src.core.time_parse import TIMEZONE_ABBREVIATIONS
from src.settings import get_settings


@tool
def lookup_configured_city(city_name: str) -> str:
    """Look up a city in the team's configured cities list.

    Use this first to check if the city is in the team's configured locations.
    These are the preferred cities because they represent team member locations.

    Args:
        city_name: Name of the city to look up (case-insensitive)

    Returns:
        FOUND: City Name → IANA timezone if found
        NOT_FOUND: message with available cities if not found
    """
    settings = get_settings()
    cities = settings.config.timezone.team_cities
    city_lower = city_name.lower().strip()

    for city in cities:
        if city.name.lower() == city_lower:
            return f"FOUND: {city.name} → {city.tz}"

    available = [c.name for c in cities]
    return f"NOT_FOUND: '{city_name}' not in team cities. Available: {available}"


@tool
def lookup_tz_abbreviation(abbrev: str) -> str:
    """Look up a timezone abbreviation like PT, PST, EST, CET, etc.

    Use this when the user provides a timezone code instead of a city name.

    Args:
        abbrev: Timezone abbreviation (case-insensitive)

    Returns:
        FOUND: abbreviation → IANA timezone if recognized
        NOT_FOUND: message if unknown abbreviation
    """
    abbrev_lower = abbrev.lower().strip()
    tz = TIMEZONE_ABBREVIATIONS.get(abbrev_lower)

    if tz:
        return f"FOUND: {abbrev.upper()} → {tz}"

    return f"NOT_FOUND: Unknown timezone abbreviation '{abbrev}'"


@tool
def geocode_city(city_name: str) -> str:
    """Look up any city worldwide to find its timezone.

    Uses geonamescache with 190k+ cities. Supports any language input -
    will automatically normalize non-English names (including Russian
    dative case like "Москве" → "Moscow").

    Args:
        city_name: Name of the city to look up (any language)

    Returns:
        FOUND: city → IANA timezone if found
        NOT_FOUND: message if city cannot be found
    """
    result = geocode_city_str(city_name, use_llm=True)
    if result.startswith("NOT_FOUND:"):
        # Provide helpful message for agent
        return (
            f"NOT_FOUND: '{city_name}' not found. "
            "Try a more specific city name (e.g., Moscow, London, Tokyo)."
        )
    return result


@tool
def save_timezone(tz_iana: str) -> str:
    """Save the resolved IANA timezone for the user.

    Call this when you have determined the correct timezone.
    The IANA timezone should be in format like 'America/Los_Angeles' or 'Europe/London'.

    Args:
        tz_iana: IANA timezone identifier (e.g., 'America/Los_Angeles')

    Returns:
        SAVE:timezone confirmation message
    """
    # Validate it looks like an IANA timezone
    if "/" not in tz_iana and tz_iana != "UTC":
        return f"ERROR: '{tz_iana}' doesn't look like a valid IANA timezone. Expected format: Region/City"

    return f"SAVE:{tz_iana}"


@tool
def convert_time(time_str: str, source_tz: str, target_tz: str) -> str:
    """Convert time from one timezone to another.

    Use this when user wants to know what time it is in a city,
    or convert a meeting time between timezones.

    Args:
        time_str: Time string like "15:00", "3pm", "завтра в 12"
        source_tz: Source IANA timezone (e.g., 'Europe/Moscow')
        target_tz: Target IANA timezone (e.g., 'America/New_York')

    Returns:
        CONVERT: source_time source_tz → target_time target_tz
    """
    from datetime import datetime

    import pytz

    try:
        source = pytz.timezone(source_tz)
        target = pytz.timezone(target_tz)

        # Parse simple time formats
        now = datetime.now(source)
        hour, minute = 0, 0

        # Try to parse time
        time_lower = time_str.lower().strip()
        if ":" in time_str:
            parts = time_str.replace("am", "").replace("pm", "").strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            if "pm" in time_lower and hour < 12:
                hour += 12
        elif time_str.isdigit():
            hour = int(time_str)
        else:
            # Try to extract number
            import re

            match = re.search(r"(\d{1,2})", time_str)
            if match:
                hour = int(match.group(1))

        # Create source time
        source_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        target_dt = source_dt.astimezone(target)

        return f"CONVERT: {source_dt.strftime('%H:%M')} {source_tz} → {target_dt.strftime('%H:%M')} {target_tz}"

    except Exception as e:
        return f"ERROR: Could not convert time - {e}"


@tool
def no_action() -> str:
    """Indicate that no response is needed (false positive detection).

    Use this when the city was mentioned but user doesn't want
    time conversion or to report relocation.

    Returns:
        NO_ACTION confirmation
    """
    return "NO_ACTION: City mention was not actionable"


# List of all tools for the agent
AGENT_TOOLS = [
    lookup_configured_city,
    lookup_tz_abbreviation,
    geocode_city,
    save_timezone,
]

# Extended tools for geo intent agent (includes time conversion)
GEO_INTENT_TOOLS = [
    geocode_city,
    save_timezone,
    convert_time,
    no_action,
]


# Backwards compatibility - these are now in geo.py
def geocode_city_full(city_name: str) -> str:
    """Deprecated: Use geo.geocode_city_str() instead."""
    return geocode_city_str(city_name, use_llm=True)
