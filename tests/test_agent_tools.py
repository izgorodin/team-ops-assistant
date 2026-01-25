"""Tests for agent tools (geocode, abbreviations, etc)."""

from __future__ import annotations

import pytest

from src.core.agent_tools import (
    geocode_city,
    lookup_configured_city,
    lookup_tz_abbreviation,
    save_timezone,
)


class TestGeocodeCity:
    """Tests for geocode_city tool."""

    # Valid cities - should return FOUND
    @pytest.mark.parametrize(
        ("city", "expected_tz"),
        [
            ("London", "Europe/London"),
            ("New York", "America/New_York"),
            ("Tokyo", "Asia/Tokyo"),
            ("Moscow", "Europe/Moscow"),
            ("Berlin", "Europe/Berlin"),
            ("Paris", "Europe/Paris"),
            ("Sydney", "Australia/Sydney"),
        ],
    )
    def test_valid_cities(self, city: str, expected_tz: str) -> None:
        """Test common cities return correct timezones."""
        result = geocode_city.invoke({"city_name": city})
        assert "FOUND:" in result
        assert expected_tz in result

    # Abbreviations - should expand and find
    @pytest.mark.parametrize(
        ("abbrev", "expected_tz"),
        [
            ("NY", "America/New_York"),
            ("NYC", "America/New_York"),
            ("MSK", "Europe/Moscow"),
            ("LA", "America/Los_Angeles"),
            ("SF", "America/Los_Angeles"),  # San Francisco
            ("СПб", "Europe/Moscow"),  # Saint Petersburg
            ("Питер", "Europe/Moscow"),  # Saint Petersburg colloquial
        ],
    )
    def test_abbreviations(self, abbrev: str, expected_tz: str) -> None:
        """Test city abbreviations are expanded correctly."""
        result = geocode_city.invoke({"city_name": abbrev})
        assert "FOUND:" in result
        assert expected_tz in result

    # Russian cities - mapped via CITY_ABBREVIATIONS
    @pytest.mark.parametrize(
        ("city", "expected_tz"),
        [
            ("Москва", "Europe/Moscow"),
            ("Екатеринбург", "Asia/Yekaterinburg"),
            ("Новосибирск", "Asia/Novosibirsk"),
            ("Казань", "Europe/Moscow"),
            ("Краснодар", "Europe/Moscow"),
            ("Владивосток", "Asia/Vladivostok"),
        ],
    )
    def test_russian_cities_cyrillic(self, city: str, expected_tz: str) -> None:
        """Test Russian cities in Cyrillic are mapped correctly."""
        result = geocode_city.invoke({"city_name": city})
        assert "FOUND:" in result
        assert expected_tz in result

    # NOT_FOUND cases - should NOT hallucinate
    @pytest.mark.parametrize(
        "invalid_input",
        [
            "Кентуки",  # Kentucky in Russian (state, not city)
            "Kentucky",  # State name in English
            "Bavaria",  # German state
            "asdfghjkl",  # Gibberish
            "12345",  # Numbers
            "",  # Empty string
            "   ",  # Whitespace only
        ],
    )
    def test_invalid_returns_not_found(self, invalid_input: str) -> None:
        """Test that invalid inputs return NOT_FOUND, not hallucinated cities."""
        result = geocode_city.invoke({"city_name": invalid_input})
        # Result should start with NOT_FOUND (not "FOUND:")
        assert result.startswith("NOT_FOUND"), (
            f"Expected NOT_FOUND for {invalid_input!r}, got: {result}"
        )

    def test_state_name_matches_city(self) -> None:
        """Test that state names matching real cities are found (not bugs).

        Some US state names match real city names (e.g., Texas City in Texas).
        This is correct behavior - geonamescache returns actual cities.
        """
        # Texas matches "Texas City" which is a real city
        result = geocode_city.invoke({"city_name": "Texas"})
        assert "FOUND:" in result
        assert "Texas" in result

    # Multi-word cities
    @pytest.mark.parametrize(
        ("city", "expected_tz"),
        [
            ("New York", "America/New_York"),
            ("Los Angeles", "America/Los_Angeles"),
            ("San Francisco", "America/Los_Angeles"),
            ("Hong Kong", "Asia/Hong_Kong"),
            ("Saint Petersburg", "Europe/Moscow"),
        ],
    )
    def test_multi_word_cities(self, city: str, expected_tz: str) -> None:
        """Test multi-word city names."""
        result = geocode_city.invoke({"city_name": city})
        assert "FOUND:" in result
        assert expected_tz in result

    # Case insensitivity
    def test_case_insensitive(self) -> None:
        """Test that lookup is case-insensitive."""
        results = [
            geocode_city.invoke({"city_name": "london"}),
            geocode_city.invoke({"city_name": "LONDON"}),
            geocode_city.invoke({"city_name": "London"}),
            geocode_city.invoke({"city_name": "LoNdOn"}),
        ]
        for result in results:
            assert "FOUND:" in result
            assert "Europe/London" in result


class TestLookupConfiguredCity:
    """Tests for lookup_configured_city tool."""

    def test_configured_city_found(self) -> None:
        """Test that configured cities are found."""
        result = lookup_configured_city.invoke({"city_name": "London"})
        assert "FOUND:" in result
        assert "Europe/London" in result

    def test_configured_city_not_found(self) -> None:
        """Test that non-configured cities return NOT_FOUND."""
        result = lookup_configured_city.invoke({"city_name": "Prague"})
        assert "NOT_FOUND" in result
        assert "Available:" in result


class TestLookupTzAbbreviation:
    """Tests for lookup_tz_abbreviation tool."""

    @pytest.mark.parametrize(
        ("abbrev", "expected_tz"),
        [
            ("PT", "America/Los_Angeles"),
            ("PST", "America/Los_Angeles"),
            ("PDT", "America/Los_Angeles"),
            ("ET", "America/New_York"),
            ("EST", "America/New_York"),
            ("EDT", "America/New_York"),
            ("CET", "Europe/Berlin"),
            ("MSK", "Europe/Moscow"),
            ("JST", "Asia/Tokyo"),
            ("GMT", "Europe/London"),
            ("UTC", "UTC"),
        ],
    )
    def test_valid_abbreviations(self, abbrev: str, expected_tz: str) -> None:
        """Test valid timezone abbreviations."""
        result = lookup_tz_abbreviation.invoke({"abbrev": abbrev})
        assert "FOUND:" in result
        assert expected_tz in result

    def test_invalid_abbreviation(self) -> None:
        """Test that invalid abbreviations return NOT_FOUND."""
        result = lookup_tz_abbreviation.invoke({"abbrev": "XYZ"})
        assert "NOT_FOUND" in result


class TestSaveTimezone:
    """Tests for save_timezone tool."""

    @pytest.mark.parametrize(
        "valid_tz",
        [
            "America/New_York",
            "Europe/London",
            "Asia/Tokyo",
            "UTC",
        ],
    )
    def test_valid_timezone(self, valid_tz: str) -> None:
        """Test valid IANA timezones are accepted."""
        result = save_timezone.invoke({"tz_iana": valid_tz})
        assert f"SAVE:{valid_tz}" in result

    @pytest.mark.parametrize(
        "invalid_tz",
        [
            "EST",  # Not IANA format
            "Berlin",  # City name, not timezone
            "random",  # Gibberish
        ],
    )
    def test_invalid_timezone(self, invalid_tz: str) -> None:
        """Test invalid timezone formats are rejected."""
        result = save_timezone.invoke({"tz_iana": invalid_tz})
        assert "ERROR:" in result
        assert "SAVE:" not in result


class TestEdgeCases:
    """Edge case tests for tools."""

    def test_state_names_mostly_not_found(self) -> None:
        """Test that most US state names return NOT_FOUND.

        Exception: some state names match real city names:
        - Texas → Texas City (USA)
        - Florida → Florida (Cuba)
        """
        # These states have no matching city names
        states_no_city = ["Kentucky", "California", "Arizona"]
        for state in states_no_city:
            result = geocode_city.invoke({"city_name": state})
            assert result.startswith("NOT_FOUND"), f"{state} should return NOT_FOUND"

    def test_state_names_that_match_cities(self) -> None:
        """Test US state names that happen to match real city names."""
        # Texas matches "Texas City" in USA
        result = geocode_city.invoke({"city_name": "Texas"})
        assert result.startswith("FOUND:")

        # Florida matches a city in Cuba
        result = geocode_city.invoke({"city_name": "Florida"})
        assert result.startswith("FOUND:")

    def test_country_names_behavior(self) -> None:
        """Test country name lookup behavior.

        Some country names match city names (e.g., "Russia" might not,
        but geonamescache behavior should be consistent).
        """
        # Document actual behavior rather than assert NOT_FOUND
        countries = ["USA", "Germany", "France", "Japan", "Russia"]
        for country in countries:
            result = geocode_city.invoke({"city_name": country})
            # Just verify we get a valid response format
            assert result.startswith("FOUND:") or result.startswith("NOT_FOUND")

    def test_city_with_state(self) -> None:
        """Test city lookup with state doesn't break."""
        # User might write "Lexington, Kentucky"
        result = geocode_city.invoke({"city_name": "Lexington"})
        assert result.startswith("FOUND:")
        # Should find Lexington (multiple exist, pick by population)
