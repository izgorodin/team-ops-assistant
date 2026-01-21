"""Tests for settings module."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.settings import (
    Configuration,
    Settings,
    get_settings,
    reset_settings,
)


@pytest.fixture(autouse=True)
def reset_settings_fixture() -> None:
    """Reset settings before each test."""
    reset_settings()


class TestConfiguration:
    """Tests for Configuration model."""

    def test_default_configuration(self) -> None:
        """Test that Configuration has sensible defaults."""
        config = Configuration()

        assert config.app.name == "Team Ops Assistant"
        assert config.database.name == "team_ops"
        assert config.timezone.default == "UTC"
        assert config.confidence.threshold == 0.7
        assert config.dedupe.ttl_seconds == 604800

    def test_configuration_from_dict(self) -> None:
        """Test Configuration.model_validate with partial data."""
        data = {
            "app": {"name": "Custom Name"},
            "timezone": {"default": "Europe/London"},
        }
        config = Configuration.model_validate(data)

        assert config.app.name == "Custom Name"
        assert config.timezone.default == "Europe/London"
        # Other defaults should still apply
        assert config.database.name == "team_ops"


class TestSettings:
    """Tests for Settings class."""

    def test_settings_loads_env_vars(self) -> None:
        """Test that Settings loads environment variables."""
        with patch.dict(
            os.environ,
            {
                "MONGODB_URI": "mongodb://test:27017",
                "TELEGRAM_BOT_TOKEN": "test-token",
                "APP_PORT": "9000",
            },
        ):
            settings = Settings()

            assert settings.mongodb_uri == "mongodb://test:27017"
            assert settings.telegram_bot_token == "test-token"
            assert settings.app_port == 9000

    def test_settings_has_defaults(self) -> None:
        """Test that Settings has default values."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.app_host == "0.0.0.0"
            assert settings.app_port == 8000
            assert settings.app_debug is False

    def test_settings_loads_yaml_config(self) -> None:
        """Test that Settings loads configuration.yaml."""
        settings = Settings()

        # Should load from the actual configuration.yaml
        assert settings.config is not None
        assert isinstance(settings.config, Configuration)
        assert len(settings.config.timezone.team_timezones) > 0


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_returns_singleton(self) -> None:
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reset_settings_clears_singleton(self) -> None:
        """Test that reset_settings clears the singleton."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()

        # Should be different instances
        assert settings1 is not settings2
