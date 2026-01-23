# Time Detection Pipeline

## Date: 2026-01-22 (Updated)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Time Detection Pipeline                       │
│                                                                  │
│  Layer 1: ML Classifier (TF-IDF + Logistic Regression)          │
│  • Binary: "Does text contain time reference?"                   │
│  • Inference: <1ms, local                                        │
│  • ~75% of messages filtered here                                │
│                          │                                       │
│                          ▼ if "yes"                              │
│  Layer 2: Regex Extraction                                       │
│  • Extracts concrete HH:MM                                       │
│  • Handles: HH:MM, Hpm/Ham, ranges, timezone suffixes            │
│  • Inference: <0.1ms                                             │
│                          │                                       │
│                          ▼ if regex failed                       │
│  Layer 3: LLM Fallback (Qwen3)                                  │
│  • Complex cases: "half past seven", "в полдень"                │
│  • Inference: 200-500ms                                          │
│  • ~5% of messages reach here                                    │
└─────────────────────────────────────────────────────────────────┘
```

**Target Accuracy:** 90%

---

## Data

**Training set:** `data/time_extraction_train.csv`
- Used to train ML classifier
- Curated for diversity and balance

**Control set:** `data/time_extraction_control.csv`
- Held-out validation data
- Not seen during training

---

## Corpus Statistics

| Metric | Value |
|--------|-------|
| Languages | EN, RU, HE, AM, ES, FR, DE, AR, JA, ZH, KO |

### Edge case coverage:

**Positive patterns:**
- Standard: HH:MM, Hpm/Ham, bare numbers with context
- Ranges: 9-17, 10:00-14:00, from 9 to 5
- Timezones: PST, EST, GMT, UTC, MSK
- Multilingual: Russian, Hebrew, Armenian, Chinese, Japanese, Korean

**Negative patterns (false positive traps):**
- Bible verses (John 3:16)
- Sports scores (Score 12:15, 25:23)
- Aspect ratios (16:9)
- Music durations (Track 03:15)
- MAC addresses, IP addresses
- Timestamps in filenames
- Versions (v2.0, 3.5.1)
- Prices ($14.99, €20)

---

## Test Structure (TDD)

```
tests/
├── test_ml_classifier.py     # Layer 1: ML classifier in isolation
│   ├── Contract tests (returns bool, is_trained, proba range)
│   └── Behavior tests (positive/negative cases)
│
├── test_time_parser.py       # Layer 2: Regex patterns in isolation
│   ├── Contract tests (PATTERNS dict exists)
│   └── Pattern tests (hh_mm, h_ampm, ranges, etc.)
│
├── test_time_detection.py    # Integration: Full pipeline on corpus
│   ├── Detection tests (contains_time_reference)
│   └── Parsing tests (parse_times extraction)
│
├── test_llm_fallback.py      # Layer 3: LLM fallback (slow, needs API)
│   └── @pytest.mark.slow     # Skip by default
│
└── test_core_handler.py      # End-to-end handler tests
```

### Running tests:

```bash
# All fast tests
pytest -v

# Skip slow LLM tests (default)
pytest -v -m "not slow"

# Include slow tests (LLM)
pytest -v -m ""

# Only pipeline tests
pytest tests/test_time_detection.py -v
```

---

## Current Results

**Last run:** 2026-01-22

### Speed improvement:
- **Before:** 256s (4+ min) — LLM fallback on uncertain cases
- **After:** 4.5s — LLM disabled via `conftest.py` autouse fixture
- **Speedup:** 57x faster

### Test breakdown:

| Test | Total | Failed | Pass Rate |
|------|-------|--------|-----------|
| detection_positive | 485 | 201 | **58%** |
| detection_negative | 302 | 45 | **85%** |
| parsing_extracts_times | 485 | 236 | **51%** |
| parsing_returns_empty | 302 | 31 | **90%** |
| **Total** | 2044 | 536 | **74%** |

### Analysis:

**Classifier (Layer 1):**
- Good on negatives: 85% (rejects FP correctly)
- Weak on positives: 58% (misses some time refs)
- Issue: Multilingual, word-based times, ranges not in training data

**Regex (Layer 2):**
- Extraction pass rate: 51% (many gaps)
- Main gaps: ranges, military time, bare numbers

### Known failures:

1. **Detection false positives:**
   - "I'll be free after 17:00" — semantic = "after"
   - Bible verses, sports scores — need context

2. **Parsing gaps (regex):**
   - Ranges: `5-7pm`, `9-5`, `10:00-14:00`
   - Military: `2200`, `0745`
   - Word times: "noon", "midnight"
   - Bare numbers: "в 14", "at 6"

3. **Multilingual:**
   - Dutch: "9 uur"
   - Greek: "στις 9"
   - Hindi: "7 बजे"

---

## Next Steps

1. **Improve regex patterns** — ranges, military time, bare numbers
2. **Retrain classifier** — add multilingual positives
3. **Target: 85%** → then 90%
