# Vision: Extensible State & Trigger Architecture

This document describes the broader architectural vision for Team Ops Assistant beyond the current timezone-focused MVP.

## Current State (MVP)

The current implementation handles one specific use case: **timezone conversion**.

```
Message with time → Detect time → Resolve user timezone → Convert → Reply
```

## Vision: 3-Layer Architecture

The underlying patterns can be generalized into a reusable framework for **any stateful trigger-response system**.

```
                    ┌─────────────────────────────────────────────────────┐
                    │              LAYER 1: TRIGGER DETECTION             │
                    │                                                     │
                    │  Detect meaningful patterns in messages             │
                    │  Current: Time references (3pm, 10:30, etc.)        │
                    │  Future: Dates, questions, tone, intent, etc.       │
                    └─────────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │            LAYER 2: STATE MANAGEMENT                │
                    │                                                     │
                    │  2.1 State Initialization                           │
                    │      - First-time user → prompt for verification    │
                    │      - Infer from explicit mentions                 │
                    │                                                     │
                    │  2.2 State Drift Detection                          │
                    │      - Detect anomalies/changes in behavior         │
                    │      - User traveling? Changed location?            │
                    │      - Update confidence accordingly                │
                    │                                                     │
                    │  Current: UserTzState (timezone + confidence)       │
                    │  Future: Generic UserState<T> for any parameter     │
                    └─────────────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │           LAYER 3: PREDICTION & CONFIDENCE          │
                    │                                                     │
                    │  Predict state at query time with confidence        │
                    │  Current: Use verified tz if confidence >= 0.7      │
                    │  Future: Temporal prediction (24h ahead)            │
                    │          Decay over time                            │
                    │          Multi-signal fusion                        │
                    └─────────────────────────────────────────────────────┘
```

## Layer Details

### Layer 1: Trigger Detection

**Current Implementation:**
- `time_parse.py` — Regex patterns (90%+ coverage)
- `trigger_detect.md` — LLM fallback prompt

**Generalization Path:**
```python
# Abstract interface
class TriggerDetector(Protocol):
    async def detect(self, text: str) -> list[DetectedTrigger]:
        """Detect triggers in message text."""
        ...

# Current implementation
class TimeTriggerDetector(TriggerDetector):
    """Detects time references."""

# Future implementations
class QuestionDetector(TriggerDetector):
    """Detects questions that might need routing."""

class SentimentDetector(TriggerDetector):
    """Detects emotional tone for support escalation."""
```

### Layer 2: State Management

**Current Implementation:**
- `UserTzState` model with `tz_iana`, `confidence`, `source`
- `ChatState` with `default_tz`, `active_timezones`
- Web verification flow

**2.1 State Initialization:**
```python
# Current: First message triggers verification
if user_tz is None or user_tz.confidence < threshold:
    return prompt_verification()

# Future: Multi-source initialization
async def init_user_state(user_id: str, platform: Platform) -> UserState:
    # Try explicit verification first
    if verified := await check_verification(user_id):
        return verified

    # Try inference from messages
    if inferred := await infer_from_history(user_id):
        return inferred

    # Fall back to default
    return UserState(confidence=0.0, source="default")
```

**2.2 State Drift Detection:**
```python
# Future: Detect when state might be stale
class StateDriftDetector:
    async def check_anomaly(
        self,
        current_state: UserState,
        new_signal: Signal
    ) -> DriftResult:
        """
        Detect if new signal suggests state change.

        Example: User says "3pm" but their timezone says it's 3am there.
        This might indicate they're traveling.
        """
        ...
```

### Layer 3: Prediction & Confidence

**Current Implementation:**
- `timezone_identity.py` — `get_effective_timezone()`
- Confidence sources: WEB_VERIFIED (1.0), CITY_PICK (0.85), INFERRED (<0.7)

**Generalization Path:**
```python
class StatePredictor(Generic[T]):
    async def predict(
        self,
        user_id: str,
        at_time: datetime | None = None
    ) -> Prediction[T]:
        """
        Predict state value with confidence.

        Args:
            user_id: User to predict for
            at_time: Optional future time (for temporal prediction)

        Returns:
            Prediction with value, confidence, and reasoning
        """
        ...

# Current: Simple lookup with threshold
predictor = TimezonePredictor()
result = await predictor.predict(user_id)
if result.confidence >= 0.7:
    use(result.value)

# Future: Temporal prediction
result = await predictor.predict(user_id, at_time=now + timedelta(hours=24))
# "User will likely still be in Europe/London in 24 hours (confidence: 0.85)"
```

## Current vs. Future Mapping

| Component | Current (Hardcoded) | Future (Generic) |
|-----------|---------------------|------------------|
| Trigger | `ParsedTime` | `ParsedEntity[T]` |
| State | `UserTzState` | `UserState[T]` |
| Predictor | `timezone_identity.py` | `StatePredictor[T]` |
| Detector | `time_parse.py` | `TriggerDetector` registry |

## Why This Matters

The same patterns apply to many use cases:

1. **Timezone conversion** (current) — State: user timezone
2. **Language preference** — State: user language
3. **Working hours** — State: user availability schedule
4. **Notification preferences** — State: how/when to notify
5. **Expertise routing** — State: user skills for question routing

## Implementation Roadmap

### Phase 1: MVP ✅ COMPLETE

- ✅ Timezone detection and conversion (Regex + LLM fallback)
- ✅ Web verification flow
- ✅ Confidence scoring with decay
- ✅ Relocation detection (triggers re-verification)

### Phase 2: Stabilization (Current)

- ✅ Telegram connector (complete)
- ○ Discord/WhatsApp connectors (skeletons ready)
- ○ Production deployment
- ○ Real-world validation

### Phase 3: Abstraction ✅ MOSTLY COMPLETE

- ✅ `TriggerDetector` protocol implemented
- ✅ `StateManager[T]` protocol implemented
- ✅ `ActionHandler` protocol implemented
- ✅ Pipeline orchestrator with protocol-based DI
- ✅ Configuration-driven (all params in YAML)
- ✅ Prompts externalized (Jinja2 templates)

### Phase 4: New Use Cases (Future)

- Add new trigger types using the framework
- Multi-signal state management
- Temporal predictions

## Key Principles

1. **Rules-First, LLM-Fallback** — Regex/rules handle 90%+ cases
2. **Confidence-Based Decisions** — Never assume, always score
3. **Graceful Degradation** — Unknown state → prompt user
4. **Thin Adapters** — Platform code contains zero business logic
5. **Immutable Models** — State changes create new records

## References

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Current system design
- [CLAUDE.md](../CLAUDE.md) — AI development guidelines
- [CHANGELOG.md](../CHANGELOG.md) — Version history
