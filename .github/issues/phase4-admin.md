## Problem

No way to view system statistics or manage users/chats without database access.

## Solution

Add protected admin API endpoints:

### Endpoints

```
GET  /admin/stats           - System statistics
GET  /admin/users           - List users with timezone data
GET  /admin/users/:id       - Get specific user
GET  /admin/chats           - List chats
POST /admin/chats/:id/tz    - Set chat default timezone
```

### Statistics Response
```json
{
  "users_total": 150,
  "users_verified": 120,
  "chats_total": 25,
  "messages_today": 450,
  "conversions_today": 89,
  "uptime_seconds": 86400
}
```

### Authentication

Use API key in header:
```
Authorization: Bearer <ADMIN_API_KEY>
```

## Security

- Admin endpoints protected by API key
- Rate limited (10 req/min)
- Logged with correlation ID
- No sensitive data in responses

## Acceptance Criteria

- [ ] /admin/stats endpoint implemented
- [ ] /admin/users endpoint implemented
- [ ] API key authentication
- [ ] Rate limiting on admin endpoints
- [ ] Documented in docs/API.md

## Labels
- enhancement
- feature

## Part of
Epic #19
