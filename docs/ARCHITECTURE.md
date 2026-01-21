# Team Ops Assistant - Architecture

## System Overview

Team Ops Assistant is a multi-platform bot that converts time mentions to multiple timezones. It follows a "thin adapters, rich core" architecture.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Platform Connectors                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Telegram   │  │   Discord   │  │  WhatsApp   │              │
│  │  Inbound    │  │  Inbound    │  │  Inbound    │              │
│  │  Outbound   │  │  Outbound   │  │  Outbound   │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  Normalization Layer                         │ │
│  │    Platform-specific → NormalizedEvent → OutboundMessage     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Core Domain                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Time Parser │  │  Timezone   │  │   Message   │              │
│  │ (Rules+LLM) │  │  Converter  │  │   Handler   │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Timezone   │  │   Dedupe    │  │   Config    │              │
│  │  Identity   │  │   Manager   │  │   System    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage Layer                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    MongoDB Atlas                             │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────────┐              │ │
│  │  │  users  │  │  chats  │  │  dedupe_events  │              │ │
│  │  └─────────┘  └─────────┘  └─────────────────┘              │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Thin Adapters

Platform connectors do minimal work:
- **Inbound**: Parse platform payload → `NormalizedEvent`
- **Outbound**: `OutboundMessage` → Platform API call

All business logic lives in the core domain.

### 2. Rules-First Processing

Time parsing follows a rules-first approach:
1. Regex patterns handle common formats (HH:MM, Hpm, "at H")
2. LLM is fallback only when rules are uncertain
3. This keeps latency low and costs minimal

### 3. Confidence-Based Decisions

User timezone confidence affects behavior:
- Confidence ≥ 0.7: Use timezone for conversions
- Confidence < 0.7: Prompt user to verify
- Different sources have different confidence levels

### 4. Graceful Degradation

The system handles failures gracefully:
- Unknown timezone → Prompt verification
- Unparseable time → Skip response
- LLM unavailable → Rules-only parsing

## Data Flow

### Message Processing

```
1. Webhook receives platform payload
2. Inbound adapter normalizes to NormalizedEvent
3. Handler checks for duplicates
4. Handler checks for time references
5. Time parser extracts times
6. Timezone identity resolves user's timezone
7. Converter generates multi-timezone response
8. Outbound adapter sends response
```

### Timezone Verification

```
1. Bot detects unknown timezone
2. Bot sends verification link
3. User clicks link → /verify page
4. Browser detects timezone via Intl API
5. User confirms → POST /api/verify
6. Backend stores timezone with high confidence
```

## Data Model

### MongoDB Collections

#### users

Stores user timezone preferences.

```javascript
{
  platform: "telegram",
  user_id: "12345678",
  tz_iana: "America/Los_Angeles",
  confidence: 1.0,
  source: "web_verified",
  created_at: ISODate(),
  updated_at: ISODate(),
  last_verified_at: ISODate()
}
```

**Indexes:**
- `(platform, user_id)` - unique

#### chats

Stores chat/channel configuration.

```javascript
{
  platform: "telegram",
  chat_id: "-100123456789",
  default_tz: "UTC",
  active_timezones: ["America/Los_Angeles", "Europe/London"],
  created_at: ISODate(),
  updated_at: ISODate()
}
```

**Indexes:**
- `(platform, chat_id)` - unique

#### dedupe_events

Deduplication tracking with TTL.

```javascript
{
  platform: "telegram",
  event_id: "-100123456789_42",
  chat_id: "-100123456789",
  created_at: ISODate()
}
```

**Indexes:**
- `(platform, event_id)` - unique
- `created_at` - TTL (7 days)

## Technology Choices

### Why Quart?

- Async-native (unlike Flask)
- Flask-compatible API (familiar patterns)
- Works well with Motor (async MongoDB)
- Simple deployment

### Why MongoDB?

- Flexible schema for different platforms
- TTL indexes for auto-cleanup
- Atlas provides easy managed hosting
- Good async support via Motor

### Why Together AI + Qwen3?

- Cost-effective for LLM fallback
- Good reasoning for time parsing
- API is simple and reliable
- Model handles multiple languages

## Extension Points

### Adding a New Platform

1. Create `src/connectors/<platform>/`
2. Implement inbound normalization
3. Implement outbound sending
4. Add webhook route
5. Add contract tests

### Adding New Time Formats

1. Add regex pattern to `time_parse.py`
2. Add test cases
3. Update LLM prompt if needed

### Adding New Features

The modular design allows additions:
- Scheduling integration
- Calendar sync
- Meeting room booking
- Custom timezone nicknames

## Security Considerations

### Verification Tokens

- HMAC-SHA256 signed
- Include expiration
- Tied to specific user/chat
- Cannot be reused

### API Authentication

- Platform webhooks use platform-specific verification
- No public APIs beyond health check
- Secrets loaded from environment

### Data Privacy

- Minimal data stored
- No message content stored
- Timezone data only
- TTL on deduplication records

## AI Development

### Skills (Fundamentals)

High-level development patterns in `.claude/skills/`:

| Skill | Purpose |
|-------|---------|
| `/tdd-first` | Test-Driven Development - tests before code |
| `/clean-models` | Pydantic, typing, database hygiene |
| `/thin-adapters` | Adapter pattern - connectors have zero logic |

### Commands (Utilities)

Quick actions in `.claude/commands/`:

| Command | Action |
|---------|--------|
| `/check` | Run all quality gates (lint + types + tests) |
| `/test` | Run pytest with optional args |
| `/lint` | Run ruff format and check |
| `/types` | Run pyright type checker |
