"""Tests for city → timezone lookup using geonamescache.

Note: Basic geocoding tests are in test_geo.py. This file tests
the agent tool interface and LLM normalization mocking.
"""

from __future__ import annotations

from unittest.mock import patch

from src.core.geo import geocode_city_str


class TestGeocodeCityStr:
    """Tests for geocode_city_str function (direct lookup without LLM)."""

    def test_moscow_english(self) -> None:
        """Test Moscow in English."""
        result = geocode_city_str("Moscow", use_llm=False)
        assert "FOUND:" in result
        assert "Europe/Moscow" in result

    def test_london_prioritizes_uk(self) -> None:
        """Test London returns UK, not Canada."""
        result = geocode_city_str("London", use_llm=False)
        assert "FOUND:" in result
        assert "Europe/London" in result
        assert "America/Toronto" not in result

    def test_los_angeles_prioritizes_us(self) -> None:
        """Test Los Angeles returns US, not Spain."""
        result = geocode_city_str("Los Angeles", use_llm=False)
        assert "FOUND:" in result
        assert "America/Los_Angeles" in result
        assert "Europe/Madrid" not in result

    def test_tokyo(self) -> None:
        """Test Tokyo."""
        result = geocode_city_str("Tokyo", use_llm=False)
        assert "FOUND:" in result
        assert "Asia/Tokyo" in result

    def test_berlin(self) -> None:
        """Test Berlin."""
        result = geocode_city_str("Berlin", use_llm=False)
        assert "FOUND:" in result
        assert "Europe/Berlin" in result

    def test_new_york_full_name(self) -> None:
        """Test New York (full name) returns NYC timezone."""
        result = geocode_city_str("new york", use_llm=False)
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_not_found_gibberish(self) -> None:
        """Test gibberish returns NOT_FOUND."""
        result = geocode_city_str("xyz123abc", use_llm=False)
        assert "NOT_FOUND:" in result

    def test_ny_abbreviation_via_alternatenames(self) -> None:
        """Test NY abbreviation is found via alternatenames (no LLM needed)."""
        result = geocode_city_str("NY", use_llm=False)
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_cyrillic_via_alternatenames(self) -> None:
        """Test Cyrillic is found via alternatenames (no LLM needed)."""
        result = geocode_city_str("москва", use_llm=False)
        assert "FOUND:" in result
        assert "Europe/Moscow" in result


class TestGeocodeCityWithLLM:
    """Tests for geocode_city_str with mocked LLM normalization."""

    def test_msk_abbreviation(self) -> None:
        """Test MSK abbreviation for Moscow via LLM."""
        with patch("src.core.geo._normalize_with_llm", return_value="Moscow"):
            result = geocode_city_str("msk", use_llm=True)
            assert "FOUND:" in result
            assert "Europe/Moscow" in result

    def test_spb_cyrillic(self) -> None:
        """Test СПб abbreviation for Saint Petersburg via LLM."""
        with patch(
            "src.core.geo._normalize_with_llm",
            return_value="Saint Petersburg",
        ):
            result = geocode_city_str("спб", use_llm=True)
            assert "FOUND:" in result
            assert "Europe/Moscow" in result  # Same timezone as Moscow

    def test_la_abbreviation(self) -> None:
        """Test LA abbreviation for Los Angeles via LLM."""
        with patch("src.core.geo._normalize_with_llm", return_value="Los Angeles"):
            result = geocode_city_str("LA", use_llm=True)
            assert "FOUND:" in result
            assert "America/Los_Angeles" in result

    def test_sf_abbreviation(self) -> None:
        """Test SF abbreviation for San Francisco via LLM."""
        with patch(
            "src.core.geo._normalize_with_llm",
            return_value="San Francisco",
        ):
            result = geocode_city_str("sf", use_llm=True)
            assert "FOUND:" in result
            assert "America/Los_Angeles" in result

    def test_english_city_no_llm_needed(self) -> None:
        """Test English city names don't need LLM."""
        # LLM should not be called for English city names
        with patch("src.core.geo._normalize_with_llm") as mock_normalize:
            result = geocode_city_str("London", use_llm=True)
            assert "FOUND:" in result
            assert "Europe/London" in result
            mock_normalize.assert_not_called()

    def test_llm_returns_none(self) -> None:
        """Test graceful handling when LLM returns None."""
        with patch("src.core.geo._normalize_with_llm", return_value=None):
            result = geocode_city_str("unknowncity", use_llm=True)
            assert "NOT_FOUND:" in result


class TestPopulationPriority:
    """Tests for population-based prioritization."""

    def test_new_york_city_is_largest(self) -> None:
        """Test that New York City (largest) is returned for 'new york'."""
        result = geocode_city_str("new york", use_llm=False)
        assert "FOUND:" in result
        # Should return the largest New York (NYC), not New York in other states
        assert "America/New_York" in result
