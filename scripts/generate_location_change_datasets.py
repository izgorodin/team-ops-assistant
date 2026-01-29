#!/usr/bin/env python3
from __future__ import annotations

import csv
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

HEADER = ["phrase", "has_location_change", "trigger_type", "location", "notes"]
ROOT = Path(__file__).resolve().parents[1]

# Adjusted to fit available templates (3900 pos, 655 neg)
# Use all negatives, split proportionally
TRAIN_TOTAL = 2000
TRAIN_POS = 1500
TRAIN_NEG = 500

TEST_TOTAL = 500
TEST_POS = 400
TEST_NEG = 100


def write_csv(path: Path, rows: Iterable[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        writer.writerows(rows)


def add_row(
    rows: list[list[str]],
    seen: set[str],
    phrase: str,
    has_change: int,
    trigger_type: str,
    location: str = "",
    notes: str = "",
) -> None:
    phrase = phrase.strip()
    if not phrase:
        return
    if phrase in seen:
        return
    seen.add(phrase)
    rows.append([phrase, str(has_change), trigger_type, location, notes])


def take_n(rows: list[list[str]], n: int) -> list[list[str]]:
    return rows[:n]


def build_positive_templates(cities: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    seen: set[str] = set()

    change_verbs = [
        "переехал в",
        "переехала в",
        "перебрался в",
        "теперь в",
        "сейчас в",
        "теперь живу в",
        "живу в",
        "буду в",
        "лечу в",
        "прилетаю в",
        "приехал в",
        "приехала в",
        "нахожусь в",
        "я в",
    ]
    context_suffix = ["", "на неделю", "пока", "до пятницы", "сегодня", "на выходных"]

    for verb, city, suffix in product(change_verbs, cities, context_suffix):
        add_row(
            rows, seen, f"{verb} {city} {suffix}".strip(), 1, "explicit_location", city, "ru loc"
        )

    questions = [
        "ты в",
        "вы в",
        "а ты сейчас в",
        "ты уже в",
        "мы в",
    ]
    for q, city in product(questions, cities):
        add_row(rows, seen, f"{q} {city}?", 1, "question", city, "ru question")

    change_phrases = [
        "раньше был",
        "раньше была",
        "был в",
        "была в",
        "до этого был",
        "до этого была",
        "уехал в",
        "уехала в",
        "съехал в",
        "съехала в",
    ]
    for phrase, city in product(change_phrases, cities):
        add_row(rows, seen, f"{phrase} {city}", 1, "change_phrase", city, "ru change")

    weather_phrases = [
        "погода в",
        "в",
        "шторм в",
        "дождь в",
        "снег в",
        "жара в",
    ]
    for prefix, city in product(weather_phrases, cities):
        add_row(rows, seen, f"{prefix} {city}", 1, "explicit_location", city, "weather")

    news_phrases = [
        "новости из",
        "репортаж из",
        "в",
        "срочно из",
        "сообщают из",
    ]
    for prefix, city in product(news_phrases, cities):
        add_row(rows, seen, f"{prefix} {city}", 1, "explicit_location", city, "news")

    en_verbs = [
        "I am in",
        "we are in",
        "now in",
        "moving to",
        "moved to",
        "flying to",
        "landing in",
        "based in",
        "living in",
    ]
    for verb, city in product(en_verbs, cities):
        add_row(rows, seen, f"{verb} {city}", 1, "explicit_location", city, "en loc")

    en_questions = [
        "are you in",
        "are we in",
        "are you already in",
        "are you still in",
    ]
    for verb, city in product(en_questions, cities):
        add_row(rows, seen, f"{verb} {city}?", 1, "question", city, "en question")

    en_weather = ["weather in", "storm in", "snow in", "heat in"]
    for prefix, city in product(en_weather, cities):
        add_row(rows, seen, f"{prefix} {city}", 1, "explicit_location", city, "en weather")

    mixed = [
        "meeting в",
        "созвон from",
        "я сейчас in",
        "переехал to",
    ]
    for prefix, city in product(mixed, cities):
        add_row(rows, seen, f"{prefix} {city}", 1, "explicit_location", city, "mixed")

    return rows


def build_negative_templates() -> list[list[str]]:
    rows: list[list[str]] = []
    seen: set[str] = set()

    neutrals = [
        "привет",
        "ок",
        "спасибо",
        "понял",
        "готово",
        "на связи",
        "переносим",
        "созвон отменяем",
        "позже напишу",
        "sounds good",
        "roger",
        "all good",
        "готовлю отчёт",
        "делаю задачу",
        "всё ок",
        "вопрос решен",
        "перерыв",
        "жду фидбек",
    ]
    for phrase in neutrals:
        add_row(rows, seen, phrase, 0, "none", "", "neutral")

    number_contexts = [
        "версия",
        "room",
        "ticket",
        "code",
        "номер",
        "задач",
        "статус",
        "релиз",
        "оценка",
        "пакет",
        "скидка",
        "процент",
        "итого",
        "балл",
    ]
    numbers = ["3.0", "15", "123", "404", "5", "12", "20", "30", "50", "100", "2.5"]
    for ctx, num in product(number_contexts, numbers):
        add_row(rows, seen, f"{ctx} {num}", 0, "none", "", "number")

    time_like = [
        "3:2",
        "4:1",
        "10:5",
        "2:0",
        "score 4:1",
        "счёт 3:2",
    ]
    for phrase in time_like:
        add_row(rows, seen, phrase, 0, "none", "", "score")

    money_contexts = ["$", "€", "₽", "стоимость", "цена", "invoice", "fee", "rate"]
    money_values = ["15", "20", "99", "14.50", "1200", "350", "10%", "5%"]
    for ctx, val in product(money_contexts, money_values):
        add_row(
            rows,
            seen,
            f"{ctx}{val}" if ctx in ["$", "€", "₽"] else f"{ctx} {val}",
            0,
            "none",
            "",
            "money",
        )

    misc = [
        "давай потом",
        "без изменений",
        "все по плану",
        "send the report",
        "working on it",
        "thanks",
        "call later",
        "on it",
        "need help",
        "через час",
        "созвонимся позже",
        "без локации",
        "просто сообщение",
    ]
    for phrase in misc:
        add_row(rows, seen, phrase, 0, "none", "", "misc")

    verbs = [
        "подготовь",
        "проверь",
        "отправь",
        "сделай",
        "исправь",
        "обнови",
        "заверши",
        "согласуй",
        "закоммить",
        "запусти",
        "stop",
        "start",
        "pause",
        "finish",
        "review",
        "update",
        "share",
        "submit",
        "close",
        "open",
    ]
    objects = [
        "задачу",
        "тикет",
        "отчет",
        "сборку",
        "деплой",
        "документ",
        "таблицу",
        "презентацию",
        "план",
        "файл",
        "календарь",
        "описание",
        "комментарий",
        "лог",
        "таб",
        "issue",
        "PR",
        "status",
        "draft",
        "note",
    ]
    for verb, obj in product(verbs, objects):
        add_row(rows, seen, f"{verb} {obj}", 0, "none", "", "task")

    return rows


def build_dataset(total: int, pos_target: int, neg_target: int, seed: int) -> list[list[str]]:
    import random

    cities = [
        "Москва",
        "Питер",
        "Санкт-Петербург",
        "Берлин",
        "Париж",
        "Лондон",
        "Тбилиси",
        "Киев",
        "Минск",
        "Рига",
        "Прага",
        "Варшава",
        "Рим",
        "Барселона",
        "Стамбул",
        "Дубай",
        "Токио",
        "Сеул",
        "Сингапур",
        "Нью-Йорк",
        "Лос-Анджелес",
        "Сан-Франциско",
        "Торонто",
        "Монреаль",
        "Мехико",
        "Сан-Паулу",
        "Буэнос-Айрес",
        "Кейптаун",
        "Сидней",
        "Окленд",
    ]

    positive_rows = build_positive_templates(cities)
    negative_rows = build_negative_templates()

    # Shuffle with seed for reproducibility
    rng = random.Random(seed)
    rng.shuffle(positive_rows)
    rng.shuffle(negative_rows)

    if len(positive_rows) < pos_target:
        raise RuntimeError(f"positive templates insufficient: {len(positive_rows)}")
    if len(negative_rows) < neg_target:
        raise RuntimeError(f"negative templates insufficient: {len(negative_rows)}")

    pos = positive_rows[:pos_target]
    neg = negative_rows[:neg_target]

    rows = pos + neg
    if len(rows) != total:
        raise AssertionError(f"expected {total} rows, got {len(rows)}")

    return rows


def main() -> None:
    import random

    cities = [
        "Москва",
        "Питер",
        "Санкт-Петербург",
        "Берлин",
        "Париж",
        "Лондон",
        "Тбилиси",
        "Киев",
        "Минск",
        "Рига",
        "Прага",
        "Варшава",
        "Рим",
        "Барселона",
        "Стамбул",
        "Дубай",
        "Токио",
        "Сеул",
        "Сингапур",
        "Нью-Йорк",
        "Лос-Анджелес",
        "Сан-Франциско",
        "Торонто",
        "Монреаль",
        "Мехико",
        "Сан-Паулу",
        "Буэнос-Айрес",
        "Кейптаун",
        "Сидней",
        "Окленд",
    ]

    # Generate all templates
    positive_rows = build_positive_templates(cities)
    negative_rows = build_negative_templates()

    print(f"Generated {len(positive_rows)} positive, {len(negative_rows)} negative templates")

    # Shuffle with fixed seed for reproducibility
    rng = random.Random(42)
    rng.shuffle(positive_rows)
    rng.shuffle(negative_rows)

    # Split into train/test without overlap
    total_pos_needed = TRAIN_POS + TEST_POS
    total_neg_needed = TRAIN_NEG + TEST_NEG

    if len(positive_rows) < total_pos_needed:
        raise RuntimeError(f"Need {total_pos_needed} positive, have {len(positive_rows)}")
    if len(negative_rows) < total_neg_needed:
        raise RuntimeError(f"Need {total_neg_needed} negative, have {len(negative_rows)}")

    # Train gets first portion, test gets next portion (no overlap)
    train_pos = positive_rows[:TRAIN_POS]
    test_pos = positive_rows[TRAIN_POS : TRAIN_POS + TEST_POS]

    train_neg = negative_rows[:TRAIN_NEG]
    test_neg = negative_rows[TRAIN_NEG : TRAIN_NEG + TEST_NEG]

    train_rows = train_pos + train_neg
    test_rows = test_pos + test_neg

    # Verify no overlap
    train_phrases = {r[0].lower() for r in train_rows}
    test_phrases = {r[0].lower() for r in test_rows}
    overlap = train_phrases & test_phrases
    if overlap:
        raise RuntimeError(f"Overlap detected: {len(overlap)} phrases")

    write_csv(ROOT / "data" / "tz_location_change_train.csv", train_rows)
    write_csv(ROOT / "data" / "tz_location_change_test.csv", test_rows)

    print(f"train rows: {len(train_rows)} ({len(train_pos)} pos, {len(train_neg)} neg)")
    print(f"test rows: {len(test_rows)} ({len(test_pos)} pos, {len(test_neg)} neg)")
    print("No overlap between train and test ✓")


if __name__ == "__main__":
    main()
