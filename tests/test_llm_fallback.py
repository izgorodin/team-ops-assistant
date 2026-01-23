"""Unit tests for LLM fallback (Layer 3).

Tests LLM API calls with mocked HTTP responses.
Contract: detect_time_with_llm(text) → bool
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from src.core.llm_fallback import _parse_llm_response, detect_time_with_llm

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
async def test_llm_api_success_true() -> None:
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
async def test_llm_api_success_false() -> None:
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
async def test_llm_api_error_fails_open() -> None:
    """LLM API error should fail open (return True)."""
    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        return_value=Response(500, text="Internal Server Error")
    )

    result = await detect_time_with_llm("Test text")
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_timeout_fails_open() -> None:
    """LLM API timeout should fail open (return True)."""
    import httpx

    respx.post("https://integrate.api.nvidia.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    result = await detect_time_with_llm("Test text")
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_llm_api_invalid_json_response() -> None:
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
async def test_llm_api_markdown_response() -> None:
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
