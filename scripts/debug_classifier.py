#!/usr/bin/env python3
"""Debug classifier output for specific text."""

from src.core.time_classifier import get_classifier
from src.core.time_parse import contains_time_reference

clf = get_classifier()
text = "Hello there!"
prob = clf.predict_proba(text)
result = contains_time_reference(text)

print(f"Text: {text!r}")
print(f"Probability: {prob:.3f}")
print(f"Result: {result}")
print("Thresholds: 0.48/0.52")
print("With 0.48/0.52: prob > 0.52 means YES, prob < 0.48 means NO")
