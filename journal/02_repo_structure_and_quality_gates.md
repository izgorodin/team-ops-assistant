# 02 - Repository Structure and Quality Gates

## Repository Structure

The repository follows a clean separation of concerns:

```
team-ops-assistant/
├── src/                    # Application source code
│   ├── app.py             # Quart application entry point
│   ├── settings.py        # Configuration loading
│   ├── core/              # Platform-agnostic business logic
│   ├── storage/           # Data persistence (MongoDB)
│   ├── web/               # Web routes and templates
│   └── connectors/        # Platform adapters
├── tests/                  # Test suite
├── docs/                   # Documentation
├── journal/                # Implementation specs
├── prompts/                # LLM prompt templates
├── configuration.yaml      # Non-secret config
├── requirements.txt        # Dependencies
├── pyproject.toml         # Project metadata and tool config
├── pyrightconfig.json     # Type checking config
└── run.sh                  # Startup script
```

## Quality Gates

### Code Style and Linting

Using **Ruff** for both linting and formatting:

```bash
# Format code
ruff format src tests

# Check for issues
ruff check src tests

# Auto-fix issues
ruff check src tests --fix
```

Configuration in `pyproject.toml`:
- Target: Python 3.11
- Line length: 100
- Selected rules: E, W, F, I, B, C4, UP, ARG, SIM, TCH, PTH, RUF

### Type Checking

Using **Pyright** in strict mode:

```bash
pyright src tests
```

Configuration in `pyrightconfig.json`:
- Python 3.11
- Strict mode enabled
- Some "unknown" warnings relaxed for external libraries

### Testing

Using **pytest** with **pytest-asyncio**:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_core_handler.py

# Run with coverage
pytest --cov=src --cov-report=html
```

Configuration in `pyproject.toml`:
- Async mode: auto
- Test path: tests/

### Network Mocking

Using **respx** for mocking HTTP calls in tests:

```python
import respx
from httpx import Response

@respx.mock
async def test_api_call():
    respx.post("https://api.telegram.org/...").mock(
        return_value=Response(200, json={"ok": True})
    )
    # test code...
```

## Dependency Choices

### Production Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| quart | >=0.19.0,<1.0.0 | Async web framework |
| motor | >=3.3.0,<4.0.0 | Async MongoDB driver |
| pydantic | >=2.5.0,<3.0.0 | Data validation |
| pydantic-settings | >=2.1.0,<3.0.0 | Settings management |
| python-dotenv | >=1.0.0,<2.0.0 | .env file loading |
| PyYAML | >=6.0.0,<7.0.0 | YAML parsing |
| httpx | >=0.25.0,<1.0.0 | Async HTTP client |
| Jinja2 | >=3.1.0,<4.0.0 | Template engine |
| langchain | >=0.1.0,<1.0.0 | LLM framework |
| langchain-core | >=0.1.0,<1.0.0 | LangChain core |
| langgraph | >=0.0.50,<1.0.0 | LLM workflows |
| together | >=1.0.0,<2.0.0 | Together AI SDK |
| python-dateutil | >=2.8.0,<3.0.0 | Date parsing |
| pytz | >=2024.1 | Timezone handling |

### Development Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=7.4.0,<9.0.0 | Testing framework |
| pytest-asyncio | >=0.23.0,<1.0.0 | Async test support |
| respx | >=0.21.0,<1.0.0 | HTTP mocking |
| ruff | >=0.1.0,<1.0.0 | Linting/formatting |
| pyright | >=1.1.340,<2.0.0 | Type checking |

### Dependency Notes

1. **together**: The Together AI Python SDK is stable on PyPI. We use it directly rather than a custom wrapper.

2. **pytz vs zoneinfo**: We include pytz for compatibility but primarily use Python 3.11's built-in `zoneinfo` module.

3. **Version ranges**: Upper bounds prevent breaking changes while allowing patch updates.

## CI/CD Recommendations

For GitHub Actions or similar:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: ruff check src tests
      - run: ruff format --check src tests
      - run: pyright src tests
      - run: pytest --cov=src
```

## Pre-commit Hooks (Recommended)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```
