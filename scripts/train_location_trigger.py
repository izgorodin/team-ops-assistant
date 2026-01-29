#!/usr/bin/env python3
"""Train and evaluate the LocationChangeTrigger classifier."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.location_change_trigger import (
    evaluate_on_test,
    get_classifier,
    reset_classifier,
    train_from_corpus,
)


def main() -> None:
    print("=" * 60)
    print("LocationChangeTrigger Training")
    print("=" * 60)

    # Reset to force retrain
    reset_classifier()

    # Train
    print("\nTraining on corpus...")
    train_metrics = train_from_corpus(save=True)
    print("\nTraining Metrics:")
    for key, value in train_metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    # Evaluate
    print("\n" + "-" * 60)
    print("Evaluating on test set...")
    test_metrics = evaluate_on_test()
    print("\nTest Metrics:")
    for key, value in test_metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    # Quick sanity check
    print("\n" + "-" * 60)
    print("Sanity Check Examples:")

    classifier = get_classifier()
    test_cases = [
        # Positives
        ("переехал в Берлин", True),
        ("я в Москве", True),
        ("лечу в Париж завтра", True),
        ("I am in London", True),
        ("moving to New York", True),
        # Negatives
        ("привет, как дела?", False),
        ("готово, закоммитил", False),
        ("версия 3.0", False),
        ("созвон в 15:00", False),
        ("send the report", False),
    ]

    correct = 0
    for text, expected in test_cases:
        result = classifier.predict(text)
        status = "✓" if result.triggered == expected else "✗"
        if result.triggered == expected:
            correct += 1
        print(f"  {status} '{text}' -> triggered={result.triggered}, conf={result.confidence:.2f}")

    print(f"\nSanity check: {correct}/{len(test_cases)} correct")

    # Summary
    print("\n" + "=" * 60)
    accuracy = test_metrics.get("test_accuracy", 0)
    target = 0.92
    if accuracy >= target:
        print(f"✓ SUCCESS: Test accuracy {accuracy:.2%} >= {target:.0%} target")
    else:
        print(f"✗ BELOW TARGET: Test accuracy {accuracy:.2%} < {target:.0%} target")
    print("=" * 60)


if __name__ == "__main__":
    main()
