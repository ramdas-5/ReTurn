"""Route-aware matching suggestions for manager dispatch.

A pending order is evaluated against each eligible, on-duty driver that already
has an active route: the driver's remaining stops are re-planned with the new
pickup and delivery inserted, the added distance/duration is measured against
the current remaining route, and every hard constraint is reported as a
machine-readable blocker. This is a deterministic insertion heuristic — it is
not AI or machine learning, and distances follow the routing provider's
labelled source (OSRM or an explicit estimate).

Nothing here assigns work on its own: a suggestion is only a recommendation,
and the manager's approval revalidates all constraints before dispatch.
"""
from __future__ import annotations

from datetime import timedelta

from .. import domain
from ..errors import ApiError
from ..extensions import db
from ..models import MatchingSuggestion
from . import dispatch
from .notifications import MATCHING_OPPORTUNITY, notify_responsible_managers
from .route_planner import (
    as_utc,
    config,
    distance_along_sequence,
    nearest_route_distance_km,
    plan,
    stop_from_route_stop,
    stops_for_order,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _dedupe(rows: list[dict]) -> list[dict]:
    return list({row["code"]: row for row in rows}.values())


def pending_stops(route_plan) -> list[dict]:
    """Remaining (not started/completed) stops of an active route plan."""
    if route_plan is None:
        return []
    return [
        stop_from_route_stop(stop)
        for stop in route_plan.stops
        if stop.status in (domain.STOP_PENDING, domain.STOP_ARRIVED)
    ]


def _sequence(planned: dict) -> list[dict]:
    return [
        {
            "sequence": row["sequence"],
            "order_id": row["order_id"],
            "order_number": row.get("order_number"),
            "kind": row["kind"],
            "planned_arrival": domain.iso(row["planned_arrival"]),
            "planned_departure": domain.iso(row["planned_departure"]),
            "leg_distance_km": row["leg_distance_km"],
            "leg_duration_minutes": row["leg_duration_minutes"],
            "load_weight_kg": row["load_weight_kg"],
            "late": row["late"],
        }
        for row in planned.get("stops", [])
    ]


def _score(detour_km: float, max_detour_km: float) -> float:
    """0–100: a smaller detour relative to the configured limit scores higher."""
    if max_detour_km <= 0:
        return 0.0
    ratio = min(max(detour_km, 0.0), max_detour_km) / max_detour_km
    return round((1.0 - ratio) * 100.0, 2)


def _empty_evaluation(driver_user, profile, vehicle, batch, route_plan, blockers) -> dict:
    return {
        "driver": driver_user,
        "profile": profile,
        "vehicle": vehicle,
        "batch": batch,
        "route_plan": route_plan,
        "blockers": blockers,
        "compatible": not blockers,
        "snapshot": {},
        "capacity": None,
        "detour_km": 0.0,
        "added_duration_minutes": 0.0,
        "current_distance_km": 0.0,
        "proposed_distance_km": 0.0,
        "pickup_route_distance_km": None,
        "baseline_km": None,
        "distance_source": "estimated",
        "score": 0.0,
        "reasons": [],
        "proposed_sequence": [],
    }


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #
def evaluate_candidate(order, driver_user) -> dict:
    """Evaluate one driver for one order against their active route."""
    eligibility = dispatch.driver_eligibility(
        order, driver_user, require_active_route=True
    )
    profile = eligibility["profile"]
    vehicle = eligibility["vehicle"]
    batch = eligibility["batch"]
    route_plan = eligibility["route_plan"]
    blockers = list(eligibility["blockers"])

    cfg = config()
    max_detour = float(cfg.get("max_detour_km", 6.0))
    max_radius = float(cfg.get("max_pickup_radius_km", 5.0))
    now = domain.utcnow()

    result = _empty_evaluation(driver_user, profile, vehicle, batch, route_plan, blockers)

    if order.parcel is None or order.pickup_address is None or order.delivery_address is None:
        blockers.append(
            dispatch.blocker(
                "order_not_assignable", "The order is missing parcel or address data."
            )
        )

    existing = pending_stops(route_plan)
    if route_plan is not None and not existing:
        blockers.append(
            dispatch.blocker("no_active_route", "Every stop on the route is already closed.")
        )

    if blockers:
        result["blockers"] = _dedupe(blockers)
        result["compatible"] = False
        return result

    start_lat, start_lng, start_source = dispatch.start_point(profile, existing[0])
    if start_lat is None or start_lng is None:
        blockers.append(
            dispatch.blocker(
                "no_active_route", "No start point is available for the current route."
            )
        )
        result["blockers"] = _dedupe(blockers)
        result["compatible"] = False
        return result

    pickup = order.pickup_address
    corridor_km = nearest_route_distance_km(
        float(pickup.latitude),
        float(pickup.longitude),
        (start_lat, start_lng),
        existing,
    )
    if corridor_km > max_radius:
        blockers.append(
            dispatch.blocker(
                "pickup_too_far_from_route",
                (
                    f"The pickup is {corridor_km:.2f} km from the active route corridor "
                    f"(limit {max_radius:g} km)."
                ),
            )
        )

    new_stops = stops_for_order(order, cfg=cfg)
    current = plan(
        existing,
        start_latitude=start_lat,
        start_longitude=start_lng,
        start_time=now,
        cfg=cfg,
    )
    proposed = plan(
        existing + new_stops,
        start_latitude=start_lat,
        start_longitude=start_lng,
        start_time=now,
        cfg=cfg,
    )

    detour = max(0.0, round(proposed["distance_km"] - current["distance_km"], 3))
    added_duration = max(0.0, round(proposed["duration_minutes"] - current["duration_minutes"], 1))
    if detour > max_detour:
        blockers.append(
            dispatch.blocker(
                "route_detour_too_large",
                f"Adding this order would detour {detour:.2f} km (limit {max_detour:g} km).",
            )
        )

    late_rows = [row for row in proposed["stops"] if row["late"]]
    for row in late_rows:
        if row["kind"] == domain.STOP_DELIVERY:
            blockers.append(
                dispatch.blocker(
                    "delivery_deadline_conflict",
                    "A delivery on the proposed route would miss its deadline.",
                )
            )
        else:
            blockers.append(
                dispatch.blocker(
                    "pickup_window_conflict",
                    "A pickup on the proposed route would miss its window.",
                )
            )
    if any(row["order_id"] == order.id and row["kind"] == domain.STOP_DELIVERY for row in late_rows):
        blockers.append(
            dispatch.blocker(
                "delivery_deadline_conflict",
                "This order's delivery deadline cannot be met on the current route.",
            )
        )

    # Same-basis direct trip for this order alone (labelled estimate/OSRM).
    baseline_km, _baseline_minutes = distance_along_sequence(
        new_stops,
        start_latitude=float(pickup.latitude),
        start_longitude=float(pickup.longitude),
        cfg=cfg,
    )

    capacity = (
        dispatch.capacity_snapshot(eligibility["snapshot"], vehicle, [order.parcel])
        if vehicle is not None
        else None
    )

    reasons: list[dict] = [
        {
            "code": "pickup_on_route",
            "label": f"Pickup is {corridor_km:.2f} km from the active route corridor.",
        },
        {
            "code": "detour",
            "label": (
                f"Adding the order changes the estimated route by {detour:.2f} km "
                f"and {added_duration:.0f} minutes."
            ),
        },
        {
            "code": "precedence",
            "label": "The pickup is scheduled before this parcel's delivery.",
        },
        {
            "code": "distance_source",
            "label": f"Distance source: {proposed['distance_source']}.",
        },
    ]
    if capacity is not None:
        reasons.append(
            {
                "code": "capacity",
                "label": (
                    f"Projected load {capacity['projected']['weight_kg']:g} kg of "
                    f"{capacity['max_weight_kg']:g} kg with all active work included."
                ),
            }
        )
    reasons.append(
        {
            "code": "start_point",
            "label": f"Route start point: {start_source.replace('_', ' ')}.",
        }
    )

    result.update(
        {
            "blockers": _dedupe(blockers),
            "compatible": not blockers,
            "snapshot": eligibility["snapshot"],
            "capacity": capacity,
            "detour_km": detour,
            "added_duration_minutes": added_duration,
            "current_distance_km": current["distance_km"],
            "proposed_distance_km": proposed["distance_km"],
            "pickup_route_distance_km": corridor_km,
            "baseline_km": baseline_km,
            "distance_source": proposed["distance_source"],
            "score": _score(detour, max_detour),
            "reasons": reasons,
            "proposed_sequence": _sequence(proposed),
        }
    )
    return result


# --------------------------------------------------------------------------- #
# Scan and persistence
# --------------------------------------------------------------------------- #
def notify_opportunity(order, suggestion_count: int, actor=None) -> None:
    address = order.pickup_address
    notify_responsible_managers(
        MATCHING_OPPORTUNITY,
        f"On-route opportunity for {order.order_number}",
        (
            f"{suggestion_count} compatible driver(s) already travelling a suitable route "
            "can take this pickup. Review the recommendation before assigning."
        ),
        area_name=address.area if address else None,
        latitude=address.latitude if address else None,
        longitude=address.longitude if address else None,
        link=f"/manager/orders/{order.id}",
        event_data={"order_id": order.id, "suggestions": suggestion_count},
        exclude_ids={actor.id} if actor is not None else None,
    )


def scan_order(order, actor, *, notify: bool = True) -> dict:
    """Evaluate every driver visible to the manager and store feasible suggestions."""
    now = domain.utcnow()
    for previous in MatchingSuggestion.query.filter_by(
        order_id=order.id, status=domain.SUGGESTION_PENDING
    ).all():
        previous.status = domain.SUGGESTION_SUPERSEDED
        previous.reviewed_at = now
        previous.decision_note = previous.decision_note or "Superseded by a newer scan."
    db.session.flush()

    cfg = config()
    ttl_minutes = int(cfg.get("suggestion_ttl_minutes", 45))
    evaluations: list[dict] = []
    created: list[MatchingSuggestion] = []

    for driver in dispatch.drivers_for_actor(actor):
        evaluation = evaluate_candidate(order, driver)
        evaluations.append(evaluation)
        if not evaluation["compatible"]:
            continue
        suggestion = MatchingSuggestion(
            order_id=order.id,
            driver_id=driver.id,
            batch_id=evaluation["batch"].id if evaluation["batch"] else None,
            route_plan_id=(
                evaluation["route_plan"].id if evaluation["route_plan"] else None
            ),
            status=domain.SUGGESTION_PENDING,
            score=evaluation["score"],
            detour_km=evaluation["detour_km"],
            added_duration_minutes=evaluation["added_duration_minutes"],
            distance_source=evaluation["distance_source"],
            capacity_snapshot=evaluation["capacity"] or {},
            reasons=evaluation["reasons"],
            blockers=[],
            proposed_sequence=evaluation["proposed_sequence"],
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        db.session.add(suggestion)
        created.append(suggestion)

    db.session.flush()
    if created and notify:
        notify_opportunity(order, len(created), actor)
    return {"order": order, "evaluations": evaluations, "created": created}


# --------------------------------------------------------------------------- #
# Manager decisions
# --------------------------------------------------------------------------- #
def approve_suggestion(suggestion: MatchingSuggestion, actor):
    """Revalidate and assign the order, extending the driver's active route."""
    if suggestion.status != domain.SUGGESTION_PENDING:
        raise ApiError(
            "suggestion_not_pending",
            "That suggestion has already been reviewed or superseded.",
            409,
            details={"status": suggestion.status},
        )
    expires = as_utc(suggestion.expires_at)
    if expires is not None and expires <= domain.utcnow():
        suggestion.status = domain.SUGGESTION_EXPIRED
        raise ApiError(
            "suggestion_expired",
            "That suggestion has expired. Run the scan again.",
            409,
        )

    order = suggestion.order
    if order is None:
        raise ApiError("not_found", "That order no longer exists.", 404)
    if order.status != domain.ORDER_AWAITING_ASSIGNMENT:
        raise ApiError(
            "order_not_assignable",
            "This order is no longer awaiting assignment.",
            409,
            details={"status": order.status},
        )

    evaluation = evaluate_candidate(order, suggestion.driver)
    if not evaluation["compatible"]:
        raise ApiError(
            "driver_not_eligible",
            "The driver or route changed and this suggestion is no longer feasible.",
            409,
            details={
                "driver_id": suggestion.driver_id,
                "blockers": evaluation["blockers"],
            },
        )

    now = domain.utcnow()
    assignment = dispatch.assign_order(
        order,
        suggestion.driver,
        actor=actor,
        vehicle_id=evaluation["vehicle"].id if evaluation["vehicle"] else None,
        source="manager",
        reason=(
            f"Approved on-route suggestion: adds {evaluation['detour_km']:.2f} km "
            "to the active route"
        ),
    )
    suggestion.status = domain.SUGGESTION_APPROVED
    suggestion.reviewed_by_id = getattr(actor, "id", None)
    suggestion.reviewed_at = now
    suggestion.batch_id = assignment.batch_id
    suggestion.route_plan_id = assignment.route_plan_id
    suggestion.detour_km = evaluation["detour_km"]
    suggestion.added_duration_minutes = evaluation["added_duration_minutes"]
    suggestion.score = evaluation["score"]
    suggestion.capacity_snapshot = evaluation["capacity"] or {}
    suggestion.reasons = evaluation["reasons"]
    suggestion.proposed_sequence = evaluation["proposed_sequence"]

    for other in MatchingSuggestion.query.filter(
        MatchingSuggestion.order_id == order.id,
        MatchingSuggestion.id != suggestion.id,
        MatchingSuggestion.status == domain.SUGGESTION_PENDING,
    ).all():
        other.status = domain.SUGGESTION_SUPERSEDED
        other.reviewed_at = now
        other.decision_note = "Order assigned from another recommendation."

    from .audit import audit

    audit(
        "matching.suggestion_approved",
        "order",
        order.id,
        actor=actor,
        summary=(
            f"On-route suggestion approved for {order.order_number}: "
            f"{suggestion.driver.full_name if suggestion.driver else 'driver'}"
        ),
        event_metadata={
            "suggestion_id": suggestion.id,
            "driver_id": suggestion.driver_id,
            "detour_km": evaluation["detour_km"],
        },
    )
    return suggestion, assignment


def reject_suggestion(
    suggestion: MatchingSuggestion, actor, note: str, code: str | None = None
) -> MatchingSuggestion:
    if suggestion.status != domain.SUGGESTION_PENDING:
        raise ApiError(
            "suggestion_not_pending",
            "That suggestion has already been reviewed or superseded.",
            409,
            details={"status": suggestion.status},
        )
    suggestion.status = domain.SUGGESTION_REJECTED
    suggestion.reviewed_by_id = getattr(actor, "id", None)
    suggestion.reviewed_at = domain.utcnow()
    suggestion.decision_note = note[:500]
    suggestion.rejection_code = (code or "manager_rejected")[:80]

    from .audit import audit

    audit(
        "matching.suggestion_rejected",
        "order",
        suggestion.order_id,
        actor=actor,
        summary="On-route suggestion rejected by a manager",
        reason=note,
        event_metadata={"suggestion_id": suggestion.id, "code": suggestion.rejection_code},
    )
    return suggestion
