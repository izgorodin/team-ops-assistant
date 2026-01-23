"""Core message handler.

Rules-first pipeline that processes normalized events and returns outbound messages.
LLM is used only as fallback when rules-based parsing fails.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.core.dedupe import DedupeManager
from src.core.models import (
    HandlerResult,
    NormalizedEvent,
    OutboundMessage,
    Platform,
    TimezoneSource,
)
from src.core.time_convert import (
    convert_to_timezones,
    format_conversion_response,
    is_valid_iana_timezone,
)
from src.core.time_parse import contains_time_reference, parse_times
from src.core.timezone_identity import (
    TimezoneIdentityManager,
    generate_verify_token,
    get_verify_url,
)
from src.settings import get_settings

if TYPE_CHECKING:
    from src.storage.mongo import MongoStorage

logger = logging.getLogger(__name__)


class MessageHandler:
    """Core message handler implementing rules-first pipeline."""

    def __init__(self, storage: MongoStorage, base_url: str = "") -> None:
        """Initialize the message handler.

        Args:
            storage: MongoDB storage instance.
            base_url: Base URL for verification links.
        """
        self.storage = storage
        self.settings = get_settings()
        self.tz_manager = TimezoneIdentityManager(storage)
        self.dedupe = DedupeManager(storage)
        self.base_url = base_url

    async def handle(self, event: NormalizedEvent) -> HandlerResult:
        """Handle an incoming normalized event.

        Args:
            event: Normalized event from any platform.

        Returns:
            HandlerResult with outbound messages if any.
        """
        # 1. Check for duplicate
        if await self.dedupe.is_duplicate(event.platform, event.event_id):
            logger.debug(f"Duplicate event: {event.event_id}")
            return HandlerResult(should_respond=False)

        # 2. Check throttling
        if self.dedupe.is_throttled(event.platform, event.chat_id):
            logger.debug(f"Throttled chat: {event.chat_id}")
            return HandlerResult(should_respond=False)

        # 2.5. Check if message is a city pick reply (before time detection)
        city_result = await self._try_city_pick(event)
        if city_result is not None:
            return city_result

        # 3. Check if message contains time reference
        if not contains_time_reference(event.text):
            return HandlerResult(should_respond=False)

        # 4. Parse times from message
        parsed_times = parse_times(event.text)

        if not parsed_times:
            # Could invoke LLM fallback here if configured
            # For MVP, we just skip messages we can't parse
            logger.debug(f"No parseable times in: {event.text[:50]}...")
            return HandlerResult(should_respond=False)

        # 5. Get the best parsed time
        best_time = parsed_times[0]  # Already sorted by confidence

        # 6. Determine source timezone using disambiguation policy
        explicit_tz = best_time.timezone_hint
        source_tz, _confidence = await self.tz_manager.get_effective_timezone(
            event.platform, event.user_id, event.chat_id, explicit_tz
        )

        # 7. If timezone is unknown, prompt verification
        if source_tz is None:
            return await self._handle_unknown_timezone(event)

        # 8. Get target timezones
        target_tzs = await self._get_target_timezones(event.platform, event.chat_id)

        # 9. Convert times
        conversions = convert_to_timezones(best_time, source_tz, target_tzs)

        if not conversions:
            return HandlerResult(should_respond=False)

        # 10. Format response
        response_text = format_conversion_response(best_time.original_text, source_tz, conversions)

        # 11. Mark as processed
        await self.dedupe.mark_processed(event.platform, event.event_id, event.chat_id)
        self.dedupe.record_response(event.platform, event.chat_id)

        # 12. Return outbound message
        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=response_text,
            reply_to_message_id=event.event_id if event.reply_to_message_id else None,
        )

        return HandlerResult(should_respond=True, messages=[message])

    async def _handle_unknown_timezone(self, event: NormalizedEvent) -> HandlerResult:
        """Handle case where user's timezone is unknown.

        Prompts user to verify their timezone.

        Args:
            event: The event being processed.

        Returns:
            HandlerResult with verification prompt.
        """
        # Generate verification token
        token = generate_verify_token(event.platform, event.user_id, event.chat_id)
        verify_url = get_verify_url(token, self.base_url)

        # Build verification prompt with city fallback
        cities = self.settings.config.timezone.team_cities
        city_list = ", ".join(c.name for c in cities[:4])

        text = (
            "🌍 I noticed you mentioned a time! To convert it for the team, "
            "I need to know your timezone.\n\n"
            f"<b>Set your timezone once:</b>\n"
            f'• <a href="{verify_url}">Verify TZ</a> - auto-detects from browser\n'
            f"• Or pick a city: {city_list}\n\n"
            "<i>Reply with your city name and I'll remember it!</i>"
        )

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=text,
            parse_mode="html",
        )

        return HandlerResult(
            should_respond=True,
            messages=[message],
            ask_timezone=True,
            verify_url=verify_url,
        )

    async def _get_target_timezones(self, platform: Platform, chat_id: str) -> list[str]:
        """Get target timezones for conversion.

        Uses chat's active timezones if available, otherwise team defaults.

        Args:
            platform: Chat platform.
            chat_id: Chat identifier.

        Returns:
            List of IANA timezone identifiers.
        """
        # Check for chat-specific active timezones
        chat_state = await self.storage.get_chat_state(platform, chat_id)
        if chat_state and chat_state.active_timezones:
            return chat_state.active_timezones

        # Fall back to team defaults
        return self.settings.config.timezone.team_timezones

    async def _try_city_pick(self, event: NormalizedEvent) -> HandlerResult | None:
        """Try to process the message as a city pick.

        Checks if the message text matches a configured city name.
        Only matches short messages that are just a city name.

        Args:
            event: The normalized event.

        Returns:
            HandlerResult if city was matched and processed, None otherwise.
        """
        text = event.text.strip()

        # Only check short messages (city names are short)
        # This avoids matching "London" in "Meeting at 3pm in London"
        if len(text) > 50 or " " in text.strip():
            return None

        # Try to match a city
        tz = await self.handle_city_pick(event.platform, event.user_id, text)

        if tz is None:
            return None

        # City matched - respond with confirmation
        # Find the city name for display
        city_name = text  # Default to what user typed
        for city in self.settings.config.timezone.team_cities:
            if city.name.lower() == text.lower():
                city_name = city.name
                break

        message = OutboundMessage(
            platform=event.platform,
            chat_id=event.chat_id,
            text=f"✅ Got it! Your timezone is set to <b>{city_name}</b> ({tz}).\n\n"
            "I'll now convert times you mention to your team's timezones.",
            parse_mode="html",
        )

        return HandlerResult(should_respond=True, messages=[message])

    async def handle_city_pick(
        self, platform: Platform, user_id: str, city_name: str
    ) -> str | None:
        """Handle a user picking a city for their timezone.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            city_name: City name to look up.

        Returns:
            IANA timezone if city found, None otherwise.
        """
        cities = self.settings.config.timezone.team_cities
        city_lower = city_name.lower().strip()

        for city in cities:
            if city.name.lower() == city_lower:
                await self.tz_manager.update_user_timezone(
                    platform=platform,
                    user_id=user_id,
                    tz_iana=city.tz,
                    source=TimezoneSource.CITY_PICK,
                )
                return city.tz

        return None

    async def handle_web_verify(self, platform: Platform, user_id: str, tz_iana: str) -> bool:
        """Handle timezone verification from web flow.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            tz_iana: IANA timezone from browser.

        Returns:
            True if verification succeeded.
        """
        if not is_valid_iana_timezone(tz_iana):
            return False

        await self.tz_manager.update_user_timezone(
            platform=platform,
            user_id=user_id,
            tz_iana=tz_iana,
            source=TimezoneSource.WEB_VERIFIED,
        )
        return True
