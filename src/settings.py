"""Settings module for Team Ops Assistant.

Loads configuration from environment variables (.env) and configuration.yaml.
"""

from __future__ import annotations

import logging
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
    """Confidence threshold configuration."""

    threshold: float = 0.7
    verified: float = 1.0
    city_pick: float = 0.85
    decay_per_day: float = 0.01


class DedupeConfig(BaseModel):
    """Deduplication configuration."""

    ttl_seconds: int = 604800  # 7 days
    throttle_seconds: int = 2


class ClassifierConfig(BaseModel):
    """ML classifier configuration."""

    # Probability thresholds for time detection
    # p > high_threshold → confident YES
    # p < low_threshold → confident NO
    # low_threshold ≤ p ≤ high_threshold → uncertain → LLM fallback
    low_threshold: float = 0.40
    high_threshold: float = 0.60


class LLMConfig(BaseModel):
    """LLM configuration."""

    model: str = "qwen/qwen3-next-80b-a3b-instruct"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    fallback_only: bool = True
    max_tokens: int = 256
    temperature: float = 0.3


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
    dedupe: DedupeConfig = Field(default_factory=DedupeConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class Settings:
    """Application settings loaded from environment and configuration file."""

    def __init__(self) -> None:
        """Initialize settings from environment and configuration file."""
        # Environment variables
        self.mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.discord_bot_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
        self.whatsapp_access_token: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.whatsapp_verify_token: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        self.together_api_key: str = os.getenv("TOGETHER_API_KEY", "")
        self.nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
        self.app_secret_key: str = os.getenv("APP_SECRET_KEY", "dev-secret-key")
        self.app_host: str = os.getenv("APP_HOST", "0.0.0.0")
        self.app_port: int = int(os.getenv("APP_PORT", "8000"))
        self.app_debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
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
        logging.basicConfig(
            level=getattr(logging, self.config.logging.level, logging.INFO),
            format=self.config.logging.format,
        )


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
