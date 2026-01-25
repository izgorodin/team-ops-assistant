"""Chat timezone utilities.

Manages active timezones for chats - tracking which timezones
are used by participants in each chat.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.models import Platform
    from src.storage.mongo import MongoStorage


async def add_timezone_to_chat(
    storage: MongoStorage,
    platform: Platform,
    chat_id: str,
    tz_iana: str,
) -> None:
    """Add a timezone to a chat's active_timezones list.

    Called when a user sets their timezone in a chat.
    Uses atomic $addToSet operation - safe for concurrent calls.

    Args:
        storage: MongoDB storage instance.
        platform: Chat platform.
        chat_id: Chat identifier.
        tz_iana: IANA timezone to add.
    """
    await storage.add_timezone_to_chat(platform, chat_id, tz_iana)


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
