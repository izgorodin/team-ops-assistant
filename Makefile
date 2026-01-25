# Team Ops Assistant - Development Commands
# See CLAUDE.md for full documentation

.PHONY: help install dev test lint format typecheck check run clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make install    - Install production dependencies"
	@echo "  make dev        - Install all dependencies (prod + dev)"
	@echo "  make test       - Run pytest test suite"
	@echo "  make lint       - Run ruff linter"
	@echo "  make format     - Format code with ruff"
	@echo "  make typecheck  - Run pyright type checker"
	@echo "  make check      - Run all checks (lint + typecheck + test)"
	@echo "  make run        - Start the application"
	@echo "  make clean      - Remove cache files"

# Dependencies
install:
	pip install -r requirements.txt

dev: install
	pip install -r requirements-dev.txt

# Quality checks
test:
	pytest

lint:
	ruff check src tests scripts

format:
	ruff format src tests scripts
	ruff check src tests scripts --fix

typecheck:
	pyright src tests

# Combined check (CI-like)
check: lint typecheck test
	@echo "✅ All checks passed!"

# Run application
run:
	./run.sh

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "🧹 Cache cleaned!"
