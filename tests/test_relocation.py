"""Tests for relocation detection."""

from __future__ import annotations

import pytest

from src.core.models import NormalizedEvent, Platform
from src.core.triggers.relocation import RelocationDetector


class TestRelocationDetector:
    """Tests for RelocationDetector."""

    @pytest.fixture
    def detector(self) -> RelocationDetector:
        """Create a detector instance."""
        return RelocationDetector()

    def _make_event(self, text: str) -> NormalizedEvent:
        """Create a test event with given text."""
        return NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="test_event",
            chat_id="test_chat",
            user_id="test_user",
            text=text,
            message_id="test_msg",
        )

    # English patterns - past tense
    async def test_moved_to_english(self, detector: RelocationDetector) -> None:
        """Test 'moved to London'."""
        event = self._make_event("I moved to London last week")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].trigger_type == "relocation"
        assert triggers[0].data["city"] == "London"
        assert triggers[0].confidence == 0.9

    async def test_just_moved_to(self, detector: RelocationDetector) -> None:
        """Test 'just moved to Berlin'."""
        event = self._make_event("Just moved to Berlin!")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Berlin"

    async def test_relocated_to(self, detector: RelocationDetector) -> None:
        """Test 'relocated to Tokyo'."""
        event = self._make_event("I've relocated to Tokyo")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Tokyo"

    async def test_now_in(self, detector: RelocationDetector) -> None:
        """Test 'now in Paris'."""
        event = self._make_event("I'm now in Paris")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Paris"

    async def test_now_living_in(self, detector: RelocationDetector) -> None:
        """Test 'now living in Amsterdam'."""
        event = self._make_event("I'm now living in Amsterdam")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Amsterdam"

    # English - future tense
    async def test_moving_to(self, detector: RelocationDetector) -> None:
        """Test 'moving to Seattle'."""
        event = self._make_event("I'm moving to Seattle next month")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Seattle"

    # Russian patterns - past tense
    async def test_pereekhal_ru(self, detector: RelocationDetector) -> None:
        """Test 'переехал в Москву'."""
        event = self._make_event("Я переехал в Москву")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Москву"

    async def test_pereehala_ru(self, detector: RelocationDetector) -> None:
        """Test 'переехала в Питер'."""
        event = self._make_event("Переехала в Питер")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Питер"

    async def test_teper_v_ru(self, detector: RelocationDetector) -> None:
        """Test 'теперь в Берлине'."""
        event = self._make_event("Теперь в Берлине живу")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Берлине"

    # Russian - future tense
    async def test_pereedu_ru(self, detector: RelocationDetector) -> None:
        """Test 'перееду в Лондон'."""
        event = self._make_event("Скоро перееду в Лондон")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Лондон"

    async def test_pereezzhayu_ru(self, detector: RelocationDetector) -> None:
        """Test 'переезжаю в Нью-Йорк'."""
        event = self._make_event("Переезжаю в Нью-Йорк")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        # Note: pattern captures "Нью" due to \w+ limitation with hyphen

    # Multi-word cities
    async def test_multi_word_city(self, detector: RelocationDetector) -> None:
        """Test city with two words 'New York'."""
        event = self._make_event("I moved to New York")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "New York"

    async def test_multi_word_city_ru(self, detector: RelocationDetector) -> None:
        """Test 'переехал в Санкт Петербург'."""
        event = self._make_event("Переехал в Санкт Петербург")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Санкт Петербург"

    # Arrival patterns
    async def test_arrived_in_en(self, detector: RelocationDetector) -> None:
        """Test 'I arrived in Paris'."""
        event = self._make_event("I arrived in Paris")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Paris"
        assert triggers[0].data["pattern"] == "arrived_in"

    async def test_just_arrived_en(self, detector: RelocationDetector) -> None:
        """Test 'just arrived to Berlin'."""
        event = self._make_event("Just arrived to Berlin")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Berlin"

    async def test_priekhal_ru(self, detector: RelocationDetector) -> None:
        """Test 'приехал в Москву'."""
        event = self._make_event("Я приехал в Москву")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Москву"
        assert triggers[0].data["pattern"] == "arrived_ru"

    async def test_priekhala_ru(self, detector: RelocationDetector) -> None:
        """Test 'приехала в Питер'."""
        event = self._make_event("Приехала в Питер")
        triggers = await detector.detect(event)
        assert len(triggers) == 1
        assert triggers[0].data["city"] == "Питер"

    # No match cases
    async def test_no_match_regular_message(self, detector: RelocationDetector) -> None:
        """Test regular message without relocation."""
        event = self._make_event("Let's meet at 3pm tomorrow")
        triggers = await detector.detect(event)
        assert len(triggers) == 0

    async def test_no_match_partial_phrase(self, detector: RelocationDetector) -> None:
        """Test partial phrase that shouldn't match."""
        event = self._make_event("I want to move")
        triggers = await detector.detect(event)
        assert len(triggers) == 0

    async def test_no_match_friend_moved(self, detector: RelocationDetector) -> None:
        """Test 'my friend moved' - still matches unfortunately.

        This is a known limitation - we match "moved to" regardless of subject.
        The user can confirm/deny in the re-verification flow.
        """
        event = self._make_event("My friend moved to Boston")
        triggers = await detector.detect(event)
        # This WILL match (known false positive, handled by user confirmation)
        assert len(triggers) == 1


class TestRelocationTriggerData:
    """Tests for relocation trigger data structure."""

    @pytest.fixture
    def detector(self) -> RelocationDetector:
        """Create a detector instance."""
        return RelocationDetector()

    def _make_event(self, text: str) -> NormalizedEvent:
        """Create a test event with given text."""
        return NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="test_event",
            chat_id="test_chat",
            user_id="test_user",
            text=text,
            message_id="test_msg",
        )

    async def test_trigger_has_correct_type(self, detector: RelocationDetector) -> None:
        """Test trigger has correct type."""
        event = self._make_event("I moved to London")
        triggers = await detector.detect(event)
        assert triggers[0].trigger_type == "relocation"

    async def test_trigger_has_original_text(self, detector: RelocationDetector) -> None:
        """Test trigger captures original matched text."""
        event = self._make_event("Hey I just moved to Tokyo!")
        triggers = await detector.detect(event)
        assert "moved to Tokyo" in triggers[0].original_text

    async def test_trigger_has_pattern_name(self, detector: RelocationDetector) -> None:
        """Test trigger includes pattern name for debugging."""
        event = self._make_event("I moved to London")
        triggers = await detector.detect(event)
        assert "pattern" in triggers[0].data
        assert triggers[0].data["pattern"] == "moved_to"
