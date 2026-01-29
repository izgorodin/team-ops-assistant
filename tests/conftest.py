"""Pytest configuration and fixtures.

This module provides shared fixtures for all tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def disable_llm_extraction(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Disable LLM extraction fallback in non-integration tests for speed.

    When regex fails, parse_times would call LLM API which is slow.
    This fixture makes LLM extraction return empty list.

    Tests marked with @pytest.mark.integration skip this mock and use real LLM.
    """
    # Skip mocking for integration tests
    if "integration" in request.keywords:
        yield
        return

    async def mock_extract(*args, **kwargs):
        return []

    with patch(
        "src.core.llm_fallback.extract_times_with_llm",
        side_effect=mock_extract,
    ):
        yield


# Register custom markers
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests that use real external services (LLM, APIs)",
    )
