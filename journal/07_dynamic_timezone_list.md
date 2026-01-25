# Dynamic Timezone List

## Context

**Date:** 2026-01-25
**PR:** #17
**Scope:** Time conversion shows timezones based on chat participants, not just config

## Problem

Before: Time conversion always showed the same static list from config:
```
🕐 3:00 PM in London → 6:00 PM in Moscow, 11:00 AM in New York
```

This didn't reflect the actual team members in a specific chat.

## Solution

**Config + Detected approach:**
1. Start with config timezones (team_cities)
2. When user sets timezone → add to chat's `active_timezones`
3. Time conversion merges both lists

```python
# Example:
config_tzs = ["Europe/London", "America/New_York"]  # from config
chat_tzs = ["Asia/Tokyo"]  # detected from user

result = ["Europe/London", "America/New_York", "Asia/Tokyo"]
```

## Implementation

### New Module: `src/core/chat_timezones.py`

```python
async def add_timezone_to_chat(storage, platform, chat_id, tz_iana):
    """Add timezone to chat's active_timezones (atomic, no duplicates)."""
    await storage.add_timezone_to_chat(platform, chat_id, tz_iana)

def merge_timezones(config_tzs, chat_tzs) -> list[str]:
    """Merge config + chat, config first, no duplicates."""
```

### MongoStorage: Atomic Update

```python
async def add_timezone_to_chat(self, platform, chat_id, tz_iana):
    """Uses $addToSet for atomic, idempotent updates."""
    await self.db.chats.update_one(
        {"platform": platform.value, "chat_id": chat_id},
        {
            "$addToSet": {"active_timezones": tz_iana},
            "$set": {"updated_at": datetime.utcnow()},
            "$setOnInsert": {...},
        },
        upsert=True,
    )
```

Why `$addToSet`? Concurrent-safe, idempotent, no read-modify-write race.

### Pipeline: Storage Injection

Before (protocol violation):
```python
storage = tz_manager.storage  # type: ignore[attr-defined]
```

After (clean injection):
```python
class Pipeline:
    def __init__(self, ..., storage: MongoStorage | None = None):
        self.storage = storage
```

## PR Review Fixes

Copilot review had 5 comments, all addressed:

| Comment | Fix |
|---------|-----|
| Protocol violation | Injected storage into Pipeline |
| Error handling | Wrapped add_timezone_to_chat in try/except |
| Missing integration test | Added TestPipelineContextResolution |
| Datetime inconsistency | Storage handles all timestamps |
| Non-atomic update | Added $addToSet method |

## Test Coverage

- `TestChatActiveTimezones` - storage delegation
- `TestMergeTimezones` - merge logic
- `TestPipelineContextResolution` - integration test

Total: 483 tests passing

## Files Changed

- `src/core/chat_timezones.py` - NEW
- `src/storage/mongo.py` - add_timezone_to_chat()
- `src/core/pipeline.py` - storage injection
- `src/core/agent_handler.py` - add tz on session complete
- `src/app.py` - pass storage to Pipeline
- `tests/test_dynamic_timezones.py` - NEW
