"""End-to-end pipeline tests using control dataset.

Tests the full time detection pipeline:
  Classifier → Regex → (LLM fallback disabled in tests)

Uses control.csv (held-out data not seen during training).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import NamedTuple

import pytest

from src.core.time_parse import contains_time_reference, parse_times


class ControlEntry(NamedTuple):
    """Single entry from control corpus."""

    phrase: str
    expected_times: list[str]  # Empty = negative case
    notes: str
    line_number: int


def load_control_corpus() -> list[ControlEntry]:
    """Load control corpus from CSV file."""
    corpus_path = Path(__file__).parent.parent / "data" / "time_extraction_control.csv"

    if not corpus_path.exists():
        pytest.skip(f"Control corpus not found: {corpus_path}")

    entries: list[ControlEntry] = []

    with corpus_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            phrase = row.get("phrase", "").strip()
            times_str = row.get("times", "").strip()
            notes = row.get("notes", "").strip()

            if not phrase:
                continue

            # Parse expected times
            expected_times: list[str] = []
            if times_str:
                for t in times_str.split(";"):
                    t = t.strip()
                    if t and not t.endswith("+") and not t.endswith("-"):
                        expected_times.append(t)

            entries.append(ControlEntry(phrase, expected_times, notes, i))

    return entries


# Load once at module level
CONTROL_CORPUS = load_control_corpus()
POSITIVE_CASES = [e for e in CONTROL_CORPUS if e.expected_times]
NEGATIVE_CASES = [e for e in CONTROL_CORPUS if not e.expected_times]


# ============================================================================
# E2E Detection Tests (Layer 1: Classifier)
# ============================================================================


@pytest.mark.xfail(reason="Target 90% detection accuracy - WIP", strict=False)
@pytest.mark.parametrize(
    "entry",
    POSITIVE_CASES,
    ids=[f"pos:{e.line_number}" for e in POSITIVE_CASES],
)
def test_e2e_detection_positive(entry: ControlEntry) -> None:
    """E2E: Classifier should detect time references in positive cases."""
    result = contains_time_reference(entry.phrase)
    assert result is True, (
        f"Pipeline should detect time in: '{entry.phrase}' "
        f"(expected: {entry.expected_times}, notes: {entry.notes})"
    )


@pytest.mark.xfail(reason="Target 90% detection accuracy - WIP", strict=False)
@pytest.mark.parametrize(
    "entry",
    NEGATIVE_CASES,
    ids=[f"neg:{e.line_number}" for e in NEGATIVE_CASES],
)
def test_e2e_detection_negative(entry: ControlEntry) -> None:
    """E2E: Classifier should reject negative cases."""
    result = contains_time_reference(entry.phrase)
    assert result is False, (
        f"Pipeline should NOT detect time in: '{entry.phrase}' (notes: {entry.notes})"
    )


# ============================================================================
# E2E Extraction Tests (Layer 2: Regex)
# ============================================================================


@pytest.mark.xfail(reason="Target 90% extraction accuracy - WIP", strict=False)
@pytest.mark.parametrize(
    "entry",
    POSITIVE_CASES,
    ids=[f"extract:{e.line_number}" for e in POSITIVE_CASES],
)
def test_e2e_extraction(entry: ControlEntry) -> None:
    """E2E: Regex should extract correct times from positive cases."""
    parsed = parse_times(entry.phrase)
    parsed_times = [f"{p.hour:02d}:{p.minute:02d}" for p in parsed]

    for expected in entry.expected_times:
        assert expected in parsed_times, (
            f"Expected '{expected}' not in {parsed_times} "
            f"for: '{entry.phrase}' (notes: {entry.notes})"
        )


# ============================================================================
# Pipeline Statistics
# ============================================================================


def test_pipeline_statistics() -> None:
    """Report pipeline accuracy on control corpus."""
    detection_pos_ok = 0
    detection_neg_ok = 0
    extraction_ok = 0

    for entry in POSITIVE_CASES:
        if contains_time_reference(entry.phrase):
            detection_pos_ok += 1
            parsed = parse_times(entry.phrase)
            parsed_times = [f"{p.hour:02d}:{p.minute:02d}" for p in parsed]
            if all(t in parsed_times for t in entry.expected_times):
                extraction_ok += 1

    for entry in NEGATIVE_CASES:
        if not contains_time_reference(entry.phrase):
            detection_neg_ok += 1

    total = len(CONTROL_CORPUS)
    pos_total = len(POSITIVE_CASES)
    neg_total = len(NEGATIVE_CASES)

    print(f"\n{'=' * 60}")
    print("E2E PIPELINE STATISTICS (Control Corpus)")
    print(f"{'=' * 60}")
    print(f"Total entries: {total}")
    print(f"Positive: {pos_total}, Negative: {neg_total}")
    print("\nDetection (Classifier):")
    print(f"  Positive: {detection_pos_ok}/{pos_total} = {detection_pos_ok / pos_total * 100:.1f}%")
    print(f"  Negative: {detection_neg_ok}/{neg_total} = {detection_neg_ok / neg_total * 100:.1f}%")
    print(f"  Overall:  {(detection_pos_ok + detection_neg_ok) / total * 100:.1f}%")
    print("\nExtraction (Regex on detected):")
    print(
        f"  Correct:  {extraction_ok}/{detection_pos_ok} = {extraction_ok / detection_pos_ok * 100:.1f}%"
        if detection_pos_ok
        else "  N/A"
    )
    print(f"{'=' * 60}")
