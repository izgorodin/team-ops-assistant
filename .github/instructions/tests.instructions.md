---
applyTo: "tests/**/*.py"
---

# Test Guidelines

## Framework
- Use pytest with async support
- All test functions should be `async def test_*`
- Use `pytest.mark.asyncio` where needed (auto mode enabled)

## Test Types
- **Contract tests**: Verify connector input/output format
- **Unit tests**: Test core logic in isolation
- **Integration tests**: Test full pipeline (mock external services)

## Naming
```python
# Function under test + scenario + expected result
async def test_parse_time_with_timezone_returns_parsed_time():
    ...

async def test_handler_unknown_timezone_prompts_verification():
    ...
```

## Fixtures
- Use `@pytest.fixture` for reusable setup
- Mock external services (MongoDB, HTTP)
- Use factory functions for test data

## Assertions
```python
# Be specific
assert result.timezone == "America/New_York"
assert result.confidence >= 0.7

# Not vague
assert result is not None  # Avoid
```
