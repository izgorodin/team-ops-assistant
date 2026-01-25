"""Integration tests for LLM (Qwen3-Next-80B) with real API calls.

These tests verify that the LLM model works correctly with:
1. Agent tool calling (timezone resolution)
2. LLM fallback for time extraction

Run with: pytest tests/test_llm_integration.py -v -s
"""

from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from src.core.agent_tools import AGENT_TOOLS
from src.core.llm_fallback import extract_times_with_llm
from src.settings import get_settings

# Load environment
load_dotenv()

# Skip all tests if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("NVIDIA_API_KEY"),
    reason="NVIDIA_API_KEY not set - skipping integration tests",
)


class TestAgentToolCalling:
    """Test agent's ability to call tools correctly."""

    @pytest.fixture
    def agent(self):
        """Create agent with real LLM."""
        from pydantic import SecretStr

        settings = get_settings()
        llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=SecretStr(settings.nvidia_api_key),
            model=settings.config.llm.model,
            temperature=0.3,
            timeout=25.0,
        )
        return create_react_agent(llm, AGENT_TOOLS)

    @pytest.mark.asyncio
    async def test_english_city_london(self, agent):
        """Agent should resolve London to Europe/London."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I live in London. Save my timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "Europe/London" in all_content

    @pytest.mark.asyncio
    async def test_english_city_new_york(self, agent):
        """Agent should resolve New York to America/New_York."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I'm in New York. Please save my timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "America/New_York" in all_content

    @pytest.mark.asyncio
    async def test_russian_city_moscow(self, agent):
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
    async def test_abbreviation_nyc(self, agent):
        """Agent should resolve NYC abbreviation."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I am in NYC. Save timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "America/New_York" in all_content

    @pytest.mark.asyncio
    async def test_abbreviation_la(self, agent):
        """Agent should resolve LA abbreviation."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "I'm in LA. Please save my timezone."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        assert "SAVE:" in all_content
        assert "America/Los_Angeles" in all_content

    @pytest.mark.asyncio
    async def test_multi_word_city_los_angeles(self, agent):
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
    async def test_ambiguous_input_asks_clarification(self, agent):
        """Agent should ask for clarification on ambiguous input."""
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Yes, that is correct."}]}
        )
        messages = result.get("messages", [])
        all_content = " ".join(str(m.content) for m in messages if hasattr(m, "content"))
        # Should NOT save without knowing the city
        assert "SAVE:" not in all_content


class TestLLMFallbackTimeExtraction:
    """Test LLM fallback for time extraction when regex fails."""

    @pytest.mark.asyncio
    async def test_extract_simple_time(self):
        """LLM should extract simple time mentions."""
        result = await extract_times_with_llm("Let's meet at 3pm")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 15
        assert result[0].minute == 0

    @pytest.mark.asyncio
    async def test_extract_time_with_timezone(self):
        """LLM should extract time with timezone hint."""
        result = await extract_times_with_llm("Call me at 10am PST")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 10
        # PST hint should be detected
        assert result[0].timezone_hint in ("America/Los_Angeles", "PST", None)

    @pytest.mark.asyncio
    async def test_extract_european_format(self):
        """LLM should extract European time format."""
        result = await extract_times_with_llm("Meeting at 14h30")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 14
        assert result[0].minute == 30

    @pytest.mark.asyncio
    async def test_extract_russian_time(self):
        """LLM should extract Russian time mentions."""
        result = await extract_times_with_llm("Созвон в 15:00 по Москве")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 15
        assert result[0].minute == 0

    @pytest.mark.asyncio
    async def test_no_time_returns_empty(self):
        """LLM should return empty list when no time mentioned."""
        result = await extract_times_with_llm("Hello, how are you today?")
        assert result is not None
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_extract_tomorrow_time(self):
        """LLM should detect tomorrow prefix."""
        result = await extract_times_with_llm("Let's talk tomorrow at 9am")
        assert result is not None
        assert len(result) > 0
        assert result[0].hour == 9
        # Tomorrow flag should be set
        assert result[0].is_tomorrow is True


class TestModelConfiguration:
    """Test that model configuration is correct."""

    def test_model_name_is_qwen3(self):
        """Verify correct model is configured."""
        settings = get_settings()
        assert settings.config.llm.model == "qwen/qwen3-next-80b-a3b-instruct"

    def test_base_url_is_nvidia(self):
        """Verify NVIDIA NIM API is used."""
        settings = get_settings()
        assert "nvidia" in settings.config.llm.base_url.lower()
