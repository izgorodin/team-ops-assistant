## Problem

Webhook endpoints accept any request without verifying it comes from the actual platform.

## Security Risk

Attackers could send fake webhook payloads to trigger bot actions.

## Solution

### Telegram
Use `X-Telegram-Bot-Api-Secret-Token` header:
```python
secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
if secret_token != settings.telegram_webhook_secret:
    return jsonify({"error": "Unauthorized"}), 401
```

### Slack
Verify request signature using `X-Slack-Signature`:
```python
from slack_sdk.signature import SignatureVerifier
verifier = SignatureVerifier(settings.slack_signing_secret)
if not verifier.is_valid(body, timestamp, signature):
    return jsonify({"error": "Unauthorized"}), 401
```

### WhatsApp
Already has verify token check for GET, add signature for POST.

## Acceptance Criteria

- [ ] Telegram webhook verifies secret token
- [ ] Slack webhook verifies request signature
- [ ] WhatsApp webhook verifies payload signature
- [ ] Unauthorized requests return 401
- [ ] New env vars documented in env.example

## Labels
- security
- enhancement

## Part of
Epic #19
