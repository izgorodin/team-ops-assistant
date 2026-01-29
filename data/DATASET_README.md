# Time Detection Dataset

## Overview

Dataset for training ML classifiers to detect time references and timezone context in messages.

## Files

### Time Extraction (Time Detection)

| File | Description | Samples |
|------|-------------|---------|
| `time_extraction_train.csv` | Training data | 791 |
| `time_extraction_control.csv` | Held-out validation | 258 |
| `time_extraction_real_messages.csv` | Real-world test messages | 69 |
| `time_classifier.pkl` | Trained model | - |

### TZ Context Trigger (Timezone Detection)

| File | Description | Purpose |
|------|-------------|---------|
| `tz_context_trigger_train.csv` | Training data | ML classifier training |
| `tz_context_trigger_test.csv` | Test set | Model evaluation |
| `tz_context_trigger_validation.csv` | Edge cases | Final validation |
| `tz_context_trigger_synthetic.csv` | Auto-generated | Augmentation (optional) |
| `tz_context_trigger.pkl` | Trained model | - |

### Location Change Trigger

| File | Description | Purpose |
|------|-------------|---------|
| `tz_location_change_train.csv` | Training data | ML classifier training |
| `tz_location_change_test.csv` | Test set | Model evaluation |
| `location_change_trigger.pkl` | Trained model | - |

### Other

| File | Description |
|------|-------------|
| `timezone_signals_train.csv` | Regex extraction patterns |
| `archive/` | Old/temp files |

---

## TZ Context Trigger Dataset

### Format

```csv
phrase,has_tz_context,trigger_type,source_tz,notes
"16:30 Мск",1,explicit_tz,Europe/Moscow,time + RU abbrev
"это по москве?",1,clarification_question,,question about TZ
"встреча в 12",0,none,,no TZ signal
```

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `phrase` | string | Message text |
| `has_tz_context` | 0/1 | Does message have TZ context? |
| `trigger_type` | enum | `explicit_tz`, `clarification_question`, `none` |
| `source_tz` | string | IANA timezone (e.g., `Europe/Moscow`) or empty |
| `notes` | string | Category/explanation |

### Trigger Types

| Type | Description | Examples |
|------|-------------|----------|
| `explicit_tz` | Explicit TZ mention | "16:30 Мск", "3pm PST", "по Тбилиси" |
| `clarification_question` | Asking about TZ | "это по москве?", "what timezone?" |
| `none` | No TZ context | "встреча в 15", "hi there" |

### Labeling Rules

**Mark as `explicit_tz` (1) when:**
- TZ abbreviation present: Мск, MSK, PST, EST, UTC, GMT, etc.
- "по + город" pattern: "по Москве", "по Тбилиси"
- "по + прилагательное + времени": "по московскому времени"
- UTC offset: "UTC+3", "GMT-5"
- City time: "London time", "Tokyo time"

**Mark as `clarification_question` (1) when:**
- Вопрос о таймзоне: "это по москве?", "какая таймзона?"
- TZ comparison: "EST or PST?", "твоё время или моё?"
- Уточнение: "в смысле по какому времени?"

**Mark as `none` (0) when:**
- Just time without TZ: "встреча в 15:00", "call at 3pm"
- City as location (not time): "еду в Москву", "I'm in London"
- TZ abbreviation in other context: "PST файл", "MSK-123 тикет"
- Numbers that look like times: "версия 3.0", "room 15"
- Relative time: "через час", "in 2 hours"

---

## Location Change Trigger Dataset

Detects when a message mentions a location that might indicate user's physical location change.

### Format

```csv
phrase,has_location,trigger_type,notes
"переехал в Берлин",1,explicit_location,RU relocation verb
"я в Москве",1,explicit_location,RU presence phrase
"привет, как дела?",0,none,greeting
```

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `phrase` | string | Message text |
| `has_location` | 0/1 | Does message mention location change? |
| `trigger_type` | enum | `explicit_location`, `change_phrase`, `question`, `none` |
| `notes` | string | Category/explanation |

### Trigger Types

| Type | Description | Examples |
|------|-------------|----------|
| `explicit_location` | Direct location mention | "я в Берлине", "I'm in London" |
| `change_phrase` | Relocation/travel phrase | "переехал в Москву", "moving to Paris" |
| `question` | Location question | "ты где сейчас?", "where are you?" |
| `none` | No location context | "привет", "let's meet" |

### Labeling Rules

**Mark as location trigger (1) when:**
- Relocation verbs: переехал, moved to, relocating
- Presence verbs: я в, I'm in, living in, based in
- Travel verbs: лечу в, flying to, landing in

**Mark as `none` (0) when:**
- Greetings without location: "привет", "hi there"
- Work updates: "закоммитил", "done with review"
- Version numbers: "v3.0", "iOS 17"
- Just city name without context: "Москва - красивый город"

---

## Time Extraction Dataset

**File:** `time_extraction_train.csv`

| Metric | Value |
|--------|-------|
| Total samples | 791 |
| Positive (has time) | 492 (62%) |
| Negative (no time) | 299 (38%) |

### Coverage

**Positives include:**
- Standard formats: `14:30`, `3pm`, `9 AM`
- Timezones: `13 GMT`, `3pm PST`, `1500Z`
- Ranges: `10-14`, `5-7pm`, `from 9 to 5`
- Russian: `в 14`, `9 утра`, `через час`
- Transport: `Flight at 14:20`, `Train 18:05`
- Labels: `Kickoff 20:45`, `ETA 14:00`
- Multilingual: German, French, Spanish, Hebrew, Armenian, etc.

**Negatives include:**
- ISO timestamps: `2024-01-15T14:30:00`
- Aspect ratios: `16:9`, `4:3`
- Scores: `3:2`, `25-23`
- Prices: `$14.99`, `99`
- Versions: `v2.0`, `iOS 17`
- IP addresses: `192.168.1.1`
- Phone numbers, order numbers, page numbers, etc.

## Control Set Statistics

**File:** `time_extraction_control.csv`

| Metric | Value |
|--------|-------|
| Total samples | 258 |
| Positive | 133 (52%) |
| Negative | 125 (48%) |

Held-out validation set - never used for training.

## Real Messages Statistics

**File:** `time_extraction_real_messages.csv`

| Metric | Value |
|--------|-------|
| Total samples | 69 |
| Positive | 39 (57%) |
| Negative | 30 (43%) |

Real-world test cases from actual chat messages.

## Model Performance

**Latest training results (2026-01-22):**

| Dataset | Accuracy |
|---------|----------|
| Control set | 91.9% |
| Real messages | 91.3% |

## CSV Format

```csv
phrase,times,notes
"Let's meet at 3pm",15:00,english standard
"I have 3 cats",,negative - number without time context
```

| Column | Description |
|--------|-------------|
| `phrase` | Message text (quoted if contains commas) |
| `times` | Time in HH:MM format, or empty for negatives |
| `notes` | Category/language/explanation |

For multiple times: `09:00;17:00` (semicolon-separated)

## LLM Fallback

When ML classifier probability is uncertain (0.3-0.7), the system
uses LLM fallback for final decision. This covers edge cases.

Thresholds:
- `p > 0.7` - confident YES
- `p < 0.3` - confident NO
- `0.3 <= p <= 0.7` - uncertain, ask LLM
