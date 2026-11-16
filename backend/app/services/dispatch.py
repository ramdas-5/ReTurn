"""Driver eligibility, assignment and batch dispatch.

Every function here enforces the operational rules server-side: verified driver
and vehicle, a live duty session, service-area coverage, real capacity limits,
pickup-before-delivery precedence and one active assignment per order. Eligible
states and reasons are machine-readable so the manager UI can explain refusals.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from flask import current_app

from .. import domain
from ..errors import ApiError
from ..extensions import db
from ..models import (
    BatchOrder,
    DeliveryBatch,
    DriverAssignment,
    DriverLocationEvent,
    DriverProfile,
    DriverServiceArea,
    Order,
    RouteAssignmentHistory,
    RouteLeg,
    RoutePlan,
    RouteStop,
    User,
    Vehicle,
)
from . import availability, duty
from .audit import audit
from .notifications import (
    BATCH_ASSIGNED,
    ORDER_ASSIGNED,
    ORDER_STATUS,
    ROUTE_UPDATED,
    notify_driver,
    notify_user,
)
from .routing import haversine_km
from .route_planner import (
    as_utc,
    config,
    geometry,
    plan,
    stops_for_order,
    stops_for_orders,
)
from ..serializers import active_route_plan  # noqa: F401  (documented re-export)


# --------------------------------------------------------------------------- #
# Lookups and blockers
# --------------------------------------------------------------------------- #
def blocker(code: str, detail: str | None = None) -> dict:
    return {"code": code, "label": domain.rejection_label(code), "detail": detail}


def active_batch_for_driver(driver_user) -> tuple[DeliveryBatch | None, RoutePlan | None]:
    batches = (
        DeliveryBatch.query.filter(
            DeliveryBatch.driver_id == driver_user.id,
            DeliveryBatch.status.in_((domain.BATCH_ASSIGNED, domain.BATCH_ACTIVE)),
        )
        .order_by(DeliveryBatch.id.desc())
        .all()
    )
    for batch in batches:
        plan_row = next(
            (row for row in batch.route_plans if row.status == domain.ROUTE_ACTIVE),
            None,
        )
        if plan_row is not None:
            return batch, plan_row
    return (batches[0], None) if batches else (None, None)


def active_vehicle(profile: DriverProfile, vehicle_id: int | None = None) -> Vehicle:
    if vehicle_id is not None:
        vehicle = db.session.get(Vehicle, vehicle_id)
        if vehicle is None or vehicle.driver_id != profile.id:
            raise ApiError("vehicle_not_found", "That vehicle does not belong to the driver.", 404)
        if not vehicle.is_active:
            raise ApiError("vehicle_inactive", "That vehicle is not active.", 409)
        return vehicle
    vehicles = [row for row in profile.vehicles if row.is_active]
    if not vehicles:
        raise ApiError(
            "vehicle_missing",
            "The driver has no active vehicle. Add a vehicle before assigning work.",
            409,
            details={"blockers": [blocker("vehicle_missing")]},
        )
    verified = [
        row
        for row in vehicles
        if row.verification_status
        in (domain.VERIFICATION_VERIFIED, domain.VERIFICATION_NOT_REQUIRED)
    ]
    if not verified:
        raise ApiError(
            "vehicle_not_verified",
            "The driver's vehicle is not verified for operations.",
            409,
            details={"blockers": [blocker("vehicle_not_verified")]},
        )
    return verified[0]


def load_snapshot(driver_user) -> dict:
    """Current real workload from active assignments (terminal orders excluded)."""
    rows = (
        DriverAssignment.query.join(Order, Order.id == DriverAssignment.order_id)
        .filter(
            DriverAssignment.driver_id == driver_user.id,
            DriverAssignment.status == "active",
            Order.status.notin_(domain.TERMINAL_ORDER_STATUSES),
        )
        .all()
    )
    weight = Decimal("0")
    volume = Decimal("0")
    parcels = 0
    in_custody = 0
    orders = []
    for row in rows:
        order = row.order
        if order is None or order.parcel is None:
            continue
        weight += Decimal(str(order.parcel.weight_kg or 0))
        volume += Decimal(str(order.parcel.volume_m3 or 0))
        parcels += int(order.parcel.quantity or 1)
        if order.status in domain.IN_CUSTODY_STATUSES:
            in_custody += 1
        orders.append(
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "in_custody": order.status in domain.IN_CUSTODY_STATUSES,
            }
        )
    return {
        "orders": orders,
        "order_count": len(orders),
        "parcels": parcels,
        "weight_kg": float(weight),
        "volume_m3": float(volume),
        "in_custody": in_custody,
    }


def _capacity_of(vehicle: Vehicle):
    return vehicle.capacity_profile if vehicle is not None else None


def capacity_snapshot(snapshot: dict, vehicle: Vehicle, parcels: list) -> dict:
    capacity = _capacity_of(vehicle)
    weight = snapshot["weight_kg"] + sum(float(row.weight_kg or 0) for row in parcels)
    volume = snapshot["volume_m3"] + sum(float(row.volume_m3 or 0) for row in parcels)
    count = snapshot["parcels"] + sum(int(row.quantity or 1) for row in parcels)

    def pct(value, maximum):
        return round(value / float(maximum) * 100, 1) if maximum and float(maximum) > 0 else None

    return {
        "vehicle_id": vehicle.id if vehicle else None,
        "registration_number": vehicle.registration_number if vehicle else None,
        "capacity_profile_id": capacity.id if capacity else None,
        "capacity_profile_name": capacity.name if capacity else None,
        "max_weight_kg": float(capacity.max_weight_kg) if capacity else None,
        "max_volume_m3": float(capacity.max_volume_m3) if capacity else None,
        "max_parcels": capacity.max_parcels if capacity else None,
        "max_length_cm": float(capacity.max_length_cm) if capacity else None,
        "max_width_cm": float(capacity.max_width_cm) if capacity else None,
        "max_height_cm": float(capacity.max_height_cm) if capacity else None,
        "current": {
            "parcels": snapshot["parcels"],
            "weight_kg": snapshot["weight_kg"],
            "volume_m3": snapshot["volume_m3"],
        },
        "projected": {
            "parcels": count,
            "weight_kg": round(weight, 3),
            "volume_m3": round(volume, 5),
        },
        "weight_utilisation_pct": pct(weight, getattr(capacity, "max_weight_kg", None)),
        "volume_utilisation_pct": pct(volume, getattr(capacity, "max_volume_m3", None)),
        "parcel_utilisation_pct": pct(count, getattr(capacity, "max_parcels", None)),
    }


def capacity_blockers(vehicle: Vehicle, parcels: list, snapshot: dict) -> list[dict]:
    capacity = _capacity_of(vehicle)
    rows: list[dict] = []
    if capacity is None:
        return [blocker("vehicle_missing", "The vehicle has no capacity profile.")]
    projected = capacity_snapshot(snapshot, vehicle, parcels)["projected"]
    if capacity.max_weight_kg is not None and projected["weight_kg"] > float(capacity.max_weight_kg):
        rows.append(blocker("vehicle_capacity_exceeded", "Projected weight exceeds the vehicle limit."))
    if capacity.max_volume_m3 is not None and projected["volume_m3"] > float(capacity.max_volume_m3):
        rows.append(blocker("vehicle_capacity_exceeded", "Projected volume exceeds the vehicle limit."))
    if capacity.max_parcels is not None and projected["parcels"] > int(capacity.max_parcels):
        rows.append(blocker("vehicle_capacity_exceeded", "Projected parcel count exceeds the vehicle limit."))
    for parcel in parcels:
        for dimension, maximum in (
            ("length_cm", capacity.max_length_cm),
            ("width_cm", capacity.max_width_cm),
            ("height_cm", capacity.max_height_cm),
        ):
            if maximum is not None and float(getattr(parcel, dimension) or 0) > float(maximum):
                rows.append(
                    blocker(
                        "parcel_dimension_exceeded",
                        f"The parcel is larger than the vehicle's {dimension.replace('_cm', '')} limit.",
                    )
                )
                break
        if (parcel.is_fragile or "fragile" in parcel.handling_list) and not capacity.supports_fragile:
            rows.append(blocker("handling_restriction_conflict", "This vehicle cannot carry fragile parcels."))
        if "restricted" in parcel.handling_list and not capacity.supports_restricted:
            rows.append(blocker("handling_restriction_conflict", "This vehicle cannot carry restricted parcels."))

    defaults = current_app.config.get("MATCHING_DEFAULTS", {})
    max_workload = int(defaults.get("max_workload_parcels", 12))
    if projected["parcels"] > max_workload:
        rows.append(blocker("workload_limit_exceeded", f"The safe workload is {max_workload} parcels."))
    max_weight_pct = float(defaults.get("max_workload_weight_pct", 90.0))
    if capacity.max_weight_kg and float(capacity.max_weight_kg) > 0:
        used_pct = projected["weight_kg"] / float(capacity.max_weight_kg) * 100
        if used_pct > max_weight_pct:
            rows.append(
                blocker(
                    "workload_limit_exceeded",
                    f"Weight would reach {used_pct:.1f}% of capacity (safe limit {max_weight_pct:g}%).",
                )
            )
    return rows


def duty_blockers(profile: DriverProfile) -> list[dict]:
    session = duty.active_session(profile)
    if session is None:
        return [blocker("driver_off_duty", "Start a duty session first.")]
    if not duty.session_is_recent(session):
        return [blocker("driver_not_available", "The duty heartbeat is stale.")]
    if session.status == domain.DUTY_ON_BREAK:
        return [blocker("driver_on_break", "The driver is on a break.")]
    if session.status not in domain.ACCEPTING_WORK_STATUSES:
        return [blocker("driver_not_available", f"Duty status is {session.status}.")]
    return []


def service_area_blockers(profile: DriverProfile, order: Order) -> list[dict]:
    rows: list[dict] = []
    for kind, address in (
        ("pickup", order.pickup_address),
        ("delivery", order.delivery_address),
    ):
        if address is None or not availability.driver_covers_point(
            profile, address.area, address.latitude, address.longitude
        ):
            rows.append(
                blocker(
                    "service_area_unsupported",
                    f"The {kind} point is outside the driver's service areas.",
                )
            )
    return rows


def profile_for(driver_user) -> DriverProfile:
    profile = getattr(driver_user, "driver_profile", None)
    if profile is None:
        raise ApiError("driver_profile_missing", "This account has no driver profile.", 409)
    return profile


def driver_eligibility(
    order: Order,
    driver_user,
    *,
    vehicle_id: int | None = None,
    require_active_route: bool = False,
) -> dict:
    profile = profile_for(driver_user)
    blockers: list[dict] = []
    if driver_user.status != "active":
        blockers.append(blocker("driver_not_available", "The driver account is not active."))
    if profile.verification_status != domain.VERIFICATION_VERIFIED:
        blockers.append(blocker("driver_not_verified"))
    blockers.extend(duty_blockers(profile))
    blockers.extend(service_area_blockers(profile, order))
    try:
        vehicle = active_vehicle(profile, vehicle_id)
    except ApiError as error:
        vehicle = None
        blockers.append(blocker(error.code, error.message))
    snapshot = load_snapshot(driver_user)
    if vehicle is not None and order.parcel is not None:
        blockers.extend(capacity_blockers(vehicle, [order.parcel], snapshot))
    batch, plan_row = active_batch_for_driver(driver_user)
    if require_active_route and (batch is None or plan_row is None or batch.status != domain.BATCH_ACTIVE):
        blockers.append(blocker("no_active_route", "The driver has no active batch route to extend."))
    existing = (
        DriverAssignment.query.filter_by(order_id=order.id, status="active").first()
    )
    if existing is not None and existing.driver_id == driver_user.id:
        blockers.append(blocker("order_already_assigned", "This order is already assigned to the driver."))
    deduped = list({row["code"]: row for row in blockers}.values())
    return {
        "profile": profile,
        "vehicle": vehicle,
        "snapshot": snapshot,
        "batch": batch,
        "route_plan": plan_row,
        "blockers": deduped,
    }


def batch_capacity_blockers(
    vehicle: Vehicle, orders: list[Order], snapshot: dict
) -> list[dict]:
    parcels = [order.parcel for order in orders if order.parcel is not None]
    return capacity_blockers(vehicle, parcels, snapshot)


def _start_point(profile: DriverProfile, fallback_stop: dict | None):
    event = (
        DriverLocationEvent.query.filter_by(driver_id=profile.id)
        .order_by(DriverLocationEvent.received_at.desc())
        .first()
    )
    timeout = int(current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15))
    if event is not None:
        received = as_utc(event.received_at)
        if received and received >= domain.utcnow() - timedelta(minutes=timeout * 2):
            return (
                float(event.latitude),
                float(event.longitude),
                "live_driver_location",
            )
    if fallback_stop is not None:
        return (
            float(fallback_stop["latitude"]),
            float(fallback_stop["longitude"]),
            "first_pending_stop",
        )
    return (None, None, "unavailable")


def start_point(profile: DriverProfile, fallback_stop: dict | None):
    """Public alias used by the route-aware suggestion engine."""
    return _start_point(profile, fallback_stop)


def drivers_for_actor(actor) -> list[User]:
    """Active driver accounts a manager may dispatch, bounded by service areas."""
    query = (
        User.query.join(DriverProfile, DriverProfile.user_id == User.id)
        .filter(User.role == domain.ROLE_DRIVER, User.status == "active")
    )
    if actor.role == domain.ROLE_ADMIN:
        return query.order_by(User.full_name).all()
    profile = getattr(actor, "manager_profile", None)
    area_ids = (
        {link.service_area_id for link in profile.service_areas} if profile else set()
    )
    if not area_ids:
        return []
    driver_ids = db.select(DriverServiceArea.driver_id).where(
        DriverServiceArea.service_area_id.in_(area_ids)
    )
    return query.filter(DriverProfile.id.in_(driver_ids)).order_by(User.full_name).all()


# --------------------------------------------------------------------------- #
# Route persistence
# --------------------------------------------------------------------------- #
def rebuild_route(
    batch: DeliveryBatch,
    *,
    actor,
    start_time: datetime | None = None,
    reason: str | None = None,
) -> RoutePlan | None:
    links = [link for link in batch.order_links if link.removed_at is None]
    orders = [link.order for link in links if link.order is not None]
    if not orders:
        return None

    cfg = config()
    stops = stops_for_orders(orders, cfg=cfg)
    if not stops:
        return None
    driver_user = batch.driver
    profile = profile_for(driver_user) if driver_user is not None else None
    fallback = stops[0]
    latitude, longitude, start_source = (
        _start_point(profile, fallback) if profile is not None else (fallback["latitude"], fallback["longitude"], "first_pending_stop")
    )
    if latitude is None:
        return None
    starting_at = as_utc(start_time) or domain.utcnow()
    if batch.planned_start is not None and start_time is None:
        planned = as_utc(batch.planned_start)
        if planned and planned > starting_at and batch.status != domain.BATCH_ACTIVE:
            starting_at = planned
    result = plan(
        stops,
        start_latitude=latitude,
        start_longitude=longitude,
        start_time=starting_at,
        cfg=cfg,
    )
    if not result["stops"]:
        return None

    now = domain.utcnow()
    for row in batch.route_plans:
        if row.status == domain.ROUTE_ACTIVE:
            row.status = domain.ROUTE_SUPERSEDED
            row.superseded_at = now
    version = max((row.version for row in batch.route_plans), default=0) + 1

    track, track_source = geometry(result["stops"], cfg)
    route = RoutePlan(
        batch_id=batch.id,
        version=version,
        status=domain.ROUTE_ACTIVE,
        algorithm=result["algorithm"],
        distance_km=result["distance_km"],
        duration_minutes=round(result["duration_minutes"]),
        distance_source=result["distance_source"],
        geometry=track,
        geometry_source=track_source,
        metrics={
            "stop_count": len(result["stops"]),
            "precedence": result["precedence"],
            "start_point_source": start_source,
            "notes": result["notes"],
        },
        created_by_id=getattr(actor, "id", None),
        activated_at=now,
    )
    db.session.add(route)
    db.session.flush()

    stop_rows = []
    for row in result["stops"]:
        stop = RouteStop(
            route_plan_id=route.id,
            order_id=row["order_id"],
            kind=row["kind"],
            sequence=row["sequence"],
            label=str(row["label"])[:160],
            contact_name=str(row["contact_name"])[:160],
            contact_phone=(row.get("contact_phone") or None),
            address_line=str(row["address_line"])[:255],
            area=str(row["area"])[:120],
            city=str(row["city"])[:120],
            postal_code=(row.get("postal_code") or None),
            latitude=row["latitude"],
            longitude=row["longitude"],
            planned_arrival=row["planned_arrival"],
            planned_departure=row["planned_departure"],
            service_minutes=int(row.get("service_minutes") or cfg.get("service_minutes", 6)),
            leg_distance_km=row["leg_distance_km"],
            leg_duration_minutes=row["leg_duration_minutes"],
            load_weight_kg=row["load_weight_kg"],
            load_volume_m3=row["load_volume_m3"],
            status=domain.STOP_PENDING,
        )
        db.session.add(stop)
        stop_rows.append((stop, row))
    db.session.flush()

    previous_stop = None
    for stop, row in stop_rows:
        db.session.add(
            RouteLeg(
                route_plan_id=route.id,
                from_stop_id=previous_stop.id if previous_stop else None,
                to_stop_id=stop.id,
                sequence=row["sequence"],
                distance_km=row["leg_distance_km"],
                duration_minutes=row["leg_duration_minutes"],
                distance_source=result["distance_source"],
            )
        )
        previous_stop = stop

    batch.distance_km = result["distance_km"]
    batch.duration_minutes = round(result["duration_minutes"])
    batch.distance_source = result["distance_source"]
    batch.geometry = track
    batch.geometry_source = track_source
    batch.algorithm = result["algorithm"]
    batch.explanation = {
        "precedence": result["precedence"],
        "start_point_source": start_source,
        "distance_source": result["distance_source"],
        "notes": result["notes"],
        "stop_order": [
            {"sequence": row["sequence"], "kind": row["kind"], "order_number": row.get("order_number")}
            for row in result["stops"]
        ],
        "reason": reason,
    }
    batch.planned_end = result["end_time"]
    batch.version = max(batch.version or 1, version)

    for order in orders:
        assignment = (
            DriverAssignment.query.filter_by(order_id=order.id, status="active")
            .order_by(DriverAssignment.assigned_at.desc())
            .first()
        )
        if assignment is not None:
            assignment.batch_id = batch.id
            assignment.route_plan_id = route.id
            if batch.vehicle_id is not None:
                assignment.vehicle_id = batch.vehicle_id
    return route


# --------------------------------------------------------------------------- #
# Assignment
# --------------------------------------------------------------------------- #
def _assert_eligible(eligibility: dict, driver_user) -> None:
    if eligibility["blockers"]:
        raise ApiError(
            "driver_not_eligible",
            "This driver cannot take that order.",
            409,
            details={
                "driver_id": driver_user.id,
                "blockers": eligibility["blockers"],
            },
        )


def _assign_once(
    order: Order,
    driver_user,
    *,
    actor,
    vehicle: Vehicle,
    source: str,
    reason: str | None,
) -> DriverAssignment:
    batch, _plan = active_batch_for_driver(driver_user)
    if batch is not None and batch.status in (domain.BATCH_ASSIGNED, domain.BATCH_ACTIVE):
        link = (
            BatchOrder.query.filter_by(batch_id=batch.id, order_id=order.id)
            .filter(BatchOrder.removed_at.is_(None))
            .first()
        )
        if link is None:
            db.session.add(
                BatchOrder(batch_id=batch.id, order_id=order.id, added_by_id=getattr(actor, "id", None))
            )
            db.session.flush()
        assignment = DriverAssignment(
            order_id=order.id,
            driver_id=driver_user.id,
            batch_id=batch.id,
            vehicle_id=vehicle.id,
            assigned_by_id=getattr(actor, "id", None),
            status="active",
        )
        db.session.add(assignment)
        db.session.flush()
        route = rebuild_route(batch, actor=actor, start_time=domain.utcnow(), reason=reason)
        if route is not None:
            assignment.route_plan_id = route.id
    else:
        assignment = DriverAssignment(
            order_id=order.id,
            driver_id=driver_user.id,
            vehicle_id=vehicle.id,
            assigned_by_id=getattr(actor, "id", None),
            status="active",
        )
        db.session.add(assignment)
        db.session.flush()
        batch = None

    if order.status != domain.ORDER_ASSIGNED:
        from .orders import record_status

        record_status(
            order,
            domain.ORDER_ASSIGNED,
            actor=actor,
            source=source,
            reason=reason or "Driver assigned",
            event_metadata={
                "driver_id": driver_user.id,
                "vehicle_id": vehicle.id,
                "batch_id": batch.id if batch else None,
            },
        )
    db.session.add(
        RouteAssignmentHistory(
            order_id=order.id,
            batch_id=batch.id if batch else None,
            driver_id=driver_user.id,
            vehicle_id=vehicle.id,
            route_plan_id=assignment.route_plan_id,
            action="assigned",
            actor_id=getattr(actor, "id", None),
            reason=reason,
            event_metadata={"source": source},
        )
    )
    return assignment


def assign_order(
    order: Order,
    driver_user,
    *,
    actor,
    vehicle_id: int | None = None,
    source: str = "manager",
    reason: str | None = None,
) -> DriverAssignment:
    if order.status not in (domain.ORDER_AWAITING_ASSIGNMENT, domain.ORDER_ASSIGNED):
        raise ApiError(
            "order_not_assignable",
            "Only an approved order awaiting assignment can be assigned.",
            409,
            details={"status": order.status},
        )
    active = DriverAssignment.query.filter_by(order_id=order.id, status="active").first()
    if active is not None:
        raise ApiError(
            "order_already_assigned",
            "This order already has an active driver assignment. Use reassign instead.",
            409,
            details={"driver_id": active.driver_id, "assignment_id": active.id},
        )

    eligibility = driver_eligibility(order, driver_user, vehicle_id=vehicle_id)
    _assert_eligible(eligibility, driver_user)
    vehicle = eligibility["vehicle"]

    assignment = _assign_once(
        order,
        driver_user,
        actor=actor,
        vehicle=vehicle,
        source=source,
        reason=reason,
    )
    audit(
        "dispatch.order_assigned",
        "order",
        order.id,
        actor=actor,
        summary=f"Order {order.order_number} assigned to {driver_user.full_name}",
        reason=reason,
        event_metadata={"driver_id": driver_user.id, "source": source},
    )
    notify_driver(
        driver_user.id,
        ORDER_ASSIGNED,
        f"New task: {order.order_number}",
        f"Pickup in {order.pickup_address.area if order.pickup_address else 'your area'}."
        + (" Your route has been updated." if assignment.route_plan_id else ""),
        link=f"/driver/orders/{order.id}",
        event_data={"order_id": order.id, "route_plan_id": assignment.route_plan_id},
    )
    notify_user(
        order.consumer,
        ORDER_ASSIGNED,
        f"Order {order.order_number} assigned to a driver",
        "Your delivery partner is preparing the route.",
        link=f"/consumer/orders/{order.id}",
        event_data={"order_id": order.id},
    )
    return assignment


def reassign_order(
    order: Order,
    new_driver,
    *,
    actor,
    vehicle_id: int | None = None,
    reason: str,
) -> DriverAssignment:
    if order.status in domain.IN_CUSTODY_STATUSES:
        raise ApiError(
            "order_in_custody",
            "The parcel is already with a driver. Resolve the situation with a delivery exception.",
            409,
        )
    if order.status not in (
        domain.ORDER_ASSIGNED,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
    ):
        raise ApiError(
            "order_not_assignable",
            "This order cannot be reassigned in its current state.",
            409,
            details={"status": order.status},
        )

    previous = (
        DriverAssignment.query.filter_by(order_id=order.id, status="active")
        .order_by(DriverAssignment.assigned_at.desc())
        .first()
    )
    previous_driver = previous.driver if previous is not None else None
    now = domain.utcnow()
    old_batch = None
    if previous is not None:
        old_batch = previous.batch
        previous.status = "reassigned"
        previous.ended_at = now
        previous.end_reason = reason[:500]
        link = (
            BatchOrder.query.filter_by(order_id=order.id)
            .filter(BatchOrder.removed_at.is_(None))
            .first()
        )
        if link is not None:
            link.removed_at = now
            link.removed_reason = reason[:500]
            old_batch = link.batch
            db.session.flush()
    if old_batch is not None:
        remaining = [link for link in old_batch.order_links if link.removed_at is None]
        if remaining and old_batch.status in (domain.BATCH_ASSIGNED, domain.BATCH_ACTIVE):
            old_driver = old_batch.driver
            if old_driver is not None:
                rebuild_route(
                    old_batch,
                    actor=actor,
                    start_time=now,
                    reason=f"Order {order.order_number} reassigned",
                )
        elif not remaining and old_batch.status == domain.BATCH_ASSIGNED:
            old_batch.status = domain.BATCH_CANCELLED
            old_batch.cancelled_at = now
            old_batch.cancellation_reason = "All orders were reassigned."

    if order.status in (domain.ORDER_PICKUP_SCHEDULED, domain.ORDER_PICKUP_ARRIVED):
        from .orders import record_status

        record_status(
            order,
            domain.ORDER_AWAITING_ASSIGNMENT,
            actor=actor,
            source="manager",
            reason=f"Reassignment: {reason[:160]}",
        )

    assignment = assign_order(
        order,
        new_driver,
        actor=actor,
        vehicle_id=vehicle_id,
        source="manager",
        reason=reason,
    )
    audit(
        "dispatch.order_reassigned",
        "order",
        order.id,
        actor=actor,
        summary=(
            f"Order {order.order_number} reassigned"
            + (f" from {previous_driver.full_name}" if previous_driver else "")
            + f" to {new_driver.full_name}"
        ),
        reason=reason,
    )
    if previous_driver is not None:
        notify_driver(
            previous_driver.id,
            ORDER_STATUS,
            f"Task removed: {order.order_number}",
            "A manager reassigned this parcel. Check your updated route.",
            link=f"/driver/batches"
            if old_batch is not None
            else f"/driver/assignments",
            event_data={"order_id": order.id},
        )
    return assignment


# --------------------------------------------------------------------------- #
# Batches
# --------------------------------------------------------------------------- #
def _validate_batch_orders(orders: list[Order]) -> None:
    if not orders:
        raise ApiError("batch_empty", "Select at least one order for the batch.", 422)
    if len(orders) > 12:
        raise ApiError("batch_too_large", "Keep batches to 12 orders or fewer.", 422)
    ids = [order.id for order in orders]
    if len(set(ids)) != len(ids):
        raise ApiError("batch_duplicate_order", "Each order can appear only once.", 422)
    for order in orders:
        if order.status != domain.ORDER_AWAITING_ASSIGNMENT:
            raise ApiError(
                "order_not_assignable",
                f"Order {order.order_number} is not awaiting assignment.",
                409,
                details={"order_id": order.id, "status": order.status},
            )
        if DriverAssignment.query.filter_by(order_id=order.id, status="active").first():
            raise ApiError(
                "order_already_assigned",
                f"Order {order.order_number} already has an active assignment.",
                409,
                details={"order_id": order.id},
            )


def batch_candidate(orders: list[Order], driver_user) -> dict:
    profile = profile_for(driver_user)
    blockers: list[dict] = []
    if driver_user.status != "active":
        blockers.append(blocker("driver_not_available", "The driver account is not active."))
    if profile.verification_status != domain.VERIFICATION_VERIFIED:
        blockers.append(blocker("driver_not_verified"))
    blockers.extend(duty_blockers(profile))
    for order in orders:
        blockers.extend(service_area_blockers(profile, order))
    try:
        vehicle = active_vehicle(profile)
    except ApiError as error:
        vehicle = None
        blockers.append(blocker(error.code, error.message))
    snapshot = load_snapshot(driver_user)
    if vehicle is not None:
        blockers.extend(batch_capacity_blockers(vehicle, orders, snapshot))
    active_batch, _active_plan = active_batch_for_driver(driver_user)
    if active_batch is not None:
        blockers.append(
            blocker(
                "driver_has_active_batch",
                f"Driver already has batch {active_batch.batch_number}.",
            )
        )
    deduped = list({row["code"]: row for row in blockers}.values())
    result = {
        "driver": {
            "id": driver_user.id,
            "full_name": driver_user.full_name,
            "email": driver_user.email,
        },
        "vehicle": vehicle,
        "snapshot": snapshot,
        "compatible": not deduped,
        "blockers": deduped,
        "reasons": [],
        "route": None,
        "capacity": None,
    }
    if vehicle is not None:
        result["capacity"] = capacity_snapshot(snapshot, vehicle, [o.parcel for o in orders if o.parcel])
    if deduped:
        return result

    cfg = config()
    stops = stops_for_orders(orders, cfg=cfg)
    latitude, longitude, start_source = _start_point(profile, stops[0] if stops else None)
    if latitude is None:
        result["compatible"] = False
        result["blockers"] = [blocker("no_active_route", "No start point is available for planning.")]
        return result
    planned = plan(
        stops,
        start_latitude=latitude,
        start_longitude=longitude,
        start_time=domain.utcnow(),
        cfg=cfg,
    )
    late_rows = [row for row in planned["stops"] if row["late"]]
    if late_rows:
        codes = {
            "delivery_deadline_conflict"
            if row["kind"] == domain.STOP_DELIVERY
            else "pickup_window_conflict"
            for row in late_rows
        }
        for code in codes:
            result["blockers"].append(blocker(code, "At least one stop would miss its window."))
        result["compatible"] = False
    result["route"] = _compact_route(planned)
    result["reasons"] = [
        {"code": "route_planned", "label": "Deterministic pickups-first route proposed."},
        {
            "code": "distance_estimate",
            "label": f"Distance source: {planned['distance_source']}.",
        },
    ]
    return result


def _compact_route(planned: dict) -> dict:
    return {
        "distance_km": planned["distance_km"],
        "duration_minutes": planned["duration_minutes"],
        "distance_source": planned["distance_source"],
        "algorithm": planned["algorithm"],
        "precedence": planned["precedence"],
        "notes": planned["notes"],
        "stops": [
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
                "arrival_late": row["late"],
            }
            for row in planned["stops"]
        ],
    }


def propose_batch(orders: list[Order], driver_user=None) -> dict:
    _validate_batch_orders(orders)
    if driver_user is not None:
        drivers = [driver_user]
    else:
        configured = int(
            current_app.config.get("MATCHING_DEFAULTS", {}).get("max_search_drivers", 25)
        )
        drivers = (
            User.query.join(DriverProfile, DriverProfile.user_id == User.id)
            .filter(User.role == domain.ROLE_DRIVER, User.status == "active")
            .order_by(User.full_name)
            .limit(configured)
            .all()
        )
    candidates = [batch_candidate(orders, driver) for driver in drivers]
    candidates.sort(
        key=lambda row: (
            not row["compatible"],
            row["route"]["distance_km"] if row["route"] else float("inf"),
            row["driver"]["full_name"],
        )
    )
    return {
        "order_ids": [order.id for order in orders],
        "order_count": len(orders),
        "candidates": candidates,
        "compatible": any(row["compatible"] for row in candidates),
    }


def create_batch(
    orders: list[Order],
    driver_user,
    *,
    actor,
    vehicle_id: int | None = None,
    planned_start: datetime | None = None,
    notes: str | None = None,
) -> DeliveryBatch:
    _validate_batch_orders(orders)
    profile = profile_for(driver_user)
    blockers: list[dict] = []
    if profile.verification_status != domain.VERIFICATION_VERIFIED:
        blockers.append(blocker("driver_not_verified"))
    blockers.extend(duty_blockers(profile))
    for order in orders:
        blockers.extend(service_area_blockers(profile, order))
    try:
        vehicle = active_vehicle(profile, vehicle_id)
    except ApiError as error:
        vehicle = None
        blockers.append(blocker(error.code, error.message))
    snapshot = load_snapshot(driver_user)
    if vehicle is not None:
        blockers.extend(batch_capacity_blockers(vehicle, orders, snapshot))
    active_batch, _active_plan = active_batch_for_driver(driver_user)
    if active_batch is not None:
        blockers.append(
            blocker(
                "driver_has_active_batch",
                f"Driver already has batch {active_batch.batch_number}.",
            )
        )
    if blockers:
        raise ApiError(
            "driver_not_eligible",
            "This driver cannot take that batch.",
            409,
            details={"driver_id": driver_user.id, "blockers": blockers},
        )

    start = as_utc(planned_start) or domain.utcnow()
    service_area = availability.area_for_point(
        orders[0].pickup_address.area if orders[0].pickup_address else None,
        float(orders[0].pickup_address.latitude) if orders[0].pickup_address else None,
        float(orders[0].pickup_address.longitude) if orders[0].pickup_address else None,
    )
    capacity = capacity_snapshot(
        snapshot, vehicle, [order.parcel for order in orders if order.parcel]
    )
    batch = DeliveryBatch(
        batch_number=f"PENDING-{uuid4().hex[:10].upper()}",
        status=domain.BATCH_ASSIGNED,
        manager_id=getattr(actor, "id", None),
        driver_id=driver_user.id,
        vehicle_id=vehicle.id,
        service_area_id=service_area.id if service_area else None,
        planned_start=start,
        planned_end=start,
        distance_km=0,
        duration_minutes=0,
        baseline_km=0,
        distance_source="estimated",
        geometry_source="estimated",
        algorithm="greedy nearest-feasible insertion (pickup-before-delivery)",
        explanation={
            "capacity_snapshot": capacity,
            "created_by": getattr(actor, "id", None),
            "notes": notes,
        },
        notes=notes,
        version=1,
    )
    db.session.add(batch)
    db.session.flush()
    batch.batch_number = domain.batch_number(batch.id)

    assignments = []
    for order in orders:
        db.session.add(
            BatchOrder(batch_id=batch.id, order_id=order.id, added_by_id=getattr(actor, "id", None))
        )
        assignment = DriverAssignment(
            order_id=order.id,
            driver_id=driver_user.id,
            batch_id=batch.id,
            vehicle_id=vehicle.id,
            assigned_by_id=getattr(actor, "id", None),
            status="active",
        )
        db.session.add(assignment)
        assignments.append((order, assignment))
    db.session.flush()

    from .orders import record_status

    for order, _assignment in assignments:
        record_status(
            order,
            domain.ORDER_ASSIGNED,
            actor=actor,
            source="manager",
            reason=f"Assigned to batch {batch.batch_number}",
            event_metadata={"batch_id": batch.id, "driver_id": driver_user.id},
        )
        db.session.add(
            RouteAssignmentHistory(
                order_id=order.id,
                batch_id=batch.id,
                driver_id=driver_user.id,
                vehicle_id=vehicle.id,
                action="batched",
                actor_id=getattr(actor, "id", None),
                reason=f"Batch {batch.batch_number} created",
                event_metadata={"batch_number": batch.batch_number},
            )
        )
    route = rebuild_route(batch, actor=actor, start_time=start, reason="Batch created")
    for _order, assignment in assignments:
        if route is not None:
            assignment.route_plan_id = route.id

    audit(
        "dispatch.batch_created",
        "batch",
        batch.id,
        actor=actor,
        summary=(
            f"Batch {batch.batch_number} created for {driver_user.full_name} "
            f"with {len(orders)} order(s)"
        ),
        event_metadata={"order_ids": [order.id for order in orders]},
    )
    notify_driver(
        driver_user.id,
        BATCH_ASSIGNED,
        f"New batch {batch.batch_number}",
        f"{len(orders)} parcel(s). Review the proposed stop sequence.",
        link=f"/driver/batches/{batch.id}",
        event_data={"batch_id": batch.id, "order_count": len(orders)},
    )
    for order, _assignment in assignments:
        notify_user(
            order.consumer,
            ORDER_ASSIGNED,
            f"Order {order.order_number} is on a delivery route",
            f"Batch {batch.batch_number} has been assigned to a driver.",
            link=f"/consumer/orders/{order.id}",
            event_data={"order_id": order.id, "batch_id": batch.id},
        )
    return batch


def cancel_batch(batch: DeliveryBatch, *, actor, reason: str) -> DeliveryBatch:
    if batch.status not in (domain.BATCH_DRAFT, domain.BATCH_PROPOSED, domain.BATCH_ASSIGNED):
        raise ApiError(
            "batch_in_progress",
            "An active batch cannot be cancelled from here. Resolve its exceptions first.",
            409,
            details={"status": batch.status},
        )
    now = domain.utcnow()
    from .orders import record_status

    for link in [row for row in batch.order_links if row.removed_at is None]:
        order = link.order
        link.removed_at = now
        link.removed_reason = reason[:500]
        assignment = (
            DriverAssignment.query.filter_by(order_id=order.id, status="active")
            .order_by(DriverAssignment.assigned_at.desc())
            .first()
        )
        if assignment is not None:
            assignment.status = "reassigned"
            assignment.ended_at = now
            assignment.end_reason = reason[:500]
        if order.status in (domain.ORDER_ASSIGNED, domain.ORDER_PICKUP_SCHEDULED, domain.ORDER_PICKUP_ARRIVED):
            record_status(
                order,
                domain.ORDER_AWAITING_ASSIGNMENT,
                actor=actor,
                source="manager",
                reason=f"Batch cancelled: {reason[:180]}",
            )
        notify_user(
            order.consumer,
            ORDER_STATUS,
            f"Order {order.order_number} needs a new route",
            "A manager is re-planning your delivery.",
            link=f"/consumer/orders/{order.id}",
            event_data={"order_id": order.id},
        )
    batch.status = domain.BATCH_CANCELLED
    batch.cancelled_at = now
    batch.cancellation_reason = reason[:500]
    if batch.driver_id:
        notify_driver(
            batch.driver_id,
            ORDER_STATUS,
            f"Batch {batch.batch_number} cancelled",
            reason[:500],
            link="/driver/batches",
            event_data={"batch_id": batch.id},
        )
    audit(
        "dispatch.batch_cancelled",
        "batch",
        batch.id,
        actor=actor,
        summary=f"Batch {batch.batch_number} cancelled",
        reason=reason,
    )
    return batch


def assign_batch_driver(
    batch: DeliveryBatch,
    new_driver,
    *,
    actor,
    reason: str,
) -> DeliveryBatch:
    if batch.status != domain.BATCH_ASSIGNED:
        raise ApiError(
            "batch_not_reassignable",
            "Only an assigned batch can be given to another driver.",
            409,
            details={"status": batch.status},
        )
    profile = profile_for(new_driver)
    blockers: list[dict] = []
    if profile.verification_status != domain.VERIFICATION_VERIFIED:
        blockers.append(blocker("driver_not_verified"))
    blockers.extend(duty_blockers(profile))
    orders = [
        link.order
        for link in batch.order_links
        if link.removed_at is None and link.order is not None
    ]
    for order in orders:
        blockers.extend(service_area_blockers(profile, order))
    try:
        vehicle = active_vehicle(profile)
    except ApiError as error:
        vehicle = None
        blockers.append(blocker(error.code, error.message))
    snapshot = load_snapshot(new_driver)
    if vehicle is not None:
        blockers.extend(batch_capacity_blockers(vehicle, orders, snapshot))
    if blockers:
        raise ApiError(
            "driver_not_eligible",
            "This driver cannot take that batch.",
            409,
            details={"driver_id": new_driver.id, "blockers": blockers},
        )

    now = domain.utcnow()
    previous_driver = batch.driver
    for link in [row for row in batch.order_links if row.removed_at is None]:
        assignment = (
            DriverAssignment.query.filter_by(order_id=link.order_id, status="active")
            .order_by(DriverAssignment.assigned_at.desc())
            .first()
        )
        if assignment is not None:
            assignment.status = "reassigned"
            assignment.ended_at = now
            assignment.end_reason = reason[:500]
        db.session.add(
            DriverAssignment(
                order_id=link.order_id,
                driver_id=new_driver.id,
                batch_id=batch.id,
                vehicle_id=vehicle.id,
                assigned_by_id=getattr(actor, "id", None),
                status="active",
            )
        )
    batch.driver_id = new_driver.id
    batch.vehicle_id = vehicle.id
    db.session.flush()
    route = rebuild_route(batch, actor=actor, start_time=now, reason=reason)
    for link in batch.order_links:
        if link.removed_at is not None:
            continue
        assignment = (
            DriverAssignment.query.filter_by(order_id=link.order_id, status="active")
            .order_by(DriverAssignment.assigned_at.desc())
            .first()
        )
        if assignment is not None and route is not None:
            assignment.route_plan_id = route.id
    audit(
        "dispatch.batch_reassigned",
        "batch",
        batch.id,
        actor=actor,
        summary=f"Batch {batch.batch_number} moved to {new_driver.full_name}",
        reason=reason,
    )
    notify_driver(
        new_driver.id,
        BATCH_ASSIGNED,
        f"Batch {batch.batch_number} assigned to you",
        f"{len(orders)} parcel(s). Review the updated route.",
        link=f"/driver/batches/{batch.id}",
        event_data={"batch_id": batch.id},
    )
    if previous_driver is not None and previous_driver.id != new_driver.id:
        notify_driver(
            previous_driver.id,
            ORDER_STATUS,
            f"Batch {batch.batch_number} removed",
            reason[:500],
            link="/driver/batches",
            event_data={"batch_id": batch.id},
        )
    return batch
