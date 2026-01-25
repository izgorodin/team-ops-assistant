"""Unit tests for LLM fallback (Layer 3).

Tests LLM API calls with mocked HTTP responses.
Contract: detect_time_with_llm(text) → bool
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import respx
from httpx import Response

from src.core.llm_fallback import _parse_llm_response, detect_time_with_llm

if TYPE_CHECKING:
    from collections.abc import Iterator


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_api_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Mock settings to have a test API key so HTTP mocks work."""
    from src import settings

    original = getattr(settings, "_settings", None)

    class MockConfig:
        class llm:
            base_url = "https://integrate.api.nvidia.com/v1"
            model = "test-model"

            class detection:
                max_tokens = 100
                temperature = 0.1
                timeout = 10.0

    class MockSettings:
        nvidia_api_key = "test-api-key"
        config = MockConfig()

    monkeypatch.setattr(settings, "_settings", MockSettings())
    yield
    # Restore original
    if original is not None:
        monkeypatch.setattr(settings, "_settings", original)


# ============================================================================
# Contract Tests - Response Parsing
# ============================================================================


def test_parse_llm_response_returns_bool() -> None:
    """Contract: _parse_llm_response returns bool."""
    result = _parse_llm_response('{"contains_time": true}')
    assert isinstance(result, bool)


def test_parse_llm_response_json_true() -> None:
    """Parse JSON with contains_time: true."""
    content = '{"contains_time": true}'
    assert _parse_llm_response(content) is True


def test_parse_llm_response_json_false() -> None:
    """Parse JSON with contains_time: false."""
    content = '{"contains_time": false}'
    assert _parse_llm_response(content) is False


def test_parse_llm_response_markdown_json() -> None:
    """Parse JSON wrapped in markdown code block."""
    content = '```json\n{"contains_time": true}\n```'
    assert _parse_llm_response(content) is True


def test_parse_llm_response_markdown_no_lang() -> None:
    """Parse JSON wrapped in markdown block without language."""
    content = '```\n{"contains_time": false}\n```'
    assert _parse_llm_response(content) is False


def test_parse_llm_response_with_extra_fields() -> None:
    """Parse JSON with extra fields."""
    content = '{"contains_time": true, "confidence": 0.9, "reason": "has 3pm"}'
    assert _parse_llm_response(content) is True


def test_parse_llm_response_with_text_around_json() -> None:
    """Parse JSON embedded in text."""
    content = 'Here is my analysis:\n{"contains_time": true}\nThe text contains a time.'
    assert _parse_llm_response(content) is True


# ============================================================================
# Edge Cases - Response Parsing
# ============================================================================


def test_parse_llm_response_invalid_json_fallback() -> None:
    """Invalid JSON should use keyword fallback."""
    content = 'The answer is "contains_time": true based on the text.'
    assert _parse_llm_response(content) is True


def test_parse_llm_response_invalid_json_false() -> None:
    """Invalid JSON with false keyword."""
    content = 'I found "contains_time": false in this text.'
    assert _parse_llm_response(content) is False


def test_parse_llm_response_garbage_fails_open() -> None:
    """Garbage response should fail open (return True)."""
    content = "I don't know what you're asking"
    assert _parse_llm_response(content) is True


def test_parse_llm_response_empty_fails_open() -> None:
    """Empty response should fail open (return True)."""
    assert _parse_llm_response("") is True


def test_parse_llm_response_whitespace_fails_open() -> None:
    """Whitespace-only response should fail open."""
    assert _parse_llm_response("   \n\t  ") is True


# ============================================================================
# API Call Tests (Mocked HTTP)
# ============================================================================


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_success_true(mock_api_key: None) -> None:
    """LLM API returns contains_time: true."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": '{"contains_time": true}'}}]},
        )
    )

    result = await detect_time_with_llm("Meeting at 3pm")
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_success_false(mock_api_key: None) -> None:
    """LLM API returns contains_time: false."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": '{"contains_time": false}'}}]},
        )
    )

    result = await detect_time_with_llm("I have 3 cats")
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_error_fails_open(mock_api_key: None) -> None:
    """LLM API error should fail open (return True)."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(500, text="Internal Server Error")
    )

    result = await detect_time_with_llm("Test text")
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_timeout_fails_open(mock_api_key: None) -> None:
    """LLM API timeout should fail open (return True)."""
    import httpx

    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    result = await detect_time_with_llm("Test text")
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_invalid_json_response(mock_api_key: None) -> None:
    """LLM API returns invalid JSON in response."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [{"message": {"content": "Yes, the text contains a time reference."}}]
            },
        )
    )

    # Fails open because can't parse response
    result = await detect_time_with_llm("Test text")
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_markdown_response(mock_api_key: None) -> None:
    """LLM API returns markdown-wrapped JSON."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": '```json\n{"contains_time": false}\n```'}}]},
        )
    )

    result = await detect_time_with_llm("I have 3 cats")
    assert result is False


# ============================================================================
# No API Key Tests
# ============================================================================


@pytest.mark.asyncio
async def test_llm_no_api_key_fails_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing API key should fail open (return True)."""
    # Mock settings to return no API key
    from src import settings

    class MockSettings:
        nvidia_api_key = ""

        class config:
            class llm:
                base_url = "https://integrate.api.nvidia.com/v1"
                model = "test"
                max_tokens = 100
                temperature = 0.1

    monkeypatch.setattr(settings, "_settings", MockSettings())

    result = await detect_time_with_llm("Test text")
    assert result is True


# ============================================================================
# Circuit Breaker Tests
# ============================================================================


class TestCircuitBreaker:
    """Tests for LLM circuit breaker functionality."""

    def test_circuit_breaker_starts_closed(self) -> None:
        """Circuit breaker should start in closed state (allowing requests)."""
        from src.core.llm_fallback import LLMCircuitBreaker
        from src.settings import CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout_seconds=60.0)
        cb = LLMCircuitBreaker(config)

        assert cb.is_open() is False

    def test_circuit_breaker_opens_after_threshold_failures(self) -> None:
        """Circuit breaker should open after consecutive failures reach threshold."""
        from src.core.llm_fallback import LLMCircuitBreaker
        from src.settings import CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout_seconds=60.0)
        cb = LLMCircuitBreaker(config)

        # Record failures
        cb.record_failure()
        assert cb.is_open() is False
        cb.record_failure()
        assert cb.is_open() is False
        cb.record_failure()
        assert cb.is_open() is True  # Should open after 3 failures

    def test_circuit_breaker_resets_on_success(self) -> None:
        """Circuit breaker failure count should reset on success."""
        from src.core.llm_fallback import LLMCircuitBreaker
        from src.settings import CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout_seconds=60.0)
        cb = LLMCircuitBreaker(config)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # Reset counter
        cb.record_failure()
        cb.record_failure()

        assert cb.is_open() is False  # Still closed because success reset counter

    def test_circuit_breaker_closes_after_timeout(self) -> None:
        """Circuit breaker should close (allow retry) after reset timeout."""
        from unittest.mock import patch

        from src.core.llm_fallback import LLMCircuitBreaker
        from src.settings import CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout_seconds=1.0)

        # Mock time consistently throughout the test
        with patch("src.core.llm_fallback.time") as mock_time:
            # Start at t=1000
            mock_time.time.return_value = 1000.0

            cb = LLMCircuitBreaker(config)
            cb.record_failure()
            cb.record_failure()
            cb.record_failure()
            assert cb.is_open() is True  # _last_failure_time = 1000.0

            # Advance time past reset_timeout_seconds (1.0s)
            mock_time.time.return_value = 1002.0  # 2 seconds later
            assert cb.is_open() is False  # elapsed = 2s > 1s reset timeout

    def test_circuit_breaker_disabled_always_closed(self) -> None:
        """Circuit breaker should stay closed when disabled."""
        from src.core.llm_fallback import LLMCircuitBreaker
        from src.settings import CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3, reset_timeout_seconds=60.0, enabled=False
        )
        cb = LLMCircuitBreaker(config)

        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        assert cb.is_open() is False  # Still closed because disabled

    @pytest.mark.asyncio
    @respx.mock
    async def test_extraction_skips_llm_when_circuit_open(self) -> None:
        """extract_times_with_llm should return empty when circuit is open."""
        import httpx

        from src.core import llm_fallback
        from src.core.llm_fallback import (
            LLMCircuitBreaker,
            extract_times_with_llm,
        )
        from src.settings import CircuitBreakerConfig

        # Create fresh circuit breaker in open state
        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout_seconds=60.0)
        cb = LLMCircuitBreaker(config)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()

        # Inject into module
        llm_fallback._circuit_breaker = cb

        try:
            # Mock should NOT be called since circuit is open
            route = respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
                side_effect=httpx.TimeoutException("should not be called")
            )

            result = await extract_times_with_llm("test text")

            assert result == []  # Empty, circuit skipped LLM
            assert route.call_count == 0  # API not called
        finally:
            # Always reset to avoid polluting other tests
            llm_fallback._circuit_breaker = None

    def test_circuit_breaker_integration_with_extract(self) -> None:
        """Circuit breaker should integrate correctly with extract_times_with_llm."""
        from src.core import llm_fallback
        from src.core.llm_fallback import LLMCircuitBreaker, get_circuit_breaker
        from src.settings import CircuitBreakerConfig

        # Create a fresh circuit breaker
        config = CircuitBreakerConfig(failure_threshold=3, reset_timeout_seconds=60.0, enabled=True)
        cb = LLMCircuitBreaker(config)
        llm_fallback._circuit_breaker = cb

        try:
            # Verify get_circuit_breaker returns our instance
            assert get_circuit_breaker() is cb

            # Simulate API failures (as would happen from timeout/error)
            cb.record_failure()
            cb.record_failure()
            assert cb.is_open() is False  # Not open yet

            cb.record_failure()
            assert cb.is_open() is True  # Now open after 3 failures

            # Verify success resets
            cb.record_success()
            assert cb.is_open() is False
        finally:
            llm_fallback._circuit_breaker = None
