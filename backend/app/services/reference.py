"""Reference data: permission catalogue, rejection codes, vehicle capacities.

These are configuration rows the platform needs in order to operate. They are
idempotent inserts, safe to run on every deploy, and contain no customer data.
"""
from __future__ import annotations

from .. import domain
from ..extensions import db
from ..models import MatchingRejectionReason, Permission, VehicleCapacityProfile

CAPACITY_PROFILES = (
    {
        "name": "Bike — small parcels",
        "vehicle_type": "bike",
        "max_weight_kg": 15,
        "max_volume_m3": 0.05,
        "max_length_cm": 60,
        "max_width_cm": 40,
        "max_height_cm": 40,
        "max_parcels": 8,
        "supports_fragile": True,
        "supports_restricted": False,
    },
    {
        "name": "Scooter — small parcels",
        "vehicle_type": "scooter",
        "max_weight_kg": 20,
        "max_volume_m3": 0.07,
        "max_length_cm": 70,
        "max_width_cm": 45,
        "max_height_cm": 45,
        "max_parcels": 10,
        "supports_fragile": True,
        "supports_restricted": False,
    },
    {
        "name": "Car — medium parcels",
        "vehicle_type": "car",
        "max_weight_kg": 60,
        "max_volume_m3": 0.30,
        "max_length_cm": 100,
        "max_width_cm": 60,
        "max_height_cm": 50,
        "max_parcels": 18,
        "supports_fragile": True,
        "supports_restricted": False,
    },
    {
        "name": "Van — bulk deliveries",
        "vehicle_type": "van",
        "max_weight_kg": 300,
        "max_volume_m3": 1.50,
        "max_length_cm": 160,
        "max_width_cm": 110,
        "max_height_cm": 100,
        "max_parcels": 60,
        "supports_fragile": True,
        "supports_restricted": True,
    },
    {
        "name": "Truck — heavy freight",
        "vehicle_type": "truck",
        "max_weight_kg": 1500,
        "max_volume_m3": 9.00,
        "max_length_cm": 300,
        "max_width_cm": 180,
        "max_height_cm": 180,
        "max_parcels": 150,
        "supports_fragile": True,
        "supports_restricted": True,
    },
)


def ensure_reference_data() -> dict:
    created = {"permissions": 0, "reasons": 0, "capacity_profiles": 0}

    existing_permissions = {row.code for row in Permission.query.all()}
    for code, label in domain.PERMISSION_CATALOG.items():
        if code not in existing_permissions:
            db.session.add(Permission(code=code, label=label, description=label))
            created["permissions"] += 1

    existing_reasons = {row.code for row in MatchingRejectionReason.query.all()}
    for order, (code, label) in enumerate(domain.MATCHING_REJECTION_REASONS.items()):
        if code not in existing_reasons:
            db.session.add(
                MatchingRejectionReason(
                    code=code,
                    label=label,
                    description=label,
                    is_blocking=True,
                    sort_order=order,
                )
            )
            created["reasons"] += 1

    existing_profiles = {row.name for row in VehicleCapacityProfile.query.all()}
    for profile in CAPACITY_PROFILES:
        if profile["name"] not in existing_profiles:
            db.session.add(VehicleCapacityProfile(**profile))
            created["capacity_profiles"] += 1

    db.session.flush()
    return created
