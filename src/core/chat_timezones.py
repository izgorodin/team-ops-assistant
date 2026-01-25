"""Chat timezone utilities.

Manages active timezones for chats - tracking which timezones
are used by participants in each chat.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.core.models import ChatState, Platform

if TYPE_CHECKING:
    from src.storage.mongo import MongoStorage


async def add_timezone_to_chat(
    storage: MongoStorage,
    platform: Platform,
    chat_id: str,
    tz_iana: str,
) -> None:
    """Add a timezone to a chat's active_timezones list.

    Called when a user sets their timezone in a chat.
    Ensures no duplicates are added.

    Args:
        storage: MongoDB storage instance.
        platform: Chat platform.
        chat_id: Chat identifier.
        tz_iana: IANA timezone to add.
    """
    chat_state = await storage.get_chat_state(platform, chat_id)

    if chat_state is None:
        chat_state = ChatState(
            platform=platform,
            chat_id=chat_id,
            active_timezones=[tz_iana],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    else:
        if tz_iana not in chat_state.active_timezones:
            chat_state.active_timezones.append(tz_iana)
        chat_state.updated_at = datetime.now(UTC)

    await storage.upsert_chat_state(chat_state)


def merge_timezones(config_tzs: list[str], chat_tzs: list[str]) -> list[str]:
    """Merge config and chat timezones, removing duplicates.

    Config timezones come first (team's standard locations),
    then chat-specific ones (detected from users).

    Args:
        config_tzs: Timezones from configuration.
        chat_tzs: Timezones detected from chat participants.

    Returns:
        Merged list with no duplicates, config first.
    """
    result = list(config_tzs)
    for tz in chat_tzs:
        if tz not in result:
            result.append(tz)
    return result
