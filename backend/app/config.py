"""Configuration loaded from environment variables (never hard-coded secrets)."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-return-session-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://return:return_dev_pw@127.0.0.1:5433/return_dev",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_size": 5}

    SESSION_COOKIE_NAME = "rt_session"
    CSRF_COOKIE_NAME = "rt_csrf"
    SESSION_TTL = timedelta(hours=int(os.getenv("SESSION_TTL_HOURS", "24")))
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_SAMESITE = "Lax"

    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ]

    RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)

    ROUTING_PROVIDER = os.getenv("ROUTING_PROVIDER", "auto")
    OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
    ROUTING_TIMEOUT_SECONDS = _float("ROUTING_TIMEOUT_SECONDS", 3.0)

    MATCHING_DEFAULTS = {
        "max_group_size": int(os.getenv("MATCHING_MAX_GROUP_SIZE", "3")),
        "max_pickup_radius_km": _float("MATCHING_MAX_PICKUP_RADIUS_KM", 8.0),
        "max_detour_km": _float("MATCHING_MAX_DETOUR_KM", 12.0),
        "min_savings_pct": _float("MATCHING_MIN_SAVINGS_PCT", 12.0),
        "service_minutes": int(os.getenv("MATCHING_SERVICE_MINUTES", "6")),
        "avg_speed_kmh": _float("MATCHING_AVG_SPEED_KMH", 24.0),
        "road_factor": _float("MATCHING_ROAD_FACTOR", 1.32),
    }

    SUSTAINABILITY_FUEL_L_PER_KM = _float("SUSTAINABILITY_FUEL_L_PER_KM", 0.07)
    SUSTAINABILITY_KG_CO2E_PER_LITRE = _float("SUSTAINABILITY_KG_CO2E_PER_LITRE", 2.68)

    # Default vehicle assumed for a feasible proposal with no verified partner online.
    UNASSIGNED_VEHICLE_PROFILE = {
        "label": "Configured demo vehicle (no partner assigned)",
        "vehicle_type": "van",
        "max_weight_kg": 40.0,
        "max_volume_m3": 0.25,
        "accepts_fragile": True,
        "accepts_restricted": True,
        "service_areas": ["Barasat", "Madhyamgram", "Salt Lake", "New Town", "Dum Dum", "Birati"],
    }

    TESTING = False
    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    RATE_LIMIT_ENABLED = False
    ROUTING_PROVIDER = "estimated"
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://return:return_dev_pw@127.0.0.1:5433/return_test",
    )
