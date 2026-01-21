"""Team Ops Assistant - Quart Application.

Main application entry point with routes and lifecycle management.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
from typing import Any

from quart import Quart, Response, jsonify, request

from src.connectors.telegram.inbound import normalize_telegram_update
from src.connectors.telegram.outbound import close_telegram_outbound, send_messages
from src.core.handler import MessageHandler
from src.settings import get_settings
from src.storage.mongo import get_storage
from src.web.routes_verify import verify_bp

logger = logging.getLogger(__name__)

# Global state for graceful shutdown
_shutdown_event: asyncio.Event | None = None
_background_tasks: set[asyncio.Task[Any]] = set()


def create_app() -> Quart:
    """Create and configure the Quart application.

    Returns:
        Configured Quart application.
    """
    app = Quart(__name__)

    settings = get_settings()
    app.secret_key = settings.app_secret_key

    # Register blueprints
    app.register_blueprint(verify_bp)

    # Lifecycle hooks
    @app.before_serving
    async def startup() -> None:
        """Application startup: connect to MongoDB, set up handlers."""
        global _shutdown_event
        _shutdown_event = asyncio.Event()

        logger.info("Starting Team Ops Assistant...")

        # Connect to MongoDB
        storage = get_storage()
        await storage.connect()

        # Store handler in app context
        base_url = f"http://{settings.app_host}:{settings.app_port}"
        app.message_handler = MessageHandler(storage, base_url)  # type: ignore[attr-defined]

        logger.info("Application started successfully")

    @app.after_serving
    async def shutdown() -> None:
        """Application shutdown: close connections, cancel tasks."""
        logger.info("Shutting down Team Ops Assistant...")

        # Signal shutdown
        if _shutdown_event:
            _shutdown_event.set()

        # Cancel background tasks
        for task in _background_tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Close outbound connectors
        await close_telegram_outbound()

        # Close MongoDB
        storage = get_storage()
        await storage.close()

        logger.info("Shutdown complete")

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    async def health_check() -> Response:
        """Health check endpoint for monitoring."""
        return jsonify({"status": "ok"})

    # Telegram webhook endpoint
    @app.route("/hooks/telegram", methods=["POST"])
    async def telegram_webhook() -> Response | tuple[Response, int]:
        """Handle incoming Telegram webhook updates."""
        try:
            update = await request.get_json()
            if not update:
                return jsonify({"error": "Invalid JSON"}), 400

            # Normalize the update
            event = normalize_telegram_update(update)
            if event is None:
                # Not a processable message, acknowledge anyway
                return jsonify({"status": "ignored"})

            # Handle the event
            handler: MessageHandler = app.message_handler  # type: ignore[attr-defined]
            result = await handler.handle(event)

            # Send outbound messages
            if result.should_respond and result.messages:
                await send_messages(result.messages)

            return jsonify({"status": "processed"})

        except Exception as e:
            logger.exception("Error processing Telegram webhook")
            return jsonify({"error": str(e)}), 500

    # Discord webhook endpoint (stub)
    @app.route("/hooks/discord", methods=["POST"])
    async def discord_webhook() -> tuple[Response, int]:
        """Handle incoming Discord interactions (STUB).

        TODO: Implement Discord interactions/events handling.
        For full Discord support, you'll likely want to use discord.py
        with gateway connection rather than webhooks.
        """
        return jsonify(
            {
                "status": "not_implemented",
                "message": "Discord connector is a skeleton. See docs for implementation guide.",
            }
        ), 501

    # WhatsApp webhook endpoints
    @app.route("/hooks/whatsapp", methods=["GET"])
    async def whatsapp_webhook_verify() -> Response | str | tuple[Response, int]:
        """Handle WhatsApp webhook verification challenge."""
        settings = get_settings()

        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == settings.whatsapp_verify_token:
            logger.info("WhatsApp webhook verified")
            return challenge or ""

        logger.warning("WhatsApp webhook verification failed")
        return jsonify({"error": "Forbidden"}), 403

    @app.route("/hooks/whatsapp", methods=["POST"])
    async def whatsapp_webhook() -> tuple[Response, int]:
        """Handle incoming WhatsApp webhook events (STUB).

        TODO: Implement WhatsApp message handling.
        """
        return jsonify(
            {
                "status": "not_implemented",
                "message": "WhatsApp connector is a skeleton. See docs for implementation guide.",
            }
        ), 501

    return app


def run_app() -> None:
    """Run the application with graceful shutdown handling."""
    parser = argparse.ArgumentParser(description="Team Ops Assistant")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()

    app = create_app()

    # Run with hypercorn for production-ready async server
    try:
        app.run(host=args.host, port=args.port, debug=False)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")


if __name__ == "__main__":
    run_app()
