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


def parse_malformed_tool_call(text: str) -> str | None:
    """Parse timezone from LLM text that contains function call syntax.

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
            tz = parse_malformed_tool_call(content)
            if tz:
                logger.warning(f"Extracted timezone from malformed tool call: {tz}")
                return ("SAVE", tz)

        if "convert_time" in content:
            match = re.search(r"convert_time\s*\([^)]+\)", content)
            if match:
                logger.warning("Detected malformed convert_time call")
                return ("CONVERT", "Time conversion requested")

        if "no_action" in content.lower():
            return ("NO_ACTION", "")

    return None
