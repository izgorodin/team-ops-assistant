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
    from collections.abc import Mapping

    from src.core.models import DetectedTrigger
    from src.core.protocols import ActionHandler, StateManager, TriggerDetector
    from src.storage.mongo import MongoStorage

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
        state_managers: Mapping[str, StateManager] | None = None,
        action_handlers: Mapping[str, ActionHandler] | None = None,
        storage: MongoStorage | None = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            detectors: List of trigger detectors to use.
            state_managers: Dict mapping state type to manager (e.g., {"timezone": TimezoneStateManager()}).
            action_handlers: Dict mapping trigger type to handler (e.g., {"time": TimeConversionHandler()}).
            storage: MongoDB storage instance for chat state lookups.
        """
        self.detectors = detectors or []
        self.state_managers: Mapping[str, StateManager] = state_managers or {}
        self.action_handlers: Mapping[str, ActionHandler] = action_handlers or {}
        self.storage = storage
        self._settings = get_settings()

    async def process(self, event: NormalizedEvent) -> PipelineResult:
        """Process a normalized event through the pipeline.

        Pipeline is responsible for:
        1. Detecting triggers from all registered detectors
        2. Resolving context (timezone, target timezones)
        3. Routing triggers to action handlers
        4. Returning triggers + context + messages for orchestrator

        Orchestrator decides what to do with unhandled triggers (create sessions, etc.)

        Args:
            event: The normalized event to process.

        Returns:
            PipelineResult containing triggers, context, messages, and errors.
        """
        messages: list[OutboundMessage] = []
        errors: list[str] = []

        # Step 1: Detect triggers from all detectors
        all_triggers: list[DetectedTrigger] = []
        for detector in self.detectors:
            try:
                triggers = await detector.detect(event)
                all_triggers.extend(triggers)
            except Exception as e:
                logger.error(f"Detector {detector.__class__.__name__} failed: {e}")
                errors.append(f"Detection error: {e}")

        if not all_triggers:
            return PipelineResult(
                triggers=[],
                context=None,
                messages=[],
                errors=errors,
            )

        # Step 2: Resolve context (timezone, target timezones)
        context = await self._resolve_context(event, all_triggers)

        # Step 3: Handle each trigger via registered action handlers
        for trigger in all_triggers:
            handler = self.action_handlers.get(trigger.trigger_type)
            if handler:
                try:
                    trigger_messages = await handler.handle(trigger, context)
                    messages.extend(trigger_messages)
                except Exception as e:
                    logger.error(f"Handler for {trigger.trigger_type} failed: {e}")
                    errors.append(f"Handler error: {e}")
            else:
                logger.debug(f"No handler registered for trigger type: {trigger.trigger_type}")

        return PipelineResult(
            triggers=all_triggers,
            context=context,
            messages=messages,
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

        # Track if source TZ is explicit (from message) vs user default
        is_explicit_source_tz = timezone_hint is not None

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

        # Get target timezones: config + chat's detected timezones
        config_timezones = self._settings.config.timezone.team_timezones
        chat_timezones: list[str] = []

        # Get chat's active timezones from storage
        if self.storage:
            try:
                chat_state = await self.storage.get_chat_state(event.platform, event.chat_id)
                if chat_state and chat_state.active_timezones:
                    chat_timezones = chat_state.active_timezones
            except Exception as e:
                logger.error(f"Failed to get chat timezones: {e}")

        # Merge: config first, then chat-specific
        from src.core.chat_timezones import merge_timezones

        target_timezones = merge_timezones(config_timezones, chat_timezones)

        return ResolvedContext(
            platform=event.platform,
            chat_id=event.chat_id,
            user_id=event.user_id,
            source_timezone=source_timezone,
            is_explicit_source_tz=is_explicit_source_tz,
            target_timezones=target_timezones,
            team_timezones=frozenset(config_timezones),
            reply_to_message_id=event.message_id,
        )
