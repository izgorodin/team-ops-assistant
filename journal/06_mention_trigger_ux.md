# Mention Trigger & UX Improvements

## Context

**Date:** 2026-01-25
**PR:** #16
**Scope:** Add @bot mention detection, help system, timezone onboarding improvements

## What We Built

### MentionDetector

New trigger detector for bot mentions and help requests:

```python
# Patterns detected:
- @bot, @timebot, @timezonebot (username mentions)
- "bot", "бот" (word detection)
- "help", "помощь" (help requests)
```

**Key design decisions:**
- No false positives: "bottleneck", "helpful", "робот" are ignored
- Case-insensitive matching
- Works in any position in message

### Help System

New `SessionGoal.HELP_REQUEST` - handled directly without creating a session:

```
User: @bot help
Bot: [Displays help message from prompts/ui/help.md]
```

Help message explains:
- Automatic time detection
- Timezone onboarding
- Relocation detection feature

### Pipeline Priority

Updated trigger priority order:
1. **Mention** (highest) - help requests
2. **Relocation** - "moved to Paris" resets timezone
3. **Time** - "3 pm" triggers conversion

This ensures help requests are handled before time detection.

## Bug Fixes in This PR

### 1. Relocation Context in Agent

**Problem:** When user said "Moved to Paris" but Telegram send failed, subsequent messages lost the relocation context.

**Fix:** Agent now prepends relocation city to session context:
```python
if relocation_city:
    user_text = f"[User said they moved to {relocation_city}] {event.text}"
```

### 2. LLM Response Parsing

**Problem:** `content.index("```json")` throws `ValueError` if not found.

**Fix:** Use `find()` instead:
```python
start = content.find("```json")
if start == -1:
    # fallback to raw JSON
```

### 3. Telegram Error Logging

**Problem:** Telegram send failures were silently swallowed.

**Fix:** Added detailed error logging in `outbound.py`:
```python
logger.error(f"Telegram API error: {response.status_code} - {response.text}")
```

## Test Coverage

- 38 new tests for MentionDetector patterns
- Tests for false positive prevention
- Total: 476 → 483 tests

## Related Files

- `src/core/triggers/mention.py` - MentionDetector
- `src/core/models.py` - SessionGoal.HELP_REQUEST
- `prompts/ui/help.md` - Help message template
- `src/core/pipeline.py` - Priority handling
- `src/core/agent_handler.py` - Relocation context fix
- `src/core/llm_fallback.py` - JSON parsing fix
