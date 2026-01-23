# Team Ops Assistant — Architecture

## Overview

This document describes both the current implementation (AS-IS) and the target architecture (TO-BE) for Team Ops Assistant — a multi-platform bot that detects time mentions and converts them across team timezones.

**Architecture Philosophy:**
- Thin Adapters, Rich Core
- Rules-First, LLM-Fallback
- Configuration-Driven (no magic numbers)
- Confidence-Based Decisions

---

## 1. Current State (AS-IS)

### 1.1 System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PLATFORM LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   Telegram   │  │   Discord    │  │   WhatsApp   │                   │
│  │  ✓ Complete  │  │  ○ Skeleton  │  │  ○ Skeleton  │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
│         │                 │                 │                            │
│         └─────────────────┼─────────────────┘                            │
│                           ▼                                              │
│              ┌────────────────────────┐                                  │
│              │    NormalizedEvent     │                                  │
│              └────────────────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           CORE LAYER                                     │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      MessageHandler                                 │ │
│  │  dedupe → detect_time → parse_time → resolve_tz → convert → respond │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │ TimeClassifier│  │  TimeParse   │  │ TzIdentity   │  │ TimeConvert │  │
│  │  (ML+LLM)    │  │   (Regex)    │  │ (Confidence) │  │  (zoneinfo) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐                                     │
│  │    Dedupe    │  │  LLMFallback │                                     │
│  │  (TTL cache) │  │ (NVIDIA NIM) │                                     │
│  └──────────────┘  └──────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                                    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                      MongoDB Atlas                                   ││
│  │  ┌─────────┐  ┌─────────┐  ┌───────────────┐                        ││
│  │  │  users  │  │  chats  │  │ dedupe_events │                        ││
│  │  │ (tz)    │  │ (config)│  │   (TTL: 7d)   │                        ││
│  │  └─────────┘  └─────────┘  └───────────────┘                        ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| **App** | `src/app.py` | Quart entry, webhook routes, lifecycle |
| **Settings** | `src/settings.py` | Configuration loading from env + yaml |
| **Handler** | `src/core/handler.py` | Message processing pipeline orchestration |
| **TimeClassifier** | `src/core/time_classifier.py` | ML binary classification (has time?) |
| **TimeParse** | `src/core/time_parse.py` | Regex extraction of time values |
| **LLMFallback** | `src/core/llm_fallback.py` | NVIDIA NIM API for complex cases |
| **TzIdentity** | `src/core/timezone_identity.py` | User timezone resolution + verification |
| **TimeConvert** | `src/core/time_convert.py` | Multi-timezone conversion |
| **Dedupe** | `src/core/dedupe.py` | Deduplication + throttling |
| **Models** | `src/core/models.py` | Pydantic data models |
| **Mongo** | `src/storage/mongo.py` | MongoDB async operations |
| **Telegram** | `src/connectors/telegram/` | Telegram inbound/outbound adapters |

### 1.3 Data Flow

```
1. Webhook → POST /hooks/{platform}
2. Inbound Adapter → NormalizedEvent
3. Handler.handle():
   3.1 check_dedupe() → skip if duplicate
   3.2 check_throttle() → skip if too frequent
   3.3 contains_time_reference() → ML classifier
   3.4 parse_times() → Regex extraction
   3.5 get_effective_timezone() → User/Chat/Default
   3.6 convert_to_timezones() → Team zones
   3.7 format_response() → OutboundMessage
4. Outbound Adapter → Platform API
```

### 1.4 Time Detection Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 1: ML Classifier (TF-IDF + Logistic Regression)                  │
│  ───────────────────────────────────────────────────────                │
│  • Input: raw message text                                              │
│  • Output: probability [0.0, 1.0]                                       │
│  • Thresholds: uncertain=[0.4, 0.6], positive>0.6                       │
│  • Speed: <1ms local                                                    │
│  • Filters: ~75% of messages (no time → stop)                           │
│                                                                         │
│  if probability ∈ [0.4, 0.6]:                                           │
│      → LLM detection fallback                                           │
└──────────────────────────────┬──────────────────────────────────────────┘
                               ▼ has_time=true
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 2: Regex Extraction                                              │
│  ─────────────────────────────                                          │
│  • Patterns: HH:MM, H am/pm, "at H", ranges, tomorrow                   │
│  • Timezone hints: PST, EST, GMT, city names                            │
│  • Speed: <0.1ms                                                        │
│  • Handles: ~80% of positive cases                                      │
└──────────────────────────────┬──────────────────────────────────────────┘
                               ▼ regex_failed
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 3: LLM Extraction (NVIDIA NIM / Qwen3)                           │
│  ─────────────────────────────────────────────                          │
│  • Handles: "half past seven", "в полдень", word-based                  │
│  • Speed: 200-500ms                                                     │
│  • Reaches: ~5% of messages                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.5 Current Limitations

| Area | Problem | Impact |
|------|---------|--------|
| **Magic Numbers** | 35 hardcoded values in code | Hard to tune without code changes |
| **Monolithic Handler** | All logic in one pipeline | Hard to extend to new triggers |
| **No Interfaces** | Concrete implementations only | Hard to swap/mock components |
| **Tight Coupling** | Components know each other | Hard to test in isolation |
| **Partial Config** | Some params in yaml, some hardcoded | Inconsistent configuration |

**Magic Numbers Found:**

| Category | Count | Examples |
|----------|-------|----------|
| ML hyperparameters | 7 | `ngram_range=(1,3)`, `WINDOW_SIZE=5` |
| Parsing confidence | 7 | 0.95, 0.9, 0.85, 0.7 |
| TZ source confidence | 3 | 0.9, 0.6, 0.5 |
| HTTP timeouts | 3 | 10.0, 15.0, 30.0 |
| LLM params | 2 | max_tokens: 500 |
| UI constants | 1 | cities[:4] |

---

## 2. Target State (TO-BE)

### 2.1 Extensible 4-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PLATFORM LAYER                                   │
│  Telegram │ Discord │ WhatsApp │ Slack │ ... (thin adapters)            │
│  Responsibility: Normalize to NormalizedEvent, send OutboundMessage     │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓ NormalizedEvent
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRIGGER LAYER                                    │
│  Protocol: TriggerDetector                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │TimeDetector  │  │DateDetector  │  │QuestionDetector│  (future)       │
│  │ ML+Regex+LLM │  │  (future)    │  │   (future)   │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│  Output: list[DetectedTrigger]                                          │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓ DetectedTrigger
┌─────────────────────────────────────────────────────────────────────────┐
│                          STATE LAYER                                     │
│  Protocol: StateManager[T]                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │TimezoneState │  │LanguageState │  │PreferenceState│  (future)        │
│  │ confidence   │  │  (future)    │  │   (future)   │                   │
│  │ verification │  │              │  │              │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│  Output: ResolvedContext                                                │
└─────────────────────────────────────────────────────────────────────────┘
                               ↓ ResolvedContext
┌─────────────────────────────────────────────────────────────────────────┐
│                         ACTION LAYER                                     │
│  Protocol: ActionHandler                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │TimeConverter │  │  Notifier    │  │  Scheduler   │   (future)        │
│  │ multi-tz     │  │  (future)    │  │   (future)   │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│  Output: list[OutboundMessage]                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Protocols (Interfaces)

```python
from typing import Protocol, Generic, TypeVar

T = TypeVar("T")

class TriggerDetector(Protocol):
    """Detects triggers in message text."""

    async def detect(self, event: NormalizedEvent) -> list[DetectedTrigger]:
        """Return list of detected triggers with confidence."""
        ...


class StateManager(Protocol, Generic[T]):
    """Manages user/chat state for a specific domain."""

    async def get_state(
        self, platform: Platform, user_id: str, chat_id: str
    ) -> StateResult[T]:
        """Get current state with confidence."""
        ...

    async def update_state(
        self, platform: Platform, user_id: str, value: T, source: str
    ) -> None:
        """Update state from a source."""
        ...


class ActionHandler(Protocol):
    """Handles detected triggers and produces responses."""

    async def handle(
        self, trigger: DetectedTrigger, context: ResolvedContext
    ) -> list[OutboundMessage]:
        """Process trigger and return response messages."""
        ...
```

### 2.3 Configuration-Driven Design

**All tunable parameters in `configuration.yaml`:**

```yaml
# Application
app:
  name: "Team Ops Assistant"
  version: "0.1.0"

# Database
database:
  name: "team_ops_assistant"

# Timezone settings
timezone:
  default: "UTC"
  team_timezones:
    - "America/Los_Angeles"
    - "America/New_York"
    - "Europe/London"
    - "Europe/Berlin"
    - "Asia/Tokyo"
    - "Australia/Sydney"
  team_cities:
    - name: "Los Angeles"
      tz: "America/Los_Angeles"
    # ...

# Confidence thresholds
confidence:
  threshold: 0.7              # Below = prompt verification
  verified: 1.0               # WEB_VERIFIED source
  city_pick: 0.85             # CITY_PICK source
  message_explicit: 0.9       # Explicit TZ in message
  inferred: 0.6               # Inferred from patterns
  chat_default: 0.5           # Chat default TZ
  decay_per_day: 0.01         # Future: daily decay

# Time parsing confidence by pattern
time_parsing:
  confidence:
    hhmm_ampm: 0.95           # "3:30 PM"
    european_hhmm: 0.9        # "15h30"
    military: 0.9             # "1500"
    plain_hhmm: 0.95          # "15:30"
    h_ampm: 0.9               # "3pm"
    range: 0.85               # "5-7pm"
    at_h: 0.7                 # "at 3"

# ML classifier settings
classifier:
  long_text_threshold: 100    # Split text if longer
  window_size: 5              # Context window for long texts
  uncertain_low: 0.4          # Below = no time
  uncertain_high: 0.6         # Above = has time
  tfidf:
    ngram_range: [1, 3]
    min_df: 2
    max_df: 0.95
  logistic_regression:
    max_iter: 1000
    random_state: 42

# Deduplication
dedupe:
  ttl_seconds: 604800         # 7 days
  throttle_seconds: 2         # Min time between responses

# LLM fallback
llm:
  model: "meta/llama-3.1-8b-instruct"
  base_url: "https://integrate.api.nvidia.com/v1"
  fallback_only: true
  detection:
    max_tokens: 150
    temperature: 0.1
    timeout: 10.0
  extraction:
    max_tokens: 500
    temperature: 0.1
    timeout: 15.0

# HTTP clients
http:
  timeouts:
    telegram_api: 30.0
    discord_api: 30.0
    whatsapp_api: 30.0

# UI settings
ui:
  max_cities_shown: 4
  verification_token_hours: 24

# Logging
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 2.4 MVP as First Implementation

The current timezone feature is the first implementation of the extensible architecture:

| Layer | Protocol | MVP Implementation |
|-------|----------|-------------------|
| Trigger | `TriggerDetector` | `TimeDetector` (ML + Regex + LLM) |
| State | `StateManager[str]` | `TimezoneStateManager` (IANA tz) |
| Action | `ActionHandler` | `TimeConversionHandler` |

---

## 3. Gap Analysis

### 3.1 Component Mapping

| AS-IS | TO-BE | Gap | Action |
|-------|-------|-----|--------|
| `handler.py` (monolith) | Pipeline stages | Missing orchestrator | Extract to `Pipeline` class |
| `time_classifier.py` | `TriggerDetector` | No protocol | Define protocol, implement |
| `time_parse.py` | Part of `TimeDetector` | Hardcoded confidence | Move to config |
| `timezone_identity.py` | `StateManager[str]` | No protocol | Define protocol, implement |
| `time_convert.py` | `ActionHandler` | No protocol | Define protocol, implement |
| Hardcoded values | `configuration.yaml` | 35 magic numbers | Move all to config |
| No interfaces | Protocols | Nothing to mock | Define protocols |

### 3.2 Configuration Gaps

| Current Location | Value | Target Config Path |
|------------------|-------|-------------------|
| `time_classifier.py:202` | `_LONG_TEXT_THRESHOLD = 100` | `classifier.long_text_threshold` |
| `time_classifier.py:215` | `_WINDOW_SIZE = 5` | `classifier.window_size` |
| `time_classifier.py:48-61` | TF-IDF/LR params | `classifier.tfidf.*`, `classifier.logistic_regression.*` |
| `time_parse.py:149-284` | Confidence 0.7-0.95 | `time_parsing.confidence.*` |
| `timezone_identity.py:117-121` | Source confidence | `confidence.*` |
| `llm_fallback.py:73,185,195-196` | Timeouts, tokens | `llm.detection.*`, `llm.extraction.*` |
| `telegram/outbound.py:43` | `timeout=30.0` | `http.timeouts.telegram_api` |
| `handler.py:143` | `cities[:4]` | `ui.max_cities_shown` |

### 3.3 Test Gaps

| Area | Current | Target |
|------|---------|--------|
| Contract tests | Per-connector | Protocol-based |
| Config tests | None | Verify no magic numbers |
| Integration tests | Partial | Full pipeline |
| Coverage | Unknown | 92% |

---

## 4. Migration Path

### Step 1: Configuration Cleanup (No Logic Changes)

1. Add all missing sections to `configuration.yaml`
2. Add Pydantic models to `settings.py` for new sections
3. Replace hardcoded values with config reads
4. Add test: "no hardcoded numeric constants in core/"

**Files:**
- `configuration.yaml` — add sections
- `src/settings.py` — add models
- `src/core/time_parse.py` — use config
- `src/core/time_classifier.py` — use config
- `src/core/timezone_identity.py` — use config
- `src/core/llm_fallback.py` — use config
- `src/connectors/telegram/outbound.py` — use config

### Step 2: Protocol Definitions (Add Interfaces)

1. Define `TriggerDetector` protocol
2. Define `StateManager[T]` protocol
3. Define `ActionHandler` protocol
4. Define shared types: `DetectedTrigger`, `StateResult[T]`, `ResolvedContext`

**Files:**
- `src/core/protocols.py` — new file with protocols
- `src/core/models.py` — add new types

### Step 3: Refactor to Protocols (Implement Interfaces)

1. Rename/refactor components to match protocols
2. `TimeDetector` implements `TriggerDetector`
3. `TimezoneStateManager` implements `StateManager[str]`
4. `TimeConversionHandler` implements `ActionHandler`
5. Create `Pipeline` orchestrator

**Files:**
- `src/core/triggers/time.py` — TimeDetector
- `src/core/state/timezone.py` — TimezoneStateManager
- `src/core/actions/time_convert.py` — TimeConversionHandler
- `src/core/pipeline.py` — Pipeline orchestrator

### Step 4: Test Alignment (TDD Completion)

1. Contract tests verify protocol compliance
2. Unit tests for each component in isolation
3. Integration tests for full pipeline
4. Coverage analysis and gap filling

---

## 5. Data Model

### 5.1 Core Models

```python
# Platform enum
class Platform(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"

# Normalized input
class NormalizedEvent(BaseModel, frozen=True):
    platform: Platform
    event_id: str
    chat_id: str
    user_id: str
    username: str | None
    display_name: str | None
    text: str
    timestamp: datetime
    reply_to_message_id: str | None = None

# Normalized output
class OutboundMessage(BaseModel, frozen=True):
    platform: Platform
    chat_id: str
    text: str
    reply_to_message_id: str | None = None
    parse_mode: str | None = None

# Parsed time
class ParsedTime(BaseModel, frozen=True):
    original_text: str
    hour: int
    minute: int
    timezone_hint: str | None = None
    is_tomorrow: bool = False
    confidence: float

# User timezone state
class UserTzState(BaseModel):
    platform: Platform
    user_id: str
    tz_iana: str
    confidence: float
    source: TimezoneSource
    created_at: datetime
    updated_at: datetime
    last_verified_at: datetime | None = None
```

### 5.2 MongoDB Collections

| Collection | Purpose | Indexes |
|------------|---------|---------|
| `users` | User timezone state | `(platform, user_id)` unique |
| `chats` | Chat configuration | `(platform, chat_id)` unique |
| `dedupe_events` | Deduplication (TTL) | `(platform, event_id)` unique, `created_at` TTL |

---

## 6. Security

### 6.1 Verification Tokens

- HMAC-SHA256 signed with `VERIFY_TOKEN_SECRET`
- Format: `{platform}|{user_id}|{chat_id}|{expires_ts}|{nonce}|{signature}`
- Expiration: configurable (default 24 hours)
- Single-use (nonce prevents replay)

### 6.2 Secrets Management

| Secret | Source | Never In |
|--------|--------|----------|
| `MONGODB_URI` | Environment | Code, logs |
| `TELEGRAM_BOT_TOKEN` | Environment | Code, logs |
| `NVIDIA_API_KEY` | Environment | Code, logs |
| `VERIFY_TOKEN_SECRET` | Environment | Code, logs |
| `APP_SECRET_KEY` | Environment | Code, logs |

### 6.3 Data Privacy

- No message content stored (only metadata for dedupe)
- Timezone data stored (user preference)
- TTL on deduplication records (7 days default)
- No PII logging

---

## 7. Extension Points

### 7.1 Adding a New Platform

1. Create `src/connectors/<platform>/inbound.py`
2. Create `src/connectors/<platform>/outbound.py`
3. Add webhook route in `src/app.py`
4. Add contract tests

### 7.2 Adding a New Trigger Type

1. Implement `TriggerDetector` protocol
2. Register in trigger registry
3. Implement corresponding `StateManager` if needed
4. Implement corresponding `ActionHandler`
5. Add to pipeline configuration

### 7.3 Adding New Time Formats

1. Add examples to training data
2. Retrain classifier if needed
3. Add regex pattern if extractable
4. Update LLM prompt for word-based times
5. Add test cases

---

## 8. References

- [VISION.md](./VISION.md) — Future architecture vision
- [CLAUDE.md](../CLAUDE.md) — AI development guidelines
- [API.md](./API.md) — API endpoint documentation
- [RUNBOOK.md](./RUNBOOK.md) — Deployment and operations
