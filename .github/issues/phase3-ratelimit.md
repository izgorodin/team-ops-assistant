## Problem

No protection against abuse. A user or chat could spam the bot.

## Current State

Only deduplication throttle exists (2 seconds between responses in same chat).

## Solution

Add proper rate limiting:

```python
from collections import defaultdict
from time import time

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time()
        # Clean old requests
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        if len(self.requests[key]) >= self.max_requests:
            return False
        self.requests[key].append(now)
        return True

# Configuration
rate_limits:
  per_user:
    requests: 10
    window_seconds: 60
  per_chat:
    requests: 30
    window_seconds: 60
```

## Features

- Per-user rate limiting
- Per-chat rate limiting
- Configurable limits in configuration.yaml
- Graceful 429 response with retry-after header

## Acceptance Criteria

- [ ] Rate limiter implemented
- [ ] Limits configurable via configuration.yaml
- [ ] Returns 429 Too Many Requests when exceeded
- [ ] Logs rate limit violations
- [ ] Tests for rate limiting logic

## Labels
- security
- enhancement

## Part of
Epic #19
