## Problem

Current logging uses Python's standard `logging` module with unstructured text output. Hard to parse in log aggregation systems.

## Solution

Switch to `structlog` for JSON-formatted logs:

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# Usage
logger.info("message_processed",
    platform="telegram",
    user_id="123",
    has_time=True,
    duration_ms=45
)
```

### Output
```json
{"event": "message_processed", "platform": "telegram", "user_id": "123", "has_time": true, "duration_ms": 45, "level": "info", "timestamp": "2026-01-25T12:00:00Z"}
```

## Benefits

- Machine-parseable logs
- Easy integration with Datadog/Splunk/ELK
- Request correlation via context vars
- Better debugging with structured context

## Acceptance Criteria

- [ ] structlog added to requirements.txt
- [ ] All loggers migrated to structlog
- [ ] JSON output in production, pretty output in dev
- [ ] Request correlation ID added
- [ ] Key events logged with context (webhook, pipeline, outbound)

## Labels
- enhancement
- observability

## Part of
Epic #19
