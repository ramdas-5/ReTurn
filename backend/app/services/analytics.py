"""Operational analytics and honest, estimated sustainability reporting."""
from __future__ import annotations

from datetime import timedelta

from flask import current_app
from sqlalchemy import func

from ..domain import (
    BATCH_ACCEPTED,
    BATCH_CANCELLED,
    BATCH_COMPLETED,
    BATCH_IN_PROGRESS,
    BATCH_OFFERED,
    BATCH_PROPOSED,
    BATCH_STATUSES,
    ISSUE_OPEN,
    ISSUE_IN_REVIEW,
    PARCEL_DELIVERED,
    PARTNER_PENDING,
    REQUEST_BATCHED,
    REQUEST_COMPLETED,
    REQUEST_FAILED,
    REQUEST_IN_PROGRESS,
    REQUEST_PENDING,
    REQUEST_STATUSES,
    iso,
    batch_code,
    utcnow,
)
from ..extensions import db
from ..models import DeliveryBatch, DeliveryRequest, IssueReport, Parcel, PartnerProfile, User


def _count(query) -> int:
    return int(query.count())


def summary() -> dict:
    since = utcnow() - timedelta(days=13)
    request_counts = {
        status: _count(DeliveryRequest.query.filter(DeliveryRequest.status == status))
        for status in REQUEST_STATUSES
    }
    batch_counts = {
        status: _count(DeliveryBatch.query.filter(DeliveryBatch.status == status))
        for status in BATCH_STATUSES
    }
    volume_rows = (
        db.session.query(
            func.date(DeliveryRequest.created_at).label("day"),
            func.count(DeliveryRequest.id),
        )
        .filter(DeliveryRequest.created_at >= since)
        .group_by(func.date(DeliveryRequest.created_at))
        .order_by(func.date(DeliveryRequest.created_at))
        .all()
    )
    volume = [{"day": str(row[0]), "count": int(row[1])} for row in volume_rows]

    service_mix = [
        {"type": row[0], "count": int(row[1])}
        for row in db.session.query(DeliveryRequest.type, func.count(DeliveryRequest.id))
        .group_by(DeliveryRequest.type)
        .all()
    ]
    committed = DeliveryBatch.query.filter(
        DeliveryBatch.status.in_(
            [BATCH_PROPOSED, BATCH_OFFERED, BATCH_ACCEPTED, BATCH_IN_PROGRESS, BATCH_COMPLETED]
        )
    ).all()
    avg_savings = (
        round(sum(float(batch.savings_percent) for batch in committed) / len(committed), 1)
        if committed
        else 0.0
    )
    recent_batches = (
        DeliveryBatch.query.order_by(DeliveryBatch.created_at.desc()).limit(6).all()
    )
    recent_issues = (
        IssueReport.query.filter(IssueReport.status.in_([ISSUE_OPEN, ISSUE_IN_REVIEW]))
        .order_by(IssueReport.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        "generated_at": iso(utcnow()),
        "request_counts": request_counts,
        "batch_counts": batch_counts,
        "pending_requests": request_counts[REQUEST_PENDING],
        "proposed_batches": batch_counts[BATCH_PROPOSED],
        "active_routes": batch_counts[BATCH_ACCEPTED] + batch_counts[BATCH_IN_PROGRESS],
        "completed_parcels": _count(Parcel.query.filter(Parcel.status == PARCEL_DELIVERED)),
        "failed_parcels": _count(Parcel.query.filter(Parcel.status == "failed")),
        "open_issues": _count(
            IssueReport.query.filter(IssueReport.status.in_([ISSUE_OPEN, ISSUE_IN_REVIEW]))
        ),
        "pending_partner_verifications": _count(
            PartnerProfile.query.filter(PartnerProfile.verification_status == PARTNER_PENDING)
        ),
        "customers": _count(User.query.filter(User.role == "customer")),
        "partners": _count(User.query.filter(User.role == "partner")),
        "batched_requests": request_counts[REQUEST_BATCHED],
        "in_progress_requests": request_counts[REQUEST_IN_PROGRESS],
        "completed_requests": request_counts[REQUEST_COMPLETED],
        "failed_requests": request_counts[REQUEST_FAILED],
        "average_savings_percent": avg_savings,
        "request_volume": volume,
        "service_mix": service_mix,
        "recent_batches": [
            {
                "id": batch.id,
                "code": batch_code(batch.id),
                "status": batch.status,
                "distance_km": float(batch.distance_km),
                "baseline_km": float(batch.baseline_km),
                "savings_km": float(batch.savings_km),
                "savings_percent": float(batch.savings_percent),
                "distance_source": batch.distance_source,
                "created_at": iso(batch.created_at),
                "partner_name": batch.partner.name if batch.partner else None,
                "request_count": len([link for link in batch.request_links if link.released_at is None]),
            }
            for batch in recent_batches
        ],
        "recent_issues": [
            {
                "id": issue.id,
                "category": issue.category,
                "severity": issue.severity,
                "status": issue.status,
                "created_at": iso(issue.created_at),
                "request_code": DeliveryRequest.query.get(issue.request_id).code
                if issue.request_id
                else None,
            }
            for issue in recent_issues
        ],
        "disclaimer": "All operational savings shown are modelled estimates based on planned routes and stated assumptions.",
    }


def sustainability() -> dict:
    batches = (
        DeliveryBatch.query.filter(
            DeliveryBatch.status.in_(
                [BATCH_PROPOSED, BATCH_OFFERED, BATCH_ACCEPTED, BATCH_IN_PROGRESS, BATCH_COMPLETED]
            )
        )
        .order_by(DeliveryBatch.created_at.desc())
        .all()
    )
    fuel_factor = float(current_app.config["SUSTAINABILITY_FUEL_L_PER_KM"])
    co2_factor = float(current_app.config["SUSTAINABILITY_KG_CO2E_PER_LITRE"])
    rows = []
    total_baseline = 0.0
    total_shared = 0.0
    for batch in batches:
        baseline = float(batch.baseline_km)
        shared = float(batch.distance_km)
        saved = max(0.0, baseline - shared)
        fuel = round(saved * fuel_factor, 3)
        co2 = round(fuel * co2_factor, 3)
        total_baseline += baseline
        total_shared += shared
        rows.append(
            {
                "batch_id": batch.id,
                "code": batch_code(batch.id),
                "status": batch.status,
                "created_at": iso(batch.created_at),
                "request_count": len([link for link in batch.request_links if link.released_at is None]),
                "baseline_km": round(baseline, 2),
                "shared_km": round(shared, 2),
                "saved_km": round(saved, 2),
                "savings_percent": float(batch.savings_percent),
                "estimated_fuel_saved_l": fuel,
                "estimated_co2e_avoided_kg": co2,
                "distance_source": batch.distance_source,
            }
        )
    saved_total = max(0.0, total_baseline - total_shared)
    total_fuel = round(saved_total * fuel_factor, 3)
    total_co2 = round(total_fuel * co2_factor, 3)
    return {
        "generated_at": iso(utcnow()),
        "measured": False,
        "labelled": "estimated",
        "factors": {
            "fuel_l_per_km": fuel_factor,
            "kg_co2e_per_litre": co2_factor,
        },
        "totals": {
            "batches": len(batches),
            "baseline_km": round(total_baseline, 2),
            "shared_km": round(total_shared, 2),
            "estimated_distance_saved_km": round(saved_total, 2),
            "estimated_savings_percent": round(
                (saved_total / total_baseline * 100) if total_baseline else 0, 1
            ),
            "estimated_fuel_saved_l": total_fuel,
            "estimated_co2e_avoided_kg": total_co2,
        },
        "batches": rows,
        "methodology": [
            "Baseline: one direct pickup → destination trip per request, measured on the same distance basis as the shared route.",
            "Shared route: the ordered multi-stop itinerary stored with each batch, including the same stop service time.",
            "Partner repositioning to the first pickup is excluded from both figures.",
            f"Estimated fuel = estimated distance saved × {fuel_factor:g} L/km (configurable factor).",
            f"Estimated CO₂e = estimated fuel × {co2_factor:g} kg CO₂e/L (configurable factor).",
            "Figures are modelled estimates for planning and are not measured emissions or guaranteed trip removals.",
            "When the distance source is 'estimated', road routing was unavailable and distances use a documented road-factor approximation.",
        ],
        "disclaimer": "All savings are estimates based on modelled routes and stated assumptions. No live GPS, measured fuel use or verified emissions data is used.",
    }


def kpi_strip() -> dict:  # pragma: no cover - convenience for the dashboard
    data = summary()
    return {
        key: data[key]
        for key in (
            "pending_requests",
            "proposed_batches",
            "active_routes",
            "completed_parcels",
        )
    }
