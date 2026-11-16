"""Configuration loaded from environment variables (never hard-coded secrets)."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
# The repository `.env` is a local-development file (git-ignored, never shipped
# in the Docker image). On Render/Vercel the platform-injected variables are the
# only source, so overriding here is safe and keeps local runs predictable.
load_dotenv(PROJECT_ROOT / ".env", override=True)
load_dotenv(BACKEND_DIR / ".env", override=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _database_url() -> str:
    """Normalise provider URLs (Neon/Render/Heroku style) for SQLAlchemy + psycopg."""
    raw = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://return:return_dev_pw@127.0.0.1:5433/return_dev",
    ).strip()
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-return-session-secret")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_size": 5, "pool_recycle": 280}

    # Sessions -------------------------------------------------------------
    SESSION_COOKIE_NAME = "rt_session"
    CSRF_COOKIE_NAME = "rt_csrf"
    SESSION_TTL = timedelta(hours=_int("SESSION_TTL_HOURS", 24))
    SESSION_COOKIE_SECURE = _bool(
        "SESSION_COOKIE_SECURE",
        os.getenv("FLASK_ENV", "development").strip().lower() in {"production", "prod"},
    )
    SESSION_COOKIE_SAMESITE = "Lax"
    TRUST_PROXY_HEADERS = _bool("TRUST_PROXY_HEADERS", False)

    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]
    PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:3000")
    RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)
    # Development convenience: return reset/activation tokens in the API response
    # because no email provider is configured. Must stay false in production once
    # an email integration exists.
    AUTH_EXPOSE_RESET_TOKENS = _bool(
        "AUTH_EXPOSE_RESET_TOKENS",
        os.getenv("FLASK_ENV", "development").strip().lower() not in {"production", "prod"},
    )
    MAX_CONTENT_LENGTH = _int("MAX_CONTENT_LENGTH_BYTES", 12 * 1024 * 1024)
    PASSWORD_MIN_LENGTH = _int("PASSWORD_MIN_LENGTH", 10)

    # Demo data is opt-in and never seeds automatically in production.
    SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", False)
    APP_ENV = os.getenv("FLASK_ENV", "development").strip().lower()

    # Routing --------------------------------------------------------------
    ROUTING_PROVIDER = os.getenv("ROUTING_PROVIDER", "auto")
    OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
    ROUTING_TIMEOUT_SECONDS = _float("ROUTING_TIMEOUT_SECONDS", 3.0)

    # Matching -------------------------------------------------------------
    MATCHING_DEFAULTS = {
        "max_detour_km": _float("MATCHING_MAX_DETOUR_KM", 6.0),
        "max_pickup_radius_km": _float("MATCHING_MAX_PICKUP_RADIUS_KM", 5.0),
        "max_workload_parcels": _int("MATCHING_MAX_WORKLOAD_PARCELS", 12),
        "max_workload_weight_pct": _float("MATCHING_MAX_WORKLOAD_WEIGHT_PCT", 90.0),
        "service_minutes": _int("MATCHING_SERVICE_MINUTES", 6),
        "avg_speed_kmh": _float("MATCHING_AVG_SPEED_KMH", 24.0),
        "road_factor": _float("MATCHING_ROAD_FACTOR", 1.32),
        "deadline_buffer_minutes": _int("MATCHING_DEADLINE_BUFFER_MINUTES", 10),
        "suggestion_ttl_minutes": _int("MATCHING_SUGGESTION_TTL_MINUTES", 45),
        "max_search_drivers": _int("MATCHING_MAX_SEARCH_DRIVERS", 25),
    }

    # Order intake ---------------------------------------------------------
    # One exterior parcel photograph is part of the normal booking flow. The
    # documented exception (inaccessible camera / approved case) is a written
    # reason stored on the parcel. Set false only for an approved deployment
    # where photographs are collected another way.
    PARCEL_PHOTO_REQUIRED = _bool("PARCEL_PHOTO_REQUIRED", True)
    PARCEL_PHOTO_MIN_EXCEPTION_CHARS = _int("PARCEL_PHOTO_MIN_EXCEPTION_CHARS", 12)
    # Orders outside every active service area are rejected: no service exists.
    REQUIRE_SERVICE_AREA_FOR_ORDERS = _bool("REQUIRE_SERVICE_AREA_FOR_ORDERS", True)
    # A duty session older than this without a heartbeat is treated as stale.
    DUTY_HEARTBEAT_TIMEOUT_MINUTES = _int("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15)
    MAX_PARCEL_IMAGES = _int("MAX_PARCEL_IMAGES", 5)
    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")

    # Proof of pickup / delivery ------------------------------------------
    PROOF_MAX_CAPTURE_AGE_MINUTES = _int("PROOF_MAX_CAPTURE_AGE_MINUTES", 20)
    PROOF_GPS_RADIUS_METERS = _float("PROOF_GPS_RADIUS_METERS", 400.0)
    PROOF_MAX_ACCURACY_METERS = _float("PROOF_MAX_ACCURACY_METERS", 250.0)
    PROOF_REQUIRE_GPS = _bool("PROOF_REQUIRE_GPS", True)
    PICKUP_PROOF_REQUIRED = _bool("PICKUP_PROOF_REQUIRED", False)
    DELIVERY_PROOF_REQUIRED = _bool("DELIVERY_PROOF_REQUIRED", True)

    # Media storage --------------------------------------------------------
    MEDIA_BACKEND = os.getenv("MEDIA_BACKEND", "local").strip().lower()
    MEDIA_LOCAL_DIR = os.getenv("MEDIA_LOCAL_DIR", str(BACKEND_DIR / "var" / "media"))
    MEDIA_SIGNING_SECRET = os.getenv("MEDIA_SIGNING_SECRET", "")
    MEDIA_SIGNED_URL_TTL_SECONDS = _int("MEDIA_SIGNED_URL_TTL_SECONDS", 300)
    S3_BUCKET = os.getenv("S3_BUCKET", "")
    S3_REGION = os.getenv("S3_REGION", "")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")

    # Bootstrap ------------------------------------------------------------
    BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
    BOOTSTRAP_ADMIN_NAME = os.getenv("BOOTSTRAP_ADMIN_NAME", "ReTurn Administrator")
    BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

    SUSTAINABILITY_FUEL_L_PER_KM = _float("SUSTAINABILITY_FUEL_L_PER_KM", 0.07)
    SUSTAINABILITY_KG_CO2E_PER_LITRE = _float("SUSTAINABILITY_KG_CO2E_PER_LITRE", 2.68)

    TESTING = False
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    RATE_LIMIT_ENABLED = False
    ROUTING_PROVIDER = "estimated"
    SEED_DEMO_DATA = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://return:return_dev_pw@127.0.0.1:5433/return_test",
    )
