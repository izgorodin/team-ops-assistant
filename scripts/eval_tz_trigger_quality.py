#!/usr/bin/env python3
"""Evaluate TZ Context Trigger classifier quality.

Analyzes errors, finds patterns for improvement, and reports metrics.

Usage:
    python scripts/eval_tz_trigger_quality.py
    python scripts/eval_tz_trigger_quality.py --dataset data/tz_context_trigger_test.csv
    python scripts/eval_tz_trigger_quality.py --retrain  # Retrain before eval
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sklearn.metrics import classification_report, confusion_matrix

# ============================================================================
# Configuration
# ============================================================================

DATA_DIR = Path(__file__).parent.parent / "data"
TRAIN_PATH = DATA_DIR / "tz_context_trigger_train.csv"
TEST_PATH = DATA_DIR / "tz_context_trigger_test.csv"


@dataclass
class EvalResult:
    """Single evaluation result."""

    phrase: str
    expected_triggered: bool
    expected_type: str
    predicted_triggered: bool
    predicted_type: str
    confidence: float
    is_correct: bool


def load_dataset(path: Path) -> list[tuple[str, int, str]]:
    """Load dataset: (phrase, has_tz_context, trigger_type)."""
    samples = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip comments
            phrase = row.get("phrase", "")
            if phrase.startswith("#") or not phrase.strip():
                continue
            samples.append(
                (
                    phrase,
                    int(row.get("has_tz_context", 0)),
                    row.get("trigger_type", "none"),
                )
            )
    return samples


def evaluate_classifier(dataset_path: Path, retrain: bool = False) -> list[EvalResult]:
    """Run classifier on dataset and collect results."""
    from src.core.tz_context_trigger import TzContextTrigger, get_classifier, load_training_data

    if retrain:
        print("Retraining classifier...")
        texts, binary_labels, type_labels = load_training_data()
        classifier = TzContextTrigger()
        metrics = classifier.train(texts, binary_labels, type_labels)
        classifier.save()
        print(f"Train accuracy: {metrics['accuracy']:.2%}")
    else:
        classifier = get_classifier()

    samples = load_dataset(dataset_path)
    results = []

    for phrase, expected_triggered, expected_type in samples:
        prediction = classifier.predict(phrase)

        is_correct = prediction.triggered == bool(expected_triggered) and (
            not prediction.triggered or prediction.trigger_type == expected_type
        )

        results.append(
            EvalResult(
                phrase=phrase,
                expected_triggered=bool(expected_triggered),
                expected_type=expected_type,
                predicted_triggered=prediction.triggered,
                predicted_type=prediction.trigger_type,
                confidence=prediction.confidence,
                is_correct=is_correct,
            )
        )

    return results


def print_metrics(results: list[EvalResult]) -> None:
    """Print overall metrics."""
    total = len(results)
    correct = sum(1 for r in results if r.is_correct)
    accuracy = correct / total if total > 0 else 0

    print("\n" + "=" * 60)
    print("OVERALL METRICS")
    print("=" * 60)
    print(f"Accuracy: {accuracy:.2%} ({correct}/{total})")

    # Binary classification report
    y_true = [r.expected_triggered for r in results]
    y_pred = [r.predicted_triggered for r in results]

    print("\n--- Binary Classification (triggered/not) ---")
    print(classification_report(y_true, y_pred, target_names=["none", "triggered"]))

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    print("Confusion Matrix:")
    print("              Pred None  Pred Trig")
    print(f"  True None   {cm[0][0]:^9} {cm[0][1]:^9}")
    print(f"  True Trig   {cm[1][0]:^9} {cm[1][1]:^9}")


def print_errors(results: list[EvalResult], limit: int = 20) -> None:
    """Print error analysis."""
    errors = [r for r in results if not r.is_correct]

    print("\n" + "=" * 60)
    print(f"ERROR ANALYSIS ({len(errors)} errors)")
    print("=" * 60)

    # Group by error type
    false_positives = [r for r in errors if r.predicted_triggered and not r.expected_triggered]
    false_negatives = [r for r in errors if not r.predicted_triggered and r.expected_triggered]
    wrong_type = [
        r
        for r in errors
        if r.predicted_triggered and r.expected_triggered and r.predicted_type != r.expected_type
    ]

    print(f"\nFalse Positives: {len(false_positives)}")
    print(f"False Negatives: {len(false_negatives)}")
    print(f"Wrong Type: {len(wrong_type)}")

    # Show examples
    if false_positives:
        print("\n--- FALSE POSITIVES (predicted TZ context, should be none) ---")
        for r in false_positives[:limit]:
            print(f"  '{r.phrase}' → {r.predicted_type} (conf={r.confidence:.2f})")

    if false_negatives:
        print("\n--- FALSE NEGATIVES (missed TZ context) ---")
        for r in false_negatives[:limit]:
            print(f"  '{r.phrase}' (expected: {r.expected_type})")

    if wrong_type:
        print("\n--- WRONG TYPE (triggered but wrong category) ---")
        for r in wrong_type[:limit]:
            print(f"  '{r.phrase}' → {r.predicted_type}, expected {r.expected_type}")


def analyze_confidence(results: list[EvalResult]) -> None:
    """Analyze confidence distribution."""
    print("\n" + "=" * 60)
    print("CONFIDENCE ANALYSIS")
    print("=" * 60)

    # Buckets
    buckets: dict[str, list[EvalResult]] = defaultdict(list)
    for r in results:
        if r.confidence < 0.5:
            bucket = "0.0-0.5"
        elif r.confidence < 0.7:
            bucket = "0.5-0.7"
        elif r.confidence < 0.9:
            bucket = "0.7-0.9"
        else:
            bucket = "0.9-1.0"
        buckets[bucket].append(r)

    print("\nAccuracy by confidence bucket:")
    for bucket in ["0.0-0.5", "0.5-0.7", "0.7-0.9", "0.9-1.0"]:
        items = buckets[bucket]
        if items:
            acc = sum(1 for r in items if r.is_correct) / len(items)
            print(f"  {bucket}: {acc:.2%} ({len(items)} samples)")

    # Low confidence errors
    low_conf_errors = [r for r in results if not r.is_correct and r.confidence < 0.7]
    if low_conf_errors:
        print(f"\nLow-confidence errors ({len(low_conf_errors)}):")
        for r in low_conf_errors[:10]:
            print(f"  conf={r.confidence:.2f}: '{r.phrase}'")


def find_patterns(results: list[EvalResult]) -> None:
    """Find patterns in errors for improvement."""
    print("\n" + "=" * 60)
    print("PATTERN ANALYSIS (for improvement)")
    print("=" * 60)

    errors = [r for r in results if not r.is_correct]

    # Word frequency in errors
    word_counts: dict[str, int] = defaultdict(int)
    for r in errors:
        words = r.phrase.lower().split()
        for word in words:
            word_counts[word] += 1

    # Top words in errors
    top_words = sorted(word_counts.items(), key=lambda x: -x[1])[:15]
    print("\nMost common words in errors:")
    for word, count in top_words:
        print(f"  '{word}': {count}")

    # Pattern suggestions
    print("\n--- SUGGESTED PATTERNS TO ADD ---")

    false_negatives = [r for r in errors if not r.predicted_triggered and r.expected_triggered]
    if false_negatives:
        print("\nMissed patterns (need more training data):")
        # Group by expected type
        by_type: dict[str, list[str]] = defaultdict(list)
        for r in false_negatives:
            by_type[r.expected_type].append(r.phrase)

        for typ, phrases in by_type.items():
            print(f"\n  {typ}:")
            for phrase in phrases[:5]:
                print(f"    - {phrase}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Evaluate TZ trigger classifier")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=TEST_PATH,
        help="Dataset to evaluate on",
    )
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Retrain classifier before evaluation",
    )
    parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Show only error analysis",
    )

    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"Error: Dataset not found: {args.dataset}")
        return

    print(f"Evaluating on: {args.dataset}")
    results = evaluate_classifier(args.dataset, retrain=args.retrain)

    if not args.errors_only:
        print_metrics(results)
        analyze_confidence(results)

    print_errors(results)
    find_patterns(results)


if __name__ == "__main__":
    main()
