## Problem

Several documentation files incorrectly state that Discord/WhatsApp connectors are "skeleton" or "not implemented":

1. `docs/API.md:82-93` - Says Discord returns `{"status": "not_implemented"}`
2. `docs/API.md:122-133` - Says WhatsApp returns `{"status": "not_implemented"}`
3. `journal/01_scope_assumptions.md` - Lists Discord/WhatsApp as skeleton
4. `docs/ONBOARDING.md` - Mentions "skeleton implementation"

**Reality:** All connectors are fully implemented in `src/app.py` and return `{"status": "processed"}`.

## Solution

Update all documentation to reflect actual implementation status:
- Discord: Fully implemented (webhook + outbound)
- WhatsApp: Fully implemented (webhook + outbound)  
- Slack: Fully implemented (webhook + outbound)

## Files to Update

- [ ] `docs/API.md` - Update response examples
- [ ] `docs/ONBOARDING.md` - Remove "skeleton" references
- [ ] `journal/01_scope_assumptions.md` - Update status

## Acceptance Criteria

- [ ] All docs accurately reflect implementation status
- [ ] No mentions of "skeleton" or "not_implemented" for completed connectors

## Labels
- documentation

## Part of
Epic #19
