## Problem

Pyright strict mode reports 1 error:

```
tests/test_llm_integration.py:42:21 - error:
Argument of type "str" cannot be assigned to parameter "api_key" of type "SecretStr | None"
```

## Solution

Change:
```python
api_key="test-key"
```

To:
```python
from pydantic import SecretStr
api_key=SecretStr("test-key")
```

## Acceptance Criteria

- [ ] `pyright src tests` passes with 0 errors
- [ ] Tests still pass

## Labels
- bug
- good first issue

## Part of
Epic #19
