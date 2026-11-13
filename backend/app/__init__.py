"""Application factory for the ReTurn Flask API."""
from __future__ import annotations

import os

from flask import Flask, jsonify

from .config import Config
from .extensions import db, migrate
from .errors import ApiError, register_error_handlers
from .security import load_session, validate_csrf


def create_app(config_object: type = Config, **overrides) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.config.update(overrides)

    if app.config.get("TRUST_PROXY_HEADERS"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        # One trusted hop: the platform reverse proxy (Render/Vercel).
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Alembic/SQLAlchemy metadata is complete.
    from . import models  # noqa: F401

    @app.before_request
    def _security_pipeline():
        load_session()
        validate_csrf()

    @app.after_request
    def _headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        origin = request_origin()
        allowed = app.config.get("CORS_ALLOWED_ORIGINS", [])
        if origin and origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        return response

    @app.route("/api/v1/<path:_path>", methods=["OPTIONS"])
    def _options(_path: str):
        response = jsonify({"data": None})
        origin = request_origin()
        allowed = app.config.get("CORS_ALLOWED_ORIGINS", [])
        if origin and origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        return response

    from .api.admin import bp as admin_bp
    from .api.analytics import bp as analytics_bp
    from .api.auth import bp as auth_bp
    from .api.batches import bp as batches_bp
    from .api.customers import bp as customers_bp
    from .api.health import bp as health_bp
    from .api.issues import bp as issues_bp
    from .api.locations import bp as locations_bp
    from .api.matching import bp as matching_bp
    from .api.notifications import bp as notifications_bp
    from .api.parcels import bp as parcels_bp
    from .api.partners import bp as partners_bp
    from .api.requests import bp as requests_bp

    for blueprint in (
        health_bp,
        auth_bp,
        requests_bp,
        matching_bp,
        batches_bp,
        parcels_bp,
        partners_bp,
        customers_bp,
        issues_bp,
        notifications_bp,
        analytics_bp,
        admin_bp,
        locations_bp,
    ):
        app.register_blueprint(blueprint)

    register_error_handlers(app)

    @app.get("/")
    def index():
        return jsonify(
            {
                "data": {
                    "name": "ReTurn",
                    "description": "Smart Reverse Delivery & Shared Logistics Platform",
                    "api": "/api/v1/health",
                }
            }
        )

    @app.cli.command("seed")
    def seed_command():  # pragma: no cover - exercised via manage.py
        from .services.seed import seed_demo_data

        summary = seed_demo_data(reset=True)
        print(summary)

    return app


def request_origin() -> str | None:
    from flask import request

    return request.headers.get("Origin")


__all__ = ["create_app", "ApiError", "os"]
