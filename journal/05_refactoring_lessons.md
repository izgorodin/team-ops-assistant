# Refactoring Lessons: Pipeline Architecture Migration

## Context

**Date:** 2026-01-24
**PRs:** #6 (pipeline migration), #7 (datetime fix)
**Scope:** Replace monolithic `handler.py` with extensible Pipeline architecture

## What We Did

### Before: Monolithic Handler

```
app.py → orchestrator.py → handler.py (ALL logic here)
                              ├── dedupe check
                              ├── city pick detection
                              ├── time parsing
                              ├── timezone resolution
                              ├── session creation
                              └── response formatting
```

### After: Pipeline Architecture

```
app.py → orchestrator.py → pipeline.py
                              ├── TimeDetector (triggers/)
                              ├── TimezoneStateManager (state/)
                              └── TimeConversionHandler (actions/)
                           → agent_handler.py (for TZ collection sessions)
```

## What Went Wrong

### Bug 1: Lost `mark_processed` Call

**Symptom:** Duplicate timezone prompts on webhook retries

**Root cause:** When extracting session creation logic from handler.py to orchestrator.py, we forgot to copy `mark_processed()` call for the session creation path.

```python
# OLD (handler.py) - had mark_processed
if needs_session:
    create_session()
    mark_processed()  # ← Was here!
    return prompt

# NEW (orchestrator.py) - FORGOT mark_processed
if result.needs_state_collection:
    return await self._handle_state_collection(event, result)
    # ← mark_processed MISSING!
```

**Fix:** Added mark_processed inside `_handle_state_collection()` method.

### Bug 2: Missed PR Review Comment

**Symptom:** `datetime.utcnow()` deprecation warning

**Root cause:** Copilot review had 4 comments. We fixed 3 and merged, missing comment #4.

**Fix:** PR #7 changed `datetime.utcnow()` → `datetime.now(UTC)`

## Why It Happened

1. **Focused on happy path** - session creation worked, didn't check side effects
2. **No behavior inventory** - didn't list ALL behaviors before refactoring
3. **Rushed PR review** - merged without checking ALL comments
4. **No D6 reflection** - didn't ask "why did I miss this?"

## Prevention: Architecture Analysis Skill

Created `.claude/skills/architecture-analysis/skill.md` with:

### Behavior Inventory (Phase 1)

Before touching ANY code, list EVERYTHING it does:

- Happy path (what it's supposed to do)
- Error handling (what happens on failure)
- Side effects (dedupe, throttle, logging, state changes)
- Implicit contracts (input/output types, dependencies)

**Rule:** If you can't list 10+ behaviors, you haven't looked hard enough.

### Code Paths Diagram (Phase 2)

Draw ALL paths, not just main flow:

```
Input
  ├─ Dedupe check → [SKIP: duplicate]
  ├─ Throttle check → [SKIP: throttled]
  ├─ No trigger → [SKIP: no time]
  ├─ Time + TZ unknown → [SESSION + PROMPT]
  │                        └─ mark_processed ← EASY TO MISS!
  └─ Time + TZ known → [CONVERT + RESPOND]
                         └─ mark_processed
                         └─ record_response
```

### Old → New Mapping (Phase 3)

| Old Location | Behavior | New Location | Verified? |
|--------------|----------|--------------|-----------|
| handler.py:45 | dedupe check | orchestrator.py:92 | ✓ |
| handler.py:78 | mark_processed (happy) | orchestrator.py:117 | ✓ |
| handler.py:95 | mark_processed (session) | **MISSING** | BUG! |

**If behavior has no new location → it's lost → BUG**

## Checklist for Future Refactoring

```
[ ] Listed ALL behaviors (10+ items)
[ ] Drew code paths diagram
[ ] Mapped old → new for each behavior
[ ] Verified NO behaviors lost
[ ] Tests exist for critical paths
[ ] Can explain what EACH deleted line did
```

## Key Takeaways

1. **Happy path is just the base** - real code has side effects everywhere
2. **Side effects are invisible** - dedupe, throttle, logging, metrics
3. **Refactoring = moving behaviors** - if you can't map them, you'll lose some
4. **Tests don't catch everything** - tests might not cover lost side effects
5. **D1-D7 workflow is mandatory** - every review comment, no exceptions

## Related Files

- `.claude/skills/architecture-analysis/skill.md` - full skill definition
- `CLAUDE.md` - added "Planning & Refactoring" section
- `src/core/orchestrator.py` - fixed implementation
