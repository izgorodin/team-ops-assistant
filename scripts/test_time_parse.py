#!/usr/bin/env python
"""Quick test for time parsing with RU patterns."""

from src.core.time_parse import parse_times

# Test cases
tests = [
    "встреча в 15 Мск",
    "созвон в 14 по Тбилиси",
    "давай в 3pm PST",
    "в 10 по московскому времени",
    "завтра в 11 по Минску",
    "в 16:30 мск",
    "на 12 по Москве",
]

for t in tests:
    result = parse_times(t)
    if result:
        print(f"{t!r} -> hour={result[0].hour}, tz={result[0].timezone_hint}")
    else:
        print(f"{t!r} -> NO TIMES")
