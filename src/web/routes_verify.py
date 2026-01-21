"""Verification routes for timezone verification flow.

Provides the web-based timezone verification UX.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from quart import Blueprint, Response, jsonify, request

from src.core.models import TimezoneSource, UserTzState
from src.core.time_convert import is_valid_iana_timezone
from src.core.timezone_identity import parse_verify_token
from src.settings import get_settings
from src.storage.mongo import get_storage

logger = logging.getLogger(__name__)

verify_bp = Blueprint("verify", __name__)


@verify_bp.route("/verify", methods=["GET"])
async def verify_page() -> Response | tuple[str, int]:
    """Serve the timezone verification page.

    Query params:
        token: Verification token from bot link.

    Returns:
        HTML page for timezone verification.
    """
    token = request.args.get("token", "")

    if not token:
        return "Missing verification token", 400

    # Validate token
    parsed = parse_verify_token(token)
    if parsed is None:
        return "Invalid or expired verification token", 400

    # Read and serve the HTML template
    template_path = Path(__file__).parent / "verify_page.html"
    with template_path.open(encoding="utf-8") as f:
        html = f.read()

    # Inject token and settings into template
    settings = get_settings()
    cities_js = ", ".join(
        f'{{name: "{c.name}", tz: "{c.tz}"}}' for c in settings.config.timezone.team_cities
    )

    html = html.replace("{{TOKEN}}", token)
    html = html.replace("{{CITIES}}", cities_js)

    return Response(html, mimetype="text/html")


@verify_bp.route("/api/verify", methods=["POST"])
async def verify_timezone() -> tuple[Response, int]:
    """Handle timezone verification submission.

    Request body:
        token: Verification token.
        tz_iana: IANA timezone identifier.

    Returns:
        JSON response with success status.
    """
    data = await request.get_json()

    if not data:
        return jsonify({"error": "Missing request body"}), 400

    token = data.get("token", "")
    tz_iana = data.get("tz_iana", "")

    if not token:
        return jsonify({"error": "Missing token"}), 400

    if not tz_iana:
        return jsonify({"error": "Missing timezone"}), 400

    # Validate token
    parsed = parse_verify_token(token)
    if parsed is None:
        return jsonify({"error": "Invalid or expired token"}), 400

    # Validate timezone
    if not is_valid_iana_timezone(tz_iana):
        return jsonify({"error": "Invalid timezone"}), 400

    # Store timezone
    storage = get_storage()

    now = datetime.utcnow()
    state = UserTzState(
        platform=parsed.platform,
        user_id=parsed.user_id,
        tz_iana=tz_iana,
        confidence=get_settings().config.confidence.verified,
        source=TimezoneSource.WEB_VERIFIED,
        updated_at=now,
        last_verified_at=now,
    )

    await storage.upsert_user_tz_state(state)

    logger.info(f"Timezone verified: {parsed.platform.value}/{parsed.user_id} -> {tz_iana}")

    return jsonify(
        {
            "success": True,
            "message": "Timezone saved! You can close this page.",
            "timezone": tz_iana,
        }
    ), 200
