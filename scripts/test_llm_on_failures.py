#!/usr/bin/env python3
"""Test LLM fallback on real message failures.

Tests specific cases where ML classifier or parser failed.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.llm_fallback import detect_time_with_llm

# ML Classifier failures (6 cases)
ML_FAILURES = [
    # False Negatives (should be True)
    ("Please ensure all tickets are closed by 5pm today before the sprint ends", True, "FN - deadline context"),
    ("Meeting confirmed: 2026-01-22 at 14:00 CET in the main conference room", True, "FN - formal confirmation"),
    ("Please review the pull request #1234 before 5pm and leave your comments", True, "FN - PR + deadline"),

    # False Positives (should be False)
    ("Ребят, кто может посмотреть тикет #404? Клиент жалуется на ошибку", False, "FP - ticket number"),
    ("Смотри, в отчете на странице 15 есть интересная статистика", False, "FP - page number"),
    ("The odds are 5:1 that we'll finish the feature this week", False, "FP - odds/ratio"),
]

# Parser failures (12 cases) - all should contain time
PARSER_FAILURES = [
    ("Let's meet at the usual place around 7ish?", True, "approximate colloquial"),
    ("Set an alarm for 6:30am", True, "alarm instruction"),  # This should work with regex!
    ("Мы стартуем в 9 утра по Москве", True, "russian tz context"),
    ("Let's sync up at 1100 hours military time", True, "military formal"),
    ("The deadline is COB Friday", True, "COB = close of business"),
    ("I'll ping you EOD", True, "EOD = end of day"),
    ("Встреча перенесена на полдень", True, "russian noon"),
    ("Join the standup at half past nine", True, "half past"),
    ("The train leaves quarter to six", True, "quarter to"),
    ("У нас созвон через полчаса", True, "russian relative"),
    ("Be ready by noon sharp", True, "noon explicit"),
    ("We start at midnight", True, "midnight explicit"),
]


async def test_cases(cases: list[tuple[str, bool, str]], label: str) -> tuple[int, int, list]:
    """Test cases against LLM fallback."""
    correct = 0
    total = len(cases)
    errors = []

    print(f"\n{'='*60}")
    print(f"Testing {label}: {total} cases")
    print('='*60)

    for text, expected, notes in cases:
        result = await detect_time_with_llm(text)
        status = "✓" if result == expected else "✗"

        if result == expected:
            correct += 1
            print(f"{status} [{notes}]")
        else:
            error_type = "FP" if result else "FN"
            errors.append((text, expected, result, notes, error_type))
            print(f"{status} [{error_type}] [{notes}]")
            print(f"   Text: {text[:60]}...")
            print(f"   Expected: {expected}, Got: {result}")

    return correct, total, errors


async def main():
    print("Testing LLM Fallback on Real Message Failures")
    print("="*60)

    # Test ML failures
    ml_correct, ml_total, ml_errors = await test_cases(ML_FAILURES, "ML Classifier Failures")

    # Test Parser failures
    parser_correct, parser_total, parser_errors = await test_cases(PARSER_FAILURES, "Parser Failures")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"ML Failures tested:     {ml_correct}/{ml_total} ({100*ml_correct/ml_total:.1f}%)")
    print(f"Parser Failures tested: {parser_correct}/{parser_total} ({100*parser_correct/parser_total:.1f}%)")

    total_correct = ml_correct + parser_correct
    total_cases = ml_total + parser_total
    print(f"TOTAL:                  {total_correct}/{total_cases} ({100*total_correct/total_cases:.1f}%)")

    if ml_errors or parser_errors:
        print("\n" + "="*60)
        print("REMAINING ERRORS")
        print("="*60)
        for text, _expected, _got, notes, error_type in ml_errors + parser_errors:
            print(f"[{error_type}] {notes}")
            print(f"    {text[:70]}...")


if __name__ == "__main__":
    asyncio.run(main())
