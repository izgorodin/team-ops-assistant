"""Integration tests for LLM (Qwen3-Next-80B) with real API calls.

These tests verify that the LLM model works correctly with:
1. Agent tool calling (timezone resolution)
2. LLM fallback for time extraction

Run with: pytest tests/test_llm_integration.py -v -s
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.core.agent_tools import AGENT_TOOLS, GEO_INTENT_TOOLS
from src.core.llm_fallback import extract_times_with_llm
from src.core.session_utils import extract_tool_action
from src.settings import get_settings

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

# Load environment
load_dotenv()

# Skip marker for tests requiring live API
_skip_if_no_api_key = pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY not set - skipping integration tests",
)


@pytest.mark.integration
@_skip_if_no_api_key
class TestAgentToolCalling:
    """Test agent's ability to call tools correctly."""

    @pytest.fixture
    def agent(self) -> CompiledStateGraph[Any]:
        """Create agent with real LLM using config settings."""
        from pydantic import SecretStr

        settings = get_settings()
        agent_config = settings.config.llm.agent
        llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=SecretStr(settings.nvidia_api_key),
            model=settings.config.llm.model,
            temperature=agent_config.temperature,
            timeout=agent_config.timeout,
        )
        return create_react_agent(llm, AGENT_TOOLS)

    @pytest.mark.asyncio
    async def test_english_city_london(self, agent: CompiledStateGraph[Any]) -> None:
        """Agent should resolve London to Europe/London."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I live in London. Save my timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "Europe/London" in all_content

    @pytest.mark.asyncio
    async def test_english_city_new_york(self, agent: CompiledStateGraph[Any]) -> None:
        """Agent should resolve New York to America/New_York."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I'm in New York. Please save my timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "America/New_York" in all_content

    @pytest.mark.asyncio
    async def test_russian_city_moscow(self, agent: CompiledStateGraph[Any]) -> None:
        """Agent should resolve Москва to Europe/Moscow."""
        result = await agent.ainvoke(
            {
                "messages": [
                    {"role": "user", "content": "Я живу в Москве. Сохрани мой часовой пояс."}
                ]
            }
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "Europe/Moscow" in all_content

    @pytest.mark.asyncio
    async def test_abbreviation_nyc(self, agent: CompiledStateGraph[Any]) -> None:
        """Agent should resolve NYC abbreviation."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I am in NYC. Save timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "America/New_York" in all_content

    @pytest.mark.asyncio
    async def test_abbreviation_la(self, agent: CompiledStateGraph[Any]) -> None:
        """Agent should resolve LA abbreviation."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I'm in LA. Please save my timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "America/Los_Angeles" in all_content

    @pytest.mark.asyncio
    async def test_multi_word_city_los_angeles(self, agent: CompiledStateGraph[Any]) -> None:
        """Agent should handle multi-word city names."""
        result = await agent.ainvoke(
            {
                "messages": [
                    {"role": "user", "content": "My location is Los Angeles. Save timezone."}
                ]
            }
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "America/Los_Angeles" in all_content

    @pytest.mark.asyncio
    async def test_ambiguous_input_asks_clarification(self, agent: CompiledStateGraph[Any]) -> None:
        """Agent should ask for clarification on ambiguous input."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Yes, that is correct."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        # Should NOT save without knowing the city
        assert "SAVE:" not in all_content


@pytest.mark.integration
@_skip_if_no_api_key
class TestGeoIntentToolCalling:
    """Test geo intent agent's ability to call tools correctly.

    This tests the specific issue where LLM outputs tool calls as text
    instead of properly calling the tools.
    """

    @pytest.fixture
    def geo_agent(self) -> CompiledStateGraph[Any]:
        """Create geo intent agent with real LLM."""
        from pydantic import SecretStr

        settings = get_settings()
        agent_config = settings.config.llm.agent
        llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=SecretStr(settings.nvidia_api_key),
            model=settings.config.llm.model,
            temperature=agent_config.temperature,
            timeout=agent_config.timeout,
        )
        return create_react_agent(llm, GEO_INTENT_TOOLS)

    @pytest.mark.asyncio
    async def test_save_timezone_proper_tool_call(self, geo_agent: CompiledStateGraph[Any]) -> None:
        """Agent should CALL save_timezone, not output it as text."""
        result = await geo_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You have tools. User is relocating to Rome. "
                            "Call save_timezone with Europe/Rome. DO NOT output function as text!"
                        ),
                    },
                    {"role": "user", "content": "I moved to Rome"},
                ]
            }
        )
        messages = result.get("messages", [])

        # Extract action - should find SAVE: from proper tool execution
        action = extract_tool_action(messages)
        assert action is not None, "No action extracted from agent messages"
        assert action[0] == "SAVE", f"Expected SAVE action, got {action[0]}"
        assert "Europe/Rome" in action[1], f"Expected Europe/Rome, got {action[1]}"

    @pytest.mark.asyncio
    async def test_convert_time_proper_tool_call(self, geo_agent: CompiledStateGraph[Any]) -> None:
        """Agent should CALL convert_time, not output it as text."""
        result = await geo_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "User wants to know time in Bangkok. Their timezone is Europe/Rome. "
                            "Call convert_time tool. DO NOT output function as text!"
                        ),
                    },
                    {"role": "user", "content": "What's 12:00 in Bangkok?"},
                ]
            }
        )
        messages = result.get("messages", [])

        # Extract action - should find CONVERT: from proper tool execution
        action = extract_tool_action(messages)
        assert action is not None, "No action extracted from agent messages"
        assert action[0] == "CONVERT", f"Expected CONVERT action, got {action[0]}"
        # Should contain actual conversion result, not placeholder
        assert "Time conversion requested" not in action[1], (
            "Got placeholder instead of real conversion"
        )

    @pytest.mark.asyncio
    async def test_no_action_proper_tool_call(self, geo_agent: CompiledStateGraph[Any]) -> None:
        """Agent should CALL no_action for false positives."""
        result = await geo_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "User mentioned Paris but is just commenting, not asking about time or relocating. "
                            "Call no_action tool. DO NOT output function as text!"
                        ),
                    },
                    {"role": "user", "content": "Paris is a beautiful city"},
                ]
            }
        )
        messages = result.get("messages", [])

        # Extract action - should find NO_ACTION
        action = extract_tool_action(messages)
        assert action is not None, "No action extracted from agent messages"
        assert action[0] == "NO_ACTION", f"Expected NO_ACTION, got {action[0]}"

    @pytest.mark.asyncio
    async def test_russian_relocation_tool_call(self, geo_agent: CompiledStateGraph[Any]) -> None:
        """Agent should handle Russian input and call save_timezone."""
        result = await geo_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "User says they arrived in Moscow. This is relocation. "
                            "Call save_timezone with Europe/Moscow. Respond in Russian."
                        ),
                    },
                    {"role": "user", "content": "Я приехал в Москву"},
                ]
            }
        )
        messages = result.get("messages", [])

        action = extract_tool_action(messages)
        assert action is not None, "No action extracted from agent messages"
        assert action[0] == "SAVE", f"Expected SAVE action, got {action[0]}"
        assert "Europe/Moscow" in action[1], f"Expected Europe/Moscow, got {action[1]}"


@pytest.mark.integration
@_skip_if_no_api_key
class TestLLMFallbackTimeExtraction:
    """Test LLM fallback for time extraction when regex fails."""

    @pytest.mark.asyncio
    async def test_extract_simple_time(self) -> None:
        """LLM should extract simple time mentions."""
        result = await extract_times_with_llm("Let's meet at 3pm")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 15
        assert result[0].minute == 0

    @pytest.mark.asyncio
    async def test_extract_time_with_timezone(self) -> None:
        """LLM should extract time with timezone hint."""
        result = await extract_times_with_llm("Call me at 10am PST")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 10
        # PST hint should be detected
        assert result[0].timezone_hint in ("America/Los_Angeles", "PST", None)

    @pytest.mark.asyncio
    async def test_extract_european_format(self) -> None:
        """LLM should extract European time format."""
        result = await extract_times_with_llm("Meeting at 14h30")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 14
        assert result[0].minute == 30

    @pytest.mark.asyncio
    async def test_extract_russian_time(self) -> None:
        """LLM should extract Russian time mentions."""
        result = await extract_times_with_llm("Созвон в 15:00 по Москве")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 15
        assert result[0].minute == 0

    @pytest.mark.asyncio
    async def test_no_time_returns_empty(self) -> None:
        """LLM should return empty list when no time mentioned."""
        result = await extract_times_with_llm("Hello, how are you today?")
        assert result is not None
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_extract_tomorrow_time(self) -> None:
        """LLM should detect tomorrow prefix."""
        result = await extract_times_with_llm("Let's talk tomorrow at 9am")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 9
        # Tomorrow flag should be set
        assert result[0].is_tomorrow is True


class TestModelConfiguration:
    """Test that model configuration is correct (runs in CI without API key)."""

    def test_model_name_is_qwen3(self) -> None:
        """Verify correct model is configured."""
        settings = get_settings()
        assert settings.config.llm.model == "qwen/qwen3-next-80b-a3b-instruct"

    def test_base_url_is_nvidia(self) -> None:
        """Verify NVIDIA NIM API is used."""
        settings = get_settings()
        assert "nvidia" in settings.config.llm.base_url.lower()

    def test_agent_temperature_is_low(self) -> None:
        """Verify agent temperature is low for deterministic tool calling."""
        settings = get_settings()
        assert settings.config.llm.agent.temperature <= 0.2, (
            f"Agent temperature {settings.config.llm.agent.temperature} is too high for reliable tool calling"
        )
