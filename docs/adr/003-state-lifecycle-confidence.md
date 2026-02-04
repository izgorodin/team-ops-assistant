# ADR-003: State Lifecycle & Confidence-Based Re-verification

## Status
**Implemented** | 2026-01-24 | PR #13

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
 Decay            Regex Detector       User Action
 (passive)          (active)            (explicit)

 -0.01/day         "переехал в X"       "change tz"
                   → confidence = 0.0    → session
```

### Signals & Their Effects

| Signal | Effect on Confidence | Notes |
|--------|---------------------|-------|
| Time decay | -0.01/day | Passive, always running |
| Regex: relocation intent detected | = 0.0 (reset) | "moved to", "переехал", "arrived in" |
| No relocation match | no change | Normal messages |
| User explicitly requests change | = 0.0 → session | "change my timezone" |
| User confirms current tz | = 1.0 | After re-verification |
| tz_hint mismatch in message | **no change** | User convenience, not relocation signal |

### What is NOT a Signal

- **tz_hint mismatch**: User writes "3pm PT" while saved tz is ET
  - This is convenience for colleagues, NOT a relocation signal
  - User in NY might say "3pm PT" to help LA colleagues
  - Do NOT reduce confidence for this

### Regex Detector for Relocation Intent

Rule-based detection using regex patterns:
- Input: message text
- Output: boolean match + extracted city
- Patterns cover EN/RU relocation phrases

```python
# Examples from src/core/triggers/relocation.py
RELOCATION_PATTERNS = [
    r"переехал[аи]?\s+(в\s+)?(\w+)",
    r"moved?\s+to\s+(\w+)",
    r"arrived\s+in\s+(\w+)",
    r"теперь\s+(в|живу\s+в)\s+(\w+)",
    r"now\s+(in|living\s+in)\s+(\w+)",
    r"relocated\s+to\s+(\w+)",
    r"долетел[аи]?\s+(в|до)\s+(\w+)",
]
```

**Decision**: Regex-only approach chosen over ML. See "Upgrade Path" for rationale.

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

### Phase 2: Relocation Detection (Rule-based) ✅

- Add regex patterns for relocation phrases (EN + RU, past + future tense)
- Reset confidence when detected
- Trigger re-verification
- **Implemented in PR #13** (`src/core/triggers/relocation.py`)

### Phase 3: ML Enhancement (Decided Against)

We evaluated ML classifiers but decided to stay with regex-only:

- ML added complexity with marginal accuracy gain
- Regex patterns are transparent and easy to extend
- "Arrived" patterns added for better coverage
- See "Upgrade Path" for detailed rationale.

## Known Limitations (MVP)

Current regex-based detection has significant limitations:

### Language Support

- **Only English and Russian** - no other languages supported
- Adding new languages requires manual regex patterns

### Detection Quality

- **False positives**: "My friend moved to Boston" triggers detection
- **\w+ limitation**: Hyphenated cities like "Нью-Йорк" captured as "Нью"
- **Context-blind**: Can't distinguish "I moved" vs "he moved"

### Upgrade Path (Current Decision: Regex-Only)

1. **Expand regex patterns** ✅ CURRENT APPROACH
   - EN/RU patterns with past/present/future tense
   - "Arrived" patterns added for travel completion
   - Tune based on false positive feedback
   - Transparent, easy to debug and extend

2. **Two-layer: Regex + LLM confirmation** (available if needed)
   - Regex catches candidates, LLM confirms/rejects
   - Currently NOT needed - regex accuracy is sufficient
   - Can add if false positive rate becomes problematic

3. **ML classifier** ❌ DECIDED AGAINST
   - Evaluated but rejected (2026-02-04)
   - Added complexity with marginal accuracy gain over regex
   - Required labeled dataset maintenance
   - Regex + smart patterns proved sufficient

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
