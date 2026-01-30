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

# Singleton geonamescache instance (lazy init)
_gc: GeonamesCache | None = None


def _get_geonames_cache() -> GeonamesCache:
    """Get singleton GeonamesCache instance."""
    global _gc
    if _gc is None:
        _gc = GeonamesCache()
    return _gc


def _normalize_city_with_llm(city_name: str, is_retry: bool = False) -> str | None:
    """Use LLM to normalize location to a city name.

    Handles:
    - Abbreviations (NY, MSK)
    - Non-Latin scripts (Москва, дубай)
    - Islands → their capitals (Madeira → Funchal)
    - States/regions → their largest cities (Kentucky → Louisville)

    Args:
        city_name: Location name in any language/format.
        is_retry: If True, this is a retry after geonames lookup failed.

    Returns:
        Normalized city name, or None if normalization failed.
    """
    from langchain_openai import ChatOpenAI

    settings = get_settings()

    # Only skip LLM for simple ASCII on first try
    # On retry (after geonames failed), always try LLM to resolve regions/islands
    if not is_retry and city_name.isascii() and len(city_name) > 3 and " " not in city_name:
        return None

    try:
        llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=settings.nvidia_api_key,  # type: ignore[arg-type]
            model=settings.config.llm.model,
            temperature=0,
            timeout=5.0,
        ).bind(max_tokens=50)

        prompt = f"""Convert this location to a CITY name that exists in geographic databases.
Input: "{city_name}"

Rules:
- Abbreviations: NY → New York, MSK → Moscow
- Non-English: Москва → Moscow, Мадейра → Funchal
- Islands: Madeira → Funchal, Bali → Denpasar, Hawaii → Honolulu
- States/regions: Kentucky → Louisville, California → Los Angeles
- Already a city: Paris → Paris

Output ONLY the city name. If truly unknown, output: UNKNOWN"""

        result = llm.invoke(prompt)
        normalized = str(result.content).strip()

        if normalized and normalized != "UNKNOWN" and normalized.lower() != city_name.lower():
            logger.debug(f"LLM normalized '{city_name}' → '{normalized}'")
            return normalized

    except Exception as e:
        logger.warning(f"LLM city normalization failed: {e}")

    return None


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
    will automatically normalize non-English names using LLM.

    Args:
        city_name: Name of the city to look up (any language)

    Returns:
        FOUND: city → IANA timezone if found
        NOT_FOUND: message if city cannot be found
    """
    result = geocode_city_full(city_name)
    if result.startswith("NOT_FOUND:"):
        # Provide helpful message for agent
        return (
            f"NOT_FOUND: '{city_name}' not found. "
            "Try a more specific city name (e.g., Moscow, London, Tokyo)."
        )
    return result


def geocode_city_full(city_name: str) -> str:
    """Full geocode lookup with LLM normalization.

    This is the main entry point for geocoding - it tries geonames first,
    then uses LLM to normalize. LLM handles:
    - Non-English names (Москва → Moscow)
    - Islands (Madeira → Funchal)
    - States/regions (Kentucky → Louisville)

    Args:
        city_name: Location name in any language.

    Returns:
        FOUND: City → IANA timezone if found
        NOT_FOUND: message if city cannot be found
    """
    # 1. Try direct lookup first
    result = _lookup_city_geonames(city_name)
    if result.startswith("FOUND:"):
        return result

    # 2. If not found, try LLM normalization (first pass - language normalization)
    normalized = _normalize_city_with_llm(city_name)
    if normalized:
        result = _lookup_city_geonames(normalized)
        if result.startswith("FOUND:"):
            return result

    # 3. Still not found - try LLM with is_retry=True (handles islands/regions → cities)
    normalized_retry = _normalize_city_with_llm(city_name, is_retry=True)
    if normalized_retry and normalized_retry != normalized:
        result = _lookup_city_geonames(normalized_retry)
        if result.startswith("FOUND:"):
            return result

    # 4. Not found even after all normalization attempts
    return f"NOT_FOUND: '{city_name}'"


def _lookup_city_geonames(city_name: str) -> str:
    """Lookup city timezone using geonamescache (190k+ cities).

    NOTE: Prefer geocode_city_full() which includes LLM normalization.

    Args:
        city_name: City name to look up (any language - searches alternatenames).

    Returns:
        FOUND: City → IANA timezone if found
        NOT_FOUND: message if city cannot be found
    """
    normalized = city_name.lower().strip()

    # Empty or too short input
    if len(normalized) < 2:
        return f"NOT_FOUND: '{city_name}'"

    gc = _get_geonames_cache()
    cities = gc.get_cities()

    # 1. Exact match on name (case-insensitive) - collect all and pick by population
    exact_matches: list[tuple[str, str, int]] = []
    for city_data in cities.values():
        if city_data["name"].lower() == normalized:
            population = city_data.get("population", 0)
            exact_matches.append((city_data["name"], city_data["timezone"], population))

    if exact_matches:
        # Pick the city with highest population (London UK > London Ontario)
        best = max(exact_matches, key=lambda x: x[2])
        return f"FOUND: {best[0]} → {best[1]}"

    # 2. Search in alternatenames (Russian, local names, etc.)
    altname_matches: list[tuple[str, str, int]] = []
    for city_data in cities.values():
        altnames = city_data.get("alternatenames", [])
        for altname in altnames:
            if altname.lower() == normalized:
                population = city_data.get("population", 0)
                altname_matches.append((city_data["name"], city_data["timezone"], population))
                break  # Found in this city, move to next

    if altname_matches:
        best = max(altname_matches, key=lambda x: x[2])
        logger.debug(f"Found '{city_name}' via alternatename → {best[0]}")
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
    return f"NOT_FOUND: '{city_name}'"


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
