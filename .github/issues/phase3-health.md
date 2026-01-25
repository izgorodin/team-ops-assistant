## Problem

Current `/health` endpoint only returns `{"status": "ok"}` without checking actual dependencies.

## Solution

### Deep Health Check `/health`
```python
@app.route("/health")
async def health():
    checks = {
        "mongodb": await check_mongodb(),
        "status": "ok"
    }
    status_code = 200 if all_healthy(checks) else 503
    return jsonify(checks), status_code
```

### Readiness Probe `/ready`
```python
@app.route("/ready")
async def ready():
    # Check if app is ready to receive traffic
    checks = {
        "mongodb": await check_mongodb(),
        "pipeline": app.pipeline is not None,
    }
    return jsonify(checks), 200 if all(checks.values()) else 503
```

### Liveness Probe `/live`
```python
@app.route("/live")
async def live():
    # Simple liveness check
    return jsonify({"status": "alive"})
```

## Benefits

- Better observability
- Faster incident detection
- Proper Kubernetes/Render health checks

## Acceptance Criteria

- [ ] `/health` checks MongoDB connection
- [ ] `/ready` returns 503 if dependencies unavailable
- [ ] `/live` always returns 200 if app is running
- [ ] Render health check uses `/health`
- [ ] Documented in docs/API.md

## Labels
- enhancement
- observability

## Part of
Epic #19
