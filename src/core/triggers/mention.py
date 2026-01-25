"""Mention trigger detector.

Detects when user mentions the bot or asks for help.
Implements the TriggerDetector protocol.
"""

from __future__ import annotations

import re

from src.core.models import DetectedTrigger, NormalizedEvent

# Mention patterns for bot invocation and help requests
# Each tuple: (compiled pattern, pattern name)
MENTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # @bot style mentions
    (re.compile(r"@\w*bot\b", re.IGNORECASE), "at_bot"),
    # Russian "бот" as standalone word
    (re.compile(r"\bбот\b", re.IGNORECASE), "bot_ru"),
    # English "bot" as standalone word
    (re.compile(r"\bbot\b", re.IGNORECASE), "bot_en"),
    # Russian "помощь" (help)
    (re.compile(r"\bпомощь\b", re.IGNORECASE), "help_ru"),
    # English "help" as standalone word
    (re.compile(r"\bhelp\b", re.IGNORECASE), "help_en"),
]

# Default confidence for mention detection
MENTION_CONFIDENCE = 0.95


class MentionDetector:
    """Detects bot mentions and help requests in messages.

    When user says "@bot", "бот", "help", or "помощь",
    this detector fires and signals that help info should be shown.

    Implements TriggerDetector protocol.
    """

    async def detect(self, event: NormalizedEvent) -> list[DetectedTrigger]:
        """Detect mention phrases in a message.

        Args:
            event: The normalized event to analyze.

        Returns:
            List with single trigger if mention detected, empty otherwise.
        """
        text = event.text

        for pattern, pattern_name in MENTION_PATTERNS:
            match = pattern.search(text)
            if match:
                return [
                    DetectedTrigger(
                        trigger_type="mention",
                        confidence=MENTION_CONFIDENCE,
                        original_text=match.group(0),
                        data={
                            "pattern": pattern_name,
                        },
                    )
                ]

        return []
