#!/usr/bin/env python3
"""Analyze probability distribution to find optimal thresholds."""

import csv
from pathlib import Path

from src.core.time_classifier import get_classifier

clf = get_classifier()

# Load control corpus
with Path("data/time_extraction_control.csv").open() as f:
    reader = csv.DictReader(f)
    rows = list(reader)

pos = [r for r in rows if r["times"].strip()]
neg = [r for r in rows if not r["times"].strip()]

# Analyze distribution
pos_probs = [clf.predict_proba(r["phrase"]) for r in pos]
neg_probs = [clf.predict_proba(r["phrase"]) for r in neg]

print("=== Probability Distribution ===\n")

buckets = [
    (0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
    (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)
]

print("Bucket     | Positives | Negatives | Notes")
print("-" * 55)
for low, high in buckets:
    pos_count = sum(1 for p in pos_probs if low <= p < high)
    neg_count = sum(1 for p in neg_probs if low <= p < high)
    notes = ""
    if 0.3 <= low < 0.7:
        notes = "← uncertain"
    print(f"{low:.1f} - {high:.1f}  |    {pos_count:3d}    |    {neg_count:3d}     | {notes}")

print(f"\nTotal: {len(pos)} positives, {len(neg)} negatives")

# Test different thresholds
for low_t, high_t in [(0.3, 0.7), (0.4, 0.6), (0.45, 0.55), (0.48, 0.52)]:
    uncertain_pos = sum(1 for p in pos_probs if low_t <= p <= high_t)
    uncertain_neg = sum(1 for p in neg_probs if low_t <= p <= high_t)
    total_unc = uncertain_pos + uncertain_neg
    print(f"\nThresholds ({low_t:.2f} / {high_t:.2f}): {total_unc}/{len(rows)} = {total_unc/len(rows)*100:.1f}% uncertain")

# Error analysis with 0.48/0.52
print("\n=== Error Analysis (0.48/0.52) ===\n")
LOW, HIGH = 0.48, 0.52
false_neg, false_pos = 0, 0

for r in rows:
    prob = clf.predict_proba(r["phrase"])
    has_time = bool(r["times"].strip())

    if has_time and prob < LOW:
        false_neg += 1
        print(f"FALSE NEG ({prob:.2f}): {r['phrase'][:60]}")
    elif not has_time and prob > HIGH:
        false_pos += 1
        print(f"FALSE POS ({prob:.2f}): {r['phrase'][:60]}")

print(f"\nFalse negatives: {false_neg}")
print(f"False positives: {false_pos}")
