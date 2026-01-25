"""Tests for webhook signature verification.

Tests signature verification for Telegram, Slack, and WhatsApp webhooks.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest


class TestTelegramSignatureVerification:
    """Tests for Telegram webhook secret token verification."""

    def test_verify_valid_secret(self) -> None:
        """Valid secret token should return True."""
        from src.app import verify_telegram_signature

        result = verify_telegram_signature("my-secret-token", "my-secret-token")
        assert result is True

    def test_verify_invalid_secret(self) -> None:
        """Invalid secret token should return False."""
        from src.app import verify_telegram_signature

        result = verify_telegram_signature("wrong-token", "my-secret-token")
        assert result is False

    def test_verify_empty_expected_skips_verification(self) -> None:
        """Empty expected secret should skip verification (backwards compatible)."""
        from src.app import verify_telegram_signature

        result = verify_telegram_signature("any-value", "")
        assert result is True

    def test_verify_empty_header_with_expected_fails(self) -> None:
        """Empty header with expected secret should fail."""
        from src.app import verify_telegram_signature

        result = verify_telegram_signature("", "my-secret-token")
        assert result is False


class TestSlackSignatureVerification:
    """Tests for Slack request signature verification."""

    def _compute_slack_signature(self, body: bytes, timestamp: str, secret: str) -> str:
        """Helper to compute valid Slack signature."""
        base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
        return "v0=" + hmac.new(
            secret.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def test_verify_valid_signature(self) -> None:
        """Valid signature should return True."""
        from src.app import verify_slack_signature

        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))
        secret = "test-signing-secret"
        signature = self._compute_slack_signature(body, timestamp, secret)

        result = verify_slack_signature(body, timestamp, signature, secret)
        assert result is True

    def test_verify_invalid_signature(self) -> None:
        """Invalid signature should return False."""
        from src.app import verify_slack_signature

        body = b'{"event": "test"}'
        timestamp = str(int(time.time()))
        secret = "test-signing-secret"

        result = verify_slack_signature(body, timestamp, "v0=invalid", secret)
        assert result is False

    def test_verify_empty_secret_skips_verification(self) -> None:
        """Empty signing secret should skip verification (backwards compatible)."""
        from src.app import verify_slack_signature

        result = verify_slack_signature(b"any", "123456", "v0=any", "")
        assert result is True

    def test_verify_old_timestamp_fails(self) -> None:
        """Timestamp older than 5 minutes should fail."""
        from src.app import verify_slack_signature

        body = b'{"event": "test"}'
        old_timestamp = str(int(time.time()) - 400)  # 6+ minutes ago
        secret = "test-signing-secret"
        signature = self._compute_slack_signature(body, old_timestamp, secret)

        result = verify_slack_signature(body, old_timestamp, signature, secret)
        assert result is False

    def test_verify_future_timestamp_fails(self) -> None:
        """Timestamp too far in the future should fail."""
        from src.app import verify_slack_signature

        body = b'{"event": "test"}'
        future_timestamp = str(int(time.time()) + 400)  # 6+ minutes in future
        secret = "test-signing-secret"
        signature = self._compute_slack_signature(body, future_timestamp, secret)

        result = verify_slack_signature(body, future_timestamp, signature, secret)
        assert result is False

    def test_verify_invalid_timestamp_format_fails(self) -> None:
        """Invalid timestamp format should fail."""
        from src.app import verify_slack_signature

        result = verify_slack_signature(b"body", "not-a-number", "v0=sig", "secret")
        assert result is False

    def test_verify_tampered_body_fails(self) -> None:
        """Tampered body should fail verification."""
        from src.app import verify_slack_signature

        body = b'{"event": "original"}'
        timestamp = str(int(time.time()))
        secret = "test-signing-secret"
        signature = self._compute_slack_signature(body, timestamp, secret)

        # Tamper with body
        tampered_body = b'{"event": "tampered"}'
        result = verify_slack_signature(tampered_body, timestamp, signature, secret)
        assert result is False


class TestWhatsAppSignatureVerification:
    """Tests for WhatsApp webhook signature verification."""

    def _compute_whatsapp_signature(self, body: bytes, secret: str) -> str:
        """Helper to compute valid WhatsApp signature."""
        return "sha256=" + hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

    def test_verify_valid_signature(self) -> None:
        """Valid signature should return True."""
        from src.app import verify_whatsapp_signature

        body = b'{"entry": []}'
        secret = "test-app-secret"
        signature = self._compute_whatsapp_signature(body, secret)

        result = verify_whatsapp_signature(body, signature, secret)
        assert result is True

    def test_verify_invalid_signature(self) -> None:
        """Invalid signature should return False."""
        from src.app import verify_whatsapp_signature

        result = verify_whatsapp_signature(b"body", "sha256=invalid", "secret")
        assert result is False

    def test_verify_empty_secret_skips_verification(self) -> None:
        """Empty app secret should skip verification (backwards compatible)."""
        from src.app import verify_whatsapp_signature

        result = verify_whatsapp_signature(b"any", "sha256=any", "")
        assert result is True

    def test_verify_tampered_body_fails(self) -> None:
        """Tampered body should fail verification."""
        from src.app import verify_whatsapp_signature

        body = b'{"entry": "original"}'
        secret = "test-app-secret"
        signature = self._compute_whatsapp_signature(body, secret)

        # Tamper with body
        tampered_body = b'{"entry": "tampered"}'
        result = verify_whatsapp_signature(tampered_body, signature, secret)
        assert result is False

    def test_verify_missing_prefix_fails(self) -> None:
        """Missing sha256= prefix should fail."""
        from src.app import verify_whatsapp_signature

        body = b'{"entry": []}'
        secret = "test-app-secret"
        # Compute signature without prefix
        raw_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        result = verify_whatsapp_signature(body, raw_sig, secret)
        assert result is False


class TestWebhookEndpointVerification:
    """Integration tests for webhook endpoints with signature verification."""

    @pytest.fixture
    def mock_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Mock settings with verification secrets."""
        from src import settings

        class MockSettings:
            telegram_webhook_secret = "test-telegram-secret"
            slack_signing_secret = "test-slack-secret"
            whatsapp_app_secret = "test-whatsapp-secret"
            whatsapp_verify_token = "test-verify-token"
            app_secret_key = "test-app-secret"

            class config:
                class database:
                    name = "test"

                class dedupe:
                    ttl_seconds = 604800
                    throttle_seconds = 2
                    cache_cleanup_multiplier = 10

                class llm:
                    base_url = "https://test.api.com"
                    model = "test"

                    class detection:
                        max_tokens = 100
                        temperature = 0.1
                        timeout = 10.0

                class logging:
                    level = "INFO"
                    format = "%(message)s"

        monkeypatch.setattr(settings, "_settings", MockSettings())

    @pytest.mark.asyncio
    async def test_telegram_webhook_rejects_invalid_secret(
        self, mock_settings: None
    ) -> None:
        """Telegram webhook should reject requests with invalid secret."""
        _ = mock_settings  # Fixture used for side effects
        from unittest.mock import AsyncMock, patch

        with (
            patch("src.app.get_storage") as mock_storage,
            patch("src.app.create_orchestrator") as mock_create,
        ):
            mock_storage.return_value = AsyncMock()
            mock_create.return_value = (AsyncMock(), AsyncMock())

            from src.app import create_app

            app = create_app()

            async with app.test_client() as client:
                response = await client.post(
                    "/hooks/telegram",
                    json={"message": {}},
                    headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
                )

                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_slack_webhook_rejects_invalid_signature(
        self, mock_settings: None
    ) -> None:
        """Slack webhook should reject requests with invalid signature."""
        _ = mock_settings  # Fixture used for side effects
        from unittest.mock import AsyncMock, patch

        with (
            patch("src.app.get_storage") as mock_storage,
            patch("src.app.create_orchestrator") as mock_create,
        ):
            mock_storage.return_value = AsyncMock()
            mock_create.return_value = (AsyncMock(), AsyncMock())

            from src.app import create_app

            app = create_app()

            async with app.test_client() as client:
                response = await client.post(
                    "/hooks/slack",
                    json={"event": {}},
                    headers={
                        "X-Slack-Request-Timestamp": str(int(time.time())),
                        "X-Slack-Signature": "v0=invalid",
                    },
                )

                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_whatsapp_webhook_rejects_invalid_signature(
        self, mock_settings: None
    ) -> None:
        """WhatsApp webhook should reject requests with invalid signature."""
        _ = mock_settings  # Fixture used for side effects
        from unittest.mock import AsyncMock, patch

        with (
            patch("src.app.get_storage") as mock_storage,
            patch("src.app.create_orchestrator") as mock_create,
        ):
            mock_storage.return_value = AsyncMock()
            mock_create.return_value = (AsyncMock(), AsyncMock())

            from src.app import create_app

            app = create_app()

            async with app.test_client() as client:
                response = await client.post(
                    "/hooks/whatsapp",
                    json={"entry": []},
                    headers={"X-Hub-Signature-256": "sha256=invalid"},
                )

                assert response.status_code == 401
