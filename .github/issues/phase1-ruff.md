## Problem

Ruff reports 7 warnings in scripts/ directory:

```
scripts/analyze_thresholds.py - B007: Loop control variable `expected` not used
scripts/analyze_thresholds.py - B007: Loop control variable `got` not used
scripts/test_llm_on_failures.py - B007: Loop control variable `expected` not used
scripts/test_llm_on_failures.py - B007: Loop control variable `got` not used
```

## Solution

Rename unused loop variables with underscore prefix:

```python
# Before
for text, expected, got, notes, error_type in errors:

# After
for text, _expected, _got, notes, error_type in errors:
```

## Acceptance Criteria

- [ ] `ruff check .` passes with 0 errors
- [ ] Scripts still function correctly

## Labels
- bug
- good first issue

## Part of
Epic #19
