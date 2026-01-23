"""Tools for the LangChain timezone agent.

These tools are used by the agent to resolve user timezone from various inputs.
"""

from __future__ import annotations

import logging

import httpx
from langchain_core.tools import tool

from src.core.time_parse import TIMEZONE_ABBREVIATIONS
from src.settings import get_settings

logger = logging.getLogger(__name__)


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
async def geocode_city(city_name: str) -> str:
    """Look up any city worldwide using geocoding to find its timezone.

    Use this when the city is not in the configured list.
    This makes an API call to find the timezone for any city in the world.

    Args:
        city_name: Name of the city to look up

    Returns:
        FOUND: city → IANA timezone if found
        NOT_FOUND: message if city cannot be found
    """
    settings = get_settings()

    # Use TimeZoneDB free API (or similar)
    # For MVP, we'll use a simple approach with geonames or similar
    # TODO: Add TIMEZONEDB_API_KEY to settings
    api_key = getattr(settings, "timezonedb_api_key", None)

    if not api_key:
        # Fallback: try to match common city names
        return await _fallback_city_lookup(city_name)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "http://api.timezonedb.com/v2.1/get-time-zone",
                params={
                    "key": api_key,
                    "format": "json",
                    "by": "city",
                    "city": city_name,
                },
            )
            data = resp.json()

            if data.get("status") == "OK":
                zone_name = data.get("zoneName", "")
                return f"FOUND: {city_name} → {zone_name}"

            return f"NOT_FOUND: Could not find timezone for '{city_name}'"

    except Exception as e:
        logger.warning(f"Geocoding API error for '{city_name}': {e}")
        return await _fallback_city_lookup(city_name)


async def _fallback_city_lookup(city_name: str) -> str:
    """Fallback city lookup using a built-in mapping of major cities."""
    # Extended city list for common cities worldwide
    EXTENDED_CITIES: dict[str, str] = {
        # Americas
        "los angeles": "America/Los_Angeles",
        "san francisco": "America/Los_Angeles",
        "seattle": "America/Los_Angeles",
        "portland": "America/Los_Angeles",
        "las vegas": "America/Los_Angeles",
        "san diego": "America/Los_Angeles",
        "denver": "America/Denver",
        "phoenix": "America/Phoenix",
        "chicago": "America/Chicago",
        "houston": "America/Chicago",
        "dallas": "America/Chicago",
        "austin": "America/Chicago",
        "new york": "America/New_York",
        "boston": "America/New_York",
        "miami": "America/New_York",
        "atlanta": "America/New_York",
        "washington": "America/New_York",
        "toronto": "America/Toronto",
        "vancouver": "America/Vancouver",
        "mexico city": "America/Mexico_City",
        "sao paulo": "America/Sao_Paulo",
        "buenos aires": "America/Argentina/Buenos_Aires",
        # Europe
        "london": "Europe/London",
        "dublin": "Europe/Dublin",
        "lisbon": "Europe/Lisbon",
        "funchal": "Atlantic/Madeira",
        "paris": "Europe/Paris",
        "madrid": "Europe/Madrid",
        "barcelona": "Europe/Madrid",
        "berlin": "Europe/Berlin",
        "munich": "Europe/Berlin",
        "frankfurt": "Europe/Berlin",
        "amsterdam": "Europe/Amsterdam",
        "brussels": "Europe/Brussels",
        "zurich": "Europe/Zurich",
        "vienna": "Europe/Vienna",
        "rome": "Europe/Rome",
        "milan": "Europe/Rome",
        "warsaw": "Europe/Warsaw",
        "prague": "Europe/Prague",
        "budapest": "Europe/Budapest",
        "athens": "Europe/Athens",
        "istanbul": "Europe/Istanbul",
        "moscow": "Europe/Moscow",
        "st petersburg": "Europe/Moscow",
        "kiev": "Europe/Kiev",
        "kyiv": "Europe/Kiev",
        "helsinki": "Europe/Helsinki",
        "stockholm": "Europe/Stockholm",
        "oslo": "Europe/Oslo",
        "copenhagen": "Europe/Copenhagen",
        # Asia
        "dubai": "Asia/Dubai",
        "tel aviv": "Asia/Tel_Aviv",
        "jerusalem": "Asia/Jerusalem",
        "mumbai": "Asia/Kolkata",
        "delhi": "Asia/Kolkata",
        "bangalore": "Asia/Kolkata",
        "kolkata": "Asia/Kolkata",
        "singapore": "Asia/Singapore",
        "bangkok": "Asia/Bangkok",
        "jakarta": "Asia/Jakarta",
        "kuala lumpur": "Asia/Kuala_Lumpur",
        "hong kong": "Asia/Hong_Kong",
        "shanghai": "Asia/Shanghai",
        "beijing": "Asia/Shanghai",
        "shenzhen": "Asia/Shanghai",
        "taipei": "Asia/Taipei",
        "seoul": "Asia/Seoul",
        "tokyo": "Asia/Tokyo",
        "osaka": "Asia/Tokyo",
        # Oceania
        "sydney": "Australia/Sydney",
        "melbourne": "Australia/Melbourne",
        "brisbane": "Australia/Brisbane",
        "perth": "Australia/Perth",
        "auckland": "Pacific/Auckland",
        "wellington": "Pacific/Auckland",
        # Russia
        "демидов": "Europe/Moscow",  # Small city in Russia
        "novosibirsk": "Asia/Novosibirsk",
        "yekaterinburg": "Asia/Yekaterinburg",
        "vladivostok": "Asia/Vladivostok",
    }

    city_lower = city_name.lower().strip()

    if city_lower in EXTENDED_CITIES:
        tz = EXTENDED_CITIES[city_lower]
        return f"FOUND: {city_name} → {tz}"

    return f"NOT_FOUND: Could not find timezone for '{city_name}'. Please try a major city name or timezone code (e.g., PT, CET)."


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


# List of all tools for the agent
AGENT_TOOLS = [
    lookup_configured_city,
    lookup_tz_abbreviation,
    geocode_city,
    save_timezone,
]
