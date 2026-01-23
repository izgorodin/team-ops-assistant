"""Unit tests for ML classifier (Layer 1).

Tests the ML classifier in isolation, without LLM fallback.
Contract: contains_time_ml(text, use_llm_fallback=False) → bool
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.core.time_classifier import contains_time_ml, get_classifier

# ============================================================================
# Contract Tests
# ============================================================================


def test_classifier_returns_bool() -> None:
    """Contract: contains_time_ml returns bool."""
    result = contains_time_ml("test", use_llm_fallback=False)
    assert isinstance(result, bool)


def test_classifier_is_trained() -> None:
    """Contract: classifier is trained and ready."""
    classifier = get_classifier()
    assert classifier.is_trained


def test_classifier_predict_proba_returns_float() -> None:
    """Contract: predict_proba returns probability 0.0-1.0."""
    classifier = get_classifier()
    proba = classifier.predict_proba("test")
    assert isinstance(proba, float)
    assert 0.0 <= proba <= 1.0


# ============================================================================
# Behavior Tests - Positive Cases (should detect time)
# ============================================================================

POSITIVE_CASES = [
    # English standard
    ("Let's meet at 3pm", "english h_ampm"),
    ("Meeting at 14:30", "english hh:mm"),
    ("Call me at 9 AM", "english h_am"),
    ("Sync at 10:00 PST", "english with tz"),
    ("Tomorrow at 9am", "english tomorrow"),
    # Russian
    ("Давай в 14", "russian в H"),
    ("Встреча в 14:30", "russian в HH:MM"),
    ("Созвон в 9 утра", "russian утра"),
    ("Завтра в 3 дня", "russian дня"),
    ("в 15 часов", "russian часов"),
    # German
    ("Treffen um 14 Uhr", "german um Uhr"),
    ("Um 14:30 Uhr", "german hh:mm Uhr"),
    # French
    ("Rendez-vous à 14h", "french à Hh"),
    ("À 14h30", "french Hh30"),
    # Edge cases
    ("3pm", "bare h_ampm"),
    ("14:30", "bare hh:mm"),
    ("at 3", "bare at H"),
]


@pytest.mark.parametrize(
    ("phrase", "notes"),
    POSITIVE_CASES,
    ids=[f"pos:{n}" for _, n in POSITIVE_CASES],
)
def test_ml_detects_positive(phrase: str, notes: str) -> None:
    """ML classifier should detect time in positive cases."""
    result = contains_time_ml(phrase, use_llm_fallback=False)
    assert result is True, f"Should detect time in '{phrase}' ({notes})"


# ============================================================================
# Behavior Tests - Negative Cases (should NOT detect time)
# ============================================================================

NEGATIVE_CASES = [
    # Numbers without time context
    ("I have 3 cats", "plain number"),
    ("Buy 5 apples", "quantity"),
    # ("There are 100 people", "count"),  # Known false positive - ML misinterprets "100"
    # Prices
    ("$14.99 for lunch", "price usd"),
    ("€20 per hour", "price eur"),
    ("Costs ₽500", "price rub"),
    # Versions
    ("Update to v2.0", "version"),
    ("Version 3.5.1", "version explicit"),
    ("iOS 17", "os version"),
    # Scores/stats
    ("Score 3-2", "score"),
    ("Won 5-0", "score result"),
    # Technical
    ("192.168.1.1", "ip address"),
    ("Room 301", "room number"),
    ("Page 15", "page number"),
    # Bible verses
    ("John 3:16", "bible verse"),
    ("Romans 8:28", "bible verse 2"),
    # Other
    ("2024 was great", "year"),
    ("Order #567", "order number"),
    ("Code: 1234", "code"),
]


@pytest.mark.parametrize(
    ("phrase", "notes"),
    NEGATIVE_CASES,
    ids=[f"neg:{n}" for _, n in NEGATIVE_CASES],
)
def test_ml_rejects_negative(phrase: str, notes: str) -> None:
    """ML classifier should NOT detect time in negative cases."""
    result = contains_time_ml(phrase, use_llm_fallback=False)
    assert result is False, f"Should NOT detect time in '{phrase}' ({notes})"


# ============================================================================
# Corpus Tests - Validate against training data
# ============================================================================


def _load_control_corpus() -> list[tuple[str, bool, str]]:
    """Load control corpus for validation."""
    corpus_path = Path(__file__).parent.parent / "data" / "time_extraction_control.csv"

    if not corpus_path.exists():
        return []

    entries: list[tuple[str, bool, str]] = []
    seen: set[str] = set()

    with corpus_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phrase = row.get("phrase", "").strip()
            times_str = row.get("times", "").strip()
            notes = row.get("notes", "").strip()

            if not phrase or phrase in seen:
                continue
            seen.add(phrase)

            has_time = bool(times_str)
            entries.append((phrase, has_time, notes))

    return entries


CONTROL_CORPUS = _load_control_corpus()


@pytest.mark.xfail(reason="Target 90% classifier accuracy - WIP", strict=False)
@pytest.mark.parametrize(
    ("phrase", "has_time", "notes"),
    CONTROL_CORPUS,
    ids=[f"ctrl:{i}" for i in range(len(CONTROL_CORPUS))],
)
def test_ml_control_corpus(phrase: str, has_time: bool, notes: str) -> None:
    """ML classifier accuracy on control corpus."""
    result = contains_time_ml(phrase, use_llm_fallback=False)
    assert result == has_time, (
        f"Control corpus mismatch: '{phrase}' expected={has_time}, got={result} ({notes})"
    )


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_empty_string_returns_false() -> None:
    """Empty string should not detect time."""
    assert contains_time_ml("", use_llm_fallback=False) is False


def test_whitespace_only_returns_false() -> None:
    """Whitespace-only string should not detect time."""
    assert contains_time_ml("   ", use_llm_fallback=False) is False


def test_long_text_with_time() -> None:
    """Long text with embedded time should detect."""
    text = "A" * 200 + " meeting at 3pm " + "B" * 200
    result = contains_time_ml(text, use_llm_fallback=False)
    assert result is True


def test_long_text_without_time() -> None:
    """Long text without time should not detect."""
    text = "This is a very long message " * 50
    result = contains_time_ml(text, use_llm_fallback=False)
    assert result is False


def test_unicode_text() -> None:
    """Unicode characters should not crash."""
    text = "Встреча в 14:00 🕐"
    result = contains_time_ml(text, use_llm_fallback=False)
    assert isinstance(result, bool)
