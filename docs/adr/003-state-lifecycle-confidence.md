# ADR-003: State Lifecycle & Confidence-Based Re-verification

## Status
**Proposed** | 2026-01-24

## Context

Users' timezones can change over time (relocation, travel). The system needs to:
1. Detect when a user's timezone may have changed
2. Re-verify without being annoying
3. Maintain accuracy over time

### Current State
- Timezone saved with `confidence` field (0.0-1.0)
- `decay_per_day: 0.01` configured and **implemented** (PR #9)
- No mechanism to detect timezone changes (relocation detection pending)

### Problem
User moved from NY to London → system still converts to ET → wrong conversions forever.

## Decision

### Core Principle: Confidence as Universal Mechanism

All signals affect a single `confidence` value. When `confidence < threshold` → re-verify.

```
                    CONFIDENCE
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
 Decay              ML Detector         User Action
 (passive)          (active)            (explicit)

 -0.01/day         "переехал в X"       "change tz"
                   → confidence = 0.0    → session
```

### Signals & Their Effects

| Signal | Effect on Confidence | Notes |
|--------|---------------------|-------|
| Time decay | -0.01/day | Passive, always running |
| ML: relocation intent detected | = 0.0 (reset) | "moved to", "переехал", "now in" |
| ML: uncertain | no change | Normal messages |
| User explicitly requests change | = 0.0 → session | "change my timezone" |
| User confirms current tz | = 1.0 | After re-verification |
| tz_hint mismatch in message | **no change** | User convenience, not relocation signal |

### What is NOT a Signal

- **tz_hint mismatch**: User writes "3pm PT" while saved tz is ET
  - This is convenience for colleagues, NOT a relocation signal
  - User in NY might say "3pm PT" to help LA colleagues
  - Do NOT reduce confidence for this

### ML Detector for Relocation Intent

Simple classifier (similar to time detection):
- Input: message text
- Output: probability of relocation intent
- Training data: messages with relocation phrases

```python
RELOCATION_PATTERNS = [
    r"переехал[аи]?\s+(в\s+)?(\w+)",
    r"moved?\s+to\s+(\w+)",
    r"теперь\s+(в|живу\s+в)\s+(\w+)",
    r"now\s+(in|living\s+in)\s+(\w+)",
    r"relocated\s+to\s+(\w+)",
    r"перееха[лв]\s+в\s+(\w+)",
]
```

**Note**: Initial implementation is rule-based. ML model can be added later with more training data.

### Re-verification Flow

```
confidence < 0.7
      ↓
"Твоя таймзона всё ещё {city} ({tz})?
Напиши 'да' или новый город"
      ↓
User: "да" → confidence = 1.0
User: "London" → resolve → update → confidence = 1.0
```

### Configuration

```yaml
confidence:
  threshold: 0.7        # Below this → re-verify
  verified: 1.0         # After user confirmation
  city_pick: 1.0        # After city selection
  decay_per_day: 0.01   # 1.0 → 0.7 in 30 days
  relocation_reset: 0.0 # When relocation detected
```

## Implementation Plan

### Phase 1: Decay Implementation ✅

- ~~Add `apply_confidence_decay()` to pipeline~~ → `get_effective_confidence()`
- ~~Check decay on each message~~
- ~~Re-verify when below threshold~~
- **Implemented in PR #9** (`src/core/timezone_identity.py`)

### Phase 2: Relocation Detection (Rule-based)
- Add regex patterns for relocation phrases
- Reset confidence when detected
- Trigger re-verification

### Phase 3: ML Detector (Future)
- Collect training data from production
- Train classifier similar to time detection
- Replace/augment rule-based detection

## Consequences

### Positive
- Automatic timezone drift correction
- Non-intrusive (only asks when needed)
- Extensible (new signals can adjust confidence)
- Single mechanism for all state changes

### Negative
- Occasional false positives (user mentions moving hypothetically)
- Requires tuning decay rate for good UX

### Risks
- Too fast decay → annoying re-verification
- Too slow decay → stale data
- Mitigation: Start with 30-day full decay, adjust based on feedback

## Alternatives Considered

### 1. Trigger-word only detection
**Rejected**: Too rigid, misses variations, requires constant pattern updates.

### 2. tz_hint mismatch as signal
**Rejected**: False positive rate too high. Users often specify tz for colleagues' convenience.

### 3. Always ask after N days
**Rejected**: Annoying if user hasn't moved. Confidence-based approach is smarter.

## References

- `configuration.yaml`: confidence settings
- `src/core/timezone_identity.py`: UserTzState model
- PR #9: Timezone onboarding improvements
