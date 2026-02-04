"""Tests for the unified geocoding module."""

import pytest

from src.core.geo import (
    _lookup_geonames,
    _normalize_russian_case,
    geocode_city,
    geocode_city_str,
)


class TestNormalizeRussianCase:
    """Tests for Russian case normalization."""

    @pytest.mark.parametrize(
        "input_city,expected",
        [
            # Dative -ску → -ск
            ("Бобруйску", "Бобруйск"),
            ("Минску", "Минск"),
            ("бобруйску", "бобруйск"),
            # Dative -ве → -ва
            ("Москве", "Москва"),
            ("москве", "москва"),
            # Dative -ни → -нь
            ("Казани", "Казань"),
            # Dative -ну → -н
            ("Лондону", "Лондон"),
            ("Берлину", "Берлин"),
            # Dative -не → -на
            ("Вене", "Вена"),
            # Prepositional -те → -т
            ("Ташкенте", "Ташкент"),
            # No change needed
            ("Москва", "Москва"),
            ("London", "London"),
            ("Tokyo", "Tokyo"),
        ],
    )
    def test_normalization(self, input_city: str, expected: str) -> None:
        """Test Russian case normalization."""
        assert _normalize_russian_case(input_city) == expected


class TestLookupGeonames:
    """Tests for direct geonames lookup."""

    def test_exact_match_english(self) -> None:
        """English city names should match exactly."""
        result = _lookup_geonames("London")
        assert result is not None
        assert result[0] == "London"
        assert result[1] == "Europe/London"

    def test_exact_match_case_insensitive(self) -> None:
        """Lookup should be case-insensitive."""
        result = _lookup_geonames("london")
        assert result is not None
        assert result[0] == "London"

    def test_alternatenames_cyrillic(self) -> None:
        """Should find cities via Russian alternatenames."""
        result = _lookup_geonames("Москва")
        assert result is not None
        assert result[0] == "Moscow"
        assert result[1] == "Europe/Moscow"

    def test_alternatenames_belarusian(self) -> None:
        """Should find Belarusian cities."""
        result = _lookup_geonames("Бобруйск")
        assert result is not None
        assert "Minsk" in result[1]  # Europe/Minsk timezone

    def test_population_tiebreaker(self) -> None:
        """When multiple cities match, should pick highest population."""
        result = _lookup_geonames("Moscow")
        assert result is not None
        # Should be Moscow, Russia (12M) not Moscow, Idaho (25K)
        assert result[1] == "Europe/Moscow"

    def test_not_found(self) -> None:
        """Unknown cities should return None."""
        result = _lookup_geonames("NotARealCityXYZ123")
        assert result is None

    def test_empty_input(self) -> None:
        """Empty or very short input should return None."""
        assert _lookup_geonames("") is None
        assert _lookup_geonames("A") is None


class TestGeocodeCity:
    """Tests for the main geocode_city function."""

    def test_english_city(self) -> None:
        """Simple English city lookup."""
        result = geocode_city("London")
        assert result is not None
        assert result[0] == "London"
        assert result[1] == "Europe/London"

    def test_russian_nominative(self) -> None:
        """Russian city in nominative case."""
        result = geocode_city("Москва")
        assert result is not None
        assert result[0] == "Moscow"
        assert result[1] == "Europe/Moscow"

    def test_russian_dative(self) -> None:
        """Russian city in dative case (по Москве)."""
        result = geocode_city("москве")
        assert result is not None
        assert result[0] == "Moscow"

    def test_russian_dative_bobruisk(self) -> None:
        """Бобруйску should resolve via case normalization."""
        result = geocode_city("бобруйску", use_llm=False)
        assert result is not None
        assert "Minsk" in result[1]

    def test_russian_dative_tashkent(self) -> None:
        """Ташкенту should resolve via case normalization."""
        result = geocode_city("ташкенту", use_llm=False)
        assert result is not None
        assert "Tashkent" in result[1]

    def test_without_llm(self) -> None:
        """Can disable LLM normalization."""
        # London should work without LLM
        result = geocode_city("London", use_llm=False)
        assert result is not None

    def test_not_found(self) -> None:
        """Unknown locations return None."""
        result = geocode_city("NotARealPlace123", use_llm=False)
        assert result is None


class TestGeocodeCityStr:
    """Tests for string result format (backwards compatibility)."""

    def test_found_format(self) -> None:
        """Found result should have correct format."""
        result = geocode_city_str("London", use_llm=False)
        assert result.startswith("FOUND:")
        assert "London" in result
        assert "Europe/London" in result

    def test_not_found_format(self) -> None:
        """Not found result should have correct format."""
        result = geocode_city_str("NotARealPlace123", use_llm=False)
        assert result.startswith("NOT_FOUND:")
        assert "NotARealPlace123" in result


class TestRealWorldCases:
    """Integration tests with real-world use cases."""

    @pytest.mark.parametrize(
        "city,expected_tz",
        [
            # Common cities
            ("London", "Europe/London"),
            ("New York", "America/New_York"),
            ("Tokyo", "Asia/Tokyo"),
            ("Sydney", "Australia/Sydney"),
            # Russian cities (nominative)
            ("Москва", "Europe/Moscow"),
            # Russian cities (dative - "по городу")
            ("Лондону", "Europe/London"),
            ("Берлину", "Europe/Berlin"),
            # Belarusian cities
            ("Минск", "Europe/Minsk"),
            # Uzbekistan
            ("Ташкент", "Asia/Tashkent"),
        ],
    )
    def test_common_cities(self, city: str, expected_tz: str) -> None:
        """Common cities should resolve correctly without LLM."""
        result = geocode_city(city, use_llm=False)
        assert result is not None, f"Failed to geocode '{city}'"
        assert result[1] == expected_tz, f"Expected {expected_tz}, got {result[1]}"
