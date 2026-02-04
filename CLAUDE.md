# Team Ops Assistant - AI Agent Instructions

> **Note on AI Agent Config Files**
>
> This file (`CLAUDE.md`) is the single source of truth for all AI agents:
>
> - `AGENTS.md` → symlink to `CLAUDE.md`
> - `.github/copilot-instructions.md` → symlink to `CLAUDE.md`
>
> We chose this approach for simplicity — one file to maintain.
> If you need agent-specific instructions, create local versions instead of symlinks.

## Project Overview

Multi-platform TeamOps assistant bot (Telegram/Discord/WhatsApp) that detects time mentions and replies with multi-timezone conversions.

**Tech Stack:**
- Python 3.11+ with async/await (Quart framework)
- MongoDB Atlas with Motor (async driver)
- Pydantic v2 for data validation
- NVIDIA NIM API (Llama 3.1) for LLM fallback
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

### Convenience Functions
When creating convenience functions that wrap Pydantic models:
- Include ALL optional parameters from the underlying model
- Or explicitly document which parameters are NOT supported
- Example: `format_time_conversion()` must support `is_tomorrow` if `ParsedTime` has it

## Security

- Never commit `.env` files
- Secrets via environment variables only
- Sanitize all user input before processing
- Bot tokens must never be logged

## Planning & Refactoring

**ALWAYS use `architecture-analysis` skill BEFORE:**
- Implementing new features
- Refactoring existing code (any size!)
- Replacing or deleting modules
- Moving logic between files

**Why:** Happy path is just the base. Real code has side effects, error paths, and implicit contracts. The skill ensures you inventory ALL behaviors before changing anything.

**Key principle:** Never modify code you don't fully understand. If you can't list 10+ behaviors of a module, you haven't looked hard enough.

## PR Guidelines

- Squash commits before merging
- Descriptive commit messages
- All checks must pass (ruff, pyright, pytest)
- Update tests for new functionality
- Use `pr-review-response` skill for handling review comments (D1-D7 workflow)

## Domain Context

**Core Concepts:**
- `NormalizedEvent`: Platform-agnostic message representation
- `ParsedTime`: Extracted time reference with confidence
- `UserTzState`: User's timezone with confidence score
- Confidence threshold: 0.7 (below = prompt verification)

**Message Flow (98% rules-based):**

1. Webhook → Normalize → Dedupe/throttle/rate-limit
2. Check active session → AgentHandler (if exists)
3. Pipeline: detect triggers (regex) → resolve context → action handlers
4. Orchestrator `_decide_action()`: single decision point for all triggers
5. Session handlers: ConfirmRelocationHandler (rules) or AgentHandler (LLM)

**LLM Used Only For:**

- City normalization (Cyrillic→English) when geonames fails (~5%)
- Time extraction fallback (~2%)
- Multi-turn timezone verification sessions
