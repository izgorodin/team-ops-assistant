# Team Ops Assistant - Onboarding Guide

Welcome to Team Ops Assistant! This guide will help you get started with the project.

## Project Overview

Team Ops Assistant is a multi-platform bot that monitors team chat channels and automatically converts time mentions to multiple timezones. It supports:

- **Telegram** (fully implemented - MVP)
- **Discord** (skeleton implementation)
- **WhatsApp Cloud API** (skeleton implementation)

## Quick Start

### Prerequisites

- Python 3.11 or higher
- MongoDB Atlas account (or local MongoDB)
- Bot tokens for your target platforms

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd team-ops-assistant
   ```

2. **Create environment file**
   ```bash
   cp env.example .env
   # Edit .env with your credentials
   ```

3. **Run the application**
   ```bash
   ./run.sh
   ```

   This will:
   - Create a virtual environment
   - Install dependencies
   - Start the server on port 8000

4. **Verify it's running**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"ok"}
   ```

## Project Structure

```
team-ops-assistant/
├── src/
│   ├── app.py              # Main Quart application
│   ├── settings.py         # Configuration loading
│   ├── core/               # Platform-agnostic domain logic
│   │   ├── models.py       # Pydantic data models
│   │   ├── handler.py      # Message processing pipeline
│   │   ├── time_parse.py   # Time extraction
│   │   ├── time_convert.py # Timezone conversion
│   │   ├── timezone_identity.py  # User TZ management
│   │   └── dedupe.py       # Deduplication
│   ├── storage/
│   │   └── mongo.py        # MongoDB operations
│   ├── web/
│   │   ├── routes_verify.py    # Verification web flow
│   │   └── verify_page.html    # Vue.js verification page
│   └── connectors/
│       ├── telegram/       # Telegram adapter (implemented)
│       ├── discord/        # Discord adapter (skeleton)
│       └── whatsapp/       # WhatsApp adapter (skeleton)
├── prompts/                # Jinja2 prompt templates for LLM
├── tests/                  # pytest test suite
├── docs/                   # Documentation
├── journal/                # Implementation specs and progress
├── configuration.yaml      # Non-secret configuration
├── env.example             # Environment template
├── requirements.txt        # Python dependencies
└── run.sh                  # Startup script
```

## Key Concepts

### Normalized Events

All platform-specific messages are converted to a `NormalizedEvent`:

```python
NormalizedEvent(
    platform=Platform.TELEGRAM,
    event_id="unique-id",
    chat_id="chat-id",
    user_id="user-id",
    text="Let's meet at 3pm PST",
    timestamp=datetime.utcnow(),
)
```

### Outbound Messages

The handler returns `OutboundMessage` objects:

```python
OutboundMessage(
    platform=Platform.TELEGRAM,
    chat_id="chat-id",
    text="🕐 3pm PT:\n  → 6pm ET\n  → 11pm UK",
)
```

### Timezone Disambiguation

When a user mentions a time, we determine their timezone using this priority:

1. Explicit timezone in message (e.g., "3pm PST")
2. User's verified timezone (if confidence >= 0.7)
3. Chat default timezone
4. Ask user to verify

### Verification Flow

Users verify their timezone via:

1. **Web verification**: Click link → browser auto-detects → confirm
2. **City pick**: Reply with city name (e.g., "London")

## Configuration

### Environment Variables (.env)

```bash
MONGODB_URI=mongodb+srv://...
TELEGRAM_BOT_TOKEN=your-token
APP_SECRET_KEY=random-secret
```

### Configuration File (configuration.yaml)

```yaml
timezone:
  team_timezones:
    - America/Los_Angeles
    - America/New_York
    - Europe/London
    - Asia/Tokyo

confidence:
  threshold: 0.7      # Min confidence to use timezone
  verified: 1.0       # Web verification confidence
  city_pick: 0.85     # City selection confidence
```

## Development

### Setup Pre-Commit Hooks (Required)

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Now every commit runs: ruff + pyright + basic checks
# Push runs: pytest
```

Pre-commit hooks prevent bad code from being committed. They run automatically.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_core_handler.py -v
```

### Linting and Type Checking

```bash
# Format and lint
ruff format src tests
ruff check src tests --fix

# Type check (strict mode)
pyright src tests
```

### Quality Gates

All checks must pass before merging:
1. **ruff format** - code formatting
2. **ruff check** - linting
3. **pyright** - strict type checking
4. **pytest** - all tests pass

### Adding a New Platform

1. Create connector package in `src/connectors/<platform>/`
2. Implement `inbound.py` with normalization function
3. Implement `outbound.py` with message sending
4. Add webhook route in `src/app.py`
5. Add contract tests in `tests/test_<platform>_contract.py`

See existing connectors for patterns to follow.

## Next Steps

- See [ARCHITECTURE.md](./ARCHITECTURE.md) for design details
- See [RUNBOOK.md](./RUNBOOK.md) for deployment and operations
- See [API.md](./API.md) for endpoint documentation
