"""Message processing pipeline.

Orchestrates trigger detection, state resolution, and action handling
using the extensible architecture components.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.core.models import (
    NormalizedEvent,
    OutboundMessage,
    PipelineResult,
    ResolvedContext,
)
from src.settings import get_settings

if TYPE_CHECKING:
    from src.core.models import DetectedTrigger
    from src.core.protocols import ActionHandler, StateManager, TriggerDetector

logger = logging.getLogger(__name__)


class Pipeline:
    """Message processing pipeline.

    Orchestrates:
    1. Trigger detection across all registered detectors
    2. State resolution (timezone, etc.)
    3. Action handling for detected triggers
    4. Response message collection
    """

    def __init__(
        self,
        detectors: list[TriggerDetector] | None = None,
        state_managers: dict[str, StateManager] | None = None,
        action_handlers: dict[str, ActionHandler] | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            detectors: List of trigger detectors to use.
            state_managers: Dict mapping state type to manager (e.g., {"timezone": TimezoneStateManager()}).
            action_handlers: Dict mapping trigger type to handler (e.g., {"time": TimeConversionHandler()}).
        """
        self.detectors = detectors or []
        self.state_managers = state_managers or {}
        self.action_handlers = action_handlers or {}
        self._settings = get_settings()

    async def process(self, event: NormalizedEvent) -> PipelineResult:
        """Process a normalized event through the pipeline.

        Args:
            event: The normalized event to process.

        Returns:
            PipelineResult containing response messages and statistics.
        """
        messages: list[OutboundMessage] = []
        errors: list[str] = []
        triggers_detected = 0
        triggers_handled = 0

        # Step 1: Detect triggers from all detectors
        all_triggers: list[DetectedTrigger] = []
        for detector in self.detectors:
            try:
                triggers = await detector.detect(event)
                all_triggers.extend(triggers)
            except Exception as e:
                logger.error(f"Detector {detector.__class__.__name__} failed: {e}")
                errors.append(f"Detection error: {e}")

        triggers_detected = len(all_triggers)

        if not all_triggers:
            return PipelineResult(
                messages=[],
                triggers_detected=0,
                triggers_handled=0,
                errors=errors,
            )

        # Step 2: Resolve state (timezone for now)
        context = await self._resolve_context(event, all_triggers)

        # Step 3: Handle each trigger
        for trigger in all_triggers:
            handler = self.action_handlers.get(trigger.trigger_type)
            if handler:
                try:
                    trigger_messages = await handler.handle(trigger, context)
                    messages.extend(trigger_messages)
                    triggers_handled += 1
                except Exception as e:
                    logger.error(f"Handler for {trigger.trigger_type} failed: {e}")
                    errors.append(f"Handler error: {e}")
            else:
                logger.debug(f"No handler registered for trigger type: {trigger.trigger_type}")

        return PipelineResult(
            messages=messages,
            triggers_detected=triggers_detected,
            triggers_handled=triggers_handled,
            errors=errors,
        )

    async def _resolve_context(
        self, event: NormalizedEvent, triggers: list[DetectedTrigger]
    ) -> ResolvedContext:
        """Resolve context for handling triggers.

        Args:
            event: The normalized event.
            triggers: Detected triggers (may contain timezone hints).

        Returns:
            ResolvedContext with source/target timezones.
        """
        # Extract timezone hint from triggers if available
        timezone_hint = None
        for trigger in triggers:
            if trigger.data.get("timezone_hint"):
                timezone_hint = trigger.data["timezone_hint"]
                break

        # Resolve user's timezone
        source_timezone = timezone_hint
        if not source_timezone and "timezone" in self.state_managers:
            try:
                tz_state = await self.state_managers["timezone"].get_state(
                    platform=event.platform,
                    user_id=event.user_id,
                    chat_id=event.chat_id,
                )
                source_timezone = tz_state.value
            except Exception as e:
                logger.error(f"Failed to get timezone state: {e}")

        # Get target timezones from config
        target_timezones = self._settings.config.timezone.team_timezones

        return ResolvedContext(
            platform=event.platform,
            chat_id=event.chat_id,
            user_id=event.user_id,
            source_timezone=source_timezone,
            target_timezones=target_timezones,
            reply_to_message_id=event.event_id,
        )
