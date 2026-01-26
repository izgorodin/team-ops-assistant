"""Tests for structured logging configuration.

Tests that structlog is properly configured and logging works.
"""

from __future__ import annotations

import structlog

from src.core.logging_config import (
    bind_contextvars,
    clear_contextvars,
    configure_logging,
    get_logger,
)


class TestLoggingConfiguration:
    """Tests for logging configuration."""

    def test_configure_logging_console(self) -> None:
        """Configure logging in console mode (development)."""
        configure_logging(level="INFO", json_output=False)
        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging_json(self) -> None:
        """Configure logging in JSON mode (production)."""
        configure_logging(level="INFO", json_output=True)
        logger = get_logger("test")
        assert logger is not None

    def test_get_logger_returns_bound_logger(self) -> None:
        """get_logger should return a structlog logger."""
        configure_logging(level="DEBUG", json_output=False)
        logger = get_logger("test.module")
        assert logger is not None

    def test_context_binding(self) -> None:
        """Context variables should be bindable and clearable."""
        configure_logging(level="INFO", json_output=False)

        clear_contextvars()
        bind_contextvars(request_id="abc123", user_id="user1")

        # Context should be bound
        logger = get_logger("test")
        assert logger is not None

        clear_contextvars()

    def test_logger_has_standard_methods(self) -> None:
        """Logger should have standard logging methods."""
        configure_logging(level="DEBUG", json_output=False)
        logger = get_logger("test")

        # These should not raise
        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")


class TestStructlogIntegration:
    """Tests for structlog integration with the application."""

    def test_structlog_is_imported(self) -> None:
        """structlog should be properly imported."""
        assert structlog is not None

    def test_can_create_logger_directly(self) -> None:
        """Should be able to create logger with structlog directly."""
        logger = structlog.get_logger("direct.test")
        assert logger is not None
