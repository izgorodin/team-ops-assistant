# Team Ops Assistant

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: pyright](https://img.shields.io/badge/type%20checked-pyright-blue.svg)](https://github.com/microsoft/pyright)

Multi-platform TeamOps assistant bot that detects time mentions and replies with multi-timezone conversions.

## Features

- **Time Detection** - Automatically detects time mentions in chat
- **Multi-Timezone Conversion** - Converts to all team timezones
- **One-Click Verification** - Browser-based timezone verification
- **Rules-First Pipeline** - Regex handles 90%+ cases, LLM fallback only when needed
- **Deduplication** - Prevents spam and duplicate responses

## Supported Platforms

| Platform | Status |
|----------|--------|
| Telegram | MVP Complete |
| Discord | Skeleton |
| WhatsApp | Skeleton |

## Quick Start

```bash
# Clone and setup
git clone https://github.com/izgorodin/team-ops-assistant.git
cd team-ops-assistant

# Configure
cp env.example .env
# Edit .env with your credentials

# Run
./run.sh

# Verify
curl http://localhost:8000/health
```

## Development

```bash
# Tests
pytest

# Lint & Format
ruff format src tests
ruff check src tests --fix

# Type Check
pyright src tests
```

## Project Structure

```
src/
├── app.py              # Quart application
├── core/               # Business logic (models, handler, time parsing)
├── connectors/         # Platform adapters (telegram/, discord/, whatsapp/)
├── storage/            # MongoDB operations
└── web/                # Verification flow
tests/                  # Test suite
docs/                   # Documentation
```

## AI-Assisted Development

This project uses centralized AI configuration via [AGENTS.md](https://agents.md) standard:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Main AI instructions (source of truth) |
| `CLAUDE.md` | Claude Code (symlink) |
| `.github/copilot-instructions.md` | GitHub Copilot (symlink) |
| `.github/instructions/*.md` | Path-specific rules |
| `.claude/settings.json` | Claude Code settings |

## Documentation

- [Onboarding](docs/ONBOARDING.md) - Getting started
- [Architecture](docs/ARCHITECTURE.md) - Design overview
- [API Reference](docs/API.md) - Endpoints
- [Runbook](docs/RUNBOOK.md) - Operations

## License

MIT
