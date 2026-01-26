"""Core domain models for Team Ops Assistant.

Platform-agnostic data structures used across all connectors.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

# Generic type for StateResult
T = TypeVar("T")


class Platform(str, Enum):
    """Supported messaging platforms."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    SLACK = "slack"


class NormalizedEvent(BaseModel, frozen=True):
    """Platform-agnostic representation of an incoming message event.

    All platform connectors normalize their inbound payloads to this format.
    Frozen: immutable after creation - prevents accidental mutation.
    """

    platform: Platform
    event_id: str = Field(description="Unique event ID for deduplication")
    message_id: str | None = Field(
        default=None, description="Platform message ID for reply_to functionality"
    )
    chat_id: str = Field(description="Chat/channel/group ID")
    user_id: str = Field(description="User/author ID")
    username: str | None = Field(default=None, description="Username if available")
    display_name: str | None = Field(default=None, description="Display name if available")
    text: str = Field(description="Message text content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reply_to_message_id: str | None = Field(
        default=None, description="ID of message being replied to"
    )
    raw_payload: dict | None = Field(
        default=None, description="Original platform payload for debugging"
    )


class OutboundMessage(BaseModel, frozen=True):
    """Platform-agnostic representation of an outgoing message.

    The core handler returns these, and platform outbound adapters convert them.
    Frozen: immutable after creation.
    """

    platform: Platform
    chat_id: str
    text: str
    reply_to_message_id: str | None = None
    parse_mode: Literal["plain", "markdown", "html"] = "plain"


class ParsedTime(BaseModel, frozen=True):
    """A time reference extracted from message text. Frozen: immutable."""

    original_text: str = Field(description="The original time string from the message")
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    timezone_hint: str | None = Field(
        default=None, description="Timezone mentioned in message (e.g., 'PST', 'Tokyo')"
    )
    is_tomorrow: bool = Field(default=False, description="Whether the time is for tomorrow")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Parsing confidence")


class TimezoneSource(str, Enum):
    """How a user's timezone was determined."""

    WEB_VERIFIED = "web_verified"  # User verified via web flow
    CITY_PICK = "city_pick"  # User selected a city
    MESSAGE_EXPLICIT = "message_explicit"  # User stated timezone in message
    INFERRED = "inferred"  # Inferred from context
    DEFAULT = "default"  # Fallback to default


class UserTzState(BaseModel):
    """User timezone state stored in MongoDB.

    Indexed by (platform, user_id).
    """

    platform: Platform
    user_id: str
    tz_iana: str | None = Field(default=None, description="IANA timezone identifier")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: TimezoneSource = TimezoneSource.DEFAULT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_verified_at: datetime | None = None


class ChatState(BaseModel):
    """Chat/channel state stored in MongoDB.

    Indexed by (platform, chat_id).
    """

    platform: Platform
    chat_id: str
    default_tz: str | None = Field(default=None, description="Default timezone for this chat")
    user_timezones: dict[str, str] = Field(
        default_factory=dict, description="Map of user_id → tz_iana for tracking"
    )
    active_timezones: list[str] = Field(
        default_factory=list, description="Computed from user_timezones values (unique)"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DedupeEvent(BaseModel, frozen=True):
    """Deduplication record stored in MongoDB.

    Indexed by (platform, event_id) with TTL on created_at. Frozen.
    """

    platform: Platform
    event_id: str
    chat_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HandlerResult(BaseModel):
    """Result from the core message handler."""

    should_respond: bool = True
    messages: list[OutboundMessage] = Field(default_factory=list)
    ask_timezone: bool = False
    verify_url: str | None = None


class VerifyToken(BaseModel, frozen=True):
    """Token for timezone verification flow. Frozen."""

    platform: Platform
    user_id: str
    chat_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime


# ============================================================================
# Session Models (Agent Mode)
# ============================================================================


class SessionStatus(str, Enum):
    """Status of an agent session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class SessionGoal(str, Enum):
    """Goal/purpose of an agent session."""

    AWAITING_TIMEZONE = "awaiting_timezone"  # First-time timezone onboarding
    REVERIFY_TIMEZONE = "reverify_timezone"  # Re-verify after confidence decay
    CONFIRM_RELOCATION = "confirm_relocation"  # Confirm detected relocation (simple yes/no)
    HELP_REQUEST = "help_request"  # User asked for help/info about the bot


class Session(BaseModel):
    """Agent session for multi-turn conversations.

    When the bot needs to collect information (e.g., timezone),
    it creates a session. All subsequent messages from the user
    are routed to the agent handler until the session is closed.

    Indexed by (platform, chat_id, user_id) with TTL on expires_at.
    """

    session_id: str = Field(description="Unique session identifier")
    platform: Platform
    chat_id: str
    user_id: str

    goal: SessionGoal
    status: SessionStatus = SessionStatus.ACTIVE

    # Context for the agent
    context: dict[str, Any] = Field(
        default_factory=lambda: {"attempts": 0, "history": []},
        description="Session context: original_text, parsed_time, attempts, history",
    )

    # For reply detection (optional)
    bot_message_id: str | None = Field(
        default=None, description="ID of bot's last message for reply detection"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(description="Session expiration time (TTL)")


# ============================================================================
# Extensible Architecture Models
# ============================================================================


class DetectedTrigger(BaseModel, frozen=True):
    """A trigger detected in the message.

    Generic container for any type of trigger (time, date, question, etc.).
    """

    trigger_type: str = Field(description="Type of trigger detected (e.g., 'time', 'date')")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Trigger-specific data (varies by type)"
    )
    original_text: str = Field(default="", description="Original text that triggered detection")


class StateResult(BaseModel, Generic[T]):
    """Result from a StateManager.get_state() call.

    Generic container for state with confidence and source information.
    """

    value: T | None = Field(description="The state value, or None if unknown")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence in this value")
    source: str = Field(default="unknown", description="Where this value came from")


class ResolvedContext(BaseModel, frozen=True):
    """Context resolved for handling a trigger.

    Contains all information needed by ActionHandlers to process a trigger.
    """

    platform: Platform
    chat_id: str
    user_id: str
    source_timezone: str | None = Field(
        default=None, description="User's timezone for the time reference"
    )
    target_timezones: list[str] = Field(default_factory=list, description="Timezones to convert to")
    reply_to_message_id: str | None = None


class PipelineResult(BaseModel):
    """Result from Pipeline.process() call."""

    messages: list[OutboundMessage] = Field(default_factory=list)
    triggers_detected: int = Field(default=0)
    triggers_handled: int = Field(default=0)
    errors: list[str] = Field(default_factory=list)

    # State collection signaling
    needs_state_collection: bool = Field(
        default=False, description="True if user state needs to be collected"
    )
    state_collection_trigger: DetectedTrigger | None = Field(
        default=None, description="Trigger that requires state collection"
    )
