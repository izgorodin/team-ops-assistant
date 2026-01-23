"""Protocol definitions for extensible architecture.

These protocols define the contracts that implementations must follow.
Using Python's Protocol for structural subtyping (duck typing with type hints).

Protocols:
- TriggerDetector: Detects triggers in normalized events
- StateManager[T]: Manages state with confidence tracking
- ActionHandler: Handles detected triggers and produces responses
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from src.core.models import (
        DetectedTrigger,
        NormalizedEvent,
        OutboundMessage,
        Platform,
        ResolvedContext,
        StateResult,
    )

# Generic type for StateManager
T = TypeVar("T")


@runtime_checkable
class TriggerDetector(Protocol):
    """Protocol for trigger detection in messages.

    Implementations detect specific types of triggers (time, date, etc.)
    and return structured trigger objects.

    Example implementations:
    - TimeDetector: Detects time references like "3pm", "15:30"
    - DateDetector: Detects date references like "tomorrow", "next Monday"
    - QuestionDetector: Detects questions about timezones
    """

    async def detect(self, event: NormalizedEvent) -> list[DetectedTrigger]:
        """Detect triggers in a normalized event.

        Args:
            event: The normalized event to analyze.

        Returns:
            List of detected triggers. Empty list if no triggers found.
        """
        ...


@runtime_checkable
class StateManager(Protocol[T]):
    """Protocol for managing state with confidence tracking.

    Implementations manage different types of state (timezone, language, etc.)
    with confidence scores and source tracking.

    Example implementations:
    - TimezoneStateManager: Manages user timezone state
    - LanguageStateManager: Manages user language preferences
    """

    async def get_state(
        self,
        platform: Platform,
        user_id: str,
        chat_id: str,
    ) -> StateResult[T]:
        """Get current state for a user.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            chat_id: Chat/channel ID.

        Returns:
            StateResult containing value, confidence, and source.
        """
        ...

    async def update_state(
        self,
        platform: Platform,
        user_id: str,
        value: T,
        source: str,
        confidence: float,
    ) -> None:
        """Update state for a user.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.
            value: New state value.
            source: Where this value came from.
            confidence: Confidence in this value.
        """
        ...


@runtime_checkable
class ActionHandler(Protocol):
    """Protocol for handling detected triggers.

    Implementations handle specific trigger types and produce
    outbound messages as responses.

    Example implementations:
    - TimeConversionHandler: Converts time references to multiple timezones
    - TimezoneHelpHandler: Responds to timezone questions
    """

    async def handle(
        self,
        trigger: DetectedTrigger,
        context: ResolvedContext,
    ) -> list[OutboundMessage]:
        """Handle a detected trigger and produce response messages.

        Args:
            trigger: The trigger to handle.
            context: Resolved context for handling.

        Returns:
            List of outbound messages to send.
        """
        ...
