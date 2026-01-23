"""Message Orchestrator - routes messages between main pipeline and agent mode.

The orchestrator is a simple, deterministic router that checks if there's
an active session for the user before routing the message.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.agent_handler import AgentHandler
    from src.core.handler import MessageHandler
    from src.core.models import HandlerResult, NormalizedEvent
    from src.storage.mongo import MongoStorage

logger = logging.getLogger(__name__)


class MessageOrchestrator:
    """Routes messages between main pipeline and agent mode.

    Flow:
    1. Check if there's an active session for this user
    2. If yes → route to AgentHandler
    3. If no → route to MainHandler (which may create a session)
    """

    def __init__(
        self,
        storage: MongoStorage,
        main_handler: MessageHandler,
        agent_handler: AgentHandler,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            storage: MongoDB storage instance.
            main_handler: Main message handler (time conversion pipeline).
            agent_handler: Agent handler for session-based conversations.
        """
        self.storage = storage
        self.main_handler = main_handler
        self.agent_handler = agent_handler

    async def route(self, event: NormalizedEvent) -> HandlerResult:
        """Route an incoming message to the appropriate handler.

        Args:
            event: Normalized incoming message event.

        Returns:
            HandlerResult from the appropriate handler.
        """
        # 1. Check for active session
        session = await self.storage.get_active_session(
            event.platform, event.chat_id, event.user_id
        )

        if session:
            logger.debug(
                f"Active session found for user {event.user_id}, "
                f"routing to agent handler (goal: {session.goal})"
            )
            return await self.agent_handler.handle(session, event)

        # 2. No active session - route to main pipeline
        logger.debug(f"No active session for user {event.user_id}, routing to main handler")
        return await self.main_handler.handle(event)
