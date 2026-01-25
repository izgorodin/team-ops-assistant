## Problem

No automated CI pipeline. Quality checks run only locally.

## Solution

Create GitHub Actions workflow `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install ruff
      - run: ruff check .
      - run: ruff format --check .

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pyright
      - run: pyright src tests

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v4
```

## Acceptance Criteria

- [ ] CI runs on every push to main
- [ ] CI runs on every PR
- [ ] Lint job passes
- [ ] Type check job passes
- [ ] Test job passes with coverage
- [ ] Branch protection requires CI to pass

## Labels
- enhancement
- ci/cd

## Part of
Epic #19
