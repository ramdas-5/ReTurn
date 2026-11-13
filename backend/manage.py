"""ReTurn development management commands.

Usage:
    python manage.py seed     # truncate + create the fictional demo scenario
    python manage.py check    # print schema/row counts without changing data
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.services.seed import seed_demo_data

app = create_app()


def _counts() -> dict:
    rows = {}
    for table in (
        "users",
        "locations",
        "delivery_requests",
        "parcels",
        "delivery_batches",
        "batch_stops",
        "tracking_events",
        "issue_reports",
        "audit_events",
    ):
        rows[table] = db.session.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    return rows


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "seed"
    with app.app_context():
        if command == "seed":
            summary = seed_demo_data(reset=True)
            print("Seeded ReTurn demo data:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
            print("Counts:", _counts())
            return 0
        if command == "check":
            print("Counts:", _counts())
            return 0
        print(f"Unknown command: {command}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
