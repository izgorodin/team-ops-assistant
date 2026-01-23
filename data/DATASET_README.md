# Time Detection Dataset

## Overview

Dataset for training ML classifier to detect time references in messages.

## Files

| File | Description | Samples |
|------|-------------|---------|
| `time_extraction_train.csv` | Training data | 791 |
| `time_extraction_control.csv` | Held-out validation | 258 |
| `time_extraction_real_messages.csv` | Real-world test messages | 69 |
| `time_classifier.pkl` | Trained model | - |
| `archive/` | Old/temp files | - |

## Training Set Statistics

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
