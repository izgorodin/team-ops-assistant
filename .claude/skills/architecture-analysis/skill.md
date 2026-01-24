---
name: architecture-analysis
description: Architectural analysis before any refactoring or significant change. Use BEFORE modifying, replacing, or deleting modules. Prevents lost behaviors and edge case bugs.
---

# Architecture Analysis: Understand Before Changing

## Core Principle

**Never modify code you don't fully understand.**

Happy path is just the BASE. Real systems have:
- Error paths
- Edge cases
- Side effects (dedupe, throttle, logging)
- Implicit contracts with other modules

## When This Skill Activates

Use this methodology BEFORE:
- Replacing a module with a new implementation
- Deleting code that "seems unused"
- Refactoring that touches 3+ files
- Moving logic from one place to another
- "Simplifying" existing code

## The Anti-Pattern: Refactor-and-Pray

```
"This code is messy" → Delete/rewrite → Ship → Bug reports →
"Oh, it also did X" → Patch → More bugs → ...
```

**This happens because you didn't inventory behaviors BEFORE changing.**

## The Framework

### Phase 1: Behavior Inventory

Before touching ANY code, list EVERYTHING it does:

```markdown
## Module: handler.py

### Happy Path
- [ ] Parse time from message
- [ ] Get user timezone
- [ ] Convert to target timezones
- [ ] Format response

### Error Handling
- [ ] Unknown timezone → prompt verification
- [ ] Parse failure → silent skip
- [ ] API timeout → graceful degradation

### Side Effects
- [ ] Dedupe check on entry
- [ ] Dedupe mark after response  ← EASY TO MISS!
- [ ] Throttle recording
- [ ] Session creation for unknown TZ

### Implicit Contracts
- [ ] Returns HandlerResult (not raw messages)
- [ ] Expects NormalizedEvent input
- [ ] Uses storage for state
```

**Rule: If you can't list 10+ behaviors, you haven't looked hard enough.**

### Phase 2: Code Paths Diagram

Draw ALL paths through the code, not just main flow:

```
Input
  │
  ├─ Dedupe check ─────────────────→ [SKIP: duplicate]
  │
  ├─ Throttle check ───────────────→ [SKIP: throttled]
  │
  ├─ No time reference ────────────→ [SKIP: no trigger]
  │
  ├─ Time found, TZ unknown ───────→ [CREATE SESSION + PROMPT]
  │                                    └─ mark_processed ← !
  │
  └─ Time found, TZ known ─────────→ [CONVERT + RESPOND]
                                       └─ mark_processed
                                       └─ record_response
```

**Every arrow is a behavior that must be preserved.**

### Phase 3: Map Old → New

Create explicit mapping:

| Old Location | Behavior | New Location | Verified? |
|--------------|----------|--------------|-----------|
| handler.py:45 | dedupe check | orchestrator.py:92 | [ ] |
| handler.py:52 | throttle check | orchestrator.py:97 | [ ] |
| handler.py:78 | mark_processed (happy) | orchestrator.py:117 | [ ] |
| handler.py:95 | mark_processed (session) | **MISSING!** | [x] BUG |

**If a behavior has no new location → it's lost → BUG.**

### Phase 4: Edge Cases Checklist

For EACH behavior, ask:

```
[ ] What if input is None/empty?
[ ] What if external service fails?
[ ] What if called twice with same input?
[ ] What if called concurrently?
[ ] What happens on timeout?
[ ] What state changes after this runs?
[ ] Who else depends on this behavior?
```

### Phase 5: Test Mapping

Every behavior should have a test:

| Behavior | Test Exists? | Test Location |
|----------|--------------|---------------|
| dedupe blocks duplicates | Yes | test_dedupe.py:34 |
| session created on unknown TZ | Yes | test_pipeline_e2e.py:89 |
| mark_processed after session | **NO** | Need to add! |

**No test = no confidence the behavior survives refactoring.**

## Quick Checklist

Before ANY refactoring commit:

```
[ ] I listed ALL behaviors of old code (10+ items)
[ ] I drew code paths diagram (not just happy path)
[ ] I mapped each behavior old → new location
[ ] I verified NO behaviors are lost in mapping
[ ] Edge cases are explicitly handled
[ ] Tests exist for critical behaviors
[ ] I can explain what EACH deleted line did
```

## Red Flags: Stop and Re-analyze

- "I think this code is unused" → **Prove it** with grep/usage search
- "This is just cleanup" → **List what you're cleaning** and why it's safe
- "Same logic, just moved" → **Verify side effects moved too**
- "Tests still pass" → **Tests might not cover the lost behavior**

## Common Lost Behaviors

Things frequently forgotten during refactoring:

1. **Cleanup/finalization** - closing connections, marking processed
2. **Error path side effects** - logging, metrics, state reset
3. **Concurrency guards** - locks, dedupe, throttle
4. **Implicit ordering** - A must happen before B
5. **Default values** - what happens when optional param is None

## Example: The Dedupe Bug

**What happened:**
```python
# Old code (handler.py)
if needs_session:
    create_session()
    mark_processed()  # ← Was here!
    return prompt

# New code (orchestrator.py) - BUGGY
if result.needs_state_collection:
    return await self._handle_state_collection(event, result)
    # ← mark_processed LOST!
```

**Why it happened:**
- Focused on "create session" (happy path)
- Didn't inventory ALL behaviors of the if-block
- `mark_processed` was a SIDE EFFECT, not main logic

**How to prevent:**
- Behavior inventory would have caught: "mark_processed in session path"
- Mapping table would show: "mark_processed → ???" (missing!)

## Integration with Other Skills

- **tdd-first**: Write tests for behaviors BEFORE refactoring
- **problem-solving**: If refactoring breaks things, use root cause analysis
- **pr-review-response**: D6 reflection should catch architectural gaps
