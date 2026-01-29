#!/usr/bin/env python3
from __future__ import annotations

import csv
from itertools import product
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

HEADER = ["phrase", "has_tz_context", "trigger_type", "source_tz", "notes"]
ROOT = Path(__file__).resolve().parents[1]

TRAIN_TOTAL = 2750
TRAIN_EXPLICIT = 1100
TRAIN_CLAR = 550
TRAIN_NONE = 1100

TEST_TOTAL = 600
TEST_EXPLICIT = 240
TEST_CLAR = 120
TEST_NONE = 240

PhraseRecord = tuple[str, str, str]


def unique(seq: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def build_ru_times() -> list[str]:
    parts: list[str] = []
    for hour in range(1, 24):
        for minute in (0, 15, 30, 45):
            if minute == 0:
                parts.append(str(hour))
                parts.append(f"{hour}:00")
            else:
                parts.append(f"{hour}:{minute:02d}")
    parts.extend(["12:30", "23:59", "0:30", "0:45"])
    return unique(parts)


def build_en_times() -> list[str]:
    parts: list[str] = []
    suffixes = ["am", "pm", "a.m.", "p.m."]
    for hour in range(1, 13):
        for minute in (0, 15, 30, 45):
            for suffix in suffixes:
                if minute == 0:
                    parts.append(f"{hour}{suffix}")
                    parts.append(f"{hour} {suffix}")
                else:
                    parts.append(f"{hour}:{minute:02d}{suffix}")
                    parts.append(f"{hour}:{minute:02d} {suffix}")
        for suffix in suffixes:
            parts.append(f"{hour}:{30:02d} {suffix}")
    parts.extend(["noon", "midnight", "sunrise", "sunset"])
    return unique(parts)


RU_ABBR_CONTEXTS_TRAIN = [
    "",
    "созвон",
    "встреча",
    "call",
    "meeting",
    "доклад",
    "demo",
    "briefing",
    "интервью",
    "проверка",
]
RU_ABBR_CONTEXTS_TEST = [
    "репетиция",
    "пробный",
    "тестовый созвон",
    "быстрый звонок",
    "pre-check",
    "проверю",
    "плановый",
    "пивет",
    "напоминание",
]

PREPOSITIONS_RU = ["в", "на", "к", "примерно в", "около", "в районе", "по плану на"]
TZ_ALIAS_RU = ["Мск", "мск", "МСК", "MSK", "Msk"]

RU_PO_CITY_CONTEXTS_TRAIN = [
    "созвон",
    "встреча",
    "meetup",
    "discussion",
    "call",
    "брифинг",
]
RU_PO_CITY_CONTEXTS_TEST = [
    "репетиция по",
    "тест-сессия",
    "подготовка",
    "pre-meeting",
    "проверка",
]

RU_LOCAL_SUFFIXES_TRAIN = [
    "по московскому",
    "по местному",
    "по московскому времени",
    "по местному времени",
]
RU_LOCAL_SUFFIXES_TEST = [
    "по местному времени",
    "по московскому",
    "по локальному",
    "по authorized version",
]

EN_CONTEXTS_TRAIN = ["meeting", "call", "planning", "standup", "sync", "demo", "check-in"]
EN_CONTEXTS_TEST = ["rehearsal", "prep call", "follow-up", "test meeting", "dry run", "preview"]
EN_PREPOSITIONS = ["at", "around", ""]
EN_TZ_ABBR = [
    ("PST", "America/Los_Angeles"),
    ("PDT", "America/Los_Angeles"),
    ("EST", "America/New_York"),
    ("EDT", "America/New_York"),
    ("CST", "America/Chicago"),
    ("CDT", "America/Chicago"),
    ("BST", "Europe/London"),
    ("GMT", "Europe/London"),
    ("CET", "Europe/Paris"),
    ("CEST", "Europe/Paris"),
    ("IST", "Asia/Kolkata"),
    ("JST", "Asia/Tokyo"),
]

EN_CITIES = [
    ("London", "Europe/London"),
    ("Tokyo", "Asia/Tokyo"),
    ("Berlin", "Europe/Berlin"),
    ("Sydney", "Australia/Sydney"),
    ("New York", "America/New_York"),
    ("San Francisco", "America/Los_Angeles"),
    ("Paris", "Europe/Paris"),
    ("Dubai", "Asia/Dubai"),
    ("Singapore", "Asia/Singapore"),
    ("Toronto", "America/Toronto"),
]

UTC_OFFSETS = [
    ("UTC+3", "Europe/Moscow"),
    ("UTC+2", "Europe/Berlin"),
    ("UTC-4", "America/New_York"),
    ("UTC-5", "America/Chicago"),
    ("UTC-8", "America/Los_Angeles"),
    ("UTC+1", "Europe/Paris"),
    ("UTC+9", "Asia/Tokyo"),
    ("UTC+10", "Australia/Sydney"),
    ("UTC+0", "Europe/London"),
    ("UTC-3", "America/Sao_Paulo"),
    ("UTC+4", "Asia/Dubai"),
]

RU_CITY_TIMEZONES = [
    ("Тбилиси", "Asia/Tbilisi"),
    ("Киев", "Europe/Kyiv"),
    ("Минск", "Europe/Minsk"),
    ("Баку", "Asia/Baku"),
    ("Ереван", "Asia/Yerevan"),
    ("Ташкент", "Asia/Tashkent"),
    ("Астана", "Asia/Almaty"),
    ("Самара", "Europe/Samara"),
    ("Сочи", "Europe/Moscow"),
    ("Уфа", "Asia/Yekaterinburg"),
    ("Новосибирск", "Asia/Novosibirsk"),
    ("Магнитогорск", "Asia/Yekaterinburg"),
    ("Хабаровск", "Asia/Vladivostok"),
    ("Петропавловск", "Asia/Kamchatka"),
    ("Калининград", "Europe/Kaliningrad"),
    ("Казань", "Europe/Moscow"),
    ("Якуцк", "Asia/Yakutsk"),
    ("Якутск", "Asia/Yakutsk"),
]

RU_DAY_HINTS = ["завтра", "сегодня", "на завтра", "завтра утром", "завтра вечером"]
EN_DAY_HINTS = ["today", "tomorrow", "this afternoon", "next morning", "tonight"]

CLARIFY_RU_START = [
    "это",
    "уточни",
    "какое",
    "подскажи",
    "в каком",
    "поясни",
    "что с",
    "какая",
    "ты в",
    "что значит",
]
CLARIFY_RU_OBJECT = [
    "по мск",
    "по московскому времени",
    "по твоему времени",
    "в твоем поясе",
    "по UTC",
    "в GMT",
    "по местному",
    "по зоне +3",
    "по киевскому",
    "в московской зоне",
    "это мск",
    "в твоей зоне",
    "будет локальное время",
]
CLARIFY_RU_SUFFIX = ["?", " сейчас?", " на завтра?", " вообще?", " точно?", "?"]

CLARIFY_EN_START = [
    "what",
    "which",
    "is",
    "can you confirm",
    "should I assume",
    "are we",
    "do you mean",
    "is that",
    "what timezone",
    "where",
]
CLARIFY_EN_OBJECT = [
    "timezone",
    "tz",
    "PST",
    "EST",
    "your time",
    "London time",
    "Moscow time",
    "UTC",
    "local time",
    "Pacific time",
    "Eastern time",
    "GMT",
    "CET",
]
CLARIFY_EN_SUFFIX = ["?", " please?", " now?", " for tomorrow?", "?"]

NEG_TIME_CONTEXTS_RU = [
    "встреча",
    "звонок",
    "план",
    "время",
    "перенос",
    "сегодня",
    "на завтра",
    "сейчас",
    "ещё",
    "напомню",
    "передаю",
    "жду",
]
NEG_TIME_CONTEXTS_EN = ["meeting", "call", "planning", "check", "chat", "catch-up", "catchup"]
NEG_TIME_PREPS = ["в", "на", "к", "примерно в", "около"]
NEG_NUMBERS = ["3", "4", "5", "10", "12", "15", "20", "25", "30", "100", "301", "12.5"]
NEG_NUMBERS_EXTRA = ["номер", "порядок", "группа", "протокол", "ключ"]
NEG_NUMBER_CONTEXTS_TEST = ["сколько стоит", "номер", "вес", "примерно"]
NEG_LOCATIONS = [
    "Москва",
    "Тбилиси",
    "Берлин",
    "Нью Йорк",
    "Лос Анджелес",
    "Сан Франциско",
    "Дубай",
    "Сингапур",
    "Хьюстон",
    "Омск",
    "Байкал",
    "Казахстан",
    "Рига",
    "Минск",
    "Берн",
    "Киев",
]
NEG_LOCATION_CONTEXTS_RU = [
    "я в",
    "на связи",
    "сейчас в",
    "в командировке в",
    "в гостях в",
    "поехал в",
    "в городе",
    "родился в",
    "вернулся в",
    "в центре",
    "отсюда в",
    "в зоне",
    "находлюсь в",
    "по пути в",
    "сижу в",
    "из",
    "по адресу",
]
NEG_LOCATION_CONTEXTS_TEST = [
    "отправляюсь в",
    "скоро в",
    "сообщаю, что",
    "рядом с",
    "на пути к",
    "пишу из",
]
NEG_GENERAL_CONTEXTS = [
    "",
    "ок",
    "понятно",
    "принято",
    "давай",
    "всё",
    "хорошо",
    "держу",
    "готовьте",
    "буду",
    "пока",
    "спасибо",
]
NEG_GENERAL_PHRASES = [
    "принято",
    "на связи",
    "всё отлично",
    "готово",
    "все ясно",
    "договариваемся",
    "sounds good",
    "roger",
    "буду готов",
    "понял",
    "фиксирую",
    "принял",
    "окей, спасибо",
]
NEG_GENERAL_CONTEXTS_TEST = ["copy that", "gotcha", "will do", "noted", "thanks"]
NEG_GENERAL_PHRASES_TEST = ["asap", "will loop", "catch you later", "on it", "all good"]
NEG_PRICE_CONTEXTS = [
    "",
    "цена",
    "стоимость",
    "fee",
    "cost",
    "invoice",
    "платёж",
    "invoice for",
    "rate",
]
NEG_PRICE_VALUES = [
    "500 рублей",
    "$14.99",
    "цена 1200",
    "cost 7 dollars",
    "скидка 10%",
    "invoice 450",
    "fee 25",
    "баланс 300",
    "room rate 180",
    "rate 35",
]
NEG_PRICE_CONTEXTS_TEST = ["цена", "cost", "rate", "invoice", "fee", "quote"]
NEG_PRICE_VALUES_TEST = ["$9.99", "1200", "45 евро", "3500", "20%", "350 рублей", "$14.50"]


def _add_entry(
    entries: list[list[str]],
    seen: set[str],
    phrase: str,
    has_tz_context: int,
    trigger_type: str,
    source_tz: str = "",
    notes: str = "",
) -> None:
    phrase = phrase.strip()
    if not phrase:
        return
    if phrase in seen:
        raise ValueError(f"duplicate phrase detected: {phrase!r}")
    seen.add(phrase)
    entries.append([phrase, str(has_tz_context), trigger_type, source_tz, notes])


def _write_csv(path: Path, rows: Sequence[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(HEADER)
        writer.writerows(rows)


def fill_from_generator(
    entries: list[list[str]],
    seen: set[str],
    generator: Iterator[PhraseRecord],
    target: int,
    has_tz_context: int,
    trigger_type: str,
) -> None:
    added = 0
    for phrase, source_tz, notes in generator:
        if added >= target:
            break
        try:
            _add_entry(entries, seen, phrase, has_tz_context, trigger_type, source_tz, notes)
        except ValueError:
            continue
        added += 1
    if added < target:
        raise RuntimeError(
            f"requested {target} entries but only generated {added}; generator might be exhausted"
        )


def ru_abbr_generator(contexts: Sequence[str], times: Sequence[str]) -> Iterator[PhraseRecord]:
    for context, prep, time, tz in product(contexts, PREPOSITIONS_RU, times, TZ_ALIAS_RU):
        phrase = " ".join(part for part in [context, prep, time, tz] if part).strip()
        yield phrase, "Europe/Moscow", "explicit RU abbr"


def ru_po_city_generator(
    contexts: Sequence[str],
    times: Sequence[str],
    cities: Sequence[tuple[str, str]],
) -> Iterator[PhraseRecord]:
    for context, prep, time, (city, tz) in product(contexts, PREPOSITIONS_RU, times, cities):
        phrase = " ".join(part for part in [context, prep, time, "по", city] if part).strip()
        yield phrase, tz, "explicit RU по городу"


def ru_local_generator(
    contexts: Sequence[str],
    times: Sequence[str],
    suffixes: Sequence[str],
) -> Iterator[PhraseRecord]:
    for context, prep, time, suffix in product(contexts, PREPOSITIONS_RU, times, suffixes):
        phrase = " ".join(part for part in [context, prep, time, suffix] if part).strip()
        yield phrase, "Europe/Moscow", "explicit RU местное"


def ru_day_hint_generator(
    contexts: Sequence[str],
    times: Sequence[str],
    day_hints: Sequence[str],
) -> Iterator[PhraseRecord]:
    for context, hint, time, tz in product(contexts, day_hints, times, TZ_ALIAS_RU):
        phrase = " ".join(part for part in [context, hint, time, tz] if part).strip()
        yield phrase, "Europe/Moscow", "explicit RU day hint"


def en_abbr_generator(
    contexts: Sequence[str],
    times: Sequence[str],
    tz_options: Sequence[tuple[str, str]],
) -> Iterator[PhraseRecord]:
    for context, prep, time, (abbr, tz) in product(contexts, EN_PREPOSITIONS, times, tz_options):
        phrase = " ".join(part for part in [context, prep, time, abbr] if part).strip()
        yield phrase, tz, "explicit EN abbr"


def en_city_generator(
    contexts: Sequence[str],
    times: Sequence[str],
    cities: Sequence[tuple[str, str]],
) -> Iterator[PhraseRecord]:
    for context, prep, time, (city, tz) in product(contexts, EN_PREPOSITIONS, times, cities):
        phrase = " ".join(part for part in [context, prep, time, city, "time"] if part).strip()
        yield phrase, tz, "explicit EN city"


def utc_offset_generator(
    contexts: Sequence[str],
    offsets: Sequence[tuple[str, str]],
    times: Sequence[str],
) -> Iterator[PhraseRecord]:
    for context, prep, time, (offset, tz) in product(contexts, EN_PREPOSITIONS, times, offsets):
        phrase = " ".join(part for part in [context, prep, time, offset] if part).strip()
        yield phrase, tz, "explicit UTC offset"


def range_generator(
    contexts: Sequence[str],
    time_pairs: Sequence[tuple[str, str]],
    label: str,
    tz: str,
) -> Iterator[PhraseRecord]:
    for context, prep, (start, end) in product(contexts, PREPOSITIONS_RU, time_pairs):
        phrase = " ".join(part for part in [context, prep, f"{start}-{end}", label] if part).strip()
        yield phrase, tz, "explicit range"


def range_generator_en(
    contexts: Sequence[str],
    time_pairs: Sequence[tuple[str, str]],
    label: str,
    tz: str,
) -> Iterator[PhraseRecord]:
    for context, prep, (start, end) in product(contexts, EN_PREPOSITIONS, time_pairs):
        phrase = " ".join(part for part in [context, prep, f"{start}-{end}", label] if part).strip()
        yield phrase, tz, "explicit EN range"


def city_only_generator(
    contexts: Sequence[str],
    times: Sequence[str],
    cities: Sequence[tuple[str, str]],
) -> Iterator[PhraseRecord]:
    for context, prep, time, (city, tz) in product(contexts, PREPOSITIONS_RU, times, cities):
        phrase = " ".join(part for part in [context, prep, time, city] if part).strip()
        yield phrase, tz, "explicit city only"


def clarifier_generator(
    starts: Sequence[str],
    objects: Sequence[str],
    suffixes: Sequence[str],
    note: str,
) -> Iterator[PhraseRecord]:
    for start, obj, suffix in product(starts, objects, suffixes):
        question = " ".join(part for part in [start, obj, suffix.strip()] if part).strip()
        if not question.endswith("?"):
            question = f"{question}?"
        yield question, "", note


def none_time_generator(
    contexts: Sequence[str],
    times: Sequence[str],
    suffixes: Sequence[str],
    note: str,
) -> Iterator[PhraseRecord]:
    for context, prep, time, suffix in product(contexts, NEG_TIME_PREPS, times, suffixes):
        phrase = " ".join(part for part in [context, prep, time, suffix] if part).strip()
        yield phrase, "", note


def none_numbers_generator(
    contexts: Sequence[str], numbers: Sequence[str]
) -> Iterator[PhraseRecord]:
    for context, number in product(contexts, numbers):
        phrase = f"{context} {number}".strip()
        yield phrase, "", "none numbers"


def none_location_generator(
    contexts: Sequence[str], locations: Sequence[str]
) -> Iterator[PhraseRecord]:
    for context, location in product(contexts, locations):
        phrase = " ".join(part for part in [context, location] if part).strip()
        yield phrase, "", "none location"


def none_general_generator(
    contexts: Sequence[str],
    phrases: Sequence[str],
) -> Iterator[PhraseRecord]:
    for context, phrase in product(contexts, phrases):
        full = " ".join(part for part in [context, phrase] if part).strip()
        yield full, "", "none general"


def none_prices_generator(
    contexts: Sequence[str],
    values: Sequence[str],
) -> Iterator[PhraseRecord]:
    for context, value in product(contexts, values):
        phrase = " ".join(part for part in [context, value] if part).strip()
        yield phrase, "", "none price"


def build_training() -> tuple[list[list[str]], set[str]]:
    entries: list[list[str]] = []
    seen: set[str] = set()

    ru_times = build_ru_times()
    en_times = build_en_times()
    fill_from_generator(
        entries, seen, ru_abbr_generator(RU_ABBR_CONTEXTS_TRAIN, ru_times), 360, 1, "explicit_tz"
    )
    fill_from_generator(
        entries,
        seen,
        ru_po_city_generator(RU_PO_CITY_CONTEXTS_TRAIN, ru_times, RU_CITY_TIMEZONES),
        150,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        ru_local_generator(RU_ABBR_CONTEXTS_TRAIN, ru_times, RU_LOCAL_SUFFIXES_TRAIN),
        55,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        ru_day_hint_generator(RU_ABBR_CONTEXTS_TRAIN, ru_times, RU_DAY_HINTS),
        45,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        en_abbr_generator(EN_CONTEXTS_TRAIN, en_times, EN_TZ_ABBR),
        160,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        en_city_generator(EN_CONTEXTS_TRAIN, en_times, EN_CITIES),
        140,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        utc_offset_generator(EN_CONTEXTS_TRAIN, UTC_OFFSETS, en_times),
        90,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        range_generator(
            ["встреча", "созвон"],
            list(zip(ru_times[::5], ru_times[2::5], strict=False)),
            "Мск",
            "Europe/Moscow",
        ),
        40,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        range_generator_en(
            ["meeting", "call"],
            list(zip(en_times[::6], en_times[3::6], strict=False)),
            "PST",
            "America/Los_Angeles",
        ),
        50,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        city_only_generator(["встреча", "звонок"], ru_times, RU_CITY_TIMEZONES),
        10,
        1,
        "explicit_tz",
    )

    fill_from_generator(
        entries,
        seen,
        clarifier_generator(CLARIFY_RU_START, CLARIFY_RU_OBJECT, CLARIFY_RU_SUFFIX, "clar RU"),
        330,
        1,
        "clarification_question",
    )
    fill_from_generator(
        entries,
        seen,
        clarifier_generator(CLARIFY_EN_START, CLARIFY_EN_OBJECT, CLARIFY_EN_SUFFIX, "clar EN"),
        220,
        1,
        "clarification_question",
    )

    time_suffixes = ["сегодня", "завтра", "в этот час", ""]
    fill_from_generator(
        entries,
        seen,
        none_time_generator(NEG_TIME_CONTEXTS_RU, ru_times, time_suffixes, "none time RU"),
        340,
        0,
        "none",
    )
    fill_from_generator(
        entries,
        seen,
        none_time_generator(
            NEG_TIME_CONTEXTS_EN, en_times, ["today", "tonight", "this week", ""], "none time EN"
        ),
        170,
        0,
        "none",
    )
    fill_from_generator(
        entries, seen, none_numbers_generator(NEG_TIME_CONTEXTS_RU, NEG_NUMBERS), 120, 0, "none"
    )
    fill_from_generator(
        entries, seen, none_numbers_generator(NEG_TIME_CONTEXTS_EN, NEG_NUMBERS), 80, 0, "none"
    )
    fill_from_generator(
        entries, seen, none_numbers_generator(NEG_NUMBERS_EXTRA, NEG_NUMBERS), 20, 0, "none"
    )
    fill_from_generator(
        entries,
        seen,
        none_location_generator(NEG_LOCATION_CONTEXTS_RU, NEG_LOCATIONS),
        200,
        0,
        "none",
    )
    fill_from_generator(
        entries,
        seen,
        none_general_generator(NEG_GENERAL_CONTEXTS, NEG_GENERAL_PHRASES),
        90,
        0,
        "none",
    )
    fill_from_generator(
        entries, seen, none_prices_generator(NEG_PRICE_CONTEXTS, NEG_PRICE_VALUES), 80, 0, "none"
    )

    if len(entries) != TRAIN_TOTAL:
        raise AssertionError(
            f"training dataset should have {TRAIN_TOTAL} rows but has {len(entries)}"
        )

    return entries, seen


def build_test(train_seen: set[str]) -> list[list[str]]:
    entries: list[list[str]] = []
    seen: set[str] = set(train_seen)

    ru_times = build_ru_times()
    en_times = build_en_times()
    ranges_ru = [
        (f"{start}", f"{end}") for start, end in zip(ru_times[::-6], ru_times[::-3], strict=False)
    ]
    ranges_en = [
        (f"{start}", f"{end}") for start, end in zip(en_times[::-5], en_times[::-2], strict=False)
    ]

    fill_from_generator(
        entries, seen, ru_abbr_generator(RU_ABBR_CONTEXTS_TEST, ru_times), 75, 1, "explicit_tz"
    )
    fill_from_generator(
        entries,
        seen,
        ru_po_city_generator(RU_PO_CITY_CONTEXTS_TEST, ru_times, RU_CITY_TIMEZONES),
        35,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        ru_local_generator(RU_ABBR_CONTEXTS_TEST, ru_times, RU_LOCAL_SUFFIXES_TEST),
        15,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        ru_day_hint_generator(RU_ABBR_CONTEXTS_TEST, ru_times, RU_DAY_HINTS),
        10,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        en_abbr_generator(EN_CONTEXTS_TEST, en_times, EN_TZ_ABBR),
        45,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        en_city_generator(EN_CONTEXTS_TEST, en_times, EN_CITIES),
        30,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        utc_offset_generator(EN_CONTEXTS_TEST, UTC_OFFSETS, en_times),
        10,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        range_generator(["тест", "проба"], ranges_ru, "Мск", "Europe/Moscow"),
        5,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        range_generator_en(["demo", "trial"], ranges_en, "BST", "Europe/London"),
        5,
        1,
        "explicit_tz",
    )
    fill_from_generator(
        entries,
        seen,
        city_only_generator(["пробный", "тестовый"], ru_times, RU_CITY_TIMEZONES),
        10,
        1,
        "explicit_tz",
    )

    fill_from_generator(
        entries,
        seen,
        clarifier_generator(
            CLARIFY_RU_START, CLARIFY_RU_OBJECT, ["?", "официально?"], "clar RU test"
        ),
        70,
        1,
        "clarification_question",
    )
    fill_from_generator(
        entries,
        seen,
        clarifier_generator(CLARIFY_EN_START, CLARIFY_EN_OBJECT, ["?", "please?"], "clar EN test"),
        50,
        1,
        "clarification_question",
    )

    fill_from_generator(
        entries,
        seen,
        none_time_generator(["репетиция", "тест"], ru_times, ["сегодня", ""], "none time RU test"),
        80,
        0,
        "none",
    )
    fill_from_generator(
        entries,
        seen,
        none_time_generator(["prep call", "test"], en_times, ["today", ""], "none time EN test"),
        40,
        0,
        "none",
    )
    fill_from_generator(
        entries, seen, none_numbers_generator(NEG_NUMBER_CONTEXTS_TEST, NEG_NUMBERS), 25, 0, "none"
    )
    fill_from_generator(
        entries,
        seen,
        none_location_generator(NEG_LOCATION_CONTEXTS_TEST, NEG_LOCATIONS),
        40,
        0,
        "none",
    )
    fill_from_generator(
        entries,
        seen,
        none_general_generator(NEG_GENERAL_CONTEXTS_TEST, NEG_GENERAL_PHRASES_TEST),
        20,
        0,
        "none",
    )
    fill_from_generator(
        entries,
        seen,
        none_prices_generator(NEG_PRICE_CONTEXTS_TEST, NEG_PRICE_VALUES_TEST),
        35,
        0,
        "none",
    )

    if len(entries) != TEST_TOTAL:
        raise AssertionError(f"test dataset should have {TEST_TOTAL} rows but has {len(entries)}")

    return entries


def main() -> None:
    train_entries, seen = build_training()
    test_entries = build_test(seen)

    _write_csv(ROOT / "data" / "tz_context_trigger_train.csv", train_entries)
    _write_csv(ROOT / "data" / "tz_context_trigger_test.csv", test_entries)

    print("training rows:", len(train_entries))
    print("test rows:", len(test_entries))


if __name__ == "__main__":
    main()
