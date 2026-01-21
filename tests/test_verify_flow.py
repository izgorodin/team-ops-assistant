"""Tests for timezone verification flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from quart import Quart

from src.core.models import Platform
from src.core.timezone_identity import (
    generate_verify_token,
    parse_verify_token,
)


class TestVerifyToken:
    """Tests for verification token generation and parsing."""

    def test_generate_and_parse_token(self) -> None:
        """Test that generated tokens can be parsed."""
        token = generate_verify_token(Platform.TELEGRAM, "user123", "chat456")

        parsed = parse_verify_token(token)

        assert parsed is not None
        assert parsed.platform == Platform.TELEGRAM
        assert parsed.user_id == "user123"
        assert parsed.chat_id == "chat456"

    def test_invalid_token_returns_none(self) -> None:
        """Test that invalid tokens return None."""
        assert parse_verify_token("invalid") is None
        assert parse_verify_token("a|b|c") is None
        assert parse_verify_token("") is None

    def test_tampered_token_returns_none(self) -> None:
        """Test that tampered tokens return None."""
        token = generate_verify_token(Platform.TELEGRAM, "user123", "chat456")

        # Tamper with the token
        parts = token.split("|")
        parts[1] = "hacker"  # Change user_id
        tampered = "|".join(parts)

        assert parse_verify_token(tampered) is None


class TestVerifyFlow:
    """Tests for the verification web flow."""

    @pytest.fixture
    def app(self) -> Quart:
        """Create test application."""
        from src.app import create_app

        return create_app()

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage."""
        storage = MagicMock()
        storage.connect = AsyncMock()
        storage.close = AsyncMock()
        storage.upsert_user_tz_state = AsyncMock()
        return storage

    @pytest.mark.asyncio
    async def test_verify_page_requires_token(self, app: Quart) -> None:
        """Test that verify page requires a token."""
        async with app.test_client() as client:
            response = await client.get("/verify")

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_page_rejects_invalid_token(self, app: Quart) -> None:
        """Test that verify page rejects invalid tokens."""
        async with app.test_client() as client:
            response = await client.get("/verify?token=invalid")

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_page_serves_html(self, app: Quart) -> None:
        """Test that verify page serves HTML with valid token."""
        token = generate_verify_token(Platform.TELEGRAM, "user1", "chat1")

        async with app.test_client() as client:
            response = await client.get(f"/verify?token={token}")

            assert response.status_code == 200
            html = await response.get_data(as_text=True)
            assert "Verify Your Timezone" in html

    @pytest.mark.asyncio
    async def test_api_verify_requires_body(self, app: Quart) -> None:
        """Test that API verify endpoint requires request body."""
        async with app.test_client() as client:
            response = await client.post(
                "/api/verify",
                headers={"Content-Type": "application/json"},
            )

            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_api_verify_requires_token(self, app: Quart) -> None:
        """Test that API verify endpoint requires token."""
        async with app.test_client() as client:
            response = await client.post(
                "/api/verify",
                json={"tz_iana": "America/Los_Angeles"},
            )

            assert response.status_code == 400
            data = await response.get_json()
            assert "token" in data.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_api_verify_requires_timezone(self, app: Quart) -> None:
        """Test that API verify endpoint requires timezone."""
        token = generate_verify_token(Platform.TELEGRAM, "user1", "chat1")

        async with app.test_client() as client:
            response = await client.post(
                "/api/verify",
                json={"token": token},
            )

            assert response.status_code == 400
            data = await response.get_json()
            assert "timezone" in data.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_api_verify_rejects_invalid_timezone(self, app: Quart) -> None:
        """Test that API verify endpoint rejects invalid timezones."""
        token = generate_verify_token(Platform.TELEGRAM, "user1", "chat1")

        async with app.test_client() as client:
            response = await client.post(
                "/api/verify",
                json={"token": token, "tz_iana": "Invalid/Timezone"},
            )

            assert response.status_code == 400
            data = await response.get_json()
            assert "invalid" in data.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_api_verify_success(self, app: Quart, mock_storage: MagicMock) -> None:
        """Test successful timezone verification."""
        token = generate_verify_token(Platform.TELEGRAM, "user1", "chat1")

        with patch("src.web.routes_verify.get_storage", return_value=mock_storage):
            async with app.test_client() as client:
                response = await client.post(
                    "/api/verify",
                    json={"token": token, "tz_iana": "America/Los_Angeles"},
                )

                assert response.status_code == 200
                data = await response.get_json()
                assert data["success"] is True
                assert data["timezone"] == "America/Los_Angeles"

                # Verify storage was called
                mock_storage.upsert_user_tz_state.assert_called_once()
