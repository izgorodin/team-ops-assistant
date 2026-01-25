## Problem

No visibility into test coverage. No coverage badge in README.

## Solution

1. Add pytest-cov to requirements-dev.txt
2. Configure codecov or coveralls
3. Add coverage badge to README.md
4. Set coverage threshold (target: 85%+)

## Implementation

```yaml
# In CI workflow
- run: pytest --cov=src --cov-report=xml --cov-fail-under=80
- uses: codecov/codecov-action@v4
  with:
    files: ./coverage.xml
```

```markdown
# In README.md
[![codecov](https://codecov.io/gh/izgorodin/team-ops-assistant/branch/main/graph/badge.svg)](https://codecov.io/gh/izgorodin/team-ops-assistant)
```

## Acceptance Criteria

- [ ] Coverage report generated on each CI run
- [ ] Coverage badge displays in README
- [ ] CI fails if coverage drops below threshold
- [ ] Coverage trend visible in codecov dashboard

## Labels
- enhancement
- testing
- ci/cd

## Part of
Epic #19
