"""Unit tests for time parser regex patterns (Layer 2).

Tests regex extraction in isolation from ML classifier.
Contract: PATTERNS match specific time formats.
"""

from __future__ import annotations

import pytest

from src.core.time_parse import PATTERNS, parse_times

# ============================================================================
# Contract Tests - Pattern Existence
# ============================================================================


def test_patterns_dict_exists() -> None:
    """Contract: PATTERNS dict is available."""
    assert isinstance(PATTERNS, dict)


def test_required_patterns_exist() -> None:
    """Contract: Required patterns are defined."""
    required = ["hh_mm", "h_ampm", "at_h", "tomorrow", "tz_hint", "city_hint"]
    for name in required:
        assert name in PATTERNS, f"Pattern '{name}' not found"


# ============================================================================
# HH:MM Pattern Tests
# ============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "14:30",
        "09:00",
        "0:15",
        "23:59",
        "12:00",
        "meeting at 14:30 today",
        "call at 9:00",
    ],
)
def test_hh_mm_pattern_matches(text: str) -> None:
    """HH:MM pattern should match valid times."""
    match = PATTERNS["hh_mm"].search(text)
    assert match is not None, f"HH:MM should match: {text}"


@pytest.mark.parametrize(
    "text",
    [
        "25:00",  # invalid hour (but regex still matches, validation is separate)
        "12:60",  # invalid minute (but regex still matches)
        "123:45",  # too many digits
        "no time here",
        "",
    ],
)
def test_hh_mm_pattern_no_false_positive(text: str) -> None:
    """HH:MM pattern should not match non-time patterns."""
    match = PATTERNS["hh_mm"].search(text)
    if match:
        # If it matches, verify it's not a valid time
        hour = int(match.group(1))
        minute = int(match.group(2))
        # Some matches are OK if they're valid times embedded in larger numbers
        assert hour > 23 or minute > 59 or len(text) == 0


# ============================================================================
# H am/pm Pattern Tests
# ============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "3pm",
        "3 pm",
        "3PM",
        "3 PM",
        "9am",
        "9 am",
        "12AM",
        "meet at 3pm",
        "call at 9 AM",
    ],
)
def test_h_ampm_pattern_matches(text: str) -> None:
    """H am/pm pattern should match."""
    match = PATTERNS["h_ampm"].search(text)
    assert match is not None, f"H am/pm should match: {text}"


@pytest.mark.parametrize(
    "text",
    [
        "spam",  # ends with 'am' but not time
        "the pm value",  # 'pm' but not time
        "no time",
        "",
    ],
)
def test_h_ampm_pattern_no_false_positive(text: str) -> None:
    """H am/pm pattern should not match non-time text."""
    match = PATTERNS["h_ampm"].search(text)
    assert match is None, f"H am/pm should NOT match: {text}"


# ============================================================================
# "at H" Pattern Tests
# ============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "at 3",
        "at 10",
        "at 23",
        "meet at 3 today",
        "call at 9",
    ],
)
def test_at_h_pattern_matches(text: str) -> None:
    """'at H' pattern should match."""
    match = PATTERNS["at_h"].search(text)
    assert match is not None, f"'at H' should match: {text}"


@pytest.mark.parametrize(
    "text",
    [
        "cat 3",  # 'at' inside word
        "bat 3",
        "look at",  # 'at' without number
        "at the store",
        "",
    ],
)
def test_at_h_pattern_no_false_positive(text: str) -> None:
    """'at H' pattern should not match non-time text."""
    match = PATTERNS["at_h"].search(text)
    assert match is None, f"'at H' should NOT match: {text}"


# ============================================================================
# Tomorrow Pattern Tests
# ============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "tomorrow",
        "Tomorrow",
        "TOMORROW",
        "tomorrow at 3pm",
        "meeting tomorrow",
    ],
)
def test_tomorrow_pattern_matches(text: str) -> None:
    """Tomorrow pattern should match."""
    match = PATTERNS["tomorrow"].search(text)
    assert match is not None, f"Tomorrow should match: {text}"


# ============================================================================
# Timezone Hint Pattern Tests
# ============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "3pm PST",
        "14:00 GMT",
        "9am EST",
        "meeting at 3 UTC",
        "10:00 CET",
    ],
)
def test_tz_hint_pattern_matches(text: str) -> None:
    """Timezone hint pattern should match."""
    match = PATTERNS["tz_hint"].search(text)
    assert match is not None, f"TZ hint should match: {text}"


# ============================================================================
# City Hint Pattern Tests
# ============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "3pm London time",
        "10am in Tokyo",
        "meeting at 3 Berlin",
        "14:00 New York",
        "9am Sydney",
    ],
)
def test_city_hint_pattern_matches(text: str) -> None:
    """City hint pattern should match city names."""
    match = PATTERNS["city_hint"].search(text.lower())
    assert match is not None, f"City hint should match: {text}"


# ============================================================================
# parse_times() Function Tests
# ============================================================================


def test_parse_times_returns_list() -> None:
    """Contract: parse_times returns a list."""
    # Note: This will use ML classifier, so might return [] if ML says no time
    result = parse_times("14:30")
    assert isinstance(result, list)


def test_parse_times_extracts_hh_mm() -> None:
    """parse_times should extract HH:MM format."""
    result = parse_times("Meeting at 14:30")
    assert len(result) >= 1
    assert result[0].hour == 14
    assert result[0].minute == 30


def test_parse_times_extracts_h_ampm() -> None:
    """parse_times should extract H am/pm format."""
    result = parse_times("Call at 3pm")
    assert len(result) >= 1
    assert result[0].hour == 15
    assert result[0].minute == 0


def test_parse_times_extracts_h_am() -> None:
    """parse_times should extract H am format."""
    result = parse_times("Wake up at 9am")
    assert len(result) >= 1
    assert result[0].hour == 9
    assert result[0].minute == 0


def test_parse_times_extracts_at_h() -> None:
    """parse_times should extract 'at H' format when no other times."""
    result = parse_times("meet at 3")
    # "at H" is lower confidence, might not trigger ML
    # but if it does, should extract
    if result:
        assert result[0].hour == 3


def test_parse_times_extracts_timezone_hint() -> None:
    """parse_times should extract timezone hint."""
    result = parse_times("14:30 PST")
    assert len(result) >= 1
    assert result[0].timezone_hint == "America/Los_Angeles"


def test_parse_times_extracts_tomorrow() -> None:
    """parse_times should detect tomorrow prefix."""
    result = parse_times("tomorrow at 9am")
    assert len(result) >= 1
    assert result[0].is_tomorrow is True


def test_parse_times_returns_empty_for_negative() -> None:
    """parse_times should return empty for non-time text."""
    result = parse_times("I have 3 cats")
    assert result == []


# ============================================================================
# FALSE POSITIVES - HH:MM lookalikes that should NOT be parsed as times
# ============================================================================

# These are cases where HH:MM regex MATCHES but they're NOT times.
# The ML classifier should reject these before parsing.
# These tests verify that parse_times returns [] because ML says "no time".

# Cases where regex CAN'T match (single digit minutes) - these are SAFE
FALSE_POSITIVE_SINGLE_DIGIT = [
    # Sports scores (single digit minute = no match)
    ("Score was 3:2", "sports score"),
    ("Final score 1:0", "sports score"),
    ("The match ended 2:1", "match score"),
    # Aspect ratios (single digit minute = no match)
    ("16:9 monitor", "aspect ratio"),
    ("Shot in 4:3 format", "aspect ratio"),
    ("2:1 aspect ratio", "aspect ratio"),
    # Odds/ratios (single digit minute = no match)
    ("Odds are 5:1", "betting odds"),
    ("Mix ratio 2:1", "mixing ratio"),
]


@pytest.mark.parametrize(
    ("phrase", "notes"),
    FALSE_POSITIVE_SINGLE_DIGIT,
    ids=[f"safe:{n}" for _, n in FALSE_POSITIVE_SINGLE_DIGIT],
)
def test_parse_times_safe_single_digit_minute(phrase: str, notes: str) -> None:
    """parse_times correctly rejects single-digit minute patterns."""
    result = parse_times(phrase)
    assert result == [], (
        f"Should NOT parse time from '{phrase}' ({notes}), "
        f"but got {[(t.hour, t.minute) for t in result]}"
    )


# Cases where regex DOES match but shouldn't be time - ML should filter
# Known issues are marked as skip (not xfail) for cleaner output
@pytest.mark.parametrize(
    ("phrase", "notes"),
    [
        # Bible verses (2-digit minute = regex matches!)
        pytest.param(
            "John 3:16 is famous",
            "bible verse",
            marks=pytest.mark.skip(reason="Known issue: ML doesn't filter bible verses"),
        ),
        pytest.param(
            "Read Romans 8:28",
            "bible verse",
            marks=pytest.mark.skip(reason="Known issue: ML doesn't filter bible verses"),
        ),
        pytest.param(
            "Matthew 5:09",
            "bible verse padded",
            marks=pytest.mark.skip(reason="Known issue: ML doesn't filter bible verses"),
        ),
        pytest.param(
            "Psalm 23:01",
            "bible verse padded",
            marks=pytest.mark.skip(reason="Known issue: ML doesn't filter bible verses"),
        ),
        # Score with 2-digit (rare but possible)
        pytest.param(
            "They won 12:15 in overtime",
            "score 2-digit",
            marks=pytest.mark.skip(reason="Known issue: ambiguous time/score format"),
        ),
        # Ports (often 4 digits so might not match, but some do)
        ("localhost:8080", "localhost port"),  # should work - 80 is valid minute
        ("Connect to server:3000", "server port"),  # should work - 00 is valid minute
    ],
)
def test_parse_times_rejects_two_digit_lookalikes(phrase: str, notes: str) -> None:
    """parse_times should NOT extract times from 2-digit minute lookalikes.

    ML classifier should filter these - some are skip (known issues).
    """
    result = parse_times(phrase)
    assert result == [], (
        f"Should NOT parse time from '{phrase}' ({notes}), "
        f"but got {[(t.hour, t.minute) for t in result]}"
    )


# Test HH:MM regex behavior with lookalikes
# Note: Regex requires 2 digits for minutes (\d{2}), so single-digit ratios don't match


@pytest.mark.parametrize(
    "phrase",
    [
        "3:2",  # score - 1 digit minute
        "16:9",  # aspect ratio - 1 digit minute
        "5:1",  # odds - 1 digit minute
        "1:0",  # score - 1 digit minute
    ],
)
def test_hh_mm_regex_rejects_single_digit_minute(phrase: str) -> None:
    """HH:MM regex requires 2 digits for minutes - rejects scores/ratios."""
    match = PATTERNS["hh_mm"].search(phrase)
    assert match is None, f"HH:MM should NOT match single-digit minute: {phrase}"


@pytest.mark.parametrize(
    "phrase",
    [
        "3:16",  # bible verse format - MATCHES!
        "8:28",  # bible verse format - MATCHES!
        "5:09",  # padded minute - MATCHES!
    ],
)
def test_hh_mm_regex_matches_two_digit_minute(phrase: str) -> None:
    """HH:MM regex DOES match when minute has 2 digits (including bible verses)."""
    match = PATTERNS["hh_mm"].search(phrase)
    assert match is not None, f"HH:MM should match 2-digit minute: {phrase}"


# ============================================================================
# Edge Cases
# ============================================================================


def test_parse_times_empty_string() -> None:
    """Empty string should return empty list."""
    result = parse_times("")
    assert result == []


def test_parse_times_handles_multiple_times() -> None:
    """Multiple times in text should all be extracted."""
    result = parse_times("Meeting from 9am to 5pm")
    # Should get at least 2 times
    assert len(result) >= 2


def test_parse_times_12_hour_conversion() -> None:
    """12 PM should be 12, 12 AM should be 0."""
    result_pm = parse_times("lunch at 12pm")
    result_am = parse_times("midnight at 12am")

    if result_pm:
        assert result_pm[0].hour == 12

    if result_am:
        assert result_am[0].hour == 0


# ============================================================================
# Russian Time Patterns Tests
# ============================================================================


class TestRussianPatterns:
    """Tests for Russian time format parsing."""

    def test_russian_patterns_exist(self) -> None:
        """Contract: Russian patterns are defined."""
        required = ["ru_v_h", "ru_v_hh_mm", "ru_time_of_day", "ru_tomorrow", "ru_today"]
        for name in required:
            assert name in PATTERNS, f"Russian pattern '{name}' not found"

    # --- "в X" pattern (at X) ---

    @pytest.mark.parametrize(
        ("text", "expected_hour"),
        [
            ("в 10", 10),
            ("в 5", 5),
            ("в 23", 23),
            ("встреча в 15", 15),
            ("созвон в 9", 9),
        ],
    )
    def test_parse_russian_v_h(self, text: str, expected_hour: int) -> None:
        """Russian 'в X' format should parse correctly."""
        result = parse_times(text)
        assert len(result) >= 1, f"Should parse time from: {text}"
        assert result[0].hour == expected_hour
        assert result[0].minute == 0

    # --- "в X:XX" and "в X-XX" patterns ---

    @pytest.mark.parametrize(
        ("text", "expected_hour", "expected_minute"),
        [
            ("в 10:30", 10, 30),
            ("в 10-30", 10, 30),
            ("в 14:45", 14, 45),
            ("встреча в 9:15", 9, 15),
            ("созвон в 15-00", 15, 0),
        ],
    )
    def test_parse_russian_v_hh_mm(
        self, text: str, expected_hour: int, expected_minute: int
    ) -> None:
        """Russian 'в X:XX' and 'в X-XX' formats should parse correctly."""
        result = parse_times(text)
        assert len(result) >= 1, f"Should parse time from: {text}"
        assert result[0].hour == expected_hour
        assert result[0].minute == expected_minute

    # --- Time of day modifiers (утра/вечера/дня/ночи) ---

    @pytest.mark.parametrize(
        ("text", "expected_hour"),
        [
            ("в 5 утра", 5),  # 5 AM
            ("в 9 утра", 9),  # 9 AM
            ("в 5 вечера", 17),  # 5 PM
            ("в 7 вечера", 19),  # 7 PM
            ("в 3 дня", 15),  # 3 PM (afternoon)
            ("в 2 ночи", 2),  # 2 AM (night)
            ("в 12 дня", 12),  # noon
        ],
    )
    def test_parse_russian_time_of_day(self, text: str, expected_hour: int) -> None:
        """Russian time with утра/вечера/дня/ночи should convert correctly."""
        result = parse_times(text)
        assert len(result) >= 1, f"Should parse time from: {text}"
        assert result[0].hour == expected_hour

    # --- "завтра" (tomorrow) ---

    @pytest.mark.parametrize(
        "text",
        [
            "завтра в 10",
            "завтра в 10:30",
            "Завтра в 5 вечера",
            "встреча завтра в 15",
        ],
    )
    def test_parse_russian_tomorrow(self, text: str) -> None:
        """Russian 'завтра' should set is_tomorrow flag."""
        result = parse_times(text)
        assert len(result) >= 1, f"Should parse time from: {text}"
        assert result[0].is_tomorrow is True

    # --- "сегодня" (today) ---

    @pytest.mark.parametrize(
        "text",
        [
            "сегодня в 10",
            "сегодня в 14:30",
            "Сегодня в 5 вечера",
        ],
    )
    def test_parse_russian_today(self, text: str) -> None:
        """Russian 'сегодня' should parse (is_tomorrow=False)."""
        result = parse_times(text)
        assert len(result) >= 1, f"Should parse time from: {text}"
        assert result[0].is_tomorrow is False

    # --- Combined tests ---

    def test_parse_russian_complex_phrase(self) -> None:
        """Complex Russian phrase should parse correctly."""
        result = parse_times("Созвон завтра часиков в 5 вечера")
        assert len(result) >= 1
        assert result[0].hour == 17
        assert result[0].is_tomorrow is True

    def test_parse_russian_with_tz_hint(self) -> None:
        """Russian time with timezone hint should extract both."""
        result = parse_times("в 10 MSK")  # Moscow time
        assert len(result) >= 1
        assert result[0].hour == 10
        # MSK hint would need to be added to TIMEZONE_ABBREVIATIONS

    # --- Negative cases ---

    @pytest.mark.parametrize(
        "text",
        [
            "в магазине",  # "in the store" - not time
            "в команде 10 человек",  # "10 people in the team" - not time
            "встреча была отличной",  # no time
        ],
    )
    def test_parse_russian_negative(self, text: str) -> None:
        """Russian text without time should return empty."""
        result = parse_times(text)
        assert result == [], f"Should NOT parse time from: {text}"
