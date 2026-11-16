"""ReTurn development management commands.

Usage:
    python manage.py seed            # reset + create the fictional demo scenario
    python manage.py seed-if-empty   # seed only when the database has no users
    python manage.py check           # print schema/row counts without changing data
    python manage.py bootstrap-admin # create the first administrator (env/flags)
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from app import create_app
from app.extensions import db

app = create_app()

TABLES = (
    "users",
    "orders",
    "parcel_details",
    "pickup_addresses",
    "delivery_addresses",
    "delivery_batches",
    "batch_orders",
    "route_plans",
    "route_stops",
    "driver_assignments",
    "driver_duty_sessions",
    "driver_location_events",
    "matching_suggestions",
    "proof_media",
    "delivery_exceptions",
    "notifications",
    "audit_logs",
)


def _counts() -> dict:
    rows = {}
    for table in TABLES:
        try:
            rows[table] = db.session.execute(text(f"SELECT count(*) FROM {table}")).scalar()
        except Exception:
            db.session.rollback()
            rows[table] = "missing"
    return rows


def _seed(label: str) -> int:
    try:
        from app.services.seed import seed_demo_data
    except ImportError:
        print("Demo seeding is not available in this build yet.")
        return 2
    summary = seed_demo_data(reset=True)
    print(f"{label} ReTurn demo data:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("Counts:", _counts())
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    with app.app_context():
        if command == "seed":
            return _seed("Seeded")
        if command == "seed-if-empty":
            from app.models import User

            if db.session.query(User.id).first() is not None:
                print("Users already exist; skipping demo seed.")
                print("Counts:", _counts())
                return 0
            return _seed("Seeded")
        if command == "check":
            print("Counts:", _counts())
            return 0
        print(f"Unknown command: {command}")
        print(__doc__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
