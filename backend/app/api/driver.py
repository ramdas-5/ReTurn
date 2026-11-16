"""Driver field application: duty, route, pickup and delivery evidence.

Every state-changing call requires an authenticated, active driver account, an
open duty session (with a fresh heartbeat) and an active assignment for the
order. Delivery completion is impossible without validated proof when the
configured workflow requires it: the rule is enforced here, not in the client.
"""
from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request
from werkzeug.datastructures import FileStorage

from .. import domain
from ..errors import ApiError, paginate
from ..extensions import db
from ..models import (
    DeliveryBatch,
    DeliveryException,
    DeliveryProof,
    DriverAssignment,
    DriverLocationEvent,
    Order,
    OrderStatusHistory,
    PickupProof,
    ProofMedia,
    Vehicle,
)
from ..security import (
    current_user,
    login_required,
    rate_limit,
    require_password_changed,
    role_required,
)
from ..serializers import (
    active_route_plan,
    serialize_assignment,
    serialize_batch,
    serialize_batch_summary,
    serialize_delivery_exception,
    serialize_driver_location,
    serialize_driver_profile,
    serialize_duty_session,
    serialize_order_detail,
    serialize_order_summary,
    serialize_route_stop,
    serialize_status_history,
    serialize_user,
    serialize_vehicle,
)
from ..services import availability, duty
from ..services import orders as order_service
from ..services.audit import audit
from ..services.notifications import (
    ORDER_DELIVERED,
    ORDER_EXCEPTION,
    ORDER_OUT_FOR_DELIVERY,
    ORDER_PICKED_UP,
    ORDER_STATUS,
    notify_responsible_managers,
    notify_user,
)
from ..services.proofs import validate_capture
from ..services.storage import save_image
from ..validation import Validator, json_body, pagination_args

bp = Blueprint("driver", __name__, url_prefix="/api/v1/driver")

PICKUP_FLOW = (
    domain.ORDER_ASSIGNED,
    domain.ORDER_PICKUP_SCHEDULED,
    domain.ORDER_PICKUP_ARRIVED,
)
CUSTODY = (
    domain.ORDER_PICKED_UP,
    domain.ORDER_IN_TRANSIT,
    domain.ORDER_OUT_FOR_DELIVERY,
    domain.ORDER_PROOF_PENDING,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _require_driver():
    user = current_user()
    return user, duty.driver_profile(user)


def _live_duty(profile):
    return duty.require_open_session(profile, require_live=True)


def _assignment_for(order_id: int, user, *, allow_ended: bool = False):
    order = db.session.get(Order, order_id)
    if order is None:
        raise ApiError("not_found", "That order does not exist.", 404)
    assignment = (
        DriverAssignment.query.filter_by(order_id=order.id, driver_id=user.id)
        .order_by(DriverAssignment.assigned_at.desc())
        .first()
    )
    if assignment is None:
        # Do not reveal whether another driver holds the order.
        raise ApiError("not_found", "That order is not assigned to you.", 404)
    if assignment.status != "active" and not allow_ended:
        raise ApiError(
            "assignment_not_active",
            "This assignment is no longer active. Check your batch with a manager.",
            409,
        )
    return order, assignment


def _touch_accepted(assignment: DriverAssignment) -> None:
    if assignment.accepted_at is None:
        assignment.accepted_at = domain.utcnow()


def _current_batch(order: Order, assignment: DriverAssignment):
    if assignment.batch is not None:
        return assignment.batch
    return order_service.current_batch(order)


def _mark_stop(
    order: Order,
    assignment: DriverAssignment,
    kind: str,
    status: str,
    *,
    now=None,
) -> None:
    batch = _current_batch(order, assignment)
    if batch is None:
        return
    plan = active_route_plan(batch)
    if plan is None:
        return
    now = now or domain.utcnow()
    stop = next(
        (
            row
            for row in plan.stops
            if row.order_id == order.id and row.kind == kind and row.status != domain.STOP_SKIPPED
        ),
        None,
    )
    if stop is None:
        return
    stop.status = status
    if status == domain.STOP_ARRIVED and stop.arrived_at is None:
        stop.arrived_at = now
    if status == domain.STOP_COMPLETED and stop.completed_at is None:
        stop.completed_at = now


def _maybe_complete_batch(batch) -> None:
    if batch is None or batch.status != domain.BATCH_ACTIVE:
        return
    links = [link for link in batch.order_links if link.removed_at is None]
    if not links:
        return
    if all(
        link.order is not None and link.order.status in domain.TERMINAL_ORDER_STATUSES
        for link in links
    ):
        batch.status = domain.BATCH_COMPLETED
        batch.completed_at = domain.utcnow()


def _proof_requirements() -> dict:
    return {
        "pickup_photo_required": bool(
            current_app.config.get("PICKUP_PROOF_REQUIRED", False)
        ),
        "delivery_photo_required": bool(
            current_app.config.get("DELIVERY_PROOF_REQUIRED", True)
        ),
        "gps_required": bool(current_app.config.get("PROOF_REQUIRE_GPS", True)),
        "max_capture_age_minutes": int(
            current_app.config.get("PROOF_MAX_CAPTURE_AGE_MINUTES", 20)
        ),
        "gps_radius_meters": float(
            current_app.config.get("PROOF_GPS_RADIUS_METERS", 400)
        ),
        "max_accuracy_meters": float(
            current_app.config.get("PROOF_MAX_ACCURACY_METERS", 250)
        ),
        "captured_at_required_with_photo": True,
        "capture_source": "device_camera",
    }


def _allowed_actions(order: Order, assignment: DriverAssignment) -> list[str]:
    status = order.status
    actions: list[str] = []
    if assignment.accepted_at is None and status in PICKUP_FLOW:
        actions.append("accept_assignment")
    if status in (domain.ORDER_ASSIGNED, domain.ORDER_PICKUP_SCHEDULED):
        actions.append("arrive_pickup")
    elif status == domain.ORDER_PICKUP_ARRIVED:
        actions.append("confirm_pickup")
    elif status == domain.ORDER_PICKED_UP:
        actions.append("depart")
    elif status == domain.ORDER_IN_TRANSIT:
        actions.append("out_for_delivery")
    elif status in (domain.ORDER_OUT_FOR_DELIVERY, domain.ORDER_PROOF_PENDING):
        actions.append("capture_delivery_proof")
    if status in (
        domain.ORDER_ASSIGNED,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
        domain.ORDER_IN_TRANSIT,
        domain.ORDER_OUT_FOR_DELIVERY,
        domain.ORDER_PROOF_PENDING,
    ):
        actions.append("report_exception")
    return actions


def _driver_order_payload(order: Order, assignment: DriverAssignment) -> dict:
    data = serialize_order_detail(
        order, include_consumer=True, include_driver_contact=False
    )
    data["assignment"] = serialize_assignment(
        assignment, include_driver_contact=False
    )
    data["actions"] = _allowed_actions(order, assignment)
    data["proof_requirements"] = _proof_requirements()
    data["next_stop_kind"] = (
        "pickup"
        if order.status in PICKUP_FLOW or order.status == domain.ORDER_PICKED_UP
        else "delivery"
    )
    return data


def _capture_request() -> tuple[dict, FileStorage | None]:
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        upload = (
            request.files.get("photo")
            or request.files.get("image")
            or request.files.get("file")
        )
        return dict(request.form), upload
    return json_body(), None


def _parse_capture(data: dict, *, upload: FileStorage | None) -> dict:
    v = Validator(data)
    latitude = v.number("latitude", minimum=-90, maximum=90)
    longitude = v.number("longitude", minimum=-180, maximum=180)
    accuracy_m = v.number("accuracy_m", minimum=0, maximum=100_000)
    captured_at = v.datetime("captured_at", required=bool(upload))
    capture_source = v.string("capture_source", max_length=40)
    recipient_name = v.string("recipient_name", max_length=160)
    notes = v.string("notes", max_length=500)
    v.finish()
    return {
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_m": accuracy_m,
        "captured_at": captured_at,
        "capture_source": capture_source,
        "recipient_name": recipient_name,
        "notes": notes,
        "upload": upload,
    }


def _store_proof(
    *,
    order: Order,
    driver_user,
    session,
    kind: str,
    capture: dict,
    reference_lat,
    reference_lng,
) -> ProofMedia | None:
    upload = capture["upload"]
    if upload is None:
        # No photo: still validate the location envelope when GPS is required.
        validate_capture(
            kind=kind,
            captured_at=capture["captured_at"],
            latitude=capture["latitude"],
            longitude=capture["longitude"],
            accuracy_m=capture["accuracy_m"],
            reference_lat=reference_lat,
            reference_lng=reference_lng,
            capture_source=capture["capture_source"],
        )
        return None

    validated = validate_capture(
        kind=kind,
        captured_at=capture["captured_at"],
        latitude=capture["latitude"],
        longitude=capture["longitude"],
        accuracy_m=capture["accuracy_m"],
        reference_lat=reference_lat,
        reference_lng=reference_lng,
        capture_source=capture["capture_source"],
    )
    asset = save_image(upload, uploaded_by=driver_user, error_prefix=f"{kind}_proof")
    proof_media = ProofMedia(
        order_id=order.id,
        driver_id=driver_user.id,
        duty_session_id=session.id,
        proof_type=kind,
        media_id=asset.id,
        captured_at=validated["captured_at"],
        received_at=validated["server_received_at"],
        latitude=validated["latitude"],
        longitude=validated["longitude"],
        accuracy_m=validated["accuracy_m"],
        distance_from_stop_m=validated["distance_from_stop_m"],
        verification_status=validated["verification_status"],
        notes=capture["notes"],
    )
    db.session.add(proof_media)
    db.session.flush()
    return proof_media


def _notify_managers_for_order(order: Order, notification_type: str, title: str, body: str):
    notify_responsible_managers(
        notification_type,
        title,
        body,
        area_name=order.pickup_address.area if order.pickup_address else None,
        latitude=order.pickup_address.latitude if order.pickup_address else None,
        longitude=order.pickup_address.longitude if order.pickup_address else None,
        link=f"/manager/orders/{order.id}",
        event_data={"order_id": order.id, "order_number": order.order_number},
    )


# --------------------------------------------------------------------------- #
# Duty
# --------------------------------------------------------------------------- #
@bp.get("/profile")
@login_required
@role_required(domain.ROLE_DRIVER)
def get_profile():
    user, profile = _require_driver()
    return jsonify(
        {
            "data": {
                "user": serialize_user(user),
                "driver_profile": serialize_driver_profile(profile, include_user=False),
                "service_areas": [
                    {
                        "id": link.service_area.id,
                        "name": link.service_area.name,
                        "city": link.service_area.city,
                    }
                    for link in profile.service_areas
                    if link.service_area
                ],
            }
        }
    )


@bp.patch("/vehicle")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def update_vehicle():
    user, profile = _require_driver()
    data = json_body()
    v = Validator(data)
    vehicle_id = v.integer("vehicle_id", required=True, minimum=1)
    make = v.string("make", max_length=80)
    model = v.string("model", max_length=80)
    color = v.string("color", max_length=40)
    year = v.integer("year", minimum=1990, maximum=2100)
    is_active = data.get("is_active")
    v.finish()

    vehicle = db.session.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.driver_id != profile.id:
        raise ApiError("not_found", "That vehicle does not belong to you.", 404)
    if isinstance(is_active, bool) and not is_active:
        active = DriverAssignment.query.filter_by(
            driver_id=user.id, vehicle_id=vehicle.id, status="active"
        ).count()
        if active:
            raise ApiError(
                "vehicle_in_use",
                "This vehicle is on an active assignment and cannot be deactivated.",
                409,
            )
        remaining = [
            row
            for row in profile.vehicles
            if row.is_active and row.id != vehicle.id
        ]
        if not remaining:
            raise ApiError(
                "last_vehicle",
                "Keep at least one active vehicle on your profile.",
                409,
            )
        vehicle.is_active = False
    elif isinstance(is_active, bool):
        vehicle.is_active = True
    if make is not None:
        vehicle.make = make
    if model is not None:
        vehicle.model = model
    if color is not None:
        vehicle.color = color
    if year is not None:
        vehicle.year = year
    audit(
        "driver.vehicle_updated",
        "vehicle",
        vehicle.id,
        actor=user,
        summary=f"Vehicle {vehicle.registration_number} profile updated",
    )
    db.session.commit()
    return jsonify({"data": serialize_vehicle(vehicle)})


@bp.get("/duty")
@login_required
@role_required(domain.ROLE_DRIVER)
def get_duty():
    _user, profile = _require_driver()
    session = duty.active_session(profile)
    recent = (
        db.session.query(duty.DriverDutySession)
        .filter_by(driver_id=profile.id)
        .order_by(duty.DriverDutySession.started_at.desc())
        .limit(5)
        .all()
    )
    return jsonify(
        {
            "data": {
                "duty": serialize_duty_session(session),
                "is_live": bool(session and duty.session_is_recent(session)),
                "verification_status": profile.verification_status,
                "recent_sessions": [
                    serialize_duty_session(row)
                    for row in recent
                    if row.id != getattr(session, "id", None)
                ],
                "heartbeat_timeout_minutes": int(
                    current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15)
                ),
            }
        }
    )


@bp.post("/duty/start")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
@rate_limit(10, 60, scope="duty-start")
def start_duty():
    _user, profile = _require_driver()
    data = json_body()
    v = Validator(data)
    status = v.choice(
        "status", (domain.DUTY_AVAILABLE, domain.DUTY_ON_DUTY), default=domain.DUTY_AVAILABLE
    )
    device_label = v.string("device_label", max_length=120)
    latitude = v.number("latitude", minimum=-90, maximum=90)
    longitude = v.number("longitude", minimum=-180, maximum=180)
    v.finish()
    session = duty.start_session(
        profile,
        status=status,
        device_label=device_label,
        latitude=latitude,
        longitude=longitude,
    )
    audit(
        "driver.duty_started",
        "driver_profile",
        profile.id,
        actor=_user,
        summary=f"Duty started as {status}",
    )
    db.session.commit()
    return jsonify({"data": serialize_duty_session(session)}), 201


@bp.post("/duty/status")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def change_duty_status():
    _user, profile = _require_driver()
    data = json_body()
    v = Validator(data)
    status = v.choice("status", domain.DUTY_STATUSES, required=True)
    v.finish()
    session = duty.require_open_session(profile, require_live=False)
    duty.change_status(session, status)
    audit(
        "driver.duty_status_changed",
        "driver_profile",
        profile.id,
        actor=_user,
        summary=f"Duty status set to {status}",
    )
    db.session.commit()
    return jsonify({"data": serialize_duty_session(session)})


@bp.post("/duty/heartbeat")
@login_required
@role_required(domain.ROLE_DRIVER)
def duty_heartbeat():
    _user, profile = _require_driver()
    data = json_body()
    v = Validator(data)
    latitude = v.number("latitude", minimum=-90, maximum=90)
    longitude = v.number("longitude", minimum=-180, maximum=180)
    accuracy_m = v.number("accuracy_m", minimum=0, maximum=100_000)
    v.finish()
    session = duty.require_open_session(profile, require_live=False)
    duty.heartbeat(
        session, latitude=latitude, longitude=longitude, accuracy_m=accuracy_m
    )
    db.session.commit()
    return jsonify({"data": serialize_duty_session(session)})


@bp.post("/duty/end")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def end_duty():
    user, profile = _require_driver()
    data = json_body()
    v = Validator(data)
    reason = v.string("reason", max_length=120)
    latitude = v.number("latitude", minimum=-90, maximum=90)
    longitude = v.number("longitude", minimum=-180, maximum=180)
    v.finish()
    session = duty.require_open_session(profile, require_live=False)
    workload = availability.active_workload(user.id)
    duty.end_session(
        session,
        reason=reason,
        latitude=latitude,
        longitude=longitude,
        active_workload=workload,
    )
    audit(
        "driver.duty_ended",
        "driver_profile",
        profile.id,
        actor=user,
        summary="Duty ended",
        reason=reason,
    )
    db.session.commit()
    return jsonify({"data": serialize_duty_session(session)})


@bp.post("/location")
@login_required
@role_required(domain.ROLE_DRIVER)
def report_location():
    user, profile = _require_driver()
    data = json_body()
    v = Validator(data)
    consent = v.boolean("consent_granted", default=False)
    latitude = v.number("latitude", required=True, minimum=-90, maximum=90)
    longitude = v.number("longitude", required=True, minimum=-180, maximum=180)
    accuracy_m = v.number("accuracy_m", minimum=0, maximum=100_000)
    heading = v.number("heading_degrees", minimum=0, maximum=360)
    speed = v.number("speed_kmh", minimum=0, maximum=300)
    recorded_at = v.datetime("recorded_at")
    batch_id = v.integer("batch_id", minimum=1)
    v.finish()
    if not consent:
        raise ApiError(
            "location_consent_required",
            "Location is only collected while you are on duty and have granted permission.",
            403,
        )
    session = _live_duty(profile)
    if batch_id is not None:
        batch = db.session.get(DeliveryBatch, batch_id)
        if batch is None or batch.driver_id != user.id:
            raise ApiError("not_found", "That batch is not assigned to you.", 404)
    event = duty.record_location(
        session,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
        heading_degrees=heading,
        speed_kmh=speed,
        recorded_at=recorded_at,
        batch_id=batch_id,
    )
    db.session.commit()
    timeout = int(current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15))
    return jsonify({"data": serialize_driver_location(event, timeout_minutes=timeout)}), 201


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@bp.get("/summary")
@login_required
@role_required(domain.ROLE_DRIVER)
def summary():
    user, profile = _require_driver()
    session = duty.active_session(profile)
    now = domain.utcnow()
    day_start = duty.today_start()

    assignments = (
        DriverAssignment.query.filter_by(driver_id=user.id, status="active")
        .order_by(DriverAssignment.assigned_at.desc())
        .all()
    )
    orders = [row.order for row in assignments if row.order is not None]
    active_orders = [order for order in orders if order.status in domain.ACTIVE_ORDER_STATUSES]

    def count(statuses):
        return sum(1 for order in active_orders if order.status in statuses)

    completed_today = (
        Order.query.join(DriverAssignment, DriverAssignment.order_id == Order.id)
        .filter(
            DriverAssignment.driver_id == user.id,
            Order.status == domain.ORDER_DELIVERED,
            Order.delivered_at.isnot(None),
            Order.delivered_at >= day_start,
        )
        .distinct()
        .count()
    )

    failed_orders = (
        Order.query.join(DriverAssignment, DriverAssignment.order_id == Order.id)
        .filter(
            DriverAssignment.driver_id == user.id,
            Order.status == domain.ORDER_FAILED,
        )
        .distinct()
        .count()
    )

    last_location_row = (
        DriverLocationEvent.query.filter_by(driver_id=profile.id)
        .order_by(DriverLocationEvent.received_at.desc())
        .first()
    )
    heartbeat_timeout = int(
        current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15)
    )
    last_location = (
        serialize_driver_location(
            last_location_row, timeout_minutes=heartbeat_timeout
        )
        if last_location_row is not None
        else None
    )

    in_custody = [
        order for order in active_orders if order.status in domain.IN_CUSTODY_STATUSES
    ]
    weight = sum(
        (Decimal(str(order.parcel.weight_kg)) for order in in_custody if order.parcel),
        Decimal("0"),
    )
    volume = sum(
        (Decimal(str(order.parcel.volume_m3)) for order in in_custody if order.parcel),
        Decimal("0"),
    )

    vehicle = None
    if assignments and assignments[0].vehicle is not None:
        vehicle = assignments[0].vehicle
    if vehicle is None:
        vehicle = next((row for row in profile.vehicles if row.is_active), None)
    capacity = vehicle.capacity_profile if vehicle is not None else None

    batch = next(
        (row.batch for row in assignments if row.batch is not None),
        None,
    )
    plan = active_route_plan(batch) if batch else None
    next_stop = None
    next_source = None
    if plan is not None:
        pending = [stop for stop in plan.stops if stop.status in (domain.STOP_PENDING, domain.STOP_ARRIVED)]
        if pending:
            next_stop = serialize_route_stop(pending[0])
            next_source = "route_plan"
    if next_stop is None:
        upcoming = sorted(
            (
                order
                for order in active_orders
                if order.status in PICKUP_FLOW and order.status != domain.ORDER_PICKUP_ARRIVED
            ),
            key=lambda order: order.pickup_window_start or now,
        )
        if upcoming:
            order = upcoming[0]
            next_stop = {
                "source": "schedule",
                "kind": "pickup",
                "order": {
                    "id": order.id,
                    "order_number": order.order_number,
                    "status": order.status,
                },
                "address": (
                    serialize_order_summary(order)["pickup"] if order.pickup_address else None
                ),
                "planned_at": domain.iso(order.pickup_window_start),
            }
            next_source = "schedule"
        else:
            deliveries = sorted(
                (
                    order
                    for order in active_orders
                    if order.status in CUSTODY
                ),
                key=lambda order: order.delivery_deadline or now,
            )
            if deliveries:
                order = deliveries[0]
                next_stop = {
                    "source": "schedule",
                    "kind": "delivery",
                    "order": {
                        "id": order.id,
                        "order_number": order.order_number,
                        "status": order.status,
                    },
                    "address": (
                        serialize_order_summary(order)["delivery"]
                        if order.delivery_address
                        else None
                    ),
                    "planned_at": domain.iso(order.delivery_deadline),
                }
                next_source = "schedule"

    history_rows = (
        db.session.query(OrderStatusHistory)
        .join(Order, Order.id == OrderStatusHistory.order_id)
        .join(DriverAssignment, DriverAssignment.order_id == Order.id)
        .filter(
            DriverAssignment.driver_id == user.id,
            OrderStatusHistory.created_at >= day_start,
        )
        .order_by(OrderStatusHistory.created_at.desc())
        .limit(20)
        .all()
    )

    activity = []
    for row in history_rows:
        item = serialize_status_history(row)
        item["order_number"] = row.order.order_number if row.order else None
        activity.append(item)

    return jsonify(
        {
            "data": {
                "driver": {
                    "id": user.id,
                    "full_name": user.full_name,
                    "role": user.role,
                    "verification_status": profile.verification_status,
                    "rating": float(profile.rating) if profile.rating is not None else None,
                    "completed_deliveries": profile.completed_deliveries,
                },
                "duty": serialize_duty_session(session),
                "vehicle": serialize_vehicle(vehicle) if vehicle else None,
                "counts": {
                    "assigned_orders": len(active_orders),
                    "total_parcels_assigned": len(assignments),
                    "remaining_deliveries": len(active_orders),
                    "pending_pickups": count(
                        (
                            domain.ORDER_ASSIGNED,
                            domain.ORDER_PICKUP_SCHEDULED,
                            domain.ORDER_PICKUP_ARRIVED,
                        )
                    ),
                    "out_for_delivery": count(
                        (
                            domain.ORDER_PICKED_UP,
                            domain.ORDER_IN_TRANSIT,
                            domain.ORDER_OUT_FOR_DELIVERY,
                            domain.ORDER_PROOF_PENDING,
                        )
                    ),
                    "completed_today": completed_today,
                    "completed_total": profile.completed_deliveries,
                    "failed_orders": failed_orders,
                },
                "vehicle_load": {
                    "parcels": len(in_custody),
                    "weight_kg": float(weight),
                    "volume_m3": round(float(volume), 5),
                    "max_parcels": capacity.max_parcels if capacity else None,
                    "max_weight_kg": float(capacity.max_weight_kg) if capacity else None,
                    "max_volume_m3": float(capacity.max_volume_m3) if capacity else None,
                    "weight_utilisation_pct": (
                        round(float(weight) / float(capacity.max_weight_kg) * 100, 1)
                        if capacity and float(capacity.max_weight_kg or 0) > 0
                        else None
                    ),
                },
                "next_stop": next_stop,
                "next_stop_source": next_source,
                "last_location": last_location,
                "today": {
                    "day_start_utc": domain.iso(day_start),
                    "route_distance_km": float(batch.distance_km) if batch else None,
                    "route_distance_source": batch.distance_source if batch else None,
                    "active_batch": serialize_batch_summary(batch) if batch else None,
                },
                "activity": activity,
                "generated_at": domain.iso(now),
            }
        }
    )


# --------------------------------------------------------------------------- #
# Assignments
# --------------------------------------------------------------------------- #
@bp.get("/assignments")
@login_required
@role_required(domain.ROLE_DRIVER)
def list_assignments():
    user, _profile = _require_driver()
    window = request.args.get("window", "active")
    query = DriverAssignment.query.filter_by(driver_id=user.id)
    if window == "active":
        query = query.filter(DriverAssignment.status == "active")
    elif window == "completed":
        query = query.filter(DriverAssignment.status == "completed")
    elif window != "all":
        raise ApiError("invalid_window", "Use active, completed or all.", 422)

    rows = (
        query.join(Order, Order.id == DriverAssignment.order_id)
        .order_by(Order.pickup_window_start.asc())
        .limit(100)
        .all()
    )
    data = [
        _driver_order_payload(row.order, row)
        for row in rows
        if row.order is not None
    ]
    return jsonify(
        {
            "data": data,
            "meta": {
                "window": window,
                "total": len(data),
                "generated_at": domain.iso(domain.utcnow()),
            },
        }
    )


@bp.get("/assignments/<int:order_id>")
@login_required
@role_required(domain.ROLE_DRIVER)
def get_assignment(order_id: int):
    user, _profile = _require_driver()
    order, assignment = _assignment_for(order_id, user, allow_ended=True)
    return jsonify({"data": _driver_order_payload(order, assignment)})


@bp.post("/orders/<int:order_id>/accept")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def accept_assignment(order_id: int):
    user, profile = _require_driver()
    order, assignment = _assignment_for(order_id, user)
    _live_duty(profile)
    _touch_accepted(assignment)
    audit(
        "driver.assignment_accepted",
        "order",
        order.id,
        actor=user,
        summary=f"Driver acknowledged {order.order_number}",
    )
    db.session.commit()
    return jsonify({"data": _driver_order_payload(order, assignment)})


@bp.post("/orders/<int:order_id>/arrived-pickup")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def arrived_pickup(order_id: int):
    user, profile = _require_driver()
    order, assignment = _assignment_for(order_id, user)
    _live_duty(profile)
    if order.status == domain.ORDER_PICKUP_ARRIVED:
        return jsonify({"data": _driver_order_payload(order, assignment)})
    if order.status == domain.ORDER_ASSIGNED:
        order_service.record_status(
            order,
            domain.ORDER_PICKUP_SCHEDULED,
            actor=user,
            source="driver",
            reason="Driver en route to pickup",
        )
    elif order.status != domain.ORDER_PICKUP_SCHEDULED:
        raise ApiError(
            "invalid_status",
            "The order is not waiting for a pickup arrival.",
            409,
            details={"status": order.status},
        )
    order_service.record_status(
        order,
        domain.ORDER_PICKUP_ARRIVED,
        actor=user,
        source="driver",
        reason="Driver arrived at pickup",
    )
    _touch_accepted(assignment)
    _mark_stop(order, assignment, domain.STOP_PICKUP, domain.STOP_ARRIVED)
    audit(
        "driver.arrived_pickup",
        "order",
        order.id,
        actor=user,
        summary=f"Arrived at pickup for {order.order_number}",
    )
    db.session.commit()
    return jsonify({"data": _driver_order_payload(order, assignment)})


@bp.post("/orders/<int:order_id>/pickup")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def confirm_pickup(order_id: int):
    user, profile = _require_driver()
    order, assignment = _assignment_for(order_id, user)
    session = _live_duty(profile)
    if order.status != domain.ORDER_PICKUP_ARRIVED:
        raise ApiError(
            "invalid_status",
            "Mark your arrival at the pickup before confirming collection.",
            409,
            details={"status": order.status},
        )

    data, upload = _capture_request()
    capture = _parse_capture(data, upload=upload)
    if current_app.config.get("PICKUP_PROOF_REQUIRED", False) and upload is None:
        raise ApiError(
            "pickup_proof_required",
            "This workflow requires a pickup photograph.",
            422,
            fields={"photo": "Capture the parcel before it leaves the sender."},
        )

    pickup = order.pickup_address
    proof_media = _store_proof(
        order=order,
        driver_user=user,
        session=session,
        kind=domain.PROOF_PICKUP,
        capture=capture,
        reference_lat=pickup.latitude if pickup else None,
        reference_lng=pickup.longitude if pickup else None,
    )
    now = domain.utcnow()
    if proof_media is not None:
        db.session.add(
            PickupProof(
                order_id=order.id,
                driver_id=user.id,
                proof_media_id=proof_media.id,
                confirmed_at=capture["captured_at"],
                server_received_at=now,
                status=domain.PROOF_VALID,
                notes=capture["notes"],
            )
        )

    order_service.record_status(
        order,
        domain.ORDER_PICKED_UP,
        actor=user,
        source="driver",
        reason="Parcel collected with proof" if proof_media else "Parcel collected",
        event_metadata={"proof_id": proof_media.id if proof_media else None},
    )
    _touch_accepted(assignment)
    _mark_stop(order, assignment, domain.STOP_PICKUP, domain.STOP_COMPLETED, now=now)
    audit(
        "driver.pickup_confirmed",
        "order",
        order.id,
        actor=user,
        summary=f"Pickup confirmed for {order.order_number}",
        event_metadata={
            "proof_media_id": proof_media.id if proof_media else None,
            "capture_source": capture["capture_source"],
        },
    )
    notify_user(
        order.consumer,
        ORDER_PICKED_UP,
        f"Order {order.order_number} collected",
        "Your driver has the parcel and is starting the delivery leg.",
        link=f"/consumer/orders/{order.id}",
        event_data={"order_id": order.id, "status": order.status},
    )
    db.session.commit()
    return jsonify({"data": _driver_order_payload(order, assignment)})


@bp.post("/orders/<int:order_id>/depart")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def depart(order_id: int):
    user, profile = _require_driver()
    order, assignment = _assignment_for(order_id, user)
    _live_duty(profile)
    if order.status == domain.ORDER_IN_TRANSIT:
        return jsonify({"data": _driver_order_payload(order, assignment)})
    if order.status != domain.ORDER_PICKED_UP:
        raise ApiError("invalid_status", "The parcel has not been collected yet.", 409)
    order_service.record_status(
        order,
        domain.ORDER_IN_TRANSIT,
        actor=user,
        source="driver",
        reason="Driver departed the pickup",
    )
    audit(
        "driver.departed",
        "order",
        order.id,
        actor=user,
        summary=f"In transit: {order.order_number}",
    )
    db.session.commit()
    return jsonify({"data": _driver_order_payload(order, assignment)})


@bp.post("/orders/<int:order_id>/out-for-delivery")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def out_for_delivery(order_id: int):
    user, profile = _require_driver()
    order, assignment = _assignment_for(order_id, user)
    _live_duty(profile)
    if order.status == domain.ORDER_OUT_FOR_DELIVERY:
        return jsonify({"data": _driver_order_payload(order, assignment)})
    if order.status not in (domain.ORDER_PICKED_UP, domain.ORDER_IN_TRANSIT):
        raise ApiError(
            "invalid_status",
            "The order is not ready to go out for delivery.",
            409,
        )
    order_service.record_status(
        order,
        domain.ORDER_OUT_FOR_DELIVERY,
        actor=user,
        source="driver",
        reason="Out for delivery",
    )
    audit(
        "driver.out_for_delivery",
        "order",
        order.id,
        actor=user,
        summary=f"Out for delivery: {order.order_number}",
    )
    notify_user(
        order.consumer,
        ORDER_OUT_FOR_DELIVERY,
        f"Order {order.order_number} is out for delivery",
        "Your driver is heading to the delivery address.",
        link=f"/consumer/orders/{order.id}",
        event_data={"order_id": order.id, "status": order.status},
    )
    db.session.commit()
    return jsonify({"data": _driver_order_payload(order, assignment)})


@bp.post("/orders/<int:order_id>/delivery-proof")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def capture_delivery_proof(order_id: int):
    user, profile = _require_driver()
    order, assignment = _assignment_for(order_id, user)
    session = _live_duty(profile)
    if order.status not in (domain.ORDER_OUT_FOR_DELIVERY, domain.ORDER_PROOF_PENDING):
        raise ApiError(
            "invalid_status",
            "Mark the order out for delivery before capturing delivery proof.",
            409,
            details={"status": order.status},
        )

    data, upload = _capture_request()
    capture = _parse_capture(data, upload=upload)
    required = bool(current_app.config.get("DELIVERY_PROOF_REQUIRED", True))
    if required and upload is None:
        raise ApiError(
            "delivery_proof_required",
            "A delivery cannot be completed without a freshly captured photograph.",
            422,
            details={
                "reasons": ["delivery_proof_required"],
                "corrective_actions": [
                    "Capture a new photograph of the handed-over parcel or permitted evidence.",
                ],
            },
            fields={"photo": "Delivery proof photograph is required."},
        )

    delivery = order.delivery_address
    proof_media = _store_proof(
        order=order,
        driver_user=user,
        session=session,
        kind=domain.PROOF_DELIVERY,
        capture=capture,
        reference_lat=delivery.latitude if delivery else None,
        reference_lng=delivery.longitude if delivery else None,
    )
    now = domain.utcnow()
    if proof_media is not None:
        db.session.add(
            DeliveryProof(
                order_id=order.id,
                driver_id=user.id,
                proof_media_id=proof_media.id,
                captured_at=capture["captured_at"],
                server_received_at=now,
                status=domain.PROOF_VALID,
                recipient_name=capture["recipient_name"],
                notes=capture["notes"],
            )
        )

    order_service.record_status(
        order,
        domain.ORDER_DELIVERED,
        actor=user,
        source="driver",
        reason=(
            "Delivered with validated proof"
            if proof_media
            else "Delivered (proof not required by configured workflow)"
        ),
        event_metadata={
            "proof_media_id": proof_media.id if proof_media else None,
            "capture_source": capture["capture_source"],
        },
    )
    _touch_accepted(assignment)
    assignment.status = "completed"
    assignment.ended_at = now
    assignment.end_reason = "Delivered"
    _mark_stop(order, assignment, domain.STOP_DELIVERY, domain.STOP_COMPLETED, now=now)
    profile.completed_deliveries = (profile.completed_deliveries or 0) + 1
    batch = _current_batch(order, assignment)
    _maybe_complete_batch(batch)

    audit(
        "driver.delivery_completed",
        "order",
        order.id,
        actor=user,
        summary=f"Delivery completed for {order.order_number}",
        event_metadata={
            "proof_media_id": proof_media.id if proof_media else None,
            "capture_source": capture["capture_source"],
        },
    )
    notify_user(
        order.consumer,
        ORDER_DELIVERED,
        f"Order {order.order_number} delivered",
        "Delivery proof was recorded. Thank you for using ReTurn.",
        link=f"/consumer/orders/{order.id}",
        event_data={"order_id": order.id, "status": order.status},
    )
    if batch is not None and batch.status == domain.BATCH_COMPLETED:
        _notify_managers_for_order(
            order,
            ORDER_STATUS,
            f"Batch {batch.batch_number} completed",
            "All orders on the batch are closed.",
        )
    db.session.commit()
    return jsonify({"data": _driver_order_payload(order, assignment)})


@bp.post("/orders/<int:order_id>/exception")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def report_exception(order_id: int):
    user, profile = _require_driver()
    order, assignment = _assignment_for(order_id, user)
    _live_duty(profile)
    data = json_body()
    v = Validator(data)
    exception_type = v.choice(
        "exception_type", domain.EXCEPTION_TYPES, required=True
    )
    description = v.string("description", required=True, min_length=10, max_length=1500)
    v.finish()

    batch = _current_batch(order, assignment)
    row = DeliveryException(
        order_id=order.id,
        driver_id=user.id,
        batch_id=batch.id if batch else None,
        exception_type=exception_type,
        description=description,
        status=domain.EXCEPTION_OPEN,
    )
    db.session.add(row)
    db.session.flush()

    target = None
    if exception_type == "proof_capture_failed" and order.status == domain.ORDER_OUT_FOR_DELIVERY:
        target = domain.ORDER_PROOF_PENDING
    elif order.status in (
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
        domain.ORDER_IN_TRANSIT,
        domain.ORDER_OUT_FOR_DELIVERY,
        domain.ORDER_PROOF_PENDING,
    ) and exception_type != "proof_capture_failed":
        target = domain.ORDER_FAILED
    if target is not None and domain.can_transition(order.status, target):
        order_service.record_status(
            order,
            target,
            actor=user,
            source="driver",
            reason=f"Driver reported {exception_type}: {description[:180]}",
            event_metadata={"exception_id": row.id, "exception_type": exception_type},
        )

    audit(
        "driver.exception_reported",
        "order",
        order.id,
        actor=user,
        summary=f"Exception reported for {order.order_number}: {exception_type}",
        reason=description,
        event_metadata={"exception_type": exception_type},
    )
    notify_user(
        order.consumer,
        ORDER_EXCEPTION,
        f"Delivery issue on {order.order_number}",
        "A manager is reviewing the delivery issue. No delivery has been marked complete.",
        link=f"/consumer/orders/{order.id}",
        event_data={"order_id": order.id, "exception_type": exception_type},
    )
    _notify_managers_for_order(
        order,
        ORDER_EXCEPTION,
        f"Exception on {order.order_number}",
        f"{exception_type}: {description[:220]}",
    )
    db.session.commit()
    return (
        jsonify(
            {
                "data": {
                    "exception": serialize_delivery_exception(row),
                    "order": _driver_order_payload(order, assignment),
                }
            }
        ),
        201,
    )


# --------------------------------------------------------------------------- #
# Batches and route
# --------------------------------------------------------------------------- #
@bp.get("/batches")
@login_required
@role_required(domain.ROLE_DRIVER)
def list_batches():
    user, _profile = _require_driver()
    query = DeliveryBatch.query.filter_by(driver_id=user.id)
    status = request.args.get("status")
    if status:
        if status not in domain.BATCH_STATUSES:
            raise ApiError("invalid_status", "Unknown batch status.", 422)
        query = query.filter(DeliveryBatch.status == status)
    query = query.order_by(DeliveryBatch.planned_start.desc())
    page, per_page = pagination_args()
    return paginate(query, page, per_page, serialize_batch_summary)


@bp.get("/batches/<int:batch_id>")
@login_required
@role_required(domain.ROLE_DRIVER)
def get_batch(batch_id: int):
    user, _profile = _require_driver()
    batch = db.session.get(DeliveryBatch, batch_id)
    if batch is None or batch.driver_id != user.id:
        raise ApiError("not_found", "That batch is not assigned to you.", 404)
    return jsonify({"data": serialize_batch(batch)})


@bp.post("/batches/<int:batch_id>/start")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def start_batch(batch_id: int):
    user, profile = _require_driver()
    _live_duty(profile)
    batch = db.session.get(DeliveryBatch, batch_id)
    if batch is None or batch.driver_id != user.id:
        raise ApiError("not_found", "That batch is not assigned to you.", 404)
    if batch.status == domain.BATCH_ACTIVE:
        return jsonify({"data": serialize_batch(batch)})
    if batch.status != domain.BATCH_ASSIGNED:
        raise ApiError(
            "invalid_status",
            "Only an assigned batch can be started.",
            409,
            details={"status": batch.status},
        )
    batch.status = domain.BATCH_ACTIVE
    batch.started_at = domain.utcnow()
    audit(
        "driver.batch_started",
        "batch",
        batch.id,
        actor=user,
        summary=f"Batch {batch.batch_number} started",
    )
    db.session.commit()
    return jsonify({"data": serialize_batch(batch)})


@bp.post("/batches/<int:batch_id>/complete")
@login_required
@role_required(domain.ROLE_DRIVER)
@require_password_changed()
def complete_batch(batch_id: int):
    user, profile = _require_driver()
    _live_duty(profile)
    batch = db.session.get(DeliveryBatch, batch_id)
    if batch is None or batch.driver_id != user.id:
        raise ApiError("not_found", "That batch is not assigned to you.", 404)
    if batch.status == domain.BATCH_COMPLETED:
        return jsonify({"data": serialize_batch(batch)})
    if batch.status != domain.BATCH_ACTIVE:
        raise ApiError("invalid_status", "Only an active batch can be completed.", 409)

    links = [link for link in batch.order_links if link.removed_at is None]
    pending = [
        link.order.order_number
        for link in links
        if link.order is not None
        and link.order.status not in domain.TERMINAL_ORDER_STATUSES
    ]
    if pending:
        raise ApiError(
            "batch_has_open_orders",
            "Complete or report every parcel before closing the batch.",
            409,
            details={"pending_orders": pending},
        )
    batch.status = domain.BATCH_COMPLETED
    batch.completed_at = domain.utcnow()
    audit(
        "driver.batch_completed",
        "batch",
        batch.id,
        actor=user,
        summary=f"Batch {batch.batch_number} completed",
    )
    db.session.commit()
    return jsonify({"data": serialize_batch(batch)})
