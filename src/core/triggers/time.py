"""Time trigger detector.

Detects time references in messages using ML classifier and regex parsing.
Implements the TriggerDetector protocol.
"""

from __future__ import annotations

from src.core.models import DetectedTrigger, NormalizedEvent
from src.core.time_parse import parse_times


class TimeDetector:
    """Detects time references in messages.

    Uses the existing time parsing infrastructure:
    1. ML classifier for quick detection
    2. Regex patterns for extraction
    3. LLM fallback for edge cases

    Implements TriggerDetector protocol.
    """

    async def detect(self, event: NormalizedEvent) -> list[DetectedTrigger]:
        """Detect time references in a normalized event.

        Args:
            event: The normalized event to analyze.

        Returns:
            List of detected time triggers. Empty if no times found.
        """
        # Use existing time parsing infrastructure
        parsed_times = parse_times(event.text)

        # Convert ParsedTime to DetectedTrigger
        triggers: list[DetectedTrigger] = []
        for pt in parsed_times:
            triggers.append(
                DetectedTrigger(
                    trigger_type="time",
                    confidence=pt.confidence,
                    original_text=pt.original_text,
                    data={
                        "hour": pt.hour,
                        "minute": pt.minute,
                        "timezone_hint": pt.timezone_hint,
                        "is_tomorrow": pt.is_tomorrow,
                    },
                )
            )

        return triggers
