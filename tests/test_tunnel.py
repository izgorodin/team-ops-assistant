"""Tests for ngrok tunnel manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pyngrok.exception import PyngrokNgrokError

from src.connectors.telegram.tunnel import NgrokTunnelError, TunnelManager


class TestTunnelManager:
    """Tests for TunnelManager class."""

    def test_check_authtoken_present(self) -> None:
        """Test authtoken detection when present."""
        tunnel = TunnelManager()
        mock_config = MagicMock()
        mock_config.auth_token = "test_token"

        with patch("src.connectors.telegram.tunnel.conf.get_default", return_value=mock_config):
            assert tunnel._check_authtoken() is True

    def test_check_authtoken_missing(self) -> None:
        """Test authtoken detection when missing."""
        tunnel = TunnelManager()
        mock_config = MagicMock()
        mock_config.auth_token = None

        # Mock both pyngrok config and file system paths
        mock_path = MagicMock()
        mock_path.expanduser.return_value = mock_path
        mock_path.exists.return_value = False

        with (
            patch("src.connectors.telegram.tunnel.conf.get_default", return_value=mock_config),
            patch("pathlib.Path", return_value=mock_path),
        ):
            assert tunnel._check_authtoken() is False

    def test_start_tunnel_success(self) -> None:
        """Test successful tunnel start."""
        tunnel = TunnelManager()

        mock_tunnel = MagicMock()
        mock_tunnel.public_url = "https://abc123.ngrok.io"

        with (
            patch.object(tunnel, "_check_authtoken", return_value=True),
            patch("src.connectors.telegram.tunnel.ngrok.connect", return_value=mock_tunnel),
        ):
            url = tunnel.start_tunnel()
            assert url == "https://abc123.ngrok.io"

    def test_start_tunnel_upgrades_http_to_https(self) -> None:
        """Test that HTTP URLs are upgraded to HTTPS."""
        tunnel = TunnelManager()

        mock_tunnel = MagicMock()
        mock_tunnel.public_url = "http://abc123.ngrok.io"

        with (
            patch.object(tunnel, "_check_authtoken", return_value=True),
            patch("src.connectors.telegram.tunnel.ngrok.connect", return_value=mock_tunnel),
        ):
            url = tunnel.start_tunnel()
            assert url == "https://abc123.ngrok.io"

    def test_start_tunnel_no_authtoken_cancelled(self) -> None:
        """Test tunnel start fails when authtoken prompt is cancelled."""
        tunnel = TunnelManager()

        with (
            patch.object(tunnel, "_check_authtoken", return_value=False),
            patch.object(tunnel, "_prompt_authtoken", return_value=False),
        ):
            with pytest.raises(NgrokTunnelError) as exc_info:
                tunnel.start_tunnel()
            assert "authtoken required" in str(exc_info.value)

    def test_start_tunnel_pyngrok_error(self) -> None:
        """Test tunnel start handles pyngrok errors."""
        tunnel = TunnelManager()

        with (
            patch.object(tunnel, "_check_authtoken", return_value=True),
            patch(
                "src.connectors.telegram.tunnel.ngrok.connect",
                side_effect=PyngrokNgrokError("Connection failed"),
            ),
        ):
            with pytest.raises(NgrokTunnelError) as exc_info:
                tunnel.start_tunnel()
            assert "Connection failed" in str(exc_info.value)

    def test_start_tunnel_authtoken_error(self) -> None:
        """Test tunnel start handles invalid authtoken."""
        tunnel = TunnelManager()

        with (
            patch.object(tunnel, "_check_authtoken", return_value=True),
            patch(
                "src.connectors.telegram.tunnel.ngrok.connect",
                side_effect=PyngrokNgrokError("Invalid authtoken"),
            ),
        ):
            with pytest.raises(NgrokTunnelError) as exc_info:
                tunnel.start_tunnel()
            assert "authtoken" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_set_webhook_success(self) -> None:
        """Test successful webhook configuration."""
        tunnel = TunnelManager()

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        tunnel._http_client = mock_client

        result = await tunnel.set_webhook("https://abc123.ngrok.io")
        assert result is True

        # Verify correct URL was called
        call_args = mock_client.post.call_args
        assert "/hooks/telegram" in str(call_args)

    @pytest.mark.asyncio
    async def test_set_webhook_failure(self) -> None:
        """Test webhook configuration failure."""
        tunnel = TunnelManager()

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False, "description": "Bad token"}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        tunnel._http_client = mock_client

        result = await tunnel.set_webhook("https://abc123.ngrok.io")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_current_webhook(self) -> None:
        """Test getting current webhook URL."""
        tunnel = TunnelManager()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"url": "https://example.com/hooks/telegram"},
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        tunnel._http_client = mock_client

        url = await tunnel.get_current_webhook()
        assert url == "https://example.com/hooks/telegram"

    @pytest.mark.asyncio
    async def test_get_current_webhook_none(self) -> None:
        """Test getting current webhook when none set."""
        tunnel = TunnelManager()

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": {"url": ""}}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        tunnel._http_client = mock_client

        url = await tunnel.get_current_webhook()
        assert url is None

    def test_stop_tunnel_disconnects(self) -> None:
        """Test that stop_tunnel disconnects ngrok."""
        tunnel = TunnelManager()
        tunnel._public_url = "https://abc123.ngrok.io"

        with patch("src.connectors.telegram.tunnel.ngrok.disconnect") as mock_disconnect:
            tunnel.stop_tunnel()
            mock_disconnect.assert_called_once_with("https://abc123.ngrok.io")
            assert tunnel._public_url is None

    @pytest.mark.asyncio
    async def test_stop_closes_client(self) -> None:
        """Test that stop closes HTTP client."""
        tunnel = TunnelManager()
        tunnel._public_url = "https://abc123.ngrok.io"

        mock_client = AsyncMock()
        tunnel._http_client = mock_client

        with patch("src.connectors.telegram.tunnel.ngrok.disconnect"):
            await tunnel.stop()

        mock_client.aclose.assert_called_once()
        assert tunnel._http_client is None

    def test_prompt_authtoken_success(self) -> None:
        """Test successful authtoken prompt."""
        tunnel = TunnelManager()

        with (
            patch("builtins.input", return_value="test_token_123"),
            patch("src.connectors.telegram.tunnel.ngrok.set_auth_token") as mock_set,
        ):
            result = tunnel._prompt_authtoken()
            assert result is True
            mock_set.assert_called_once_with("test_token_123")

    def test_prompt_authtoken_cancelled(self) -> None:
        """Test cancelled authtoken prompt."""
        tunnel = TunnelManager()

        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = tunnel._prompt_authtoken()
            assert result is False

    def test_prompt_authtoken_empty(self) -> None:
        """Test empty authtoken prompt."""
        tunnel = TunnelManager()

        with patch("builtins.input", return_value=""):
            result = tunnel._prompt_authtoken()
            assert result is False
