"""Confirm relocation session handler.

Rules-based handler for confirming timezone after relocation.
No LLM needed - simple yes/no confirmation or city re-entry.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.core.geo import geocode_city_str
from src.core.models import HandlerResult, OutboundMessage, SessionStatus, TimezoneSource
from src.core.prompts import get_ui_message

if TYPE_CHECKING:
    from src.core.models import NormalizedEvent, Session
    from src.storage.mongo import MongoStorage

logger = logging.getLogger(__name__)

# Confirmation words (Russian + English)
CONFIRM_WORDS = {"да", "yes", "ок", "ok", "верно", "правильно", "+", "угу", "ага", "yep"}
REJECT_WORDS = {"нет", "no", "неверно", "не", "nope"}

# Max attempts before session fails
MAX_ATTEMPTS = 3


class ConfirmRelocationHandler:
    """Handles CONFIRM_RELOCATION session goal.

    Pure rules-based handler - no LLM dependency:
    1. User confirms (да/yes) → save timezone, close session
    2. User rejects (нет/no) → ask for correct city
    3. User provides city → geocode, ask for confirmation

    This handler is called by AgentHandler for CONFIRM_RELOCATION sessions.
    """

    def __init__(self, storage: MongoStorage) -> None:
        """Initialize handler.

        Args:
            storage: MongoDB storage for session operations.
        """
        self.storage = storage

    async def handle(self, session: Session, event: NormalizedEvent) -> HandlerResult:
        """Handle user response in confirm relocation session.

        Args:
            session: Active CONFIRM_RELOCATION session with resolved_city/resolved_tz.
            event: User's response message.

        Returns:
            HandlerResult with confirmation, retry prompt, or completion.
        """
        user_text = event.text.strip().lower()
        resolved_tz = session.context.get("resolved_tz")

        # 1. Check for confirmation
        if user_text in CONFIRM_WORDS or user_text.startswith("да"):
            if resolved_tz:
                return await self._complete_session(session, event, resolved_tz)
            # No resolved_tz - shouldn't happen
            logger.warning(f"CONFIRM_RELOCATION session without resolved_tz: {session.session_id}")
            await self.storage.close_session(session.session_id, SessionStatus.FAILED)
            return HandlerResult(should_respond=False)

        # 2. Check for rejection - ask for correct city
        if user_text in REJECT_WORDS:
            text = get_ui_message("ask_city")
            return await self._continue_session(session, event, text)

        # 3. User provided city name - try to geocode
        result = geocode_city_str(event.text, use_llm=True)
        if result.startswith("FOUND:"):
            try:
                parts = result.replace("FOUND:", "").strip().split("→")
                new_city = parts[0].strip()
                new_tz = parts[1].strip()

                # Update session with new resolved timezone
                session.context["resolved_city"] = new_city
                session.context["resolved_tz"] = new_tz
                session.context["attempts"] = session.context.get("attempts", 0) + 1
                session.updated_at = datetime.now(UTC)

                # Check max attempts
                if session.context["attempts"] >= MAX_ATTEMPTS:
                    return await self._fail_session(session, event)

                await self.storage.update_session(session)

                # Ask for confirmation with new city
                text = get_ui_message("confirm_relocation", city_name=new_city, tz_iana=new_tz)
                message = OutboundMessage(
                    platform=event.platform,
                    chat_id=event.chat_id,
                    text=text,
                    parse_mode="html",
                )
                return HandlerResult(should_respond=True, messages=[message])

            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse geocode result: {result} - {e}")

        # 4. City not found - ask again
        session.context["attempts"] = session.context.get("attempts", 0) + 1
        if session.context["attempts"] >= MAX_ATTEMPTS:
            return await self._fail_session(session, event)

        await self.storage.update_session(session)
        text = get_ui_message("city_not_found", city_name=event.text)
        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="plain",
        )
        return HandlerResult(should_respond=True, messages=[message])

    async def _complete_session(
        self, session: Session, event: NormalizedEvent, timezone: str
    ) -> HandlerResult:
        """Complete session successfully - save timezone and close."""
        from src.core.models import UserTzState

        # Save timezone with high confidence (user confirmed)
        user_state = UserTzState(
            platform=event.platform,
            user_id=event.user_id,
            tz_iana=timezone,
            confidence=1.0,  # User explicitly confirmed
            source=TimezoneSource.RELOCATION_CONFIRMED,
            updated_at=datetime.now(UTC),
        )
        await self.storage.upsert_user_tz_state(user_state)

        # Close session
        await self.storage.close_session(session.session_id, SessionStatus.COMPLETED)

        # Send success message
        text = get_ui_message("saved", tz_iana=timezone)
        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="html",
        )
        return HandlerResult(should_respond=True, messages=[message])

    async def _continue_session(
        self, session: Session, event: NormalizedEvent, text: str
    ) -> HandlerResult:
        """Continue session with prompt for more info."""
        session.context["attempts"] = session.context.get("attempts", 0) + 1
        session.updated_at = datetime.now(UTC)

        if session.context["attempts"] >= MAX_ATTEMPTS:
            return await self._fail_session(session, event)

        await self.storage.update_session(session)
        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="plain",
        )
        return HandlerResult(should_respond=True, messages=[message])

    async def _fail_session(self, session: Session, event: NormalizedEvent) -> HandlerResult:
        """Fail session after max attempts."""
        await self.storage.close_session(session.session_id, SessionStatus.FAILED)
        text = get_ui_message("session_failed")
        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="plain",
        )
        return HandlerResult(should_respond=True, messages=[message])
