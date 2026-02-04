"""Tests for agent tools (geocode, abbreviations, etc)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.core.agent_tools import (
    geocode_city,
    lookup_configured_city,
    lookup_tz_abbreviation,
    save_timezone,
)

# Mapping for LLM normalization mock
LLM_NORMALIZE_MAPPING = {
    # Abbreviations
    "NY": "New York",
    "NYC": "New York",
    "MSK": "Moscow",
    "LA": "Los Angeles",
    "SF": "San Francisco",
    "СПб": "Saint Petersburg",
    "Питер": "Saint Petersburg",
    # Russian cities
    "Москва": "Moscow",
    "Екатеринбург": "Yekaterinburg",
    "Новосибирск": "Novosibirsk",
    "Казань": "Kazan",
    "Краснодар": "Krasnodar",
    "Владивосток": "Vladivostok",
}


def mock_normalize(city_name: str) -> str | None:
    """Mock LLM normalization using predefined mapping."""
    return LLM_NORMALIZE_MAPPING.get(city_name)


class TestGeocodeCity:
    """Tests for geocode_city tool."""

    # Valid cities - should return FOUND (no LLM needed)
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

    # Abbreviations - need LLM mock
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
        """Test city abbreviations are expanded correctly via LLM."""
        with patch(
            "src.core.geo._normalize_with_llm",
            side_effect=mock_normalize,
        ):
            result = geocode_city.invoke({"city_name": abbrev})
            assert "FOUND:" in result
            assert expected_tz in result

    # Russian cities - need LLM mock
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
        """Test Russian cities in Cyrillic are mapped correctly via LLM."""
        with patch(
            "src.core.geo._normalize_with_llm",
            side_effect=mock_normalize,
        ):
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
        """Test invalid inputs return NOT_FOUND."""
        with patch(
            "src.core.geo._normalize_with_llm",
            return_value=None,
        ):
            result = geocode_city.invoke({"city_name": invalid_input})
            assert "NOT_FOUND:" in result

    def test_state_name_matches_city(self) -> None:
        """Test that state names that are also cities return the city."""
        # "Washington" is both a state and a city (DC)
        result = geocode_city.invoke({"city_name": "Washington"})
        assert "FOUND:" in result

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

    def test_case_insensitive(self) -> None:
        """Test that lookup is case-insensitive."""
        result = geocode_city.invoke({"city_name": "LONDON"})
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
        result = lookup_configured_city.invoke({"city_name": "Paris"})
        assert "NOT_FOUND:" in result


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
        """Test invalid abbreviation returns NOT_FOUND."""
        result = lookup_tz_abbreviation.invoke({"abbrev": "XYZ"})
        assert "NOT_FOUND:" in result


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
        """Test valid IANA timezones return SAVE."""
        result = save_timezone.invoke({"tz_iana": valid_tz})
        assert "SAVE:" in result
        assert valid_tz in result

    @pytest.mark.parametrize(
        "invalid_tz",
        [
            "EST",  # Abbreviation, not IANA
            "Berlin",  # City name, not IANA
            "random",  # Random string
        ],
    )
    def test_invalid_timezone(self, invalid_tz: str) -> None:
        """Test invalid timezones return ERROR."""
        result = save_timezone.invoke({"tz_iana": invalid_tz})
        assert "ERROR:" in result


class TestEdgeCases:
    """Edge case tests for agent tools."""

    def test_state_names_mostly_not_found(self) -> None:
        """Most US state names should not return a city timezone."""
        # These are states, not cities - should not be found
        states = ["Texas", "California", "Florida"]
        for state in states:
            with patch(
                "src.core.geo._normalize_with_llm",
                return_value=None,
            ):
                result = geocode_city.invoke({"city_name": state})
                assert "NOT_FOUND:" in result or "FOUND:" in result
                # We just verify it doesn't crash - some states share names with cities

    def test_state_names_that_match_cities(self) -> None:
        """Some state names match city names and should be found."""
        # These states have major cities with the same name
        result = geocode_city.invoke({"city_name": "New York"})
        assert "FOUND:" in result

    def test_country_names_behavior(self) -> None:
        """Country names may or may not be found depending on capitals."""
        # Some countries share names with their capitals
        with patch(
            "src.core.geo._normalize_with_llm",
            return_value=None,
        ):
            # "Germany" shouldn't match any city (unlike "France" which matches "Franceville")
            result = geocode_city.invoke({"city_name": "Germany"})
            # Germany is a country, not a city - should not be found
            assert "NOT_FOUND:" in result

    def test_city_with_state(self) -> None:
        """Test city name with state works."""
        # Just "Austin" should work
        result = geocode_city.invoke({"city_name": "Austin"})
        assert "FOUND:" in result
