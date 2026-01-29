#!/usr/bin/env python3
"""Test edge cases for LocationChangeTrigger."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.location_change_trigger import get_classifier

classifier = get_classifier()

# Edge cases
edge_cases = [
    # Tricky positives (should trigger)
    ("погода в Москве отличная", True, "weather mention"),
    ("новости из Берлина", True, "news from"),
    ("ты в Питере?", True, "question"),
    ("are you in Paris?", True, "en question"),
    ("буду в Тбилиси на неделю", True, "future travel"),
    # Tricky negatives (should NOT trigger)
    ("версия Москва-3", False, "version name"),
    ("код 495", False, "area code"),
    ("московское время", False, "time reference"),
    ("встреча в 15:00", False, "meeting time"),
    ("отчет готов", False, "status update"),
    ("ticket #123", False, "ticket number"),
    ("давай созвонимся", False, "call request"),
    ("all good here", False, "status"),
    # Borderline cases
    ("еду домой", False, "going home - no specific location"),
    ("в пути", False, "on the way - no location"),
    ("Москва — столица России", True, "factual statement"),
]

print("Edge Case Testing:")
print("-" * 60)

correct = 0
errors = []
for text, expected, note in edge_cases:
    result = classifier.predict(text)
    is_correct = result.triggered == expected
    if is_correct:
        correct += 1
        status = "✓"
    else:
        status = "✗"
        errors.append((text, expected, result.triggered, result.confidence, note))
    print(f'{status} [{note}] "{text}" -> {result.triggered} (conf={result.confidence:.2f})')

print("-" * 60)
print(f"Result: {correct}/{len(edge_cases)} correct ({100 * correct / len(edge_cases):.0f}%)")

if errors:
    print("\nErrors:")
    for _text, expected, got, conf, note in errors:
        print(f"  - {note}: expected {expected}, got {got} (conf={conf:.2f})")
