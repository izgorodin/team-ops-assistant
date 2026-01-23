"""LangChain Agent Handler for session-based conversations.

Handles multi-turn conversations when the bot needs to collect information
from the user (e.g., timezone verification).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

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
from src.core.timezone_identity import TimezoneIdentityManager

if TYPE_CHECKING:
    from src.settings import Settings
    from src.storage.mongo import MongoStorage

logger = logging.getLogger(__name__)

# System prompt for the timezone agent
SYSTEM_PROMPT = """You are a helpful timezone assistant for a team chat bot.
Your job is to help users set their timezone so the bot can convert times correctly.

You have these tools:
- lookup_configured_city: Check if a city is in the team's configured cities (preferred)
- lookup_tz_abbreviation: Check timezone codes like PT, PST, EST, CET
- geocode_city: Look up any city worldwide to find its timezone
- save_timezone: Save the final timezone (call this when you've determined it)

Process:
1. When user provides input, first try to understand what they mean
2. Try lookup_configured_city first (team's preferred cities)
3. If not found, try lookup_tz_abbreviation for codes
4. If still not found, try geocode_city for worldwide lookup
5. When you've found the timezone, call save_timezone with the IANA format
6. If you can't determine the timezone, ask for clarification politely

Rules:
- Be concise and friendly
- Respond in the same language as the user
- If the user seems confused, offer examples
- After 3 failed attempts, suggest using the web verification link instead

Examples of user inputs you might receive:
- "London" → lookup_configured_city, then save_timezone
- "PT" or "PST" → lookup_tz_abbreviation, then save_timezone
- "Funchal" → geocode_city (not in config), then save_timezone
- "абракадабра" → ask for clarification
"""


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
        self.llm = ChatOpenAI(
            base_url=settings.config.llm.base_url,
            api_key=settings.nvidia_api_key,  # type: ignore[arg-type]
            model=settings.config.llm.model,
            temperature=0.3,
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
        if session.goal == SessionGoal.AWAITING_TIMEZONE:
            return await self._handle_timezone_session(session, event)

        # Unknown session goal - close it
        logger.warning(f"Unknown session goal: {session.goal}")
        await self.storage.close_session(session.session_id, SessionStatus.FAILED)
        return HandlerResult(should_respond=False)

    async def _handle_timezone_session(
        self, session: Session, event: NormalizedEvent
    ) -> HandlerResult:
        """Handle a timezone resolution session.

        Args:
            session: Active timezone session.
            event: User's response message.

        Returns:
            HandlerResult with confirmation or clarification.
        """
        # Build conversation history
        messages = self._build_messages(session, event.text)

        try:
            # Run the agent
            result = await self.agent.ainvoke({"messages": messages})

            # Extract the final response
            agent_messages = result.get("messages", [])
            if not agent_messages:
                return await self._handle_agent_error(session, "No response from agent")

            # Find the last AI message
            response_text = ""
            for msg in reversed(agent_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    response_text = str(msg.content)
                    break

            # Check if agent saved the timezone
            if "SAVE:" in response_text:
                tz_iana = response_text.split("SAVE:")[1].strip()
                # Clean up any extra text after the timezone
                if " " in tz_iana:
                    tz_iana = tz_iana.split()[0]
                return await self._complete_session(session, event, tz_iana)

            # Agent is asking for clarification
            return await self._continue_session(session, event, response_text)

        except Exception as e:
            logger.exception(f"Agent error: {e}")
            return await self._handle_agent_error(session, str(e))

    def _build_messages(self, session: Session, user_text: str) -> list[BaseMessage]:
        """Build message history for the agent.

        Args:
            session: Current session with history.
            user_text: User's current message.

        Returns:
            List of LangChain messages.
        """
        messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

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

        # Close the session
        await self.storage.close_session(session.session_id, SessionStatus.COMPLETED)

        # Build success message
        # Try to find a friendly city name
        city_name = self._get_city_name_for_tz(tz_iana)
        if city_name:
            text = f"✅ Got it! Your timezone is set to <b>{city_name}</b> ({tz_iana})."
        else:
            text = f"✅ Got it! Your timezone is set to <b>{tz_iana}</b>."

        text += "\n\nI'll now convert times you mention to your team's timezones."

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

    async def _fail_session(
        self, session: Session, event: NormalizedEvent
    ) -> HandlerResult:
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
        if verify_url:
            text = (
                "😕 I couldn't determine your timezone from that.\n\n"
                f'Please use the <a href="{verify_url}">web verification link</a> '
                "to set your timezone automatically, or try again with a major city name."
            )
        else:
            text = (
                "😕 I couldn't determine your timezone from that.\n\n"
                "Please try again with a major city name (e.g., London, Tokyo, New York) "
                "or a timezone code (e.g., PT, CET, JST)."
            )

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="html",
        )

        return HandlerResult(should_respond=True, messages=[message])

    async def _handle_agent_error(
        self, session: Session, error: str
    ) -> HandlerResult:
        """Handle agent errors gracefully.

        Args:
            session: Current session.
            error: Error message.

        Returns:
            HandlerResult indicating no response.
        """
        logger.error(f"Agent error in session {session.session_id}: {error}")
        # Don't close session on error - let user retry
        return HandlerResult(should_respond=False)

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
