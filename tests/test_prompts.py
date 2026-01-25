"""Tests for prompt loading utilities."""

from __future__ import annotations

import pytest

from src.core.prompts import (
    _template_cache,
    get_agent_system_prompt,
    get_ui_message,
    load_prompt,
)


class TestLoadPrompt:
    """Tests for load_prompt function."""

    def setup_method(self) -> None:
        """Clear template cache before each test."""
        _template_cache.clear()

    def test_load_existing_prompt(self) -> None:
        """Should load an existing prompt file."""
        result = load_prompt("trigger_detect", message="test message")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_load_prompt_with_variables(self) -> None:
        """Should render template variables."""
        result = load_prompt("ui/saved", tz_iana="Europe/Moscow")

        assert "Europe/Moscow" in result
        assert "✅" in result

    def test_load_prompt_caches_template(self) -> None:
        """Should cache template after first load."""
        assert "ui/onboarding" not in _template_cache

        load_prompt("ui/onboarding")

        assert "ui/onboarding" in _template_cache

    def test_load_prompt_uses_cache(self) -> None:
        """Should use cached template on subsequent calls."""
        # First call
        result1 = load_prompt("ui/onboarding")
        # Second call (should use cache)
        result2 = load_prompt("ui/onboarding")

        assert result1 == result2
        assert "ui/onboarding" in _template_cache

    def test_load_prompt_strips_whitespace(self) -> None:
        """Should strip leading/trailing whitespace."""
        result = load_prompt("ui/onboarding")

        assert not result.startswith("\n")
        assert not result.endswith("\n")

    def test_load_prompt_nonexistent_raises(self) -> None:
        """Should raise FileNotFoundError for missing prompts."""
        with pytest.raises(FileNotFoundError, match="Prompt not found"):
            load_prompt("nonexistent_prompt")

    def test_load_nested_prompt(self) -> None:
        """Should load prompts from subdirectories."""
        result = load_prompt("ui/error")

        assert isinstance(result, str)
        assert len(result) > 0


class TestGetAgentSystemPrompt:
    """Tests for get_agent_system_prompt function."""

    def setup_method(self) -> None:
        """Clear template cache before each test."""
        _template_cache.clear()

    def test_without_current_tz(self) -> None:
        """Should return prompt without dynamic CONTEXT section."""
        result = get_agent_system_prompt()

        assert "timezone assistant" in result.lower()
        # Should NOT have the dynamic CONTEXT section at the end
        assert "CONTEXT: CURRENT_TZ=" not in result

    def test_with_current_tz(self) -> None:
        """Should include dynamic CONTEXT section with timezone."""
        result = get_agent_system_prompt(current_tz="Europe/Prague")

        # Should have the dynamic CONTEXT section at the end
        assert "CONTEXT: CURRENT_TZ=Europe/Prague" in result

    def test_with_none_current_tz(self) -> None:
        """Should handle None explicitly - no dynamic CONTEXT section."""
        result = get_agent_system_prompt(current_tz=None)

        # Should NOT have the dynamic CONTEXT section
        assert "CONTEXT: CURRENT_TZ=" not in result


class TestGetUiMessage:
    """Tests for get_ui_message function."""

    def setup_method(self) -> None:
        """Clear template cache before each test."""
        _template_cache.clear()

    def test_onboarding_message(self) -> None:
        """Should load onboarding message."""
        result = get_ui_message("onboarding")

        assert "город" in result or "city" in result.lower()
        assert "🌍" in result

    def test_saved_message_with_timezone(self) -> None:
        """Should render saved message with timezone."""
        result = get_ui_message("saved", tz_iana="America/New_York")

        assert "America/New_York" in result
        assert "✅" in result

    def test_reverify_message(self) -> None:
        """Should load reverify message."""
        result = get_ui_message("reverify", existing_tz="Europe/London")

        assert "Europe/London" in result

    def test_timeout_message(self) -> None:
        """Should load timeout message."""
        result = get_ui_message("timeout")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_error_message(self) -> None:
        """Should load error message."""
        result = get_ui_message("error")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_session_failed_message(self) -> None:
        """Should load session_failed message."""
        result = get_ui_message("session_failed")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_nonexistent_ui_message_raises(self) -> None:
        """Should raise FileNotFoundError for missing UI messages."""
        with pytest.raises(FileNotFoundError, match="Prompt not found"):
            get_ui_message("nonexistent")
