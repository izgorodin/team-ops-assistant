"""Structured logging configuration using structlog.

Provides consistent JSON logging with correlation IDs for request tracing.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

# Re-export for convenience
__all__ = [
    "bind_contextvars",
    "clear_contextvars",
    "configure_logging",
    "get_logger",
]


def configure_logging(
    level: str = "INFO",
    json_output: bool | None = None,
) -> None:
    """Configure structlog for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, output JSON. If False, output colored console.
                     If None, auto-detect (JSON in production, console in dev).
    """
    # Auto-detect output format based on environment
    if json_output is None:
        # Use JSON in production (when not running in a TTY)
        json_output = not sys.stderr.isatty() or os.getenv("LOG_FORMAT") == "json"

    # Configure standard library logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stdout,
    )

    # Build processor chain
    shared_processors: list[structlog.types.Processor] = [
        # Add log level
        structlog.stdlib.add_log_level,
        # Merge bound context variables
        merge_contextvars,
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add caller info (module, function, line)
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            ]
        ),
        # Render exceptions as strings
        structlog.processors.format_exc_info,
    ]

    if json_output:
        # JSON output for production
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Colored console output for development
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger.

    Args:
        name: Logger name (typically __name__). If None, uses root logger.

    Returns:
        Configured structlog logger with bound context.
    """
    return structlog.get_logger(name)


def with_request_context(**kwargs: Any) -> None:
    """Bind context variables for the current request.

    Typically called at the start of request processing to add:
    - request_id: Unique identifier for the request
    - platform: Source platform (telegram, discord, etc.)
    - user_id: User identifier
    - chat_id: Chat identifier

    Example:
        with_request_context(
            request_id="abc123",
            platform="telegram",
            user_id="12345",
            chat_id="67890"
        )

    Args:
        **kwargs: Context variables to bind.
    """
    bind_contextvars(**kwargs)


def clear_request_context() -> None:
    """Clear all bound context variables.

    Typically called at the end of request processing.
    """
    clear_contextvars()
