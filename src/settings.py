"""Settings module for Team Ops Assistant.

Loads configuration from environment variables (.env) and configuration.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file from repository root
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


class CityConfig(BaseModel):
    """City configuration for timezone selection."""

    name: str
    tz: str


class TimezoneConfig(BaseModel):
    """Timezone configuration."""

    default: str = "UTC"
    team_timezones: list[str] = Field(default_factory=list)
    team_cities: list[CityConfig] = Field(default_factory=list)


class ConfidenceConfig(BaseModel):
    """Confidence threshold configuration.

    Confidence values represent certainty about timezone source:
    - 1.0: Web-verified (user explicitly confirmed)
    - 0.9: Explicit in message (e.g., "3pm PST")
    - 0.85: City picker selection
    - 0.7: Threshold for requiring verification
    - 0.6: Inferred from context
    - 0.5: Chat default (fallback)
    """

    threshold: float = 0.7  # Below this, prompt for verification
    verified: float = 1.0  # Web-verified timezone
    city_pick: float = 1.0  # User selected from city picker (explicit action = full confidence)
    message_explicit: float = 0.9  # Timezone explicit in message (e.g., "PST")
    inferred: float = 0.6  # Inferred from user history
    chat_default: float = 0.5  # Chat-level default timezone
    decay_per_day: float = 0.01  # Confidence decay for stale data
    relocation_reset: float = 0.0  # Reset confidence when relocation detected


class TimeParsingConfidenceConfig(BaseModel):
    """Confidence values for different time parsing patterns."""

    hhmm_ampm: float = 0.95
    european_hhmm: float = 0.9
    military: float = 0.9
    plain_hhmm: float = 0.95
    h_ampm: float = 0.9
    range: float = 0.85
    at_h: float = 0.7


class TimeParsingConfig(BaseModel):
    """Time parsing configuration."""

    confidence: TimeParsingConfidenceConfig = Field(default_factory=TimeParsingConfidenceConfig)


class DedupeConfig(BaseModel):
    """Deduplication configuration."""

    ttl_seconds: int = 604800  # 7 days
    throttle_seconds: int = 2
    cache_cleanup_multiplier: int = (
        10  # Retention cutoff: entries older than throttle_seconds * multiplier are removed
    )


class RateLimitConfig(BaseModel):
    """Rate limit configuration for a single limit type."""

    requests: int = 20
    window_seconds: int = 60


class RateLimitsConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = True
    per_user: RateLimitConfig = Field(default_factory=RateLimitConfig)
    per_chat: RateLimitConfig = Field(default_factory=RateLimitConfig)
    max_notifications: int = 3  # Notify user N times about rate limit, then be silent


class TfidfConfig(BaseModel):
    """TF-IDF vectorizer configuration."""

    ngram_range: list[int] = Field(default_factory=lambda: [1, 3])
    min_df: int = 2
    max_df: float = 0.95


class LogisticRegressionConfig(BaseModel):
    """Logistic regression configuration."""

    max_iter: int = 1000
    random_state: int = 42


class ClassifierConfig(BaseModel):
    """ML classifier configuration."""

    # Probability thresholds for time detection
    low_threshold: float = 0.40
    high_threshold: float = 0.60
    # Text processing parameters
    long_text_threshold: int = 100
    window_size: int = 5
    # ML model parameters
    tfidf: TfidfConfig = Field(default_factory=TfidfConfig)
    logistic_regression: LogisticRegressionConfig = Field(default_factory=LogisticRegressionConfig)


class LLMOperationConfig(BaseModel):
    """LLM operation-specific configuration."""

    max_tokens: int = 150
    temperature: float = 0.1
    timeout: float = 10.0


class LLMExtractionConfig(BaseModel):
    """LLM extraction-specific configuration."""

    max_tokens: int = 500
    temperature: float = 0.1
    timeout: float = 9.0
    default_confidence: float = 0.8  # Default confidence for LLM-extracted times


class LLMAgentConfig(BaseModel):
    """LLM agent-specific configuration (timezone resolution)."""

    temperature: float = 0.3
    timeout: float = 15.0


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration for LLM API calls."""

    failure_threshold: int = 3  # Open after N consecutive failures
    reset_timeout_seconds: float = 60.0  # Try again after this period
    enabled: bool = True


class LLMConfig(BaseModel):
    """LLM configuration."""

    # Default must match configuration.yaml - single source of truth is YAML
    model: str = "qwen/qwen3-next-80b-a3b-instruct"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    fallback_only: bool = True
    detection: LLMOperationConfig = Field(default_factory=LLMOperationConfig)
    extraction: LLMExtractionConfig = Field(default_factory=LLMExtractionConfig)
    # Sync bridge wraps async LLM calls - outer timeout for total latency control
    sync_bridge_timeout: float = 10.0
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    agent: LLMAgentConfig = Field(default_factory=LLMAgentConfig)


class HttpTimeoutsConfig(BaseModel):
    """HTTP client timeouts configuration."""

    telegram_api: float = 30.0
    discord_api: float = 30.0
    whatsapp_api: float = 30.0


class HttpConfig(BaseModel):
    """HTTP configuration."""

    timeouts: HttpTimeoutsConfig = Field(default_factory=HttpTimeoutsConfig)


class UiConfig(BaseModel):
    """UI configuration."""

    max_cities_shown: int = 4
    verification_token_hours: int = 24


class PollingConfig(BaseModel):
    """Telegram polling configuration for local development."""

    backoff_seconds: int = 5  # Sleep on errors
    long_polling_timeout: int = 30  # Long polling timeout
    client_timeout: float = 60.0  # HTTP client timeout


class TunnelConfig(BaseModel):
    """Ngrok tunnel configuration for local development."""

    default_port: int = 8000


class TriggersConfig(BaseModel):
    """Trigger detection configuration."""

    relocation_confidence: float = 0.9  # Confidence for explicit relocation phrases
    city_detection_confidence: float = 0.7  # Confidence for city name detection fallback


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class DatabaseConfig(BaseModel):
    """Database configuration."""

    name: str = "team_ops"


class AppConfig(BaseModel):
    """Application metadata configuration."""

    name: str = "Team Ops Assistant"
    version: str = "0.1.0"


class Configuration(BaseModel):
    """Full configuration model."""

    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    timezone: TimezoneConfig = Field(default_factory=TimezoneConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    time_parsing: TimeParsingConfig = Field(default_factory=TimeParsingConfig)
    dedupe: DedupeConfig = Field(default_factory=DedupeConfig)
    rate_limits: RateLimitsConfig = Field(default_factory=RateLimitsConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    tunnel: TunnelConfig = Field(default_factory=TunnelConfig)
    triggers: TriggersConfig = Field(default_factory=TriggersConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class Settings:
    """Application settings loaded from environment and configuration file."""

    def __init__(self) -> None:
        """Initialize settings from environment and configuration file."""
        # Environment variables
        self.mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.discord_bot_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
        self.slack_bot_token: str = os.getenv("SLACK_BOT_TOKEN", "")
        self.whatsapp_access_token: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.whatsapp_verify_token: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        self.whatsapp_app_secret: str = os.getenv("WHATSAPP_APP_SECRET", "")

        # Webhook signature verification secrets
        self.telegram_webhook_secret: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
        self.slack_signing_secret: str = os.getenv("SLACK_SIGNING_SECRET", "")
        self.together_api_key: str = os.getenv("TOGETHER_API_KEY", "")
        self.nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
        self.app_secret_key: str = os.getenv("APP_SECRET_KEY", "dev-secret-key")
        self.app_host: str = os.getenv("APP_HOST", "0.0.0.0")
        self.app_port: int = int(os.getenv("APP_PORT", "8000"))
        self.app_debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
        # Public URL for verification links (defaults to localhost for dev)
        self.app_base_url: str = os.getenv("APP_BASE_URL", f"http://localhost:{self.app_port}")
        self.verify_token_secret: str = os.getenv("VERIFY_TOKEN_SECRET", "dev-verify-secret")

        # Load configuration from YAML
        self.config = self._load_configuration()

        # Setup logging
        self._setup_logging()

    def _load_configuration(self) -> Configuration:
        """Load configuration from YAML file."""
        config_path = ROOT_DIR / "configuration.yaml"

        if config_path.exists():
            with config_path.open(encoding="utf-8") as f:
                raw_config: dict[str, Any] = yaml.safe_load(f) or {}
            return Configuration.model_validate(raw_config)

        return Configuration()

    def _setup_logging(self) -> None:
        """Configure logging based on settings."""
        from src.core.logging_config import configure_logging

        configure_logging(level=self.config.logging.level)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the global settings instance (useful for testing)."""
    global _settings
    _settings = None
