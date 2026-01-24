"""Message Orchestrator - routes messages between pipeline and agent mode.

The orchestrator is the main entry point for message processing:
1. Checks for active session → routes to AgentHandler
2. Runs Pipeline → handles triggers or signals state collection needed
3. Creates session if state collection is needed
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from src.core.dedupe import DedupeManager
from src.core.models import (
    HandlerResult,
    NormalizedEvent,
    OutboundMessage,
    PipelineResult,
    Session,
    SessionGoal,
    SessionStatus,
)
from src.core.timezone_identity import generate_verify_token, get_verify_url
from src.settings import get_settings

if TYPE_CHECKING:
    from src.core.agent_handler import AgentHandler
    from src.core.pipeline import Pipeline
    from src.storage.mongo import MongoStorage

logger = logging.getLogger(__name__)


class MessageOrchestrator:
    """Routes messages between pipeline and agent mode.

    Flow:
    1. Check for active session → AgentHandler
    2. Dedupe/throttle check
    3. Pipeline processing
    4. If needs_state_collection → create session, prompt user
    5. Otherwise → return response messages
    """

    def __init__(
        self,
        storage: MongoStorage,
        pipeline: Pipeline,
        agent_handler: AgentHandler,
        base_url: str = "",
    ) -> None:
        """Initialize the orchestrator.

        Args:
            storage: MongoDB storage instance.
            pipeline: Main message processing pipeline.
            agent_handler: Agent handler for session-based conversations.
            base_url: Base URL for verification links.
        """
        self.storage = storage
        self.pipeline = pipeline
        self.agent_handler = agent_handler
        self.base_url = base_url
        self.dedupe = DedupeManager(storage)
        self._settings = get_settings()

    async def route(self, event: NormalizedEvent) -> HandlerResult:
        """Route an incoming message to the appropriate handler.

        Args:
            event: Normalized incoming message event.

        Returns:
            HandlerResult from the appropriate handler.
        """
        # 1. Check for active session
        session = await self.storage.get_active_session(
            event.platform, event.chat_id, event.user_id
        )

        if session:
            logger.debug(
                f"Active session found for user {event.user_id}, "
                f"routing to agent handler (goal: {session.goal})"
            )
            return await self.agent_handler.handle(session, event)

        # 2. Dedupe check
        if await self.dedupe.is_duplicate(event.platform, event.event_id):
            logger.debug(f"Duplicate event: {event.event_id}")
            return HandlerResult(should_respond=False)

        # 3. Throttle check
        if self.dedupe.is_throttled(event.platform, event.chat_id):
            logger.debug(f"Throttled chat: {event.chat_id}")
            return HandlerResult(should_respond=False)

        # 4. Process through pipeline
        logger.debug(f"Processing event through pipeline for user {event.user_id}")
        result = await self.pipeline.process(event)

        # 5. Check if state collection is needed
        if result.needs_state_collection and result.state_collection_trigger:
            logger.info(f"State collection needed for user {event.user_id}")
            state_result = await self._handle_state_collection(event, result)
            # Mark as processed for dedupe to prevent duplicate sessions on webhook retries
            if state_result.should_respond:
                await self.dedupe.mark_processed(event.platform, event.event_id, event.chat_id)
            return state_result

        # 6. No triggers or successful handling - return result
        if result.messages:
            # Mark as processed for dedupe
            await self.dedupe.mark_processed(event.platform, event.event_id, event.chat_id)
            self.dedupe.record_response(event.platform, event.chat_id)

        return HandlerResult(
            should_respond=bool(result.messages),
            messages=result.messages,
        )

    async def _handle_state_collection(
        self, event: NormalizedEvent, result: PipelineResult
    ) -> HandlerResult:
        """Handle case where state collection is needed.

        Creates a session and prompts user for timezone.
        Distinguishes between first-time onboarding and re-verification.

        Args:
            event: The event being processed.
            result: Pipeline result with state_collection_trigger.

        Returns:
            HandlerResult with verification prompt.
        """

        # Generate verification token
        token = generate_verify_token(event.platform, event.user_id, event.chat_id)
        verify_url = get_verify_url(token, self.base_url)

        # Check if this is re-verification (user has existing tz) or first-time onboarding
        user_state = await self.storage.get_user_tz_state(event.platform, event.user_id)
        is_reverify = user_state is not None and user_state.tz_iana is not None

        # Choose goal and prompt based on scenario
        existing_tz: str | None = None
        if is_reverify and user_state is not None and user_state.tz_iana is not None:
            goal = SessionGoal.REVERIFY_TIMEZONE
            existing_tz = user_state.tz_iana
            text = f"🔄 Твоя таймзона всё ещё {existing_tz}?\nНапиши 'да' или новый город"
        else:
            goal = SessionGoal.AWAITING_TIMEZONE
            text = "🌍 Какой твой город? (для часового пояса)\nПримеры: NY, Москва, London, Berlin"

        # Create session for agent to handle follow-up
        trigger = result.state_collection_trigger
        session = Session(
            session_id=str(uuid4()),
            platform=event.platform,
            chat_id=event.chat_id,
            user_id=event.user_id,
            goal=goal,
            status=SessionStatus.ACTIVE,
            context={
                "original_text": event.text,
                "trigger_data": trigger.data if trigger else {},
                "verify_url": verify_url,
                "attempts": 0,
                "history": [],
                "existing_tz": existing_tz,
            },
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        await self.storage.create_session(session)
        logger.info(
            f"Created {'re-verify' if is_reverify else 'onboarding'} "
            f"session {session.session_id} for user {event.user_id}"
        )

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="plain",
        )

        # Record response for throttling
        self.dedupe.record_response(event.platform, event.chat_id)

        return HandlerResult(
            should_respond=True,
            messages=[message],
            ask_timezone=True,
            verify_url=verify_url,
        )
