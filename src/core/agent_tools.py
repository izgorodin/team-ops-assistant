"""Tools for the LangChain timezone agent.

These tools are used by the agent to resolve user timezone from various inputs.
"""

from __future__ import annotations

import logging

from geonamescache import GeonamesCache
from langchain_core.tools import tool

from src.core.time_parse import TIMEZONE_ABBREVIATIONS
from src.settings import get_settings

logger = logging.getLogger(__name__)

# City abbreviations for common inputs (expand before lookup)
CITY_ABBREVIATIONS: dict[str, str] = {
    # US cities
    "ny": "new york",
    "nyc": "new york",
    "la": "los angeles",
    "sf": "san francisco",
    "dc": "washington",
    "chi": "chicago",
    "phx": "phoenix",
    "bos": "boston",
    "atl": "atlanta",
    "sea": "seattle",
    # Russia (Latin + Cyrillic)
    "msk": "moscow",
    "москва": "moscow",
    "мск": "moscow",
    "spb": "saint petersburg",
    "спб": "saint petersburg",
    "питер": "saint petersburg",
    "санкт-петербург": "saint petersburg",
    "петербург": "saint petersburg",
    "екб": "yekaterinburg",
    "екатеринбург": "yekaterinburg",
    "нск": "novosibirsk",
    "новосиб": "novosibirsk",
    "новосибирск": "novosibirsk",
    "казань": "kazan",
    "нижний новгород": "nizhny novgorod",
    "нижний": "nizhny novgorod",
    "самара": "samara",
    "омск": "omsk",
    "челябинск": "chelyabinsk",
    "ростов": "rostov-on-don",
    "ростов-на-дону": "rostov-on-don",
    "уфа": "ufa",
    "красноярск": "krasnoyarsk",
    "пермь": "perm",
    "воронеж": "voronezh",
    "волгоград": "volgograd",
    "краснодар": "krasnodar",
    "сочи": "sochi",
    "владивосток": "vladivostok",
    "хабаровск": "khabarovsk",
    "иркутск": "irkutsk",
    "тюмень": "tyumen",
    "тбилиси": "tbilisi",
    "киев": "kiev",
    "київ": "kiev",
    "минск": "minsk",
    "рига": "riga",
    "таллин": "tallinn",
    "вильнюс": "vilnius",
    "варшава": "warsaw",
    "прага": "prague",
    "берлин": "berlin",
    "мюнхен": "munich",
    "вена": "vienna",
    "будапешт": "budapest",
    "белград": "belgrade",
    "стамбул": "istanbul",
    "дубай": "dubai",
    "тель-авив": "tel aviv",
    "тель авив": "tel aviv",
    # Europe
    "ldn": "london",
    "lon": "london",
    "лондон": "london",
    "par": "paris",
    "париж": "paris",
    "ber": "berlin",
    "ams": "amsterdam",
    "амстердам": "amsterdam",
    "рим": "rome",
    "мадрид": "madrid",
    "барселона": "barcelona",
    "лиссабон": "lisbon",
    # Asia
    "hk": "hong kong",
    "гонконг": "hong kong",
    "sg": "singapore",
    "сингапур": "singapore",
    "tok": "tokyo",
    "токио": "tokyo",
    "bkk": "bangkok",
    "бангкок": "bangkok",
    "пекин": "beijing",
    "шанхай": "shanghai",
    "сеул": "seoul",
    "бали": "denpasar",  # Bali → Denpasar (main city)
    "пхукет": "phuket",
    # Americas
    "торонто": "toronto",
    "ванкувер": "vancouver",
    "монреаль": "montreal",
    "мехико": "mexico city",
    "сан-паулу": "sao paulo",
    "буэнос-айрес": "buenos aires",
    # Australia
    "сидней": "sydney",
    "мельбурн": "melbourne",
}

# Singleton geonamescache instance (lazy init)
_gc: GeonamesCache | None = None


def _get_geonames_cache() -> GeonamesCache:
    """Get singleton GeonamesCache instance."""
    global _gc
    if _gc is None:
        _gc = GeonamesCache()
    return _gc


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

    Uses geonamescache with 190k+ cities. Supports abbreviations like NY, MSK, СПб.
    Use this when the city is not in the configured list.

    Args:
        city_name: Name of the city to look up (supports abbreviations)

    Returns:
        FOUND: city → IANA timezone if found
        NOT_FOUND: message if city cannot be found
    """
    return _lookup_city_geonames(city_name)


def _lookup_city_geonames(city_name: str) -> str:
    """Lookup city timezone using geonamescache (190k+ cities).

    Args:
        city_name: City name to look up (can be abbreviation like NY, MSK).

    Returns:
        FOUND: City → IANA timezone if found
        NOT_FOUND: message if city cannot be found
    """
    normalized = city_name.lower().strip()

    # 1. Expand abbreviations (NY → new york, MSK → moscow)
    if normalized in CITY_ABBREVIATIONS:
        normalized = CITY_ABBREVIATIONS[normalized]

    gc = _get_geonames_cache()
    cities = gc.get_cities()

    # 2. Exact match (case-insensitive) - collect all and pick by population
    exact_matches: list[tuple[str, str, int]] = []
    for city_data in cities.values():
        if city_data["name"].lower() == normalized:
            population = city_data.get("population", 0)
            exact_matches.append((city_data["name"], city_data["timezone"], population))

    if exact_matches:
        # Pick the city with highest population (London UK > London Ontario)
        best = max(exact_matches, key=lambda x: x[2])
        return f"FOUND: {best[0]} → {best[1]}"

    # 3. Prefix match for partial inputs (only if single match)
    prefix_matches: list[tuple[str, str, int]] = []
    for city_data in cities.values():
        if city_data["name"].lower().startswith(normalized) and len(normalized) >= 3:
            population = city_data.get("population", 0)
            prefix_matches.append((city_data["name"], city_data["timezone"], population))

    if len(prefix_matches) == 1:
        return f"FOUND: {prefix_matches[0][0]} → {prefix_matches[0][1]}"

    # 4. Not found
    return (
        f"NOT_FOUND: '{city_name}' не найден. "
        "Напиши город точнее (например: Moscow, London, Tokyo)."
    )


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
