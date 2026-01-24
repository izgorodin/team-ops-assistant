# ADR-001: Cross-Platform User Identity

**Status:** Proposed
**Date:** 2026-01-24
**Deciders:** TBD

## Context

Currently, user identity is scoped to platform:
- Key: `(platform, user_id)` → timezone
- User A in Telegram ≠ User A in Slack

This means:
1. Same person must verify timezone on each platform
2. No shared state across platforms
3. No unified user profile

## Problem

When a user exists on multiple platforms (Telegram + Slack + Discord):
- They configure timezone 3 times
- Their preferences don't sync
- No way to correlate activity

## Proposed Solution

### Option A: Unified User UUID

```
telegram:123 ─┐
              ├─→ unified_user:abc-def-123
slack:456    ─┘

Storage:
users:
  - unified_id: abc-def-123
    tz_iana: Europe/London
    linked_accounts:
      - platform: telegram, id: 123
      - platform: slack, id: 456
```

**Pros:**
- Clean data model
- Single source of truth
- Enables user profiles

**Cons:**
- Requires account linking flow
- Migration complexity
- Privacy considerations

### Option B: Platform Priority Chain

```
lookup_timezone(telegram, 123):
  1. Check (telegram, 123)
  2. Check linked accounts via external service
  3. Fall back to asking
```

**Pros:**
- No storage migration
- Gradual adoption

**Cons:**
- External dependency
- Eventual consistency issues

### Option C: Manual Linking Command

```
User: /link slack @myslackname
Bot: Verification sent to Slack. Confirm there.
```

**Pros:**
- User-controlled
- No magic/inference

**Cons:**
- Manual effort required
- Users may not discover it

## Decision

**Deferred.** Out of scope for MVP.

Current implementation works for single-platform teams. Cross-platform identity can be added when:
1. Multi-platform deployment is confirmed use case
2. Account linking UX is designed
3. Privacy policy covers data correlation

## Consequences

- Users must verify timezone per platform
- No state sharing between platforms
- Future migration path exists via Option A

## References

- Storage: `src/storage/mongo.py` - `(platform, user_id)` index
- State: `src/core/models.py` - `UserTzState`
