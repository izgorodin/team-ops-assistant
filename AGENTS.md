# Team Ops Assistant - AI Agent Instructions

## Project Overview

Multi-platform TeamOps assistant bot (Telegram/Discord/WhatsApp) that detects time mentions and replies with multi-timezone conversions.

**Tech Stack:**
- Python 3.11+ with async/await (Quart framework)
- MongoDB Atlas with Motor (async driver)
- Pydantic v2 for data validation
- Together AI (Qwen3) for LLM fallback
- Ruff for linting, Pyright for strict typing

**Architecture:** Thin Adapters, Rich Core
- Platform connectors normalize to `NormalizedEvent`
- Core domain processes platform-agnostically
- Rules-first approach: regex handles 90%+ cases, LLM is fallback only

## Directory Structure

```
src/
├── app.py              # Quart application entry
├── settings.py         # Configuration loading
├── core/               # Platform-agnostic business logic
├── connectors/         # Platform adapters (telegram/, discord/, whatsapp/)
├── storage/            # MongoDB operations
└── web/                # Verification flow UI
tests/                  # Pytest test suite
docs/                   # Architecture, API, Runbook
prompts/                # LLM prompt templates
```

## Build & Test Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run application
./run.sh

# Run tests
pytest

# Lint and format
ruff format src tests
ruff check src tests --fix

# Type check (strict)
pyright src tests
```

## Code Style

- **Formatting:** Ruff with 100 char line length (see `pyproject.toml`)
- **Type hints:** Required everywhere, Pyright strict mode
- **Imports:** isort via Ruff, first-party = `src`
- **Quotes:** Double quotes
- **Async:** All I/O operations must be async/await

Reference configs:
- `pyproject.toml` - Ruff and pytest settings
- `pyrightconfig.json` - Type checking settings

## Patterns & Conventions

### Data Models
- Use Pydantic models in `src/core/models.py`
- All models must be immutable where possible
- Use `Platform` enum for platform identification

### Connectors
- Each platform has `inbound.py` (normalize) and `outbound.py` (send)
- Inbound must convert to `NormalizedEvent`
- Outbound must accept `OutboundMessage`

### Error Handling
- Graceful degradation: unknown timezone → prompt verification
- Never crash on user input; log and skip malformed data
- Use structured logging

### Testing
- Contract tests for each connector
- Unit tests for core logic
- All tests must be async-compatible

## Security

- Never commit `.env` files
- Secrets via environment variables only
- Sanitize all user input before processing
- Bot tokens must never be logged

## PR Guidelines

- Squash commits before merging
- Descriptive commit messages
- All checks must pass (ruff, pyright, pytest)
- Update tests for new functionality

## Domain Context

**Core Concepts:**
- `NormalizedEvent`: Platform-agnostic message representation
- `ParsedTime`: Extracted time reference with confidence
- `UserTzState`: User's timezone with confidence score
- Confidence threshold: 0.7 (below = prompt verification)

**Pipeline Flow:**
1. Webhook → Normalize → Dedupe check
2. Parse time references (rules-first, LLM fallback)
3. Resolve user timezone (verified > chat default > prompt)
4. Convert to team timezones
5. Send formatted response
