# 01 - Scope and Assumptions

## Scope Definition

This document captures the explicit scope decisions made for the Team Ops Assistant MVP.

## MVP Platform Strategy

### Fully Implemented: Telegram

Telegram was chosen as the MVP platform because:
1. Simple webhook-based integration
2. No special permissions/intents required
3. Well-documented Bot API
4. Easy testing with @BotFather

Telegram implementation includes:
- Inbound webhook handler
- Message normalization to `NormalizedEvent`
- Outbound message sending via Bot API
- Full test coverage

### Skeleton Implementation: Discord

Discord skeleton includes:
- Inbound normalization function (implemented but not connected)
- Outbound class structure (methods stub)
- Example payload fixtures
- Contract test expectations
- Documentation for completion

To complete Discord:
1. Set up Discord.py or interaction webhooks
2. Connect normalization to gateway/webhook
3. Implement outbound API calls
4. Add rate limiting

### Skeleton Implementation: WhatsApp

WhatsApp skeleton includes:
- Inbound normalization for text messages
- Webhook verification endpoint (implemented)
- Outbound class structure (methods stub)
- Example payload fixtures
- Contract test expectations
- Notes on 24-hour messaging window

To complete WhatsApp:
1. Implement outbound `send_message` method
2. Handle template messages for out-of-window
3. Add signature verification
4. Test with Meta sandbox

## Core Features (MVP)

### Time Parsing

Implemented:
- HH:MM format (14:30)
- H am/pm format (3pm, 10 AM)
- "at H" format (at 10)
- Tomorrow prefix
- Timezone abbreviations (PST, EST, CET, etc.)
- City name hints (London, Tokyo, etc.)

Not implemented (post-MVP):
- Date parsing (January 5th)
- Relative times (in 2 hours)
- Duration parsing (from 3-5pm)
- Complex natural language

### Time Conversion

Implemented:
- IANA timezone conversion
- Multi-timezone output
- Day change indication (+1 day)
- Team timezone list from config

Not implemented (post-MVP):
- DST edge case handling
- Historical timezone data
- Timezone aliases

### User Timezone Identity

Implemented:
- Web-based verification flow
- City picker fallback
- Confidence scoring
- Disambiguation policy

Not implemented (post-MVP):
- Confidence decay over time
- Re-verification prompts
- Timezone inference from message patterns

## Assumptions

### Platform Behavior

1. Telegram webhooks are reliable with retry on 5xx
2. MongoDB Atlas is accessible from Render
3. Users will verify timezone when prompted

### Scalability

1. Single instance handles initial load
2. MongoDB connection pooling is sufficient
3. No need for external message queue

### LLM Usage

1. Rules-first handles 90%+ of cases
2. LLM fallback is acceptable latency
3. Together AI is reliable and fast enough

## Out of Scope (Post-MVP)

- Slash commands
- Interactive buttons/menus
- Rich embeds
- Message editing
- File attachments
- Voice messages
- Localization/i18n
- Analytics/metrics
- Admin dashboard
- User preferences beyond timezone
