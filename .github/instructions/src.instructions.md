---
applyTo: "src/**/*.py"
---

# Source Code Guidelines

## Async Requirements
- All I/O operations MUST use async/await
- Use `Motor` for MongoDB, `httpx` for HTTP calls
- Never use blocking calls in async functions

## Type Hints
- Required on all function signatures
- Use Pydantic models from `src/core/models.py`
- Pyright strict mode must pass

## Code Organization
- Business logic goes in `src/core/`
- Platform-specific code in `src/connectors/<platform>/`
- Database operations in `src/storage/`

## Patterns
- Connectors: `inbound.py` normalizes to `NormalizedEvent`, `outbound.py` sends `OutboundMessage`
- Configuration: Load via `src/settings.py`, never hardcode values
- Errors: Log and handle gracefully, never crash on user input

## Imports
```python
# Standard library first
from typing import TYPE_CHECKING

# Third-party
from pydantic import BaseModel

# Local
from src.core.models import NormalizedEvent
```
