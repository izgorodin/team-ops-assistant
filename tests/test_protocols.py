"""Contract tests for architecture protocols.

TDD: These tests define the contracts that implementations MUST follow.
The protocols are defined in src/core/protocols.py (to be created).

Each test verifies:
1. Protocol exists
2. Implementation conforms to protocol
3. Implementation behavior matches contract
"""

from __future__ import annotations

from datetime import UTC

import pytest

# ============================================================================
# TriggerDetector Protocol Tests
# ============================================================================


class TestTriggerDetectorProtocol:
    """Contract tests for TriggerDetector protocol."""

    @pytest.mark.xfail(reason="Protocol not yet defined - Step 2 of refactoring")
    def test_protocol_exists(self) -> None:
        """TriggerDetector protocol must be defined."""
        from src.core.protocols import TriggerDetector

        assert TriggerDetector is not None

    @pytest.mark.xfail(reason="Protocol not yet defined - Step 2 of refactoring")
    def test_protocol_has_detect_method(self) -> None:
        """TriggerDetector must have async detect() method."""
        from src.core.protocols import TriggerDetector

        assert hasattr(TriggerDetector, "detect")
        assert "detect" in dir(TriggerDetector)

    @pytest.mark.xfail(reason="TimeDetector not yet implemented - Step 3 of refactoring")
    def test_time_detector_implements_protocol(self) -> None:
        """TimeDetector must implement TriggerDetector protocol."""
        from src.core.protocols import TriggerDetector
        from src.core.triggers.time import TimeDetector

        # Check TimeDetector is a valid implementation
        detector = TimeDetector()
        assert isinstance(detector, TriggerDetector)

    @pytest.mark.xfail(reason="TimeDetector not yet implemented - Step 3 of refactoring")
    async def test_time_detector_returns_detected_triggers(self) -> None:
        """TimeDetector.detect() must return list[DetectedTrigger]."""
        from datetime import datetime

        from src.core.models import NormalizedEvent, Platform
        from src.core.triggers.time import TimeDetector

        detector = TimeDetector()
        event = NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="test_1",
            chat_id="chat_1",
            user_id="user_1",
            username="testuser",
            display_name="Test User",
            text="Let's meet at 3pm",
            timestamp=datetime.now(UTC),
        )

        result = await detector.detect(event)

        assert isinstance(result, list)
        assert len(result) > 0
        # Each item should have required attributes
        for trigger in result:
            assert hasattr(trigger, "trigger_type")
            assert hasattr(trigger, "confidence")
            assert hasattr(trigger, "data")


# ============================================================================
# StateManager Protocol Tests
# ============================================================================


class TestStateManagerProtocol:
    """Contract tests for StateManager[T] protocol."""

    @pytest.mark.xfail(reason="Protocol not yet defined - Step 2 of refactoring")
    def test_protocol_exists(self) -> None:
        """StateManager protocol must be defined."""
        from src.core.protocols import StateManager

        assert StateManager is not None

    @pytest.mark.xfail(reason="Protocol not yet defined - Step 2 of refactoring")
    def test_protocol_has_get_state_method(self) -> None:
        """StateManager must have async get_state() method."""
        from src.core.protocols import StateManager

        assert hasattr(StateManager, "get_state")

    @pytest.mark.xfail(reason="Protocol not yet defined - Step 2 of refactoring")
    def test_protocol_has_update_state_method(self) -> None:
        """StateManager must have async update_state() method."""
        from src.core.protocols import StateManager

        assert hasattr(StateManager, "update_state")

    @pytest.mark.xfail(reason="TimezoneStateManager not yet implemented - Step 3")
    def test_timezone_state_manager_implements_protocol(self) -> None:
        """TimezoneStateManager must implement StateManager[str] protocol."""
        from src.core.state.timezone import TimezoneStateManager

        manager = TimezoneStateManager()
        # Generic protocol check
        assert hasattr(manager, "get_state")
        assert hasattr(manager, "update_state")

    @pytest.mark.xfail(reason="TimezoneStateManager not yet implemented - Step 3")
    async def test_timezone_state_manager_returns_state_result(self) -> None:
        """TimezoneStateManager.get_state() must return StateResult[str]."""
        from src.core.models import Platform
        from src.core.state.timezone import TimezoneStateManager

        manager = TimezoneStateManager()
        result = await manager.get_state(
            platform=Platform.TELEGRAM,
            user_id="user_1",
            chat_id="chat_1",
        )

        # StateResult must have value, confidence, source
        assert hasattr(result, "value")
        assert hasattr(result, "confidence")
        assert hasattr(result, "source")
        # value is IANA timezone string or None
        assert result.value is None or isinstance(result.value, str)


# ============================================================================
# ActionHandler Protocol Tests
# ============================================================================


class TestActionHandlerProtocol:
    """Contract tests for ActionHandler protocol."""

    @pytest.mark.xfail(reason="Protocol not yet defined - Step 2 of refactoring")
    def test_protocol_exists(self) -> None:
        """ActionHandler protocol must be defined."""
        from src.core.protocols import ActionHandler

        assert ActionHandler is not None

    @pytest.mark.xfail(reason="Protocol not yet defined - Step 2 of refactoring")
    def test_protocol_has_handle_method(self) -> None:
        """ActionHandler must have async handle() method."""
        from src.core.protocols import ActionHandler

        assert hasattr(ActionHandler, "handle")

    @pytest.mark.xfail(reason="TimeConversionHandler not yet implemented - Step 3")
    def test_time_conversion_handler_implements_protocol(self) -> None:
        """TimeConversionHandler must implement ActionHandler protocol."""
        from src.core.actions.time_convert import TimeConversionHandler

        handler = TimeConversionHandler()
        assert hasattr(handler, "handle")

    @pytest.mark.xfail(reason="TimeConversionHandler not yet implemented - Step 3")
    async def test_time_conversion_handler_returns_messages(self) -> None:
        """TimeConversionHandler.handle() must return list[OutboundMessage]."""
        from src.core.actions.time_convert import TimeConversionHandler
        from src.core.models import DetectedTrigger, OutboundMessage, ResolvedContext

        handler = TimeConversionHandler()

        trigger = DetectedTrigger(
            trigger_type="time",
            confidence=0.95,
            data={"hour": 15, "minute": 0, "timezone_hint": None},
        )
        context = ResolvedContext(
            platform="telegram",
            chat_id="chat_1",
            user_id="user_1",
            source_timezone="America/Los_Angeles",
            target_timezones=["America/New_York", "Europe/London"],
        )

        result = await handler.handle(trigger, context)

        assert isinstance(result, list)
        for msg in result:
            assert isinstance(msg, OutboundMessage)


# ============================================================================
# Pipeline Integration Tests
# ============================================================================


class TestPipelineContract:
    """Contract tests for the message processing pipeline."""

    @pytest.mark.xfail(reason="Pipeline not yet refactored - Step 3")
    def test_pipeline_class_exists(self) -> None:
        """Pipeline orchestrator must be defined."""
        from src.core.pipeline import Pipeline

        assert Pipeline is not None

    @pytest.mark.xfail(reason="Pipeline not yet refactored - Step 3")
    def test_pipeline_accepts_detectors(self) -> None:
        """Pipeline must accept list of TriggerDetectors."""
        from src.core.pipeline import Pipeline
        from src.core.triggers.time import TimeDetector

        pipeline = Pipeline(detectors=[TimeDetector()])
        assert len(pipeline.detectors) == 1

    @pytest.mark.xfail(reason="Pipeline not yet refactored - Step 3")
    async def test_pipeline_processes_event(self) -> None:
        """Pipeline.process() must handle NormalizedEvent end-to-end."""
        from datetime import datetime

        from src.core.models import NormalizedEvent, Platform
        from src.core.pipeline import Pipeline
        from src.core.triggers.time import TimeDetector

        pipeline = Pipeline(detectors=[TimeDetector()])

        event = NormalizedEvent(
            platform=Platform.TELEGRAM,
            event_id="test_1",
            chat_id="chat_1",
            user_id="user_1",
            username="testuser",
            display_name="Test User",
            text="Let's meet at 3pm PST",
            timestamp=datetime.now(UTC),
        )

        result = await pipeline.process(event)

        # Result should contain messages to send
        assert hasattr(result, "messages")
        assert isinstance(result.messages, list)
