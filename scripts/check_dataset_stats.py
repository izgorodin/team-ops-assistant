#!/usr/bin/env python3
"""Quick script to check dataset statistics."""

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


train = load_csv(ROOT / "data/tz_location_change_train.csv")
test = load_csv(ROOT / "data/tz_location_change_test.csv")

print("=== Train Dataset ===")
print(f"Total: {len(train)}")
pos_train = sum(1 for r in train if r["has_location_change"] == "1")
neg_train = sum(1 for r in train if r["has_location_change"] == "0")
print(f"Positive: {pos_train}")
print(f"Negative: {neg_train}")
trigger_types_train = Counter(r["trigger_type"] for r in train)
print(f"Trigger types: {dict(trigger_types_train)}")
print()
print("=== Test Dataset ===")
print(f"Total: {len(test)}")
pos_test = sum(1 for r in test if r["has_location_change"] == "1")
neg_test = sum(1 for r in test if r["has_location_change"] == "0")
print(f"Positive: {pos_test}")
print(f"Negative: {neg_test}")
trigger_types_test = Counter(r["trigger_type"] for r in test)
print(f"Trigger types: {dict(trigger_types_test)}")
print()

# Check overlap
train_phrases = {r["phrase"].lower() for r in train}
test_phrases = {r["phrase"].lower() for r in test}
overlap = train_phrases & test_phrases
print("=== Overlap Check ===")
print(f"Overlap count: {len(overlap)}")
if overlap:
    print(f"Examples: {list(overlap)[:5]}")
