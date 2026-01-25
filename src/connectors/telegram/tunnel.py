"""Ngrok tunnel manager for local webhook testing.

Uses pyngrok to automatically manage ngrok installation and tunnels.

Usage:
    python -m src.app --tunnel
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx
from pyngrok import conf, ngrok
from pyngrok.exception import PyngrokNgrokError

from src.settings import get_settings

logger = logging.getLogger(__name__)

NGROK_SIGNUP_URL = "https://dashboard.ngrok.com/signup"
NGROK_AUTHTOKEN_URL = "https://dashboard.ngrok.com/get-started/your-authtoken"


class NgrokTunnelError(Exception):
    """Raised when ngrok tunnel operations fail."""


class TunnelManager:
    """Manages ngrok tunnel lifecycle for local webhook testing.

    Uses pyngrok which automatically downloads ngrok if needed.
    """

    def __init__(self, port: int | None = None) -> None:
        """Initialize the tunnel manager.

        Args:
            port: Local port to expose (default from config).
        """
        self.settings = get_settings()
        self.port = port if port is not None else self.settings.config.tunnel.default_port
        self._public_url: str | None = None
        self._original_webhook_url: str | None = None
        self._http_client: httpx.AsyncClient | None = None

    @property
    def api_base(self) -> str:
        """Get the Telegram API base URL with token."""
        return f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"

    def _check_authtoken(self) -> bool:
        """Check if ngrok authtoken is configured.

        Returns:
            True if authtoken is set, False otherwise.
        """
        try:
            # Check pyngrok's in-memory config first
            pyngrok_config = conf.get_default()
            if pyngrok_config.auth_token:
                return True

            # Also check ngrok's config file directly
            ngrok_config_paths = [
                Path("~/.ngrok2/ngrok.yml").expanduser(),
                Path("~/Library/Application Support/ngrok/ngrok.yml").expanduser(),
                Path("~/.config/ngrok/ngrok.yml").expanduser(),
            ]
            for path in ngrok_config_paths:
                if path.exists():
                    content = path.read_text()
                    if "authtoken:" in content:
                        return True
            return False
        except Exception:
            return False

    def _prompt_authtoken(self) -> bool:
        """Interactively prompt user for ngrok authtoken.

        Returns:
            True if authtoken was set successfully, False if user cancelled.
        """
        print("\n" + "=" * 60)
        print("🔐 ngrok authtoken required (one-time setup)")
        print("=" * 60)
        print()
        print("1. Create free ngrok account (if you don't have one):")
        print(f"   {NGROK_SIGNUP_URL}")
        print()
        print("2. Get your authtoken:")
        print(f"   {NGROK_AUTHTOKEN_URL}")
        print()

        try:
            authtoken = input("3. Paste your authtoken here: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return False

        if not authtoken:
            print("No authtoken provided.")
            return False

        try:
            # Set the authtoken (this saves it to ngrok config file)
            ngrok.set_auth_token(authtoken)
            print()
            print("✓ Authtoken saved! You won't need to do this again.")
            print("=" * 60 + "\n")
            return True
        except Exception as e:
            print(f"Failed to set authtoken: {e}")
            return False

    def _start_tunnel_sync(self) -> str:
        """Start ngrok tunnel synchronously (blocking).

        This is the sync implementation called via asyncio.to_thread().

        Returns:
            The public HTTPS URL.

        Raises:
            NgrokTunnelError: If tunnel fails to start.
        """
        # Check authtoken, prompt if needed
        if not self._check_authtoken() and not self._prompt_authtoken():
            raise NgrokTunnelError("ngrok authtoken required but not provided")

        logger.info(f"Starting ngrok tunnel on port {self.port}...")

        try:
            # Connect ngrok (pyngrok downloads ngrok automatically if needed)
            tunnel = ngrok.connect(str(self.port), "http")
            public_url = tunnel.public_url

            if not public_url:
                raise NgrokTunnelError("ngrok returned empty public URL")

            # Ensure HTTPS
            if public_url.startswith("http://"):
                public_url = public_url.replace("http://", "https://")

            self._public_url = public_url
            logger.info(f"ngrok tunnel established: {self._public_url}")
            return self._public_url

        except PyngrokNgrokError as e:
            raise NgrokTunnelError(f"Failed to start ngrok tunnel: {e}") from e

    async def start_tunnel(self) -> str:
        """Start ngrok tunnel and return the public URL.

        Runs blocking ngrok operations in a thread pool to avoid
        blocking the event loop.

        Returns:
            The public HTTPS URL.

        Raises:
            NgrokTunnelError: If tunnel fails to start.
        """
        return await asyncio.to_thread(self._start_tunnel_sync)

    async def get_current_webhook(self) -> str | None:
        """Get the current Telegram webhook URL.

        Returns:
            Current webhook URL or None if not set.
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        try:
            response = await self._http_client.get(f"{self.api_base}/getWebhookInfo")
            data: dict[str, Any] = response.json()
            if data.get("ok"):
                result: dict[str, Any] = data.get("result", {})
                url: str = result.get("url", "")
                return url if url else None
        except httpx.HTTPError as e:
            logger.warning(f"Failed to get current webhook: {e}")
        return None

    async def set_webhook(self, url: str) -> bool:
        """Set the Telegram webhook URL.

        Args:
            url: The base URL (webhook path will be appended).

        Returns:
            True if successful, False otherwise.
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        webhook_url = f"{url}/hooks/telegram"
        logger.info(f"Setting Telegram webhook to: {webhook_url}")

        try:
            response = await self._http_client.post(
                f"{self.api_base}/setWebhook", json={"url": webhook_url}
            )
            data: dict[str, Any] = response.json()
            if data.get("ok"):
                logger.info("Telegram webhook set successfully")
                return True
            else:
                logger.error(f"Failed to set webhook: {data}")
                return False
        except httpx.HTTPError as e:
            logger.error(f"HTTP error setting webhook: {e}")
            return False

    async def setup(self) -> str:
        """Start tunnel and configure webhook.

        Returns:
            The public URL for the tunnel.

        Raises:
            NgrokTunnelError: If setup fails.
        """
        # Store original webhook for restoration
        self._original_webhook_url = await self.get_current_webhook()
        if self._original_webhook_url:
            logger.info(f"Original webhook URL saved: {self._original_webhook_url}")

        # Start ngrok tunnel (runs blocking ops in thread pool)
        public_url = await self.start_tunnel()

        # Set Telegram webhook
        if not await self.set_webhook(public_url):
            self.stop_tunnel()
            raise NgrokTunnelError("Failed to set Telegram webhook")

        return public_url

    def stop_tunnel(self) -> None:
        """Stop the ngrok tunnel."""
        if self._public_url:
            try:
                ngrok.disconnect(self._public_url)
                logger.info("ngrok tunnel disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting tunnel: {e}")
            self._public_url = None

    async def _restore_webhook_exact(self, webhook_url: str) -> None:
        """Restore webhook URL exactly as provided.

        Used when the original webhook doesn't follow our /hooks/telegram convention.

        Args:
            webhook_url: The exact webhook URL to restore.
        """
        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        try:
            response = await self._http_client.post(
                f"{self.api_base}/setWebhook", json={"url": webhook_url}
            )
            data: dict[str, Any] = response.json()
            if data.get("ok"):
                logger.info("Original Telegram webhook restored successfully")
            else:
                logger.error(f"Failed to restore original webhook: {data}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error restoring original webhook: {e}")

    async def stop(self, restore_webhook: bool = False) -> None:
        """Stop ngrok and optionally restore original webhook.

        Args:
            restore_webhook: If True, restore the original webhook URL.
        """
        logger.info("Shutting down tunnel...")

        # Optionally restore original webhook
        if restore_webhook and self._original_webhook_url:
            logger.info(f"Restoring original webhook: {self._original_webhook_url}")
            webhook_suffix = "/hooks/telegram"
            if self._original_webhook_url.endswith(webhook_suffix):
                # Original webhook used our convention; restore via base URL
                base_url = self._original_webhook_url[: -len(webhook_suffix)]
                await self.set_webhook(base_url)
            else:
                # Original webhook has different path; restore exactly as-is
                await self._restore_webhook_exact(self._original_webhook_url)

        # Stop ngrok tunnel
        self.stop_tunnel()

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
