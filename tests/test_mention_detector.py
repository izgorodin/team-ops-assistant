"""Tests for mention trigger detector."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.models import NormalizedEvent, Platform
from src.core.triggers.mention import MentionDetector


@pytest.fixture
def detector() -> MentionDetector:
    """Create a MentionDetector instance."""
    return MentionDetector()


def make_event(text: str) -> NormalizedEvent:
    """Create a test event with given text."""
    return NormalizedEvent(
        platform=Platform.TELEGRAM,
        chat_id="123",
        user_id="456",
        message_id="789",
        text=text,
        event_id="evt_1",
        timestamp=datetime.now(UTC),
    )


class TestMentionPatterns:
    """Tests for mention pattern detection."""

    @pytest.mark.parametrize(
        "text",
        [
            "@bot",
            "@Bot",
            "@BOT",
            "@teambot",
            "@mybot",
            "Hey @bot what can you do?",
            "@bot help",
        ],
    )
    async def test_detects_at_bot_mention(self, detector: MentionDetector, text: str) -> None:
        """Should detect @bot style mentions."""
        event = make_event(text)
        triggers = await detector.detect(event)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "mention"
        assert triggers[0].confidence > 0

    @pytest.mark.parametrize(
        "text",
        [
            "бот",
            "Бот",
            "БОТ",
            "эй бот",
            "бот, что ты умеешь?",
            "привет бот",
        ],
    )
    async def test_detects_russian_bot(self, detector: MentionDetector, text: str) -> None:
        """Should detect Russian 'бот' mention."""
        event = make_event(text)
        triggers = await detector.detect(event)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "mention"

    @pytest.mark.parametrize(
        "text",
        [
            "bot",
            "Bot",
            "BOT",
            "hey bot",
            "bot help",
            "hello bot",
        ],
    )
    async def test_detects_english_bot(self, detector: MentionDetector, text: str) -> None:
        """Should detect English 'bot' mention."""
        event = make_event(text)
        triggers = await detector.detect(event)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "mention"

    @pytest.mark.parametrize(
        "text",
        [
            "помощь",
            "Помощь",
            "нужна помощь",
            "помощь пожалуйста",
        ],
    )
    async def test_detects_russian_help(self, detector: MentionDetector, text: str) -> None:
        """Should detect Russian 'помощь' request."""
        event = make_event(text)
        triggers = await detector.detect(event)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "mention"

    @pytest.mark.parametrize(
        "text",
        [
            "help",
            "Help",
            "HELP",
            "help please",
            "need help",
        ],
    )
    async def test_detects_english_help(self, detector: MentionDetector, text: str) -> None:
        """Should detect English 'help' request."""
        event = make_event(text)
        triggers = await detector.detect(event)

        assert len(triggers) == 1
        assert triggers[0].trigger_type == "mention"


class TestNoMentionDetection:
    """Tests for cases where mention should NOT be detected."""

    @pytest.mark.parametrize(
        "text",
        [
            "let's meet at 3pm",
            "переехал в Москву",
            "hello everyone",
            "привет всем",
            "the robot is cool",  # 'robot' != 'bot'
            "робот",  # 'робот' != 'бот'
            "bottleneck",  # 'bot' is substring, not word
            "helpful",  # 'help' is substring
        ],
    )
    async def test_no_false_positives(self, detector: MentionDetector, text: str) -> None:
        """Should not detect mention in regular messages."""
        event = make_event(text)
        triggers = await detector.detect(event)

        assert len(triggers) == 0


class TestMentionTriggerData:
    """Tests for trigger data structure."""

    async def test_trigger_has_pattern_info(self, detector: MentionDetector) -> None:
        """Should include matched pattern in trigger data."""
        event = make_event("@bot")
        triggers = await detector.detect(event)

        assert len(triggers) == 1
        assert "pattern" in triggers[0].data

    async def test_trigger_has_original_text(self, detector: MentionDetector) -> None:
        """Should include original matched text."""
        event = make_event("hey @teambot help")
        triggers = await detector.detect(event)

        assert len(triggers) == 1
        assert "@teambot" in triggers[0].original_text.lower()
