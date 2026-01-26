"""LangChain Agent Handler for session-based conversations.

Handles multi-turn conversations when the bot needs to collect information
from the user (e.g., timezone verification).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from openai import APITimeoutError

from src.core.agent_tools import AGENT_TOOLS
from src.core.models import (
    HandlerResult,
    NormalizedEvent,
    OutboundMessage,
    Session,
    SessionGoal,
    SessionStatus,
    TimezoneSource,
)
from src.core.prompts import get_agent_system_prompt, get_ui_message
from src.core.timezone_identity import TimezoneIdentityManager

if TYPE_CHECKING:
    from src.settings import Settings
    from src.storage.mongo import MongoStorage

logger = logging.getLogger(__name__)


def _sanitize_response(text: str) -> str:
    """Remove LLM meta-commentary from response.

    Args:
        text: Raw response text from LLM.

    Returns:
        Cleaned response without notes/assumptions.
    """
    # Patterns to remove
    patterns = [
        r"\(Note:.*?\)",
        r"\(assuming.*?\)",
        r"\(based on.*?\)",
        r"Based on the.*?description[.,]?\s*",
        r"The output of the functions.*?\.\s*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
    return text.strip()


class AgentHandler:
    """Handles session-based conversations using LangChain agent."""

    def __init__(self, storage: MongoStorage, settings: Settings) -> None:
        """Initialize the agent handler.

        Args:
            storage: MongoDB storage instance.
            settings: Application settings.
        """
        self.storage = storage
        self.settings = settings
        self.tz_manager = TimezoneIdentityManager(storage)

        # Initialize LLM (using OpenAI-compatible API with NVIDIA NIM)
        # Timeout must be under Telegram's 30s webhook limit
        agent_config = settings.config.llm.agent
        self.llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=settings.nvidia_api_key,  # type: ignore[arg-type]
            model=settings.config.llm.model,
            temperature=agent_config.temperature,
            timeout=agent_config.timeout,
        )

        # Create the ReAct agent with tools
        self.agent = create_react_agent(self.llm, AGENT_TOOLS)

    async def handle(self, session: Session, event: NormalizedEvent) -> HandlerResult:
        """Handle a message in the context of an active session.

        Args:
            session: Active session for this user.
            event: Incoming message event.

        Returns:
            HandlerResult with response messages.
        """
        if session.goal == SessionGoal.CONFIRM_RELOCATION:
            # Simple yes/no confirmation - no LLM needed!
            return await self._handle_confirm_relocation(session, event)

        if session.goal in (SessionGoal.AWAITING_TIMEZONE, SessionGoal.REVERIFY_TIMEZONE):
            return await self._handle_timezone_session(session, event)

        # Unknown session goal - close it
        logger.warning(f"Unknown session goal: {session.goal}")
        await self.storage.close_session(session.session_id, SessionStatus.FAILED)
        return HandlerResult(should_respond=False)

    async def _handle_confirm_relocation(
        self, session: Session, event: NormalizedEvent
    ) -> HandlerResult:
        """Handle relocation confirmation - simple yes/no, no LLM needed.

        User confirms pre-resolved timezone or provides different city.

        Args:
            session: Session with resolved_city and resolved_tz in context.
            event: User's response ("да", "yes", or city name).

        Returns:
            HandlerResult with confirmation or retry prompt.
        """
        from src.core.agent_tools import geocode_city_full

        user_text = event.text.strip().lower()
        resolved_tz = session.context.get("resolved_tz")

        # Check for confirmation (да, yes, ок, ok, верно, правильно, +)
        confirm_words = {"да", "yes", "ок", "ok", "верно", "правильно", "+", "угу", "ага", "yep"}
        if user_text in confirm_words or user_text.startswith("да"):
            if resolved_tz:
                return await self._complete_session(session, event, resolved_tz)
            # No resolved_tz - shouldn't happen, but handle gracefully
            logger.warning(f"CONFIRM_RELOCATION session without resolved_tz: {session.session_id}")
            await self.storage.close_session(session.session_id, SessionStatus.FAILED)
            return HandlerResult(should_respond=False)

        # Check for rejection (нет, no) - ask for correct city
        reject_words = {"нет", "no", "неверно", "не", "nope"}
        if user_text in reject_words:
            text = "Хорошо, напишите город в котором вы сейчас находитесь:"
            return await self._continue_session(session, event, text)

        # User provided a city name - try to geocode it (with LLM normalization for Cyrillic)
        result = geocode_city_full(event.text)
        if result.startswith("FOUND:"):
            try:
                parts = result.replace("FOUND:", "").strip().split("→")
                new_city = parts[0].strip()
                new_tz = parts[1].strip()

                # Update session with new resolved timezone and ask again
                session.context["resolved_city"] = new_city
                session.context["resolved_tz"] = new_tz
                session.context["attempts"] = session.context.get("attempts", 0) + 1
                session.updated_at = datetime.utcnow()

                # Check max attempts
                if session.context["attempts"] >= 3:
                    return await self._fail_session(session, event)

                await self.storage.update_session(session)

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

        # City not found - ask again
        session.context["attempts"] = session.context.get("attempts", 0) + 1
        if session.context["attempts"] >= 3:
            return await self._fail_session(session, event)

        await self.storage.update_session(session)
        text = f"Не нашёл город '{event.text}'. Напишите город точнее (например: Moscow, London, Tokyo):"
        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="plain",
        )
        return HandlerResult(should_respond=True, messages=[message])

    async def _handle_timezone_session(
        self, session: Session, event: NormalizedEvent
    ) -> HandlerResult:
        """Handle a timezone resolution session.

        All logic is delegated to the LLM agent - no hardcoded checks.
        Agent decides if user confirmed or provided a new city.

        Args:
            session: Active timezone session.
            event: User's response message.

        Returns:
            HandlerResult with confirmation or clarification.
        """
        # Get current timezone for re-verify context
        current_tz = None
        if session.goal == SessionGoal.REVERIFY_TIMEZONE:
            user_state = await self.tz_manager.get_user_timezone(event.platform, event.user_id)
            current_tz = user_state.tz_iana if user_state else session.context.get("existing_tz")

        # For first message in session, check if it's a follow-up to a relocation
        # that never got a response (e.g., Telegram send failed)
        user_text = event.text
        history = session.context.get("history", [])
        if not history and session.goal == SessionGoal.REVERIFY_TIMEZONE:
            # Check if session was triggered by relocation (has city in trigger_data)
            trigger_data = session.context.get("trigger_data", {})
            relocation_city = trigger_data.get("city")
            if relocation_city:
                # Prepend the relocation context so agent knows user said "Moved to Paris"
                logger.info(f"Adding relocation context to session: city={relocation_city}")
                user_text = f"[User said they moved to {relocation_city}] {event.text}"

        # Build conversation history with context
        messages = self._build_messages(session, user_text, current_tz)

        try:
            # Run the agent
            result = await self.agent.ainvoke({"messages": messages})

            # Extract messages
            agent_messages = result.get("messages", [])
            if not agent_messages:
                return await self._handle_agent_error(session, event, "No response from agent")

            # Check ALL messages for SAVE: (including tool responses)
            saved_tz = self._extract_saved_timezone(agent_messages)
            if saved_tz:
                return await self._complete_session(session, event, saved_tz)

            # Find the last AI message for user response
            response_text = ""
            for msg in reversed(agent_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    response_text = _sanitize_response(str(msg.content))
                    break

            # Agent is asking for clarification
            return await self._continue_session(session, event, response_text)

        except (TimeoutError, APITimeoutError) as e:
            logger.error(f"Agent timeout in session {session.session_id}: {e}")
            # Try to extract timezone from partial results (if tool already found it)
            partial_tz = self._extract_timezone_from_partial_messages(user_text)
            if partial_tz:
                logger.info(f"Recovering timezone from partial results: {partial_tz}")
                return await self._complete_session(session, event, partial_tz)
            return await self._handle_agent_timeout(session, event)
        except Exception as e:
            logger.exception(f"Agent error: {e}")
            return await self._handle_agent_error(session, event, str(e))

    def _extract_saved_timezone(self, messages: list) -> str | None:
        """Extract saved timezone from agent messages.

        Checks all messages (including tool responses) for SAVE: pattern.

        Args:
            messages: List of agent messages.

        Returns:
            IANA timezone if found, None otherwise.
        """
        for msg in messages:
            content = str(msg.content) if hasattr(msg, "content") else str(msg)
            if "SAVE:" in content:
                # Extract timezone after SAVE:
                tz_part = content.split("SAVE:")[1].strip()
                # Clean up any extra text
                if " " in tz_part:
                    tz_part = tz_part.split()[0]
                if "\n" in tz_part:
                    tz_part = tz_part.split("\n")[0]
                return tz_part
        return None

    def _build_messages(
        self, session: Session, user_text: str, current_tz: str | None = None
    ) -> list[BaseMessage]:
        """Build message history for the agent.

        Args:
            session: Current session with history.
            user_text: User's current message.
            current_tz: User's current timezone (for re-verify sessions).

        Returns:
            List of LangChain messages.
        """
        # Load system prompt from template (includes CURRENT_TZ context if provided)
        system_content = get_agent_system_prompt(current_tz)

        messages: list[BaseMessage] = [SystemMessage(content=system_content)]

        # Add conversation history from session
        history = session.context.get("history", [])
        for entry in history:
            if entry["role"] == "user":
                messages.append(HumanMessage(content=entry["content"]))
            elif entry["role"] == "assistant":
                messages.append(AIMessage(content=entry["content"]))

        # Add current user message
        messages.append(HumanMessage(content=user_text))

        return messages

    async def _complete_session(
        self, session: Session, event: NormalizedEvent, tz_iana: str
    ) -> HandlerResult:
        """Complete the session successfully with resolved timezone.

        Args:
            session: Current session.
            event: Original event.
            tz_iana: Resolved IANA timezone.

        Returns:
            HandlerResult with success message.
        """
        # Save the timezone for the user
        await self.tz_manager.update_user_timezone(
            platform=event.platform,
            user_id=event.user_id,
            tz_iana=tz_iana,
            source=TimezoneSource.CITY_PICK,  # Agent-assisted is similar to city pick
        )

        # Update user's timezone in chat - properly tracks user→tz mapping
        # so when user relocates, old timezone is removed if no other users have it
        from src.core.chat_timezones import update_user_timezone_in_chat

        try:
            await update_user_timezone_in_chat(
                self.storage, event.platform, event.chat_id, event.user_id, tz_iana
            )
        except Exception as e:
            logger.warning(f"Failed to update timezone in chat (non-critical): {e}")

        # Close the session
        await self.storage.close_session(session.session_id, SessionStatus.COMPLETED)

        # Build success message from template
        text = get_ui_message("saved", tz_iana=tz_iana)

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="html",
        )

        return HandlerResult(should_respond=True, messages=[message])

    async def _continue_session(
        self, session: Session, event: NormalizedEvent, response_text: str
    ) -> HandlerResult:
        """Continue the session with a clarification request.

        Args:
            session: Current session.
            event: Original event.
            response_text: Agent's response asking for clarification.

        Returns:
            HandlerResult with clarification message.
        """
        # Update session with new history
        session.context["attempts"] = session.context.get("attempts", 0) + 1
        history = session.context.get("history", [])
        history.append({"role": "user", "content": event.text})
        history.append({"role": "assistant", "content": response_text})
        session.context["history"] = history
        session.updated_at = datetime.utcnow()

        # Check max attempts (hardcoded to 3 for now)
        if session.context["attempts"] >= 3:
            return await self._fail_session(session, event)

        # Update session in storage
        await self.storage.update_session(session)

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=response_text,
            parse_mode="plain",
        )

        return HandlerResult(should_respond=True, messages=[message])

    async def _fail_session(self, session: Session, event: NormalizedEvent) -> HandlerResult:
        """Fail the session after too many attempts.

        Args:
            session: Current session.
            event: Original event.

        Returns:
            HandlerResult with failure message and web verify link.
        """
        await self.storage.close_session(session.session_id, SessionStatus.FAILED)

        # Get verification URL from session context if available
        verify_url = session.context.get("verify_url", "")
        text = get_ui_message("session_failed", verify_url=verify_url if verify_url else None)

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="html",
        )

        return HandlerResult(should_respond=True, messages=[message])

    async def _handle_agent_timeout(
        self,
        session: Session,  # noqa: ARG002 - kept for interface consistency
        event: NormalizedEvent,
    ) -> HandlerResult:
        """Handle LLM timeout - send friendly message, keep session open.

        Args:
            session: Current session.
            event: Original event.

        Returns:
            HandlerResult with retry prompt.
        """
        text = get_ui_message("timeout")

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="plain",
        )

        return HandlerResult(should_respond=True, messages=[message])

    async def _handle_agent_error(
        self, session: Session, event: NormalizedEvent, error: str
    ) -> HandlerResult:
        """Handle agent errors gracefully - send message, keep session open.

        Args:
            session: Current session.
            event: Original event.
            error: Error message.

        Returns:
            HandlerResult with error message.
        """
        logger.error(f"Agent error in session {session.session_id}: {error}")

        text = get_ui_message("error")

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="plain",
        )

        return HandlerResult(should_respond=True, messages=[message])

    def _get_city_name_for_tz(self, tz_iana: str) -> str | None:
        """Get a friendly city name for a timezone.

        Args:
            tz_iana: IANA timezone identifier.

        Returns:
            City name if found in config, None otherwise.
        """
        cities = self.settings.config.timezone.team_cities
        for city in cities:
            if city.tz == tz_iana:
                return city.name
        return None

    def _extract_timezone_from_partial_messages(self, user_text: str) -> str | None:
        """Try to extract timezone directly from user input if agent timed out.

        If the agent timed out after the user sent a city name, try to geocode it
        directly without the agent using geonamescache. This is a fallback for
        timeout recovery - avoids losing user input when LLM is slow.

        Args:
            user_text: Original user text (may contain city name).

        Returns:
            IANA timezone if we can find the city, None otherwise.
        """
        from src.core.agent_tools import _lookup_city_geonames

        # Try to find city in user text - simple heuristic
        # Remove common prefixes like "переехал в", "moved to", "я в", "I'm in"
        city_candidates = [
            user_text,
            user_text.lstrip("в").strip(),  # "в Москву" → "Москву"
            user_text.lstrip("на").strip(),  # "на Мадейру" → "Мадейру"
        ]

        # Also extract from relocation context like "[User said they moved to Paris] ..."
        import re

        reloc_match = re.search(r"\[User said they moved to ([^\]]+)\]", user_text)
        if reloc_match:
            city_candidates.insert(0, reloc_match.group(1))

        for candidate in city_candidates:
            if not candidate or len(candidate) < 2:
                continue

            # Try direct geonames lookup (no LLM, just the local database)
            result = _lookup_city_geonames(candidate)
            if result.startswith("FOUND:"):
                # Extract timezone: "FOUND: City → Timezone"
                try:
                    tz_part = result.split("→")[1].strip()
                    logger.info(f"Fallback geocode found: '{candidate}' → {tz_part}")
                    return tz_part
                except (IndexError, ValueError):
                    continue

        return None
