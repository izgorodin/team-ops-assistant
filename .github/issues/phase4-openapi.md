## Problem

No machine-readable API documentation. Developers must read markdown docs.

## Solution

Create OpenAPI 3.0 specification:

```yaml
# docs/openapi.yaml
openapi: 3.0.3
info:
  title: Team Ops Assistant API
  version: 0.1.0
  description: Multi-platform bot for timezone conversions

paths:
  /health:
    get:
      summary: Health check
      responses:
        '200':
          description: Application is healthy

  /hooks/telegram:
    post:
      summary: Telegram webhook endpoint
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TelegramUpdate'
      responses:
        '200':
          description: Processed successfully

  /verify:
    get:
      summary: Timezone verification page
      parameters:
        - name: token
          in: query
          required: true
          schema:
            type: string

  /api/verify:
    post:
      summary: Submit timezone verification
      requestBody:
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/VerifyRequest'
```

## Benefits

- Auto-generated API documentation
- Client SDK generation
- API testing tools support (Postman import)
- Swagger UI for interactive exploration

## Acceptance Criteria

- [ ] OpenAPI spec created at docs/openapi.yaml
- [ ] All endpoints documented
- [ ] Request/response schemas defined
- [ ] Swagger UI available at /docs (optional)
- [ ] Spec validates with openapi-spec-validator

## Labels
- documentation
- enhancement

## Part of
Epic #19
