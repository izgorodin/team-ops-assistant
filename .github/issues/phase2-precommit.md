## Problem

Pre-commit hooks exist locally but not enforced in CI. Contributors could bypass them.

## Solution

Add pre-commit check to CI workflow:

```yaml
pre-commit:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - uses: pre-commit/action@v3.0.1
```

## Benefits

- Ensures all commits pass pre-commit hooks
- Catches issues that local hooks might miss
- Consistent code quality across all contributors

## Acceptance Criteria

- [ ] Pre-commit job added to CI workflow
- [ ] All existing pre-commit hooks pass in CI
- [ ] PR cannot be merged if pre-commit fails

## Labels
- enhancement
- ci/cd

## Part of
Epic #19
