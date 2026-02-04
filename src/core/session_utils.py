"""Session handling utilities.

Common constants and utilities for session management.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Session configuration
MAX_SESSION_ATTEMPTS = 3
SESSION_TTL_TIMEZONE_MINUTES = 30  # TTL for timezone onboarding sessions
SESSION_TTL_GEO_INTENT_MINUTES = 10  # TTL for geo intent clarification sessions


def parse_malformed_save_timezone(text: str) -> str | None:
    """Parse timezone from malformed save_timezone call.

    Handles cases where LLM outputs tool calls as text instead of calling them.
    Examples:
        - save_timezone({"tz_iana": "Europe/Rome"})
        - save_timezone("Europe/Rome")
        - save_timezone(tz_iana="Europe/Rome")

    Args:
        text: Text containing potential malformed tool call.

    Returns:
        IANA timezone if found, None otherwise.
    """
    # Pattern 1: save_timezone({"tz_iana": "Europe/Rome"})
    match = re.search(
        r'save_timezone\s*\(\s*\{\s*["\']?tz_iana["\']?\s*:\s*["\']([^"\']+)["\']', text
    )
    if match:
        return match.group(1)

    # Pattern 2: save_timezone("Europe/Rome")
    match = re.search(r'save_timezone\s*\(\s*["\']([^"\']+)["\']', text)
    if match:
        return match.group(1)

    # Pattern 3: save_timezone(tz_iana="Europe/Rome")
    match = re.search(r'save_timezone\s*\(\s*tz_iana\s*=\s*["\']([^"\']+)["\']', text)
    if match:
        return match.group(1)

    return None


def parse_and_execute_convert_time(text: str) -> str | None:
    """Parse and execute malformed convert_time call.

    Handles cases where LLM outputs convert_time as text.
    Examples:
        - convert_time("12", "Asia/Bangkok", "Europe/Rome")
        - convert_time(time_str="15:00", source_tz="Europe/Moscow", target_tz="America/New_York")

    Args:
        text: Text containing potential malformed convert_time call.

    Returns:
        Conversion result string if successful, None otherwise.
    """
    from src.core.agent_tools import convert_time

    # Pattern 1: convert_time("12", "Asia/Bangkok", "Europe/Rome")
    match = re.search(
        r'convert_time\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']',
        text,
    )
    if match:
        time_str, source_tz, target_tz = match.groups()
        logger.info(f"Executing malformed convert_time: {time_str}, {source_tz} → {target_tz}")
        result = convert_time.invoke(
            {"time_str": time_str, "source_tz": source_tz, "target_tz": target_tz}
        )
        return str(result)

    # Pattern 2: convert_time(time_str="15", source_tz="...", target_tz="...")
    match = re.search(
        r"convert_time\s*\("
        r'[^)]*time_str\s*=\s*["\']([^"\']+)["\']'
        r'[^)]*source_tz\s*=\s*["\']([^"\']+)["\']'
        r'[^)]*target_tz\s*=\s*["\']([^"\']+)["\']',
        text,
    )
    if match:
        time_str, source_tz, target_tz = match.groups()
        logger.info(f"Executing malformed convert_time: {time_str}, {source_tz} → {target_tz}")
        result = convert_time.invoke(
            {"time_str": time_str, "source_tz": source_tz, "target_tz": target_tz}
        )
        return str(result)

    return None


def extract_tool_action(messages: list) -> tuple[str, str] | None:
    """Extract action from agent messages.

    Looks for SAVE:, CONVERT:, or NO_ACTION patterns in tool responses.
    Also handles malformed tool calls where LLM outputs function syntax as text.

    Args:
        messages: Agent messages from LangChain.

    Returns:
        Tuple of (action_type, data) or None.
        action_type is one of: "SAVE", "CONVERT", "NO_ACTION"
    """
    from langchain_core.messages import ToolMessage

    for msg in messages:
        content = ""
        if isinstance(msg, ToolMessage):
            content = str(msg.content) if msg.content else ""
        elif hasattr(msg, "content"):
            content = str(msg.content)
        else:
            content = str(msg)

        # Primary patterns from tool execution
        if "SAVE:" in content:
            tz_part = content.split("SAVE:")[1].strip()
            if " " in tz_part:
                tz_part = tz_part.split()[0]
            if "\n" in tz_part:
                tz_part = tz_part.split("\n")[0]
            logger.debug(f"Extracted timezone from SAVE: pattern: {tz_part}")
            return ("SAVE", tz_part)

        if "CONVERT:" in content:
            conversion = content.split("CONVERT:")[1].strip()
            return ("CONVERT", conversion)

        if "NO_ACTION" in content:
            return ("NO_ACTION", "")

        # Fallback: malformed tool calls as text
        if "save_timezone" in content:
            tz = parse_malformed_save_timezone(content)
            if tz:
                logger.warning(f"Extracted timezone from malformed tool call: {tz}")
                return ("SAVE", tz)

        if "convert_time" in content:
            result = parse_and_execute_convert_time(content)
            if result:
                logger.warning(f"Executed malformed convert_time call: {result}")
                return ("CONVERT", result.replace("CONVERT:", "").strip())

        if "no_action" in content.lower():
            return ("NO_ACTION", "")

    return None
