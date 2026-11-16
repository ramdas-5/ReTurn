"""Platform analytics derived from stored rows.

Every distance, fuel and CO₂ figure is a modelled *estimate* using the same
labelled routing source as dispatch and the configured sustainability factors.
Nothing here is measured telemetry.
"""
from __future__ import annotations

from flask import current_app

from .. import domain
from ..extensions import db
from ..models import (
    DeliveryBatch,
    DeliveryException,
    DriverAssignment,
    DriverProfile,
    MatchingSuggestion,
    Order,
    ProofMedia,
    ServiceArea,
    User,
    Vehicle,
)
from . import duty


def _float(value) -> float:
    return float(value or 0)


def overview() -> dict:
    now = domain.utcnow()
    day_start = duty.today_start()

    orders = Order.query.all()
    status_counts = {status: 0 for status in domain.ORDER_STATUSES}
    for order in orders:
        status_counts[order.status] = status_counts.get(order.status, 0) + 1

    batches = DeliveryBatch.query.all()
    batch_counts = {status: 0 for status in domain.BATCH_STATUSES}
    for batch in batches:
        batch_counts[batch.status] = batch_counts.get(batch.status, 0) + 1

    measured_batches = [
        batch
        for batch in batches
        if batch.status != domain.BATCH_CANCELLED and _float(batch.baseline_km) > 0
    ]
    baseline_km = sum(_float(batch.baseline_km) for batch in measured_batches)
    shared_km = sum(_float(batch.distance_km) for batch in measured_batches)
    saved_km = max(0.0, baseline_km - shared_km)
    fuel_factor = float(current_app.config.get("SUSTAINABILITY_FUEL_L_PER_KM", 0.07))
    co2_factor = float(
        current_app.config.get("SUSTAINABILITY_KG_CO2E_PER_LITRE", 2.68)
    )
    fuel_saved = saved_km * fuel_factor
    co2_saved = fuel_saved * co2_factor

    suggestions = MatchingSuggestion.query.all()
    suggestion_counts = {status: 0 for status in domain.SUGGESTION_STATUSES}
    for row in suggestions:
        suggestion_counts[row.status] = suggestion_counts.get(row.status, 0) + 1
    reviewed = suggestion_counts[domain.SUGGESTION_APPROVED] + suggestion_counts[
        domain.SUGGESTION_REJECTED
    ]
    approved_detours = [
        _float(row.detour_km)
        for row in suggestions
        if row.status == domain.SUGGESTION_APPROVED
    ]

    drivers = User.query.filter_by(role=domain.ROLE_DRIVER).all()
    open_duty = [
        profile
        for profile in DriverProfile.query.all()
        if duty.active_session(profile) is not None
    ]
    vehicles = Vehicle.query.all()

    area_rows = []
    for area in ServiceArea.query.filter_by(is_active=True).order_by(ServiceArea.name).all():
        area_orders = [
            order
            for order in orders
            if order.pickup_address
            and order.pickup_address.area.casefold() == area.name.casefold()
        ]
        delivered = [o for o in area_orders if o.status in (domain.ORDER_DELIVERED, domain.ORDER_RETURNED)]
        failed = [o for o in area_orders if o.status == domain.ORDER_FAILED]
        active = [o for o in area_orders if o.status in domain.ACTIVE_ORDER_STATUSES]
        area_rows.append(
            {
                "id": area.id,
                "name": area.name,
                "city": area.city,
                "radius_km": _float(area.radius_km),
                "orders": len(area_orders),
                "active": len(active),
                "delivered": len(delivered),
                "failed": len(failed),
                "drivers": len(
                    [
                        link
                        for link in area.drivers
                        if link.driver
                        and link.driver.verification_status == domain.VERIFICATION_VERIFIED
                    ]
                ),
            }
        )

    return {
        "generated_at": domain.iso(now),
        "orders": {
            "total": len(orders),
            "by_status": status_counts,
            "active": sum(1 for order in orders if order.status in domain.ACTIVE_ORDER_STATUSES),
            "delivered": status_counts[domain.ORDER_DELIVERED],
            "returned": status_counts[domain.ORDER_RETURNED],
            "failed": status_counts[domain.ORDER_FAILED],
            "cancelled": status_counts[domain.ORDER_CANCELLED],
            "today": sum(
                1 for order in orders if order.created_at and order.created_at >= day_start
            ),
            "delivered_today": sum(
                1
                for order in orders
                if order.status == domain.ORDER_DELIVERED
                and order.delivered_at is not None
                and order.delivered_at >= day_start
            ),
        },
        "batches": {
            "total": len(batches),
            "by_status": batch_counts,
            "active": batch_counts[domain.BATCH_ACTIVE]
            + batch_counts[domain.BATCH_ASSIGNED],
            "completed": batch_counts[domain.BATCH_COMPLETED],
        },
        "fleet": {
            "drivers": len(drivers),
            "verified_drivers": sum(
                1
                for driver in drivers
                if driver.driver_profile
                and driver.driver_profile.verification_status == domain.VERIFICATION_VERIFIED
            ),
            "on_duty": len(open_duty),
            "vehicles": len(vehicles),
            "active_vehicles": sum(1 for vehicle in vehicles if vehicle.is_active),
        },
        "matching": {
            "suggestions": len(suggestions),
            "by_status": suggestion_counts,
            "approval_rate_pct": round(
                suggestion_counts[domain.SUGGESTION_APPROVED] / reviewed * 100, 1
            )
            if reviewed
            else None,
            "average_added_detour_km": round(
                sum(approved_detours) / len(approved_detours), 2
            )
            if approved_detours
            else None,
        },
        "sustainability": {
            "batches_measured": len(measured_batches),
            "baseline_km": round(baseline_km, 2),
            "shared_km": round(shared_km, 2),
            "estimated_distance_saved_km": round(saved_km, 2),
            "estimated_savings_percent": round(saved_km / baseline_km * 100, 1)
            if baseline_km
            else 0.0,
            "estimated_fuel_saved_l": round(fuel_saved, 2),
            "estimated_co2e_avoided_kg": round(co2_saved, 2),
            "factors": {
                "fuel_l_per_km": fuel_factor,
                "kg_co2e_per_litre": co2_factor,
            },
            "distance_sources": sorted(
                {batch.distance_source for batch in measured_batches}
            ),
        },
        "service_areas": area_rows,
        "exceptions": {
            "open": DeliveryException.query.filter_by(status=domain.EXCEPTION_OPEN).count(),
            "resolved": DeliveryException.query.filter_by(
                status=domain.EXCEPTION_RESOLVED
            ).count(),
        },
        "proofs": {
            "total": ProofMedia.query.count(),
            "pending": ProofMedia.query.filter_by(
                verification_status=domain.PROOF_PENDING
            ).count(),
        },
        "disclaimer": (
            "Distance, fuel and CO₂e figures are modelled estimates derived from "
            "stored batch routes and configured factors. They are not measured "
            "telemetry and must not be presented as verified savings."
        ),
    }


def admin_summary() -> dict:
    data = overview()
    consumers = User.query.filter_by(role=domain.ROLE_CONSUMER).all()
    from ..models import BusinessProfile, ManagerProfile

    data["accounts"] = {
        "consumers": len(consumers),
        "business_consumers": BusinessProfile.query.count(),
        "managers": ManagerProfile.query.count(),
        "drivers": len(User.query.filter_by(role=domain.ROLE_DRIVER).all()),
        "admins": len(User.query.filter_by(role=domain.ROLE_ADMIN).all()),
        "suspended": sum(
            1 for user in User.query.all() if user.status == domain.USER_SUSPENDED
        ),
        "pending_activation": sum(
            1 for user in User.query.all() if user.status == domain.USER_PENDING_ACTIVATION
        ),
    }
    data["proofs"]["reviewed"] = max(
        0,
        data["proofs"]["total"]
        - data["proofs"]["pending"],
    )
    data["active_assignments"] = DriverAssignment.query.filter_by(status="active").count()
    data["open_exceptions"] = data["exceptions"]["open"]
    return data


def sustainability_report() -> dict:
    data = overview()
    return {
        "generated_at": data["generated_at"],
        "totals": data["sustainability"],
        "service_areas": data["service_areas"],
        "methodology": [
            "Each batch stores a baseline distance (one direct pickup→destination trip per order) and a shared route distance on the same routing basis.",
            "Estimated distance saved = max(0, baseline − shared route), excluding cancelled batches.",
            "Fuel and CO₂e use configurable factors; they are estimates, not measurements.",
            "Partner repositioning to the first pickup is excluded from both distances and disclosed here.",
        ],
        "disclaimer": data["disclaimer"],
    }


def service_area_report(area_id: int) -> dict | None:
    for row in overview()["service_areas"]:
        if row["id"] == area_id:
            return row
    return None
