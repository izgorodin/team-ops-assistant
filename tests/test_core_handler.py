"""Tests for time parsing and conversion utilities.

Note: MessageHandler is deprecated. Tests for pipeline/orchestrator are in
test_orchestrator.py and test_pipeline.py.
"""

from __future__ import annotations

import pytest

from src.core.time_convert import (
    convert_to_timezone,
    format_conversion_response,
    get_timezone_abbreviation,
)
from src.core.time_parse import contains_time_reference, parse_times


class TestTimeParsing:
    """Tests for time parsing functionality."""

    def test_parse_hh_mm_format(self) -> None:
        """Test parsing HH:MM format."""
        times = parse_times("Let's meet at 14:30")

        assert len(times) == 1
        assert times[0].hour == 14
        assert times[0].minute == 30

    def test_parse_h_ampm_format(self) -> None:
        """Test parsing H am/pm format."""
        times = parse_times("Call at 3pm")

        assert len(times) == 1
        assert times[0].hour == 15
        assert times[0].minute == 0

    def test_parse_12_pm(self) -> None:
        """Test parsing 12pm (noon)."""
        times = parse_times("Lunch at 12pm")

        assert len(times) == 1
        assert times[0].hour == 12

    def test_parse_12_am(self) -> None:
        """Test parsing 12am (midnight)."""
        times = parse_times("Midnight call at 12am")

        assert len(times) == 1
        assert times[0].hour == 0

    def test_parse_with_timezone_hint(self) -> None:
        """Test parsing with timezone abbreviation."""
        times = parse_times("Meeting at 3pm PST")

        assert len(times) == 1
        assert times[0].hour == 15
        assert times[0].timezone_hint == "America/Los_Angeles"

    def test_parse_with_city_hint(self) -> None:
        """Test parsing with city name."""
        times = parse_times("Call at 10am London time")

        assert len(times) == 1
        assert times[0].timezone_hint == "Europe/London"

    def test_parse_tomorrow(self) -> None:
        """Test parsing with tomorrow prefix."""
        times = parse_times("Tomorrow at 9am")

        assert len(times) == 1
        assert times[0].is_tomorrow is True

    def test_parse_multiple_times(self) -> None:
        """Test parsing multiple times in one message."""
        times = parse_times("From 10:00 to 14:30")

        assert len(times) == 2

    def test_parse_no_times(self) -> None:
        """Test message with no times."""
        times = parse_times("Hello everyone!")

        assert len(times) == 0


class TestContainsTimeReference:
    """Tests for contains_time_reference function."""

    def test_detects_hh_mm(self) -> None:
        """Test detection of HH:MM format."""
        assert contains_time_reference("Meet at 14:30") is True

    def test_detects_ampm(self) -> None:
        """Test detection of am/pm format."""
        assert contains_time_reference("Call at 3pm") is True

    def test_detects_meeting_with_time(self) -> None:
        """Test detection of meeting context with time."""
        # Must have digits to pass trigger guard
        assert contains_time_reference("Schedule a meeting at 10") is True

    def test_no_time_reference(self) -> None:
        """Test message without time reference (no digits = no time)."""
        # No digits → trigger guard rejects immediately
        assert contains_time_reference("The weather is nice today") is False
        assert contains_time_reference("Schedule a meeting") is False  # no digits!

    @pytest.mark.xfail(reason="Word-based times (midnight/noon) not yet supported")
    def test_detects_midnight_noon(self) -> None:
        """Test detection of time words without digits."""
        assert contains_time_reference("Submit by midnight") is True
        assert contains_time_reference("Lunch at noon") is True


class TestTimeConversion:
    """Tests for time conversion functionality."""

    def test_convert_la_to_ny(self) -> None:
        """Test conversion from LA to NY (3 hour difference)."""
        from src.core.models import ParsedTime

        parsed = ParsedTime(original_text="3pm", hour=15, minute=0)
        result = convert_to_timezone(parsed, "America/Los_Angeles", "America/New_York")

        assert result.hour == 18  # 3pm PT = 6pm ET
        assert result.minute == 0

    def test_convert_with_day_change(self) -> None:
        """Test conversion that crosses midnight."""
        from src.core.models import ParsedTime

        parsed = ParsedTime(original_text="11pm", hour=23, minute=0)
        result = convert_to_timezone(parsed, "America/Los_Angeles", "Europe/London")

        # 11pm PT = 7am next day in London (8 hours ahead)
        assert result.is_next_day is True

    def test_get_timezone_abbreviation(self) -> None:
        """Test timezone abbreviation mapping."""
        assert get_timezone_abbreviation("America/Los_Angeles") == "PT"
        assert get_timezone_abbreviation("America/New_York") == "ET"
        assert get_timezone_abbreviation("Europe/London") == "UK"
        assert get_timezone_abbreviation("Asia/Tokyo") == "JST"


class TestFormatConversionResponse:
    """Tests for response formatting."""

    def test_format_basic_response(self) -> None:
        """Test basic response formatting."""
        from src.core.time_convert import ConvertedTime

        conversions = [
            ConvertedTime("America/New_York", 18, 0, "18:00 ET", False, False),
            ConvertedTime("Europe/London", 23, 0, "23:00 UK", False, False),
        ]

        response = format_conversion_response("3pm", "America/Los_Angeles", conversions)

        assert "3pm" in response
        assert "PT" in response
        assert "18:00 ET" in response
        assert "23:00 UK" in response



# Note: MessageHandler tests removed - functionality moved to orchestrator + pipeline.
# See test_orchestrator.py for integration tests.
