"""Application factory for the ReTurn Flask API."""
from __future__ import annotations

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

    from .api.accounts import bp as accounts_bp
    from .api.auth import bp as auth_bp
    from .api.consumer import bp as consumer_bp
    from .api.driver import bp as driver_bp
    from .api.admin import bp as admin_bp
    from .api.health import bp as health_bp
    from .api.issues import bp as issues_bp
    from .api.manager import bp as manager_bp
    from .api.media import bp as media_bp
    from .api.notifications import bp as notifications_bp
    from .api.orders import bp as orders_bp
    from .api.returns import bp as returns_bp

    for blueprint in (
        health_bp,
        auth_bp,
        accounts_bp,
        orders_bp,
        returns_bp,
        media_bp,
        notifications_bp,
        consumer_bp,
        driver_bp,
        manager_bp,
        admin_bp,
        issues_bp,
    ):
        app.register_blueprint(blueprint)

    register_error_handlers(app)

    from .cli import register_cli

    register_cli(app)

    @app.get("/")
    def index():
        return jsonify(
            {
                "data": {
                    "name": "ReTurn",
                    "tagline": "One Route. Multiple Deliveries. Less Waste.",
                    "api": "/api/v1/health",
                }
            }
        )

    return app


def request_origin() -> str | None:
    from flask import request

    return request.headers.get("Origin")
