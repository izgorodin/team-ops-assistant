## Problem

No convenient way to run common development tasks. Developers must remember multiple commands.

## Solution

Add a Makefile with common targets:

```makefile
.PHONY: help install test lint format typecheck run clean

help:           ## Show this help
install:        ## Install dependencies
test:           ## Run tests
lint:           ## Run linter (ruff check)
format:         ## Format code (ruff format)
typecheck:      ## Run type checker (pyright)
run:            ## Start server
run-polling:    ## Start in polling mode
run-tunnel:     ## Start with ngrok tunnel
clean:          ## Clean cache files
all:            ## Run all checks (lint, typecheck, test)
```

## Acceptance Criteria

- [ ] `make help` shows all available targets
- [ ] `make test` runs pytest
- [ ] `make lint` runs ruff check
- [ ] `make typecheck` runs pyright
- [ ] `make all` runs full CI check locally
- [ ] README updated with Makefile usage

## Labels
- enhancement
- developer-experience

## Part of
Epic #19
