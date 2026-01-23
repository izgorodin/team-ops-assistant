"""Time conversion action handler.

Converts time references to multiple timezones and produces response messages.
Implements the ActionHandler protocol.
"""

from __future__ import annotations

from src.core.models import DetectedTrigger, OutboundMessage, ResolvedContext
from src.core.time_convert import format_time_conversion


class TimeConversionHandler:
    """Handles time triggers by converting to multiple timezones.

    Takes a detected time trigger and resolved context, then produces
    a formatted response message showing the time in all target timezones.

    Implements ActionHandler protocol.
    """

    async def handle(
        self,
        trigger: DetectedTrigger,
        context: ResolvedContext,
    ) -> list[OutboundMessage]:
        """Handle a time trigger and produce conversion response.

        Args:
            trigger: The time trigger to handle.
            context: Resolved context with source/target timezones.

        Returns:
            List containing the conversion response message.
        """
        # Extract time data from trigger
        hour = trigger.data.get("hour", 0)
        minute = trigger.data.get("minute", 0)

        # Use timezone hint from trigger if available, otherwise use context
        source_tz = trigger.data.get("timezone_hint") or context.source_timezone

        # If we still don't have a source timezone, we can't convert
        if not source_tz:
            return []

        # If no target timezones, nothing to convert to
        if not context.target_timezones:
            return []

        # Format the conversion message
        text = format_time_conversion(
            hour=hour,
            minute=minute,
            source_tz=source_tz,
            target_timezones=context.target_timezones,
            original_text=trigger.original_text,
        )

        return [
            OutboundMessage(
                platform=context.platform,
                chat_id=context.chat_id,
                text=text,
                reply_to_message_id=context.reply_to_message_id,
                parse_mode="plain",
            )
        ]
