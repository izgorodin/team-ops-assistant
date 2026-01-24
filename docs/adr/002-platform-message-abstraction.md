# ADR-002: Platform Message Abstraction Layer

**Status:** Proposed
**Date:** 2026-01-24
**Deciders:** TBD

## Context

Each messaging platform has different API formats:

| Platform | Message ID Format | Reply Format | Parse Mode |
|----------|-------------------|--------------|------------|
| Telegram | `int` (per-chat unique) | `reply_to_message_id: int` | HTML, MarkdownV2 |
| Discord | `snowflake string` (globally unique) | `message_reference.message_id` | Markdown |
| WhatsApp | `wamid.xxx` (globally unique) | `context.message_id` | None (plain) |

### Current Problem

We discovered a bug where `event_id` (for deduplication) was used as `reply_to_message_id`:

```python
# event_id = "{chat_id}_{message_id}" - for dedupe (unique across chats)
# message_id = just the message_id - for reply (per-chat unique)

# BUG: Used event_id instead of message_id
reply_to_message_id=event.event_id  # Wrong!
```

This happened because:
1. `NormalizedEvent` didn't distinguish between these two concepts
2. No abstraction layer for platform-specific message ID handling

## Problem Statement

1. **ID Confusion**: Different platforms have different ID semantics
2. **Format Differences**: Reply, mentions, formatting all vary
3. **Scattered Logic**: Each connector has its own normalization code
4. **No Validation**: Easy to mix up IDs without type safety

## Proposed Solution

### Message Abstraction Layer

Create a dedicated layer for platform-specific message handling:

```
src/core/messages/
├── __init__.py
├── base.py          # Abstract base classes
├── telegram.py      # Telegram-specific implementation
├── discord.py       # Discord-specific implementation
└── whatsapp.py      # WhatsApp-specific implementation
```

### Option A: Platform-Specific Message Classes

```python
# base.py
class PlatformMessage(Protocol):
    """Protocol for platform-specific message handling."""

    def get_event_id(self) -> str:
        """Get unique ID for deduplication (globally unique)."""
        ...

    def get_reply_id(self) -> str | None:
        """Get ID for reply_to functionality (platform-specific format)."""
        ...

    def format_text(self, text: str, parse_mode: str) -> str:
        """Format text according to platform rules."""
        ...


# telegram.py
class TelegramMessage(PlatformMessage):
    def __init__(self, raw: dict):
        self._message_id = raw["message"]["message_id"]
        self._chat_id = raw["message"]["chat"]["id"]

    def get_event_id(self) -> str:
        # For dedupe: "{chat_id}_{message_id}"
        return f"{self._chat_id}_{self._message_id}"

    def get_reply_id(self) -> str:
        # For reply: just message_id as string
        return str(self._message_id)
```

**Pros:**
- Clear separation of concerns
- Type safety through protocols
- Easy to test each platform
- Platform-specific logic contained

**Cons:**
- More classes to maintain
- Potential over-engineering for 3 platforms

### Option B: Utility Functions

```python
# messages/utils.py
def extract_telegram_ids(raw: dict) -> tuple[str, str]:
    """Extract (event_id, reply_id) from Telegram update."""
    msg = raw["message"]
    chat_id = str(msg["chat"]["id"])
    message_id = str(msg["message_id"])
    return (f"{chat_id}_{message_id}", message_id)

def extract_discord_ids(raw: dict) -> tuple[str, str]:
    """Extract (event_id, reply_id) from Discord message."""
    channel_id = raw["channel_id"]
    message_id = raw["id"]
    return (f"{channel_id}_{message_id}", message_id)
```

**Pros:**
- Simple, minimal code
- Easy to understand
- No inheritance complexity

**Cons:**
- Less type safety
- Logic scattered in functions
- Harder to extend

### Option C: Enhanced NormalizedEvent (Current + Improvements)

Keep current model but be explicit about ID semantics:

```python
class NormalizedEvent(BaseModel, frozen=True):
    # For deduplication (must be globally unique)
    event_id: str = Field(
        description="Unique across all chats for deduplication"
    )

    # For reply functionality (platform-specific)
    message_id: str | None = Field(
        default=None,
        description="Platform message ID for reply_to (may be int, snowflake, wamid)"
    )

    # For mention/threading (platform-specific)
    thread_id: str | None = Field(
        default=None,
        description="Thread/topic ID if message is in a thread"
    )
```

**Pros:**
- Minimal changes to current architecture
- Clear documentation of semantics
- Works with existing code

**Cons:**
- Doesn't solve format validation
- Platform logic still in connectors

## Recommendation

**Option C (Enhanced NormalizedEvent)** for now, with clear documentation.

**Rationale:**
1. We just fixed the immediate bug with this approach
2. Only Telegram is fully implemented; Discord/WhatsApp are skeletons
3. Avoid premature abstraction
4. Can migrate to Option A later if complexity grows

### Migration Path

1. **Now (Done):** Add `message_id` field to `NormalizedEvent`
2. **Next:** Document ID semantics clearly in model docstrings
3. **Future:** If we add Slack or more platforms, consider Option A

## Decision

**Accepted:** Option C with clear documentation.

When implementing Discord/WhatsApp connectors, revisit this ADR.

## Consequences

1. Each connector must correctly populate:
   - `event_id` - globally unique for dedupe
   - `message_id` - platform-specific for reply
2. Core code uses `message_id` for replies, not `event_id`
3. Tests should verify ID semantics for each platform

## Related

- Bug fix: `cc1dda1` - Fixed reply_to_message_id using wrong ID
- Models: `src/core/models.py` - `NormalizedEvent`
- Connectors: `src/connectors/*/inbound.py`
