## Problem

Developers need MongoDB Atlas connection for local development. No easy way to run everything locally.

## Solution

Add Docker Compose setup with local MongoDB:

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URI=mongodb://mongo:27017/team_ops
    depends_on:
      - mongo
    volumes:
      - .:/app

  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "-m", "src.app", "--host", "0.0.0.0", "--port", "8000"]
```

## Benefits

- No MongoDB Atlas needed for local dev
- One command to start everything: `docker-compose up`
- Consistent environment across developers
- Easy cleanup: `docker-compose down -v`

## Acceptance Criteria

- [ ] Dockerfile created
- [ ] docker-compose.yml created
- [ ] `docker-compose up` starts app + mongo
- [ ] App connects to local MongoDB
- [ ] Documented in docs/ONBOARDING.md

## Labels
- enhancement
- developer-experience

## Part of
Epic #19
