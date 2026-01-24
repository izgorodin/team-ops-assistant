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
SYSTEM_PROMPT = """You are a timezone assistant for a team chat bot.
Your job is to help users set their timezone so the bot can convert times correctly.

Tools available:
- lookup_configured_city: Check team's configured cities (try first)
- lookup_tz_abbreviation: Check timezone codes (PT, PST, EST, CET, MSK)
- geocode_city: Look up any city worldwide (supports abbreviations: NY, LA, MSK, СПб)
- save_timezone: ALWAYS call this when done (for both new cities AND confirmations)

IMPORTANT: ALWAYS call save_timezone when the user is done:
- For NEW CITY: look it up → call save_timezone with the resolved IANA timezone
- For CONFIRMATION: call save_timezone with their CURRENT timezone (from context)

Process:
1. If user provides a city name → look it up → call save_timezone
2. If user confirms (да, yes, конечно, верно, точно, ага, sure, ok, yep, правильно, именно, ладно, хорошо)
   → call save_timezone with CURRENT_TZ from context
3. If lookup fails → ask user to try different spelling

CRITICAL RULES:
- ALWAYS call save_timezone with IANA timezone when done
- Be concise - one sentence responses
- Respond in the same language as the user
- NEVER invent/hallucinate a timezone if lookup fails
- If NOT_FOUND, ask user to try different spelling

Examples:
- User: "NY" → geocode_city("NY") → FOUND → save_timezone("America/New_York")
- User: "да" (CURRENT_TZ: Europe/Moscow) → save_timezone("Europe/Moscow")
- User: "конечно" (CURRENT_TZ: Europe/London) → save_timezone("Europe/London")
- User: "xyz" → lookup fails → "Не нашёл 'xyz'. Напиши город точнее"
"""


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
        if session.goal in (SessionGoal.AWAITING_TIMEZONE, SessionGoal.REVERIFY_TIMEZONE):
            return await self._handle_timezone_session(session, event)

        # Unknown session goal - close it
        logger.warning(f"Unknown session goal: {session.goal}")
        await self.storage.close_session(session.session_id, SessionStatus.FAILED)
        return HandlerResult(should_respond=False)

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

        # Build conversation history with context
        messages = self._build_messages(session, event.text, current_tz)

        try:
            # Run the agent
            result = await self.agent.ainvoke({"messages": messages})

            # Extract messages
            agent_messages = result.get("messages", [])
            if not agent_messages:
                return await self._handle_agent_error(session, "No response from agent")

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

        except Exception as e:
            logger.exception(f"Agent error: {e}")
            return await self._handle_agent_error(session, str(e))

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
        # Build system prompt with context
        system_content = SYSTEM_PROMPT
        if current_tz:
            # Add context about current timezone for confirmations
            system_content += f"\n\nCONTEXT: CURRENT_TZ={current_tz}"

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

        # Close the session
        await self.storage.close_session(session.session_id, SessionStatus.COMPLETED)

        # Build success message (Russian since most users are Russian-speaking)
        text = f"✅ Сохранено: <b>{tz_iana}</b>"

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

    async def _handle_agent_error(self, session: Session, error: str) -> HandlerResult:
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
