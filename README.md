# Team Ops Assistant

[![CI](https://github.com/izgorodin/team-ops-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/izgorodin/team-ops-assistant/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/izgorodin/team-ops-assistant/branch/main/graph/badge.svg)](https://codecov.io/gh/izgorodin/team-ops-assistant)
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

| Platform | Status | Webhook Endpoint |
|----------|--------|------------------|
| Telegram | ✅ Complete | `/hooks/telegram` |
| Slack | ✅ Complete | `/hooks/slack` |
| Discord | ✅ Complete | `/hooks/discord` |
| WhatsApp | ✅ Complete | `/hooks/whatsapp` |

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

This project uses centralized AI configuration via [AGENTS.md](./AGENTS.md) standard:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Main AI instructions (source of truth) |
| `CLAUDE.md` | Claude Code (symlink) |
| `.github/copilot-instructions.md` | GitHub Copilot (symlink) |
| `.github/instructions/*.md` | Path-specific rules |
| `.claude/settings.json` | Claude Code settings |

## Platform Setup

### Telegram

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow prompts
3. Copy the bot token to `TELEGRAM_BOT_TOKEN`
4. Set webhook: `https://your-domain.com/hooks/telegram`

### Slack

1. Go to [Slack API](https://api.slack.com/apps) → Create New App
2. Choose "From scratch", select workspace
3. **OAuth & Permissions** → Add scopes:
   - `chat:write` - Send messages
   - `app_mentions:read` - Detect @mentions
   - `channels:history` - Read channel messages
   - `users:read` - Get user info
4. Install to Workspace → Copy **Bot User OAuth Token** to `SLACK_BOT_TOKEN`
5. **Event Subscriptions** → Enable, set URL: `https://your-domain.com/hooks/slack`
6. Subscribe to events: `message.channels`, `app_mention`

### Discord

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. New Application → Bot → Add Bot
3. Copy token to `DISCORD_BOT_TOKEN`
4. **Privileged Gateway Intents**: Enable Message Content Intent
5. OAuth2 → URL Generator:
   - Scopes: `bot`
   - Permissions: `Send Messages`, `Read Message History`
6. Use generated URL to invite bot to server
7. _(Optional, advanced)_ Discord bots normally connect via the gateway (not webhooks). The `/hooks/discord` endpoint is provided for custom proxy / integration-testing setups only.

### WhatsApp (Business API)

1. Create [Meta Developer Account](https://developers.facebook.com/)
2. Create App → Business → WhatsApp
3. **WhatsApp** → API Setup:
   - Copy **Access Token** to `WHATSAPP_ACCESS_TOKEN`
   - Copy **Phone Number ID** to `WHATSAPP_PHONE_NUMBER_ID`
4. Configure webhook URL: `https://your-domain.com/hooks/whatsapp`
5. Set `WHATSAPP_VERIFY_TOKEN` to any secret string (used for webhook verification)
6. Subscribe to `messages` webhook field

> **Note:** WhatsApp requires HTTPS and business verification for production use.

## Documentation

- [Onboarding](docs/ONBOARDING.md) - Getting started
- [Architecture](docs/ARCHITECTURE.md) - Design overview
- [API Reference](docs/API.md) - Endpoints
- [Runbook](docs/RUNBOOK.md) - Operations

## License

MIT
