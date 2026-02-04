"""Unified geocoding module.

Single entry point for all city → timezone lookups.
Consolidates multiple geocoding paths into one clear flow.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from geonamescache import GeonamesCache

logger = logging.getLogger(__name__)


# Minimum population for city to be included in fast matcher (reduces false positives)
MIN_CITY_POPULATION = 50000
# Minimum name length for ASCII names (avoids short ambiguous names like "Ny", "Li")
MIN_NAME_LENGTH_ASCII = 3
# Minimum name length for non-ASCII (CJK characters are complete words at 2 chars)
MIN_NAME_LENGTH_NON_ASCII = 2


@dataclass
class DetectedCity:
    """A city name detected in text."""

    original: str  # Original text as found
    normalized: str  # Normalized city name (English)
    timezone: str  # IANA timezone


class CityNameMatcher:
    """Fast city name detection in text.

    Pre-loads major city names (pop >= 50k) from geonames for O(1) lookup.
    Handles Russian case normalization for Cyrillic names.

    Usage:
        matcher = CityNameMatcher()
        cities = matcher.find_cities("Переехал в Москву")
        # [DetectedCity(original='Москву', normalized='Moscow', timezone='Europe/Moscow')]

    Language-agnostic: works with any language present in geonames alternatenames.
    """

    def __init__(self) -> None:
        """Initialize matcher, pre-loading city names."""
        self._name_to_city: dict[str, tuple[str, str, int]] = {}  # name → (city, tz, pop)
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of city name lookup table."""
        if self._initialized:
            return

        gc = _get_geonames_cache()
        cities = gc.get_cities()

        for city_data in cities.values():
            population = city_data.get("population", 0)
            if population < MIN_CITY_POPULATION:
                continue

            city_name = city_data["name"]
            timezone = city_data["timezone"]
            entry = (city_name, timezone, population)

            # Add main name
            name_lower = city_name.lower()
            if self._is_valid_name_length(name_lower):
                self._add_name(name_lower, entry)

            # Add all alternatenames
            for altname in city_data.get("alternatenames", []):
                alt_lower = altname.lower()
                if self._is_valid_name_length(alt_lower):
                    self._add_name(alt_lower, entry)

        self._initialized = True
        logger.debug(f"CityNameMatcher initialized with {len(self._name_to_city)} names")

    def _is_valid_name_length(self, name: str) -> bool:
        """Check if name meets minimum length requirements.

        Non-ASCII names (CJK, Cyrillic) use shorter threshold since
        each character carries more meaning than in ASCII.
        """
        if name.isascii():
            return len(name) >= MIN_NAME_LENGTH_ASCII
        return len(name) >= MIN_NAME_LENGTH_NON_ASCII

    def _add_name(self, name: str, entry: tuple[str, str, int]) -> None:
        """Add name to lookup table, keeping highest population city for conflicts."""
        existing = self._name_to_city.get(name)
        if existing is None or entry[2] > existing[2]:
            self._name_to_city[name] = entry

    def find_cities(self, text: str) -> list[DetectedCity]:
        """Find all city names mentioned in text.

        Args:
            text: Text to search for city names.

        Returns:
            List of detected cities with their timezones.
        """
        self._ensure_initialized()

        found: list[DetectedCity] = []
        seen_timezones: set[str] = set()  # Avoid duplicates

        # 1. Word-based search for spaced languages (Latin, Cyrillic, etc.)
        words = re.findall(r"[\w-]+", text, re.UNICODE)

        # Try multi-word combinations first (for "New York", "São Paulo", etc.)
        for n_words in (3, 2):  # Try 3-word then 2-word combinations
            for i in range(len(words) - n_words + 1):
                phrase = " ".join(words[i : i + n_words])
                city_info = self._name_to_city.get(phrase.lower())
                if city_info and city_info[1] not in seen_timezones:
                    found.append(
                        DetectedCity(
                            original=phrase,
                            normalized=city_info[0],
                            timezone=city_info[1],
                        )
                    )
                    seen_timezones.add(city_info[1])

        # Then single words
        for word in words:
            city_info = self._lookup_word(word)
            if city_info and city_info[1] not in seen_timezones:
                found.append(
                    DetectedCity(
                        original=word,
                        normalized=city_info[0],
                        timezone=city_info[1],
                    )
                )
                seen_timezones.add(city_info[1])

        # 2. Sliding window for CJK (Chinese/Japanese/Korean) - no word boundaries
        cjk_cities = self._find_cjk_cities(text, seen_timezones)
        found.extend(cjk_cities)

        return found

    def _lookup_word(self, word: str) -> tuple[str, str, int] | None:
        """Lookup a single word in city names.

        Tries direct lookup, then Russian case normalization.
        """
        word_lower = word.lower()

        # Direct lookup
        city_info = self._name_to_city.get(word_lower)
        if city_info:
            return city_info

        # Russian case normalization
        normalized = _normalize_russian_case(word)
        if normalized != word:
            city_info = self._name_to_city.get(normalized.lower())
            if city_info:
                return city_info

        return None

    def _find_cjk_cities(self, text: str, seen_timezones: set[str]) -> list[DetectedCity]:
        """Find CJK city names using sliding window.

        CJK languages (Chinese, Japanese, Korean) don't use spaces between words,
        so we need to check all substrings of length 2-4 characters.
        """
        found: list[DetectedCity] = []

        # Only process if text contains CJK characters
        if not any(self._is_cjk_char(c) for c in text):
            return found

        # Sliding window: check substrings of length 2, 3, 4
        for window_size in (2, 3, 4):
            for i in range(len(text) - window_size + 1):
                substr = text[i : i + window_size]

                # Skip if not all CJK
                if not all(self._is_cjk_char(c) for c in substr):
                    continue

                city_info = self._name_to_city.get(substr)
                if city_info and city_info[1] not in seen_timezones:
                    found.append(
                        DetectedCity(
                            original=substr,
                            normalized=city_info[0],
                            timezone=city_info[1],
                        )
                    )
                    seen_timezones.add(city_info[1])

        return found

    @staticmethod
    def _is_cjk_char(char: str) -> bool:
        """Check if character is CJK (Chinese/Japanese/Korean)."""
        code = ord(char)
        return (
            0x4E00 <= code <= 0x9FFF  # CJK Unified Ideographs
            or 0x3400 <= code <= 0x4DBF  # CJK Extension A
            or 0x3040 <= code <= 0x309F  # Hiragana
            or 0x30A0 <= code <= 0x30FF  # Katakana
            or 0xAC00 <= code <= 0xD7AF  # Korean Hangul
        )


# Singleton matcher instance (lazy init)
_matcher: CityNameMatcher | None = None


def get_city_matcher() -> CityNameMatcher:
    """Get singleton CityNameMatcher instance."""
    global _matcher
    if _matcher is None:
        _matcher = CityNameMatcher()
    return _matcher


def find_cities_in_text(text: str) -> list[DetectedCity]:
    """Find all city names in text (convenience function).

    Args:
        text: Text to search.

    Returns:
        List of detected cities.
    """
    return get_city_matcher().find_cities(text)


# Singleton geonamescache instance (lazy init)
_gc: GeonamesCache | None = None


def _get_geonames_cache() -> GeonamesCache:
    """Get singleton GeonamesCache instance."""
    global _gc
    if _gc is None:
        _gc = GeonamesCache()
    return _gc


def geocode_city(city_name: str, use_llm: bool = True) -> tuple[str, str] | None:
    """Geocode a city name to (city_name, iana_timezone).

    Single entry point for all geocoding needs. Uses a clear fallback chain:
    1. Exact match in geonames (by name or alternatenames)
    2. Russian case normalization → geonames
    3. LLM normalization (Cyrillic→English) → geonames (if use_llm=True)

    Args:
        city_name: City name in any language.
        use_llm: Whether to use LLM for normalization (default True).

    Returns:
        Tuple of (city_name, iana_timezone) or None if not found.

    Examples:
        >>> geocode_city("London")
        ("London", "Europe/London")
        >>> geocode_city("Москва")
        ("Moscow", "Europe/Moscow")
        >>> geocode_city("бобруйску")  # Russian dative case
        ("Babruysk", "Europe/Minsk")
    """
    if not city_name or len(city_name.strip()) < 2:
        return None

    city_name = city_name.strip()

    # 1. Direct geonames lookup (exact match + alternatenames)
    result = _lookup_geonames(city_name)
    if result:
        return result

    # 2. Russian case normalization
    normalized = _normalize_russian_case(city_name)
    if normalized != city_name:
        result = _lookup_geonames(normalized)
        if result:
            logger.debug(f"Found '{city_name}' via Russian normalization → {result[0]}")
            return result

    # 3. LLM normalization (for non-English names, regions, islands)
    if use_llm:
        llm_normalized = _normalize_with_llm(city_name)
        if llm_normalized and llm_normalized.lower() != city_name.lower():
            result = _lookup_geonames(llm_normalized)
            if result:
                logger.debug(f"Found '{city_name}' via LLM normalization → {result[0]}")
                return result

    return None


def _lookup_geonames(city_name: str) -> tuple[str, str] | None:
    """Lookup city in geonamescache (190k+ cities).

    Searches:
    1. Exact match on name (case-insensitive)
    2. Exact match on alternatenames (Russian, local names, etc.)

    If multiple matches, picks the city with highest population.

    Args:
        city_name: City name to look up.

    Returns:
        Tuple of (city_name, iana_timezone) or None.
    """
    normalized = city_name.lower().strip()
    if len(normalized) < 2:
        return None

    gc = _get_geonames_cache()
    cities = gc.get_cities()

    # 1. Exact match on name
    exact_matches: list[tuple[str, str, int]] = []
    for city_data in cities.values():
        if city_data["name"].lower() == normalized:
            population = city_data.get("population", 0)
            exact_matches.append((city_data["name"], city_data["timezone"], population))

    if exact_matches:
        best = max(exact_matches, key=lambda x: x[2])
        return (best[0], best[1])

    # 2. Search in alternatenames
    altname_matches: list[tuple[str, str, int]] = []
    for city_data in cities.values():
        altnames = city_data.get("alternatenames", [])
        for altname in altnames:
            if altname.lower() == normalized:
                population = city_data.get("population", 0)
                altname_matches.append((city_data["name"], city_data["timezone"], population))
                break

    if altname_matches:
        best = max(altname_matches, key=lambda x: x[2])
        return (best[0], best[1])

    return None


def _normalize_russian_case(city: str) -> str:
    """Normalize Russian city name by removing case endings.

    In Russian, city names are declined. "по Бобруйску" uses dative case.
    This function tries to convert to nominative case for geocoding.

    Common patterns:
    - "-ску" → "-ск" (Бобруйску → Бобруйск)
    - "-ву" → "-ва" (Москву → Москва) - accusative
    - "-ве" → "-ва" (Москве → Москва) - prepositional
    - "-ни" → "-нь" (Казани → Казань)
    - "-ну" → "-н" (Лондону → Лондон)
    - "-не" → "-на" (Вене → Вена)
    - "-ине" → "-ин" (Берлине → Берлин)

    Args:
        city: City name (possibly in dative/prepositional case).

    Returns:
        Normalized city name (nominative case attempt).
    """
    city_lower = city.lower()

    # -ску → -ск (Бобруйску → Бобруйск, Минску → Минск)
    if city_lower.endswith("ску"):
        return city[:-1]

    # -ву → -ва (Москву → Москва) - accusative case for -ва cities
    if city_lower.endswith("ву"):
        return city[:-1] + ("а" if city[-1].islower() else "А")

    # -ве → -ва (Москве → Москва) - prepositional case
    if city_lower.endswith("ве"):
        return city[:-1] + ("а" if city[-1].islower() else "А")

    # -ине → -ин (Берлине → Берлин) - prepositional for -ин cities
    if city_lower.endswith("ине"):
        return city[:-1]

    # -ни → -нь (Казани → Казань)
    if city_lower.endswith("ни"):
        return city[:-1] + ("ь" if city[-1].islower() else "Ь")

    # -ну → -н (Лондону → Лондон, Берлину → Берлин)
    if city_lower.endswith("ну"):
        return city[:-1]

    # -не → -на (Вене → Вена)
    if city_lower.endswith("не"):
        return city[:-1] + ("а" if city[-1].islower() else "А")

    # -те → -т (Ташкенте → Ташкент)
    if city_lower.endswith("те"):
        return city[:-1]

    # -ту → -т (for completeness)
    if city_lower.endswith("ту"):
        return city[:-1]

    # -е → remove (generic prepositional for consonant-ending cities)  # noqa: RUF003
    # Must be last as it's the most general pattern
    if city_lower.endswith("е") and len(city_lower) > 3:
        # Check if removing -е gives a valid consonant ending  # noqa: RUF003
        base = city[:-1]
        if base and base[-1].lower() not in "аеёиоуыэюя":  # Not a vowel
            return base

    return city


def _normalize_with_llm(city_name: str) -> str | None:
    """Use LLM to normalize location to a city name.

    Handles:
    - Non-Latin scripts (Москва → Moscow)
    - Islands → their capitals (Madeira → Funchal)
    - States/regions → their largest cities (Kentucky → Louisville)

    Only called when geonames lookup fails.

    Args:
        city_name: Location name in any language/format.

    Returns:
        Normalized city name, or None if normalization failed.
    """
    from langchain_openai import ChatOpenAI

    from src.core.prompts import load_prompt
    from src.settings import get_settings

    settings = get_settings()

    # Skip LLM for simple ASCII names (already tried in geonames)
    if city_name.isascii() and len(city_name) > 3 and " " not in city_name:
        return None

    try:
        llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=settings.nvidia_api_key,  # type: ignore[arg-type]
            model=settings.config.llm.model,
            temperature=0,
            timeout=15.0,
        ).bind(max_tokens=50)

        prompt = load_prompt("city_normalize", city_name=city_name)
        result = llm.invoke(prompt)
        normalized = str(result.content).strip()

        if normalized and normalized != "UNKNOWN":
            logger.debug(f"LLM normalized '{city_name}' → '{normalized}'")
            return normalized

    except Exception as e:
        logger.warning(f"LLM city normalization failed: {e}")

    return None


# Convenience function for string result (backwards compatibility)
def geocode_city_str(city_name: str, use_llm: bool = True) -> str:
    """Geocode city and return string result for agent tools.

    Args:
        city_name: City name to look up.
        use_llm: Whether to use LLM for normalization.

    Returns:
        "FOUND: City → timezone" or "NOT_FOUND: 'city'"
    """
    result = geocode_city(city_name, use_llm=use_llm)
    if result:
        return f"FOUND: {result[0]} → {result[1]}"
    return f"NOT_FOUND: '{city_name}'"
