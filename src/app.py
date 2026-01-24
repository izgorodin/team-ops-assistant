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

from src.connectors.discord.outbound import close_discord_outbound
from src.connectors.telegram.inbound import normalize_telegram_update
from src.connectors.telegram.outbound import close_telegram_outbound, send_messages
from src.connectors.whatsapp.outbound import close_whatsapp_outbound
from src.core.actions.time_convert import TimeConversionHandler
from src.core.agent_handler import AgentHandler
from src.core.orchestrator import MessageOrchestrator
from src.core.pipeline import Pipeline
from src.core.state.timezone import TimezoneStateManager
from src.core.triggers.time import TimeDetector
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

        # Create pipeline components
        time_detector = TimeDetector()
        tz_state_manager = TimezoneStateManager(storage)
        time_handler = TimeConversionHandler()

        # Create pipeline
        pipeline = Pipeline(
            detectors=[time_detector],
            state_managers={"timezone": tz_state_manager},
            action_handlers={"time": time_handler},
        )

        # Create agent handler and orchestrator
        agent_handler = AgentHandler(storage, settings)
        orchestrator = MessageOrchestrator(
            storage=storage,
            pipeline=pipeline,
            agent_handler=agent_handler,
            base_url=settings.app_base_url,
        )

        # Store in app context
        app.orchestrator = orchestrator  # type: ignore[attr-defined]
        app.pipeline = pipeline  # type: ignore[attr-defined]

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
        await close_discord_outbound()
        await close_whatsapp_outbound()

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

            # Handle the event via orchestrator
            orchestrator: MessageOrchestrator = app.orchestrator  # type: ignore[attr-defined]
            result = await orchestrator.route(event)

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
    parser.add_argument(
        "--polling",
        action="store_true",
        help="Use Telegram polling instead of webhooks (for local development)",
    )
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="Start ngrok tunnel and use webhooks (for local development)",
    )
    parser.add_argument(
        "--restore-webhook",
        action="store_true",
        help="Restore original webhook URL on shutdown (only with --tunnel)",
    )
    args = parser.parse_args()

    if args.polling and args.tunnel:
        print("Error: Cannot use both --polling and --tunnel modes")
        return

    if args.polling:
        # Run in polling mode (local development)
        asyncio.run(run_polling_mode())
    elif args.tunnel:
        # Run in tunnel mode (ngrok + webhooks)
        asyncio.run(run_tunnel_mode(port=args.port, restore_webhook=args.restore_webhook))
    else:
        # Run in webhook mode (production)
        app = create_app()
        try:
            app.run(host=args.host, port=args.port, debug=False)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")


async def run_polling_mode() -> None:
    """Run in Telegram polling mode for local development."""
    from src.connectors.telegram.polling import TelegramPoller

    logger.info("=== POLLING MODE (Local Development) ===")
    logger.info("Press Ctrl+C to stop")

    # Initialize components (same as startup())
    settings = get_settings()
    storage = get_storage()
    await storage.connect()

    # Create pipeline components
    time_detector = TimeDetector()
    tz_state_manager = TimezoneStateManager(storage)
    time_handler = TimeConversionHandler()

    pipeline = Pipeline(
        detectors=[time_detector],
        state_managers={"timezone": tz_state_manager},
        action_handlers={"time": time_handler},
    )

    agent_handler = AgentHandler(storage, settings)
    orchestrator = MessageOrchestrator(
        storage=storage,
        pipeline=pipeline,
        agent_handler=agent_handler,
        base_url=settings.app_base_url,
    )

    # Start polling
    poller = TelegramPoller(orchestrator)
    try:
        await poller.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await poller.stop()
        await close_telegram_outbound()
        await storage.close()
        logger.info("Shutdown complete")


async def run_tunnel_mode(port: int = 8000, restore_webhook: bool = False) -> None:
    """Run in tunnel mode with ngrok for local webhook testing.

    Args:
        port: Local port to expose (default: 8000).
        restore_webhook: If True, restore original webhook on shutdown.
    """
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    from src.connectors.telegram.tunnel import NgrokTunnelError, TunnelManager

    logger.info("=== TUNNEL MODE (Local Webhook Development) ===")
    logger.info("Press Ctrl+C to stop")

    tunnel = TunnelManager(port=port)

    try:
        # Start tunnel and set webhook
        public_url = await tunnel.setup()

        logger.info("")
        logger.info("=" * 50)
        logger.info(f"Public URL: {public_url}")
        logger.info(f"Webhook: {public_url}/hooks/telegram")
        logger.info("Inspector: http://localhost:4040")
        logger.info("")
        logger.info("Send a message to your Telegram bot to test!")
        logger.info("=" * 50)
        logger.info("")

        # Run the Quart app with hypercorn (async-compatible)
        app = create_app()
        config = Config()
        config.bind = [f"0.0.0.0:{port}"]

        await serve(app, config)

    except NgrokTunnelError as e:
        logger.error(f"Tunnel error: {e}")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await tunnel.stop(restore_webhook=restore_webhook)
        logger.info("Shutdown complete")


if __name__ == "__main__":
    run_app()
