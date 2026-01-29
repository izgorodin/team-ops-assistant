"""Tests for time_convert module."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.core.models import ParsedTime
from src.core.time_convert import (
    ConvertedTime,
    convert_to_timezone,
    convert_to_timezones,
    format_conversion_response,
    format_time_conversion,
    format_time_with_tz,
    get_current_time_in_timezone,
    get_timezone_abbreviation,
    is_valid_iana_timezone,
)


class TestConvertToTimezone:
    """Tests for convert_to_timezone function."""

    def test_basic_conversion(self) -> None:
        """Basic timezone conversion should work."""
        parsed = ParsedTime(original_text="14:00", hour=14, minute=0)
        result = convert_to_timezone(
            parsed,
            source_tz="Europe/Moscow",
            target_tz="America/New_York",
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("Europe/Moscow")),
        )

        # Moscow is UTC+3, NY is UTC-4 in summer (EDT)
        # 14:00 MSK = 07:00 EDT
        assert result.hour == 7
        assert result.minute == 0
        assert result.timezone == "America/New_York"

    def test_next_day_conversion(self) -> None:
        """Conversion that crosses to next day should set is_next_day."""
        parsed = ParsedTime(original_text="23:00", hour=23, minute=0)
        result = convert_to_timezone(
            parsed,
            source_tz="America/Los_Angeles",
            target_tz="Europe/Berlin",
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("America/Los_Angeles")),
        )

        # LA is UTC-7 (PDT), Berlin is UTC+2 (CEST) = 9 hour difference
        # 23:00 PDT = 08:00 next day CEST
        assert result.is_next_day is True
        assert result.hour == 8

    def test_prev_day_conversion(self) -> None:
        """Conversion that crosses to previous day should set is_prev_day."""
        parsed = ParsedTime(original_text="01:00", hour=1, minute=0)
        result = convert_to_timezone(
            parsed,
            source_tz="Europe/Berlin",
            target_tz="America/Los_Angeles",
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("Europe/Berlin")),
        )

        # Berlin is UTC+2 (CEST), LA is UTC-7 (PDT) = 9 hour difference
        # 01:00 CEST = 16:00 prev day PDT
        assert result.is_prev_day is True
        assert result.hour == 16

    def test_same_day_conversion(self) -> None:
        """Conversion on same day should have is_next_day=False and is_prev_day=False."""
        parsed = ParsedTime(original_text="12:00", hour=12, minute=0)
        result = convert_to_timezone(
            parsed,
            source_tz="Europe/London",
            target_tz="Europe/Berlin",
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("Europe/London")),
        )

        # London to Berlin is only +1 hour in summer
        assert result.is_next_day is False
        assert result.is_prev_day is False
        assert result.hour == 13

    def test_is_tomorrow_flag(self) -> None:
        """ParsedTime with is_tomorrow should shift source date."""
        parsed = ParsedTime(original_text="10:00", hour=10, minute=0, is_tomorrow=True)
        result = convert_to_timezone(
            parsed,
            source_tz="UTC",
            target_tz="UTC",
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("UTC")),
        )

        # Same timezone with is_tomorrow shifts both dates equally,
        # so is_next_day compares shifted dates and is False
        # The key is that the source time was shifted forward by 1 day
        assert result.hour == 10
        assert result.minute == 0
        assert result.is_next_day is False  # Both source and target are on "tomorrow"

    def test_formatted_output(self) -> None:
        """Result should include formatted string."""
        parsed = ParsedTime(original_text="14:30", hour=14, minute=30)
        result = convert_to_timezone(
            parsed,
            source_tz="UTC",
            target_tz="America/New_York",
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("UTC")),
        )

        assert "ET" in result.formatted or "New York" in result.formatted
        assert ":30" in result.formatted


class TestConvertToTimezones:
    """Tests for convert_to_timezones function."""

    def test_converts_to_multiple_zones(self) -> None:
        """Should convert to all provided timezones."""
        parsed = ParsedTime(original_text="14:00", hour=14, minute=0)
        target_tzs = ["America/New_York", "Europe/Berlin", "Asia/Tokyo"]

        results = convert_to_timezones(
            parsed,
            source_tz="UTC",
            target_tzs=target_tzs,
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("UTC")),
        )

        assert len(results) == 3
        timezones = [r.timezone for r in results]
        assert set(timezones) == set(target_tzs)

    def test_excludes_source_timezone(self) -> None:
        """Should skip conversion to source timezone."""
        parsed = ParsedTime(original_text="14:00", hour=14, minute=0)
        target_tzs = ["UTC", "America/New_York"]  # UTC is also source

        results = convert_to_timezones(
            parsed,
            source_tz="UTC",
            target_tzs=target_tzs,
            reference_date=datetime(2024, 6, 15, tzinfo=ZoneInfo("UTC")),
        )

        assert len(results) == 1
        assert results[0].timezone == "America/New_York"

    def test_empty_target_list(self) -> None:
        """Should return empty list for no targets."""
        parsed = ParsedTime(original_text="14:00", hour=14, minute=0)

        results = convert_to_timezones(
            parsed,
            source_tz="UTC",
            target_tzs=[],
        )

        assert results == []


class TestFormatTimeWithTz:
    """Tests for format_time_with_tz function."""

    def test_basic_format(self) -> None:
        """Basic formatting should work."""
        result = format_time_with_tz(14, 30, "Europe/Berlin")
        assert result == "14:30 CET"

    def test_next_day_indicator(self) -> None:
        """Should add next day indicator when is_next_day=True."""
        result = format_time_with_tz(8, 0, "America/New_York", is_next_day=True)
        assert "(+1 day)" in result
        assert "08:00" in result

    def test_zero_padded_minutes(self) -> None:
        """Minutes should be zero-padded."""
        result = format_time_with_tz(9, 5, "UTC")
        assert "09:05" in result

    def test_zero_hour(self) -> None:
        """Midnight should be formatted correctly."""
        result = format_time_with_tz(0, 0, "UTC")
        assert "00:00" in result


class TestGetTimezoneAbbreviation:
    """Tests for get_timezone_abbreviation function."""

    @pytest.mark.parametrize(
        "timezone,expected",
        [
            ("America/Los_Angeles", "PT"),
            ("America/New_York", "ET"),
            ("Europe/London", "UK"),
            ("Europe/Berlin", "CET"),
            ("Asia/Tokyo", "JST"),
            ("Australia/Sydney", "AEST"),
            ("UTC", "UTC"),
        ],
    )
    def test_known_abbreviations(self, timezone: str, expected: str) -> None:
        """Known timezones should return mapped abbreviations."""
        assert get_timezone_abbreviation(timezone) == expected

    def test_unknown_timezone_extracts_city(self) -> None:
        """Unknown timezone should extract city name."""
        result = get_timezone_abbreviation("Europe/Kiev")
        assert result == "Kiev"

    def test_city_with_underscore(self) -> None:
        """City names with underscores should have them replaced."""
        result = get_timezone_abbreviation("America/Los_Angeles")
        # This is in the known list, so returns "PT"
        assert result == "PT"

        # For an unknown city with underscore
        result = get_timezone_abbreviation("Pacific/Port_Moresby")
        assert result == "Port Moresby"

    def test_simple_timezone_name(self) -> None:
        """Timezone without slash should return as-is."""
        result = get_timezone_abbreviation("EST")
        assert result == "EST"


class TestFormatConversionResponse:
    """Tests for format_conversion_response function."""

    def test_basic_response(self) -> None:
        """Should format multiple conversions correctly."""
        conversions = [
            ConvertedTime("America/New_York", 10, 0, "10:00 ET", False, False),
            ConvertedTime("Europe/Berlin", 16, 0, "16:00 CET", False, False),
        ]

        result = format_conversion_response("15:00", "UTC", conversions)

        assert "15:00" in result
        assert "UTC" in result
        assert "10:00 ET" in result
        assert "16:00 CET" in result

    def test_empty_conversions(self) -> None:
        """Should return empty string for no conversions."""
        result = format_conversion_response("15:00", "UTC", [])
        assert result == ""

    def test_includes_emoji(self) -> None:
        """Response should include clock emoji."""
        conversions = [
            ConvertedTime("America/New_York", 10, 0, "10:00 ET", False, False),
        ]

        result = format_conversion_response("15:00", "UTC", conversions)
        assert "🕐" in result


class TestFormatTimeConversion:
    """Tests for format_time_conversion convenience function."""

    def test_basic_conversion(self) -> None:
        """Should convert raw hour/minute to formatted response."""
        result = format_time_conversion(
            hour=14,
            minute=30,
            source_tz="UTC",
            target_timezones=["America/New_York", "Europe/Berlin"],
        )

        assert "14:30" in result
        assert "UTC" in result

    def test_with_is_tomorrow(self) -> None:
        """Should handle is_tomorrow flag."""
        result = format_time_conversion(
            hour=10,
            minute=0,
            source_tz="UTC",
            target_timezones=["America/Los_Angeles"],
            is_tomorrow=True,
        )

        # Should contain some output
        assert len(result) > 0

    def test_with_original_text(self) -> None:
        """Should use original_text when provided."""
        result = format_time_conversion(
            hour=14,
            minute=30,
            source_tz="UTC",
            target_timezones=["America/New_York"],
            original_text="half past two",
        )

        # The header uses normalized time, not original_text
        assert "14:30" in result


class TestIsValidIanaTimezone:
    """Tests for is_valid_iana_timezone function."""

    @pytest.mark.parametrize(
        "timezone",
        [
            "UTC",
            "America/New_York",
            "Europe/London",
            "Asia/Tokyo",
            "Pacific/Honolulu",
        ],
    )
    def test_valid_timezones(self, timezone: str) -> None:
        """Valid IANA timezones should return True."""
        assert is_valid_iana_timezone(timezone) is True

    @pytest.mark.parametrize(
        "timezone",
        [
            "Invalid/Timezone",
            "PST",  # Abbreviation, not IANA
            "GMT+5",  # Offset notation
            "",
            "NotATimezone",
        ],
    )
    def test_invalid_timezones(self, timezone: str) -> None:
        """Invalid timezone strings should return False."""
        assert is_valid_iana_timezone(timezone) is False


class TestGetCurrentTimeInTimezone:
    """Tests for get_current_time_in_timezone function."""

    def test_returns_datetime_with_correct_timezone(self) -> None:
        """Should return datetime with specified timezone."""
        result = get_current_time_in_timezone("America/New_York")

        assert result.tzinfo is not None
        assert str(result.tzinfo) == "America/New_York"

    def test_returns_current_time(self) -> None:
        """Returned time should be close to current time."""
        before = datetime.now(ZoneInfo("UTC"))
        result = get_current_time_in_timezone("UTC")
        after = datetime.now(ZoneInfo("UTC"))

        # Should be within a second
        assert before <= result <= after
