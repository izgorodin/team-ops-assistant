"""Relocation action handler.

Handles detected relocation triggers by resetting confidence and triggering re-verification.
Implements the ActionHandler protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Runtime import needed for protocol compatibility
from src.core.models import DetectedTrigger, OutboundMessage, ResolvedContext  # noqa: TC001
from src.settings import get_settings

if TYPE_CHECKING:
    from src.storage.mongo import MongoStorage


class RelocationHandler:
    """Handles relocation triggers.

    When user indicates they've moved, this handler resets their timezone
    confidence to 0.0. The pipeline then returns needs_state_collection=True
    immediately (step 1.5), which causes the orchestrator to create a
    REVERIFY_TIMEZONE session.

    Flow: Pipeline detects relocation → calls this handler → returns early
    with needs_state_collection=True → Orchestrator creates re-verify session.

    Implements ActionHandler protocol.
    """

    def __init__(self, storage: MongoStorage) -> None:
        """Initialize the relocation handler.

        Args:
            storage: MongoDB storage for updating user state.
        """
        self.storage = storage
        self._settings = get_settings()

    async def handle(
        self,
        trigger: DetectedTrigger,  # noqa: ARG002
        context: ResolvedContext,
    ) -> list[OutboundMessage]:
        """Handle a relocation trigger.

        Resets confidence to trigger re-verification flow.

        Args:
            trigger: The relocation trigger with city data (unused, required by protocol).
            context: Resolved context (platform, user_id, etc.).

        Returns:
            Empty list - orchestrator handles the response via session.
        """
        config = self._settings.config.confidence

        # Get user's current state
        user_state = await self.storage.get_user_tz_state(context.platform, context.user_id)
        if user_state:
            # Reset confidence to relocation_reset value (0.0)
            # This will trigger re-verification on the next pipeline run
            user_state.confidence = config.relocation_reset
            await self.storage.upsert_user_tz_state(user_state)

        # Return empty - pipeline explicitly sets needs_state_collection=True
        # for relocation triggers (step 1.5), so orchestrator creates session
        return []
