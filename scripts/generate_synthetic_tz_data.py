#!/usr/bin/env python3
"""Generate synthetic data for TZ Context Trigger training.

Creates variations of timezone-related phrases using templates and random elements.
Focuses on edge cases that are hard to collect naturally.

Usage:
    python scripts/generate_synthetic_tz_data.py
    python scripts/generate_synthetic_tz_data.py --output data/tz_context_trigger_synthetic.csv
    python scripts/generate_synthetic_tz_data.py --merge  # Merge with main dataset
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "tz_context_trigger_synthetic.csv"
MAIN_DATASET = DATA_DIR / "tz_context_trigger_train.csv"


@dataclass
class Sample:
    """A training sample."""

    phrase: str
    has_tz_context: int
    trigger_type: str
    source_tz: str
    notes: str


# ============================================================================
# Templates and Variations
# ============================================================================

# Time variations
TIMES_24H = ["10:00", "14:30", "16:45", "09:15", "21:00", "12:00", "15:00", "18:30"]
TIMES_12H = ["3pm", "10am", "5:30pm", "9am", "12pm", "6pm", "11am", "8:30pm"]
TIMES_RU = ["в 10", "в 3", "в 15", "в час", "в полдень", "в 16:30", "в девять"]

# TZ abbreviations
TZ_ABBREVS_RU = [
    ("Мск", "Europe/Moscow"),
    ("мск", "Europe/Moscow"),
    ("MSK", "Europe/Moscow"),
    ("Спб", "Europe/Moscow"),  # Same TZ as Moscow
]

TZ_ABBREVS_EN = [
    ("PST", "America/Los_Angeles"),
    ("PDT", "America/Los_Angeles"),
    ("EST", "America/New_York"),
    ("EDT", "America/New_York"),
    ("CST", "America/Chicago"),
    ("GMT", "Europe/London"),
    ("UTC", "UTC"),
    ("CET", "Europe/Paris"),
    ("JST", "Asia/Tokyo"),
]

# Cities with their timezones
CITIES_RU = [
    ("Москве", "Europe/Moscow"),
    ("Тбилиси", "Asia/Tbilisi"),
    ("Минску", "Europe/Minsk"),
    ("Киеву", "Europe/Kyiv"),
    ("Берлину", "Europe/Berlin"),
    ("Лондону", "Europe/London"),
    ("Парижу", "Europe/Paris"),
]

CITIES_EN = [
    ("London", "Europe/London"),
    ("New York", "America/New_York"),
    ("Tokyo", "Asia/Tokyo"),
    ("Berlin", "Europe/Berlin"),
    ("Paris", "Europe/Paris"),
]

# Context prefixes/suffixes (добавляют "шум" к фразам)
PREFIXES_RU = ["", "окей ", "хорошо ", "ладно ", "давай ", "ок "]
SUFFIXES_RU = ["", "?", "!", " ок?", " норм?", " подходит?"]
PREFIXES_EN = ["", "ok ", "sure ", "sounds good ", "let's do ", "how about "]
SUFFIXES_EN = ["", "?", "!", " ok?", " works?", " good?"]

# ============================================================================
# Positive Examples (has_tz_context=1)
# ============================================================================


def generate_explicit_tz_ru() -> list[Sample]:
    """Generate Russian explicit TZ examples."""
    samples = []

    # Pattern: время + Мск/msk
    for time in TIMES_RU:
        for abbrev, tz in TZ_ABBREVS_RU:
            prefix = random.choice(PREFIXES_RU)
            suffix = random.choice(SUFFIXES_RU)
            phrase = f"{prefix}{time} {abbrev}{suffix}"
            samples.append(Sample(phrase.strip(), 1, "explicit_tz", tz, f"time + {abbrev}"))

    # Pattern: "по" + город
    for time in TIMES_RU:
        for city, tz in CITIES_RU:
            prefix = random.choice(PREFIXES_RU)
            phrase = f"{prefix}{time} по {city}"
            samples.append(Sample(phrase.strip(), 1, "explicit_tz", tz, f"по {city}"))

    # Pattern: "по московскому/местному времени"
    adjectives = ["московскому", "местному", "минскому", "киевскому", "берлинскому"]
    adj_tzs = [
        "Europe/Moscow",
        "",
        "Europe/Minsk",
        "Europe/Kyiv",
        "Europe/Berlin",
    ]
    for time in random.sample(TIMES_RU, 3):
        for adj, tz in zip(adjectives, adj_tzs, strict=False):
            phrase = f"{time} по {adj} времени"
            samples.append(Sample(phrase, 1, "explicit_tz", tz, f"по {adj} времени"))

    return samples


def generate_explicit_tz_en() -> list[Sample]:
    """Generate English explicit TZ examples."""
    samples = []

    # Pattern: time + TZ abbreviation
    for time in TIMES_12H:
        for abbrev, tz in TZ_ABBREVS_EN:
            prefix = random.choice(PREFIXES_EN)
            suffix = random.choice(SUFFIXES_EN)
            phrase = f"{prefix}{time} {abbrev}{suffix}"
            samples.append(Sample(phrase.strip(), 1, "explicit_tz", tz, f"EN time + {abbrev}"))

    # Pattern: city time
    for time in random.sample(TIMES_12H, 4):
        for city, tz in CITIES_EN:
            phrase = f"{time} {city} time"
            samples.append(Sample(phrase, 1, "explicit_tz", tz, f"{city} time"))

    # Pattern: UTC offset
    for time in random.sample(TIMES_12H, 3):
        for offset in ["+3", "-5", "+0", "-8", "+1"]:
            phrase = f"{time} UTC{offset}"
            samples.append(Sample(phrase, 1, "explicit_tz", "", f"UTC{offset}"))

    return samples


def generate_clarification_questions() -> list[Sample]:
    """Generate clarification question examples."""
    templates_ru = [
        "это по {tz}?",
        "а это по {tz}?",
        "это {tz} время?",
        "ты про {tz}?",
        "в смысле по {tz}?",
        "по какому времени?",
        "какая таймзона?",
        "какой часовой пояс?",
        "это твоё время или моё?",
        "чьё это время?",
        "а это local time?",
        "UTC или местное?",
    ]

    templates_en = [
        "is that {tz}?",
        "you mean {tz}?",
        "what timezone?",
        "which tz is that?",
        "your time or mine?",
        "is that local time?",
        "EST or PST?",
        "what time zone are we using?",
    ]

    tz_mentions_ru = ["москве", "мск", "местному", "питеру", "минску"]
    tz_mentions_en = ["PST", "EST", "GMT", "local", "your time"]

    samples = []

    for template in templates_ru:
        if "{tz}" in template:
            for tz in tz_mentions_ru:
                phrase = template.format(tz=tz)
                samples.append(Sample(phrase, 1, "clarification_question", "", "RU question"))
        else:
            samples.append(Sample(template, 1, "clarification_question", "", "RU question"))

    for template in templates_en:
        if "{tz}" in template:
            for tz in tz_mentions_en:
                phrase = template.format(tz=tz)
                samples.append(Sample(phrase, 1, "clarification_question", "", "EN question"))
        else:
            samples.append(Sample(template, 1, "clarification_question", "", "EN question"))

    return samples


def generate_mixed_language() -> list[Sample]:
    """Generate mixed RU/EN examples."""
    templates = [
        ("meeting в 15 Мск", "Europe/Moscow", "mixed RU/EN"),
        ("созвон at 3pm PST", "America/Los_Angeles", "mixed"),
        ("давай call в 10 EST", "America/New_York", "mixed"),
        ("sync в 14:00 по Москве", "Europe/Moscow", "mixed"),
        ("let's meet в полдень GMT", "Europe/London", "mixed"),
    ]

    return [Sample(phrase, 1, "explicit_tz", tz, notes) for phrase, tz, notes in templates]


# ============================================================================
# Negative Examples (has_tz_context=0)
# ============================================================================


def generate_false_positives() -> list[Sample]:
    """Generate examples that should NOT trigger (false positives to avoid)."""
    samples = []

    # TZ abbreviation as part of other context
    fp_examples = [
        ("PST файл поврежден", "PST = file format"),
        ("EST-овский код", "EST in compound word"),
        ("MSK-123 тикет", "MSK = ticket prefix"),
        ("версия 3.0 MSK edition", "MSK = product variant"),
        ("GMT racing team", "GMT = brand"),
        ("CET сертификат", "CET = abbreviation"),
        ("UTC координаты", "UTC as word part"),
    ]

    for phrase, notes in fp_examples:
        samples.append(Sample(phrase, 0, "none", "", notes))

    # City as location, not timezone
    location_examples = [
        ("живу в Москве", "location not TZ"),
        ("еду в Питер", "travel destination"),
        ("был в Лондоне", "past location"),
        ("офис в Берлине", "office location"),
        ("буду в Тбилиси", "future location"),
        ("I'm in New York", "EN location"),
        ("visiting London", "EN visit"),
    ]

    for phrase, notes in location_examples:
        samples.append(Sample(phrase, 0, "none", "", notes))

    # Numbers that look like times but aren't
    number_examples = [
        ("версия 3.0", "version number"),
        ("room 15", "room number"),
        ("issue #123", "issue number"),
        ("$15 за час", "price"),
        ("15% скидка", "percentage"),
        ("3 кота", "quantity"),
        ("15 минут назад", "duration"),
        ("через 3 часа", "relative time"),
    ]

    for phrase, notes in number_examples:
        samples.append(Sample(phrase, 0, "none", "", notes))

    # Random chat messages without TZ
    random_messages = [
        ("привет как дела", "greeting"),
        ("окей понял", "acknowledgment"),
        ("спасибо за инфо", "thanks"),
        ("sounds good", "EN ack"),
        ("see you later", "EN bye"),
        ("👍", "emoji"),
        ("ок", "short ack"),
    ]

    for phrase, notes in random_messages:
        samples.append(Sample(phrase, 0, "none", "", notes))

    return samples


def generate_time_without_tz() -> list[Sample]:
    """Generate time mentions without TZ context."""
    templates = [
        "встреча в {time}",
        "созвон в {time}",
        "давай в {time}",
        "let's meet at {time}",
        "call at {time}",
        "sync at {time}",
    ]

    samples = []
    for template in templates:
        for time in random.sample(TIMES_24H, 3):
            phrase = template.format(time=time)
            samples.append(Sample(phrase, 0, "none", "", "time no TZ"))

        for time in random.sample(TIMES_12H, 3):
            phrase = template.format(time=time)
            samples.append(Sample(phrase, 0, "none", "", "time no TZ EN"))

    return samples


# ============================================================================
# Main Generation
# ============================================================================


def generate_all() -> list[Sample]:
    """Generate all synthetic samples."""
    samples = []

    # Positive examples
    samples.extend(generate_explicit_tz_ru())
    samples.extend(generate_explicit_tz_en())
    samples.extend(generate_clarification_questions())
    samples.extend(generate_mixed_language())

    # Negative examples
    samples.extend(generate_false_positives())
    samples.extend(generate_time_without_tz())

    # Shuffle
    random.shuffle(samples)

    return samples


def save_samples(samples: list[Sample], output_path: Path) -> None:
    """Save samples to CSV."""
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["phrase", "has_tz_context", "trigger_type", "source_tz", "notes"])
        for sample in samples:
            writer.writerow(
                [
                    sample.phrase,
                    sample.has_tz_context,
                    sample.trigger_type,
                    sample.source_tz,
                    sample.notes,
                ]
            )

    print(f"✓ Saved {len(samples)} samples to {output_path}")

    # Stats
    positive = sum(1 for s in samples if s.has_tz_context == 1)
    negative = len(samples) - positive
    print(f"  Positive: {positive}, Negative: {negative}")


def merge_with_main(synthetic_path: Path, main_path: Path) -> None:
    """Merge synthetic data with main dataset."""
    # Read existing main dataset
    existing_phrases = set()
    main_rows = []

    if main_path.exists():
        with main_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                main_rows.append(row)
                existing_phrases.add(row["phrase"].lower().strip())

    # Read synthetic and add non-duplicates
    added = 0
    with synthetic_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phrase_key = row["phrase"].lower().strip()
            if phrase_key not in existing_phrases:
                main_rows.append(row)
                existing_phrases.add(phrase_key)
                added += 1

    # Write back
    with main_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["phrase", "has_tz_context", "trigger_type", "source_tz", "notes"]
        )
        writer.writeheader()
        writer.writerows(main_rows)

    print(f"✓ Merged {added} new samples into {main_path}")
    print(f"  Total samples now: {len(main_rows)}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate synthetic TZ training data")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help="Output file path",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge with main dataset after generation",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )

    args = parser.parse_args()

    random.seed(args.seed)

    # Generate
    samples = generate_all()
    save_samples(samples, args.output)

    # Optionally merge
    if args.merge:
        merge_with_main(args.output, MAIN_DATASET)


if __name__ == "__main__":
    main()
