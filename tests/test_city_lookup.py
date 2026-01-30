"""Tests for city → timezone lookup using geonamescache."""

from __future__ import annotations

from unittest.mock import patch

from src.core.agent_tools import _lookup_city_geonames, geocode_city


class TestLookupCityGeonames:
    """Tests for _lookup_city_geonames function (direct English lookup only)."""

    def test_moscow_english(self) -> None:
        """Test Moscow in English."""
        result = _lookup_city_geonames("Moscow")
        assert "FOUND:" in result
        assert "Europe/Moscow" in result

    def test_london_prioritizes_uk(self) -> None:
        """Test London returns UK, not Canada."""
        result = _lookup_city_geonames("London")
        assert "FOUND:" in result
        assert "Europe/London" in result
        assert "America/Toronto" not in result

    def test_los_angeles_prioritizes_us(self) -> None:
        """Test Los Angeles returns US, not Spain."""
        result = _lookup_city_geonames("Los Angeles")
        assert "FOUND:" in result
        assert "America/Los_Angeles" in result
        assert "Europe/Madrid" not in result

    def test_tokyo(self) -> None:
        """Test Tokyo."""
        result = _lookup_city_geonames("Tokyo")
        assert "FOUND:" in result
        assert "Asia/Tokyo" in result

    def test_berlin(self) -> None:
        """Test Berlin."""
        result = _lookup_city_geonames("Berlin")
        assert "FOUND:" in result
        assert "Europe/Berlin" in result

    def test_new_york_full_name(self) -> None:
        """Test New York (full name) returns NYC timezone."""
        result = _lookup_city_geonames("new york")
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_not_found_gibberish(self) -> None:
        """Test gibberish returns NOT_FOUND."""
        result = _lookup_city_geonames("xyz123abc")
        assert "NOT_FOUND:" in result

    def test_ny_abbreviation_via_alternatenames(self) -> None:
        """Test NY abbreviation is found via alternatenames (no LLM needed)."""
        result = _lookup_city_geonames("NY")
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_cyrillic_via_alternatenames(self) -> None:
        """Test Cyrillic is found via alternatenames (no LLM needed)."""
        result = _lookup_city_geonames("москва")
        assert "FOUND:" in result
        assert "Europe/Moscow" in result


class TestGeocodeCityWithLLM:
    """Tests for geocode_city tool with mocked LLM normalization."""

    def test_ny_abbreviation(self) -> None:
        """Test NY abbreviation resolves via LLM."""
        with patch("src.core.agent_tools._normalize_city_with_llm", return_value="New York"):
            result = geocode_city.invoke({"city_name": "NY"})
            assert "FOUND:" in result
            assert "America/New_York" in result

    def test_nyc_abbreviation(self) -> None:
        """Test NYC abbreviation resolves via LLM."""
        with patch("src.core.agent_tools._normalize_city_with_llm", return_value="New York"):
            result = geocode_city.invoke({"city_name": "NYC"})
            assert "FOUND:" in result
            assert "America/New_York" in result

    def test_moscow_cyrillic(self) -> None:
        """Test Moscow in Russian (москва) via LLM."""
        with patch("src.core.agent_tools._normalize_city_with_llm", return_value="Moscow"):
            result = geocode_city.invoke({"city_name": "москва"})
            assert "FOUND:" in result
            assert "Europe/Moscow" in result

    def test_msk_abbreviation(self) -> None:
        """Test MSK abbreviation for Moscow via LLM."""
        with patch("src.core.agent_tools._normalize_city_with_llm", return_value="Moscow"):
            result = geocode_city.invoke({"city_name": "msk"})
            assert "FOUND:" in result
            assert "Europe/Moscow" in result

    def test_spb_cyrillic(self) -> None:
        """Test СПб abbreviation for Saint Petersburg via LLM."""
        with patch(
            "src.core.agent_tools._normalize_city_with_llm",
            return_value="Saint Petersburg",
        ):
            result = geocode_city.invoke({"city_name": "спб"})
            assert "FOUND:" in result
            assert "Europe/Moscow" in result  # Same timezone as Moscow

    def test_la_abbreviation(self) -> None:
        """Test LA abbreviation for Los Angeles via LLM."""
        with patch("src.core.agent_tools._normalize_city_with_llm", return_value="Los Angeles"):
            result = geocode_city.invoke({"city_name": "LA"})
            assert "FOUND:" in result
            assert "America/Los_Angeles" in result

    def test_sf_abbreviation(self) -> None:
        """Test SF abbreviation for San Francisco via LLM."""
        with patch(
            "src.core.agent_tools._normalize_city_with_llm",
            return_value="San Francisco",
        ):
            result = geocode_city.invoke({"city_name": "sf"})
            assert "FOUND:" in result
            assert "America/Los_Angeles" in result

    def test_english_city_no_llm_needed(self) -> None:
        """Test English city names don't need LLM."""
        # LLM should not be called for English city names
        with patch("src.core.agent_tools._normalize_city_with_llm") as mock_normalize:
            result = geocode_city.invoke({"city_name": "London"})
            assert "FOUND:" in result
            assert "Europe/London" in result
            mock_normalize.assert_not_called()

    def test_llm_returns_none(self) -> None:
        """Test graceful handling when LLM returns None."""
        with patch("src.core.agent_tools._normalize_city_with_llm", return_value=None):
            result = geocode_city.invoke({"city_name": "unknowncity"})
            assert "NOT_FOUND:" in result


class TestPopulationPriority:
    """Tests for population-based prioritization."""

    def test_new_york_city_is_largest(self) -> None:
        """Test that New York City (largest) is returned for 'new york'."""
        result = _lookup_city_geonames("new york")
        assert "FOUND:" in result
        # Should return the largest New York (NYC), not New York in other states
        assert "America/New_York" in result
