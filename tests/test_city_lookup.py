"""Tests for city → timezone lookup using geonamescache."""

from __future__ import annotations

from src.core.agent_tools import _lookup_city_geonames, geocode_city


class TestCityLookupGeonames:
    """Tests for _lookup_city_geonames function."""

    def test_ny_abbreviation(self) -> None:
        """Test NY abbreviation resolves to New York."""
        result = _lookup_city_geonames("NY")
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_nyc_abbreviation(self) -> None:
        """Test NYC abbreviation resolves to New York."""
        result = _lookup_city_geonames("NYC")
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_ny_lowercase(self) -> None:
        """Test lowercase ny works."""
        result = _lookup_city_geonames("ny")
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_moscow_english(self) -> None:
        """Test Moscow in English."""
        result = _lookup_city_geonames("Moscow")
        assert "FOUND:" in result
        assert "Europe/Moscow" in result

    def test_moscow_cyrillic(self) -> None:
        """Test Moscow in Russian (москва)."""
        result = _lookup_city_geonames("москва")
        assert "FOUND:" in result
        assert "Europe/Moscow" in result

    def test_msk_abbreviation(self) -> None:
        """Test MSK abbreviation for Moscow."""
        result = _lookup_city_geonames("msk")
        assert "FOUND:" in result
        assert "Europe/Moscow" in result

    def test_spb_cyrillic(self) -> None:
        """Test СПб abbreviation for Saint Petersburg."""
        result = _lookup_city_geonames("спб")
        assert "FOUND:" in result
        assert "Europe/Moscow" in result  # Same timezone as Moscow

    def test_london_prioritizes_uk(self) -> None:
        """Test London returns UK, not Canada."""
        result = _lookup_city_geonames("London")
        assert "FOUND:" in result
        assert "Europe/London" in result
        assert "America/Toronto" not in result

    def test_la_abbreviation(self) -> None:
        """Test LA abbreviation for Los Angeles."""
        result = _lookup_city_geonames("LA")
        assert "FOUND:" in result
        assert "America/Los_Angeles" in result

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

    def test_not_found_gibberish(self) -> None:
        """Test gibberish returns NOT_FOUND."""
        result = _lookup_city_geonames("xyz123abc")
        assert "NOT_FOUND:" in result

    def test_not_found_provides_examples(self) -> None:
        """Test NOT_FOUND message includes helpful examples."""
        result = _lookup_city_geonames("abracadabra")
        assert "NOT_FOUND:" in result
        assert "Moscow" in result or "London" in result or "Tokyo" in result


class TestGeocodeCity:
    """Tests for geocode_city tool function."""

    def test_geocode_city_is_sync(self) -> None:
        """Test that geocode_city is a sync function (not async)."""
        # The @tool decorator should work with sync function
        result = geocode_city.invoke("NY")
        assert "FOUND:" in result
        assert "America/New_York" in result

    def test_geocode_city_handles_cyrillic(self) -> None:
        """Test geocode_city handles Cyrillic input."""
        result = geocode_city.invoke("москва")
        assert "FOUND:" in result
        assert "Europe/Moscow" in result


class TestPopulationPriority:
    """Tests for population-based prioritization."""

    def test_new_york_city_is_largest(self) -> None:
        """Test that New York City (largest) is returned for 'new york'."""
        result = _lookup_city_geonames("new york")
        assert "FOUND:" in result
        # Should return the largest New York (NYC), not New York in other states
        assert "America/New_York" in result

    def test_sf_abbreviation(self) -> None:
        """Test SF abbreviation for San Francisco."""
        result = _lookup_city_geonames("sf")
        assert "FOUND:" in result
        assert "America/Los_Angeles" in result
