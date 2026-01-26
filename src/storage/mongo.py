"""MongoDB storage module.

Provides async MongoDB operations using Motor client.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from src.core.models import (
    ChatState,
    DedupeEvent,
    Platform,
    Session,
    SessionStatus,
    UserTzState,
)
from src.settings import get_settings

logger = logging.getLogger(__name__)


class MongoStorage:
    """MongoDB storage operations."""

    def __init__(self) -> None:
        """Initialize MongoDB storage."""
        self.settings = get_settings()
        self._client: AsyncIOMotorClient | None = None  # type: ignore[type-arg]
        self._db: AsyncIOMotorDatabase | None = None  # type: ignore[type-arg]

    @property
    def client(self) -> AsyncIOMotorClient:  # type: ignore[type-arg]
        """Get the MongoDB client."""
        if self._client is None:
            raise RuntimeError("MongoDB client not initialized. Call connect() first.")
        return self._client

    @property
    def db(self) -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
        """Get the database instance."""
        if self._db is None:
            raise RuntimeError("MongoDB database not initialized. Call connect() first.")
        return self._db

    async def connect(self) -> None:
        """Connect to MongoDB and set up indexes."""
        logger.info("Connecting to MongoDB...")

        self._client = AsyncIOMotorClient(self.settings.mongodb_uri)
        self._db = self._client[self.settings.config.database.name]

        # Verify connection
        await self._client.admin.command("ping")
        logger.info("MongoDB connection established")

        # Set up indexes
        await self._ensure_indexes()

    async def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client:
            logger.info("Closing MongoDB connection...")
            self._client.close()
            self._client = None
            self._db = None

    async def check_connection(self) -> bool:
        """Check if MongoDB is reachable.

        Returns:
            True if connection is healthy, False otherwise.
        """
        if self._client is None:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            logger.warning("MongoDB health check failed", exc_info=True)
            return False

    async def _ensure_indexes(self) -> None:
        """Ensure all required indexes exist."""
        config = self.settings.config.dedupe

        # Users collection: unique index on (platform, user_id)
        await self.db.users.create_index(
            [("platform", ASCENDING), ("user_id", ASCENDING)],
            unique=True,
            name="platform_user_idx",
        )

        # Chats collection: unique index on (platform, chat_id)
        await self.db.chats.create_index(
            [("platform", ASCENDING), ("chat_id", ASCENDING)],
            unique=True,
            name="platform_chat_idx",
        )

        # Dedupe events: unique index on (platform, event_id) + TTL on created_at
        await self.db.dedupe_events.create_index(
            [("platform", ASCENDING), ("event_id", ASCENDING)],
            unique=True,
            name="platform_event_idx",
        )
        await self.db.dedupe_events.create_index(
            [("created_at", ASCENDING)],
            expireAfterSeconds=config.ttl_seconds,
            name="created_at_ttl",
        )

        # Sessions collection: index on (platform, chat_id, user_id, status) + TTL on expires_at
        await self.db.sessions.create_index(
            [
                ("platform", ASCENDING),
                ("chat_id", ASCENDING),
                ("user_id", ASCENDING),
                ("status", ASCENDING),
            ],
            name="platform_chat_user_status_idx",
        )
        await self.db.sessions.create_index(
            [("expires_at", ASCENDING)],
            expireAfterSeconds=0,  # TTL at exact expires_at time
            name="expires_at_ttl",
        )

        logger.info("MongoDB indexes ensured")

    # User timezone operations

    async def get_user_tz_state(self, platform: Platform, user_id: str) -> UserTzState | None:
        """Get user's timezone state.

        Args:
            platform: User's platform.
            user_id: User's platform-specific ID.

        Returns:
            UserTzState if found, None otherwise.
        """
        doc = await self.db.users.find_one({"platform": platform.value, "user_id": user_id})

        if doc is None:
            return None

        return self._doc_to_user_state(doc)

    async def upsert_user_tz_state(self, state: UserTzState) -> None:
        """Insert or update user's timezone state.

        Args:
            state: UserTzState to persist.
        """
        doc = {
            "platform": state.platform.value,
            "user_id": state.user_id,
            "tz_iana": state.tz_iana,
            "confidence": state.confidence,
            "source": state.source.value,
            "updated_at": state.updated_at,
        }

        if state.last_verified_at:
            doc["last_verified_at"] = state.last_verified_at

        await self.db.users.update_one(
            {"platform": state.platform.value, "user_id": state.user_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": state.created_at},
            },
            upsert=True,
        )

    def _doc_to_user_state(self, doc: dict[str, Any]) -> UserTzState:
        """Convert MongoDB document to UserTzState."""
        from src.core.models import TimezoneSource

        return UserTzState(
            platform=Platform(doc["platform"]),
            user_id=doc["user_id"],
            tz_iana=doc.get("tz_iana"),
            confidence=doc.get("confidence", 0.0),
            source=TimezoneSource(doc.get("source", "default")),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
            last_verified_at=doc.get("last_verified_at"),
        )

    # Chat state operations

    async def get_chat_state(self, platform: Platform, chat_id: str) -> ChatState | None:
        """Get chat state.

        Args:
            platform: Chat platform.
            chat_id: Chat identifier.

        Returns:
            ChatState if found, None otherwise.
        """
        doc = await self.db.chats.find_one({"platform": platform.value, "chat_id": chat_id})

        if doc is None:
            return None

        return self._doc_to_chat_state(doc)

    async def upsert_chat_state(self, state: ChatState) -> None:
        """Insert or update chat state.

        Args:
            state: ChatState to persist.
        """
        doc = {
            "platform": state.platform.value,
            "chat_id": state.chat_id,
            "default_tz": state.default_tz,
            "user_timezones": state.user_timezones,
            "active_timezones": state.active_timezones,
            "updated_at": state.updated_at,
        }

        await self.db.chats.update_one(
            {"platform": state.platform.value, "chat_id": state.chat_id},
            {
                "$set": doc,
                "$setOnInsert": {"created_at": state.created_at},
            },
            upsert=True,
        )

    async def update_user_timezone_in_chat(
        self, platform: Platform, chat_id: str, user_id: str, tz_iana: str
    ) -> None:
        """Update a user's timezone in a chat and recompute active_timezones.

        This properly handles relocation: when user changes timezone,
        the old one is removed from active_timezones if no other users have it.

        Args:
            platform: Chat platform.
            chat_id: Chat identifier.
            user_id: User's platform-specific ID.
            tz_iana: IANA timezone to set.
        """
        now = datetime.utcnow()

        # First, ensure the chat document exists and set the user's timezone
        await self.db.chats.update_one(
            {"platform": platform.value, "chat_id": chat_id},
            {
                "$set": {
                    f"user_timezones.{user_id}": tz_iana,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "platform": platform.value,
                    "chat_id": chat_id,
                    "default_tz": None,
                    "created_at": now,
                },
            },
            upsert=True,
        )

        # Read back and recompute active_timezones from user_timezones values
        doc = await self.db.chats.find_one({"platform": platform.value, "chat_id": chat_id})
        if doc:
            user_timezones: dict[str, str] = doc.get("user_timezones", {})
            active_timezones = sorted(set(user_timezones.values()))

            await self.db.chats.update_one(
                {"platform": platform.value, "chat_id": chat_id},
                {"$set": {"active_timezones": active_timezones}},
            )

    async def add_timezone_to_chat(self, platform: Platform, chat_id: str, tz_iana: str) -> None:
        """Legacy method - adds timezone without user tracking.

        DEPRECATED: Use update_user_timezone_in_chat() instead for proper tracking.
        Kept for backward compatibility during migration.

        Args:
            platform: Chat platform.
            chat_id: Chat identifier.
            tz_iana: IANA timezone to add.
        """
        await self.db.chats.update_one(
            {"platform": platform.value, "chat_id": chat_id},
            {
                "$addToSet": {"active_timezones": tz_iana},
                "$set": {"updated_at": datetime.utcnow()},
                "$setOnInsert": {
                    "platform": platform.value,
                    "chat_id": chat_id,
                    "default_tz": None,
                    "user_timezones": {},
                    "created_at": datetime.utcnow(),
                },
            },
            upsert=True,
        )

    def _doc_to_chat_state(self, doc: dict[str, Any]) -> ChatState:
        """Convert MongoDB document to ChatState."""
        return ChatState(
            platform=Platform(doc["platform"]),
            chat_id=doc["chat_id"],
            default_tz=doc.get("default_tz"),
            user_timezones=doc.get("user_timezones", {}),
            active_timezones=doc.get("active_timezones", []),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    # Deduplication operations

    async def check_dedupe_event(self, platform: Platform, event_id: str) -> bool:
        """Check if an event has been processed.

        Args:
            platform: Event platform.
            event_id: Unique event identifier.

        Returns:
            True if event exists (was processed).
        """
        doc = await self.db.dedupe_events.find_one(
            {"platform": platform.value, "event_id": event_id}
        )
        return doc is not None

    async def insert_dedupe_event(self, event: DedupeEvent) -> bool:
        """Insert a dedupe event record.

        Args:
            event: DedupeEvent to insert.

        Returns:
            True if inserted, False if duplicate.
        """
        try:
            await self.db.dedupe_events.insert_one(
                {
                    "platform": event.platform.value,
                    "event_id": event.event_id,
                    "chat_id": event.chat_id,
                    "created_at": event.created_at,
                }
            )
            return True
        except DuplicateKeyError:
            return False

    # Session operations (agent mode)

    async def get_active_session(
        self, platform: Platform, chat_id: str, user_id: str
    ) -> Session | None:
        """Get active session for user in chat.

        Args:
            platform: User's platform.
            chat_id: Chat identifier.
            user_id: User's platform-specific ID.

        Returns:
            Session if active session exists, None otherwise.
        """
        doc = await self.db.sessions.find_one(
            {
                "platform": platform.value,
                "chat_id": chat_id,
                "user_id": user_id,
                "status": SessionStatus.ACTIVE.value,
            }
        )

        if doc is None:
            return None

        return self._doc_to_session(doc)

    async def create_session(self, session: Session) -> None:
        """Create a new session.

        Args:
            session: Session to create.
        """
        await self.db.sessions.insert_one(
            {
                "session_id": session.session_id,
                "platform": session.platform.value,
                "chat_id": session.chat_id,
                "user_id": session.user_id,
                "goal": session.goal.value,
                "status": session.status.value,
                "context": session.context,
                "bot_message_id": session.bot_message_id,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "expires_at": session.expires_at,
            }
        )

    async def update_session(self, session: Session) -> None:
        """Update an existing session.

        Args:
            session: Session with updated fields.
        """
        await self.db.sessions.update_one(
            {"session_id": session.session_id},
            {
                "$set": {
                    "status": session.status.value,
                    "context": session.context,
                    "bot_message_id": session.bot_message_id,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    async def close_session(self, session_id: str, status: SessionStatus) -> None:
        """Close a session with given status.

        Args:
            session_id: Session identifier.
            status: Final status (COMPLETED, FAILED, EXPIRED).
        """
        await self.db.sessions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "status": status.value,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    def _doc_to_session(self, doc: dict[str, Any]) -> Session:
        """Convert MongoDB document to Session."""
        from src.core.models import SessionGoal

        return Session(
            session_id=doc["session_id"],
            platform=Platform(doc["platform"]),
            chat_id=doc["chat_id"],
            user_id=doc["user_id"],
            goal=SessionGoal(doc["goal"]),
            status=SessionStatus(doc["status"]),
            context=doc.get("context", {"attempts": 0, "history": []}),
            bot_message_id=doc.get("bot_message_id"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
            expires_at=doc["expires_at"],
        )


# Global storage instance
_storage: MongoStorage | None = None


def get_storage() -> MongoStorage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = MongoStorage()
    return _storage


def reset_storage() -> None:
    """Reset the global storage instance (useful for testing)."""
    global _storage
    _storage = None
