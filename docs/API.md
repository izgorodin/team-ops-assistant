# Team Ops Assistant - API Documentation

## Base URL

- **Local development**: `http://localhost:8000`
- **Production**: `https://your-app.onrender.com`

## Endpoints

### Health Check

Check if the application is running.

```
GET /health
```

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200` - Application is healthy

---

### Telegram Webhook

Receives Telegram Bot API updates.

```
POST /hooks/telegram
```

**Request Body:** Telegram Update object (JSON)

```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 42,
    "from": {
      "id": 12345678,
      "first_name": "John",
      "username": "johndoe"
    },
    "chat": {
      "id": -100123456789,
      "title": "Team Chat",
      "type": "supergroup"
    },
    "date": 1704067200,
    "text": "Let's meet at 3pm PST tomorrow"
  }
}
```

**Response:**
```json
{
  "status": "processed"
}
```
or
```json
{
  "status": "ignored"
}
```

**Status Codes:**
- `200` - Update processed successfully
- `400` - Invalid JSON
- `500` - Internal server error

---

### Discord Webhook (Stub)

Placeholder for Discord interactions.

```
POST /hooks/discord
```

**Response:**
```json
{
  "status": "not_implemented",
  "message": "Discord connector is a skeleton. See docs for implementation guide."
}
```

**Status Codes:**
- `501` - Not implemented

---

### WhatsApp Webhook Verification

Handles Meta webhook verification challenge.

```
GET /hooks/whatsapp
```

**Query Parameters:**
- `hub.mode` - Should be "subscribe"
- `hub.verify_token` - Must match configured token
- `hub.challenge` - Challenge string to return

**Response:**
- Success: Returns `hub.challenge` value (plain text)
- Failure: `{"error": "Forbidden"}` with status 403

---

### WhatsApp Webhook (Stub)

Placeholder for WhatsApp Cloud API webhooks.

```
POST /hooks/whatsapp
```

**Response:**
```json
{
  "status": "not_implemented",
  "message": "WhatsApp connector is a skeleton. See docs for implementation guide."
}
```

**Status Codes:**
- `501` - Not implemented

---

### Timezone Verification Page

Serves the timezone verification web page.

```
GET /verify
```

**Query Parameters:**
- `token` (required) - Signed verification token

**Response:**
- Success: HTML page (text/html)
- Missing token: `"Missing verification token"` with status 400
- Invalid token: `"Invalid or expired verification token"` with status 400

---

### Timezone Verification API

Submits timezone verification from the web flow.

```
POST /api/verify
```

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "token": "signed-verification-token",
  "tz_iana": "America/Los_Angeles"
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Timezone saved! You can close this page.",
  "timezone": "America/Los_Angeles"
}
```

**Response (Error):**
```json
{
  "error": "Invalid or expired token"
}
```

**Status Codes:**
- `200` - Timezone saved successfully
- `400` - Missing token, missing timezone, invalid token, or invalid timezone

---

## Verification Token Format

Tokens are signed strings with the following format:

```
{platform}|{user_id}|{chat_id}|{expires_timestamp}|{nonce}|{signature}
```

- **platform**: Platform identifier (telegram, discord, whatsapp)
- **user_id**: Platform-specific user ID
- **chat_id**: Platform-specific chat ID
- **expires_timestamp**: Unix timestamp when token expires
- **nonce**: Random string for uniqueness
- **signature**: HMAC-SHA256 signature (first 16 chars)

Tokens are:
- Valid for 24 hours by default
- Tied to a specific user and chat
- Signed with `VERIFY_TOKEN_SECRET`
- Cannot be forged or reused

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Description of the error"
}
```

Common errors:
- `"Missing request body"` - No JSON body provided
- `"Missing token"` - Token parameter required
- `"Missing timezone"` - Timezone parameter required
- `"Invalid or expired token"` - Token is malformed, tampered, or expired
- `"Invalid timezone"` - Provided timezone is not a valid IANA timezone

---

## Rate Limiting

The application includes built-in throttling:
- Minimum 2 seconds between responses in the same chat
- Prevents spam when multiple time mentions occur rapidly

Platform-specific rate limits also apply (e.g., Telegram Bot API limits).

---

## Webhook Setup

### Telegram

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://your-app.onrender.com/hooks/telegram" \
  -d "allowed_updates=[\"message\"]"
```

### WhatsApp

1. Configure in Meta Business Suite
2. Callback URL: `https://your-app.onrender.com/hooks/whatsapp`
3. Verify Token: Your `WHATSAPP_VERIFY_TOKEN` value

### Discord

Discord uses gateway connections or slash command interactions.
See Discord documentation for webhook configuration.
