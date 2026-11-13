"""Health and capability probe."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from ..extensions import db

bp = Blueprint("health", __name__, url_prefix="/api/v1")


@bp.get("/health")
def health():
    database_ok = True
    error = None
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - operational probe
        database_ok = False
        error = type(exc).__name__
    return (
        jsonify(
            {
                "data": {
                    "status": "ok" if database_ok else "degraded",
                    "service": "ReTurn API",
                    "database": "postgresql" if database_ok else "unavailable",
                    "database_error": error,
                    "routing_provider": current_app.config["ROUTING_PROVIDER"],
                    "osrm_configured": bool(current_app.config["OSRM_BASE_URL"]),
                }
            }
        ),
        200 if database_ok else 503,
    )
