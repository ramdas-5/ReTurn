"""Administrator API: platform-wide monitoring, account lists, fleet, service
areas, matching configuration, proof audit, analytics and audit trail.

Every endpoint is administrator-only and every sensitive mutation is audited.
Nothing here bypasses the domain rules (proof validation, assignment locks or
service-area checks); admin views read the same authoritative rows as dispatch.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from .. import domain
from ..errors import ApiError
from ..extensions import db
from ..models import (
    AdminSetting,
    AuditLog,
    BusinessProfile,
    DeliveryBatch,
    DeliveryException,
    DriverLocationEvent,
    DriverProfile,
    Order,
    ProofMedia,
    ServiceArea,
    User,
    Vehicle,
)
from ..security import (
    current_user,
    login_required,
    permission_required,
    rate_limit,
    role_required,
)
from ..serializers import (
    serialize_audit_log,
    serialize_batch,
    serialize_batch_summary,
    serialize_driver_location,
    serialize_driver_profile,
    serialize_order_detail,
    serialize_order_summary,
    serialize_proof_media,
    serialize_service_area,
    serialize_user,
    serialize_vehicle,
)
from ..services import analytics, duty
from ..services.audit import audit
from ..services.route_planner import config as routing_config
from ..validation import Validator, json_body

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")

MAX_ROWS = 500
MATCHING_SETTINGS_KEY = "matching.defaults"

MATCHING_BOUNDS = {
    "max_detour_km": (0.5, 50.0),
    "max_pickup_radius_km": (1.0, 50.0),
    "max_workload_parcels": (1, 100),
    "max_workload_weight_pct": (10.0, 100.0),
    "service_minutes": (1, 30),
    "avg_speed_kmh": (5.0, 80.0),
    "road_factor": (1.0, 2.0),
    "deadline_buffer_minutes": (0, 120),
    "suggestion_ttl_minutes": (5, 240),
    "max_search_drivers": (1, 100),
}


def _paginate(rows: list, serializer):
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    try:
        per_page = min(max(1, int(request.args.get("per_page", "25"))), 100)
    except ValueError:
        per_page = 25
    start = (page - 1) * per_page
    return jsonify(
        {
            "data": [serializer(row) for row in rows[start : start + per_page]],
            "meta": {"page": page, "per_page": per_page, "total": len(rows)},
        }
    )


# --------------------------------------------------------------------------- #
# Dashboard and analytics
# --------------------------------------------------------------------------- #
@bp.get("/summary")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def summary():
    return jsonify({"data": analytics.admin_summary()})


@bp.get("/analytics")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ANALYTICS_VIEW)
def analytics_overview():
    return jsonify({"data": analytics.overview()})


@bp.get("/analytics/sustainability")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ANALYTICS_VIEW)
def sustainability():
    return jsonify({"data": analytics.sustainability_report()})


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
@bp.get("/consumers")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ACCOUNTS_MANAGE)
def list_consumers():
    query_text = (request.args.get("q") or "").strip().lower()
    status = request.args.get("status")
    rows = User.query.filter_by(role=domain.ROLE_CONSUMER).order_by(User.created_at.desc()).limit(MAX_ROWS).all()
    if status:
        if status not in domain.USER_STATUSES:
            raise ApiError("invalid_status", "Unknown account status.", 422)
        rows = [row for row in rows if row.status == status]
    if query_text:
        rows = [
            row
            for row in rows
            if query_text in row.full_name.lower()
            or query_text in row.email.lower()
            or (row.phone and query_text in row.phone.lower())
        ]
    return _paginate(rows, serialize_user)


@bp.get("/businesses")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ACCOUNTS_MANAGE)
def list_businesses():
    query_text = (request.args.get("q") or "").strip().lower()
    rows = BusinessProfile.query.order_by(BusinessProfile.created_at.desc()).limit(MAX_ROWS).all()
    if query_text:
        rows = [
            row
            for row in rows
            if query_text in row.business_name.lower()
            or (row.category and query_text in row.category.lower())
        ]

    def payload(row: BusinessProfile) -> dict:
        from ..serializers import serialize_business_profile

        data = serialize_business_profile(row) or {}
        data["owner"] = {
            "id": row.user.id,
            "full_name": row.user.full_name,
            "email": row.user.email,
            "status": row.user.status,
        } if row.user else None
        data["orders"] = Order.query.filter_by(business_profile_id=row.id).count()
        return data

    return _paginate(rows, payload)


@bp.get("/managers")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ACCOUNTS_MANAGE)
def list_managers():
    rows = User.query.filter_by(role=domain.ROLE_MANAGER).order_by(User.full_name).limit(MAX_ROWS).all()

    def payload(user: User) -> dict:
        data = serialize_user(user)
        profile = user.manager_profile
        data["assigned_orders"] = (
            Order.query.filter_by(approved_by_id=user.id).count() if profile else 0
        )
        data["managed_batches"] = DeliveryBatch.query.filter_by(manager_id=user.id).count()
        return data

    return _paginate(rows, payload)


@bp.get("/drivers")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ACCOUNTS_MANAGE)
def list_drivers():
    rows = User.query.filter_by(role=domain.ROLE_DRIVER).order_by(User.full_name).limit(MAX_ROWS).all()

    def payload(user: User) -> dict:
        data = serialize_driver_profile(user.driver_profile, include_user=True)
        if data is None:
            return {"user": serialize_user(user)}
        from ..models import DriverAssignment

        data["active_assignments"] = DriverAssignment.query.filter_by(
            driver_id=user.id, status="active"
        ).count()
        data["active_batches"] = DeliveryBatch.query.filter(
            DeliveryBatch.driver_id == user.id,
            DeliveryBatch.status.in_((domain.BATCH_ASSIGNED, domain.BATCH_ACTIVE)),
        ).count()
        return data

    return _paginate(rows, payload)


# --------------------------------------------------------------------------- #
# Fleet
# --------------------------------------------------------------------------- #
@bp.get("/vehicles")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_VEHICLES_MANAGE)
def list_vehicles():
    rows = Vehicle.query.order_by(Vehicle.created_at.desc()).limit(MAX_ROWS).all()
    verification = request.args.get("verification_status")
    if verification:
        if verification not in domain.VERIFICATION_STATUSES:
            raise ApiError("invalid_status", "Unknown verification status.", 422)
        rows = [row for row in rows if row.verification_status == verification]

    def payload(vehicle: Vehicle) -> dict:
        data = serialize_vehicle(vehicle)
        driver = vehicle.driver.user if vehicle.driver and vehicle.driver.user else None
        data["driver"] = (
            {
                "id": driver.id,
                "full_name": driver.full_name,
                "email": driver.email,
                "verification_status": vehicle.driver.verification_status,
            }
            if driver
            else None
        )
        return data

    return _paginate(rows, payload)


@bp.patch("/vehicles/<int:vehicle_id>")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_VEHICLES_MANAGE)
@rate_limit(60, 60, scope="admin-vehicle")
def update_vehicle(vehicle_id: int):
    vehicle = db.session.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise ApiError("not_found", "That vehicle does not exist.", 404)
    data = json_body()
    v = Validator(data)
    verification = v.choice(
        "verification_status", domain.VERIFICATION_STATUSES
    )
    reason = v.string("reason", max_length=500)
    is_active = data.get("is_active")
    v.finish()

    if verification is not None:
        vehicle.verification_status = verification
    if isinstance(is_active, bool):
        vehicle.is_active = is_active
    audit(
        "admin.vehicle_updated",
        "vehicle",
        vehicle.id,
        actor=current_user(),
        summary=f"Vehicle {vehicle.registration_number} updated",
        reason=reason,
        event_metadata={"verification_status": vehicle.verification_status, "is_active": vehicle.is_active},
    )
    db.session.commit()
    return jsonify({"data": serialize_vehicle(vehicle)})


# --------------------------------------------------------------------------- #
# Orders and batches
# --------------------------------------------------------------------------- #
@bp.get("/orders")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_VIEW)
def list_orders():
    query = Order.query
    status = request.args.get("status")
    if status:
        wanted = [value.strip() for value in status.split(",") if value.strip()]
        unknown = [value for value in wanted if value not in domain.ORDER_STATUSES]
        if unknown:
            raise ApiError("invalid_status", "Unknown order status filter.", 422, details={"unknown": unknown})
        query = query.filter(Order.status.in_(wanted))
    service_type = request.args.get("service_type")
    if service_type:
        if service_type not in domain.SERVICE_TYPES:
            raise ApiError("invalid_service_type", "Unknown service type.", 422)
        query = query.filter(Order.service_type == service_type)
    text = (request.args.get("q") or "").strip()
    if text:
        query = query.filter(db.func.lower(Order.order_number).like(f"%{text.lower()}%"))
    if request.args.get("overdue") in {"1", "true", "yes"}:
        query = query.filter(
            Order.status.in_(domain.ACTIVE_ORDER_STATUSES),
            Order.delivery_deadline < domain.utcnow(),
        )
    rows = query.order_by(Order.created_at.desc()).limit(MAX_ROWS).all()
    return _paginate(rows, lambda row: serialize_order_summary(row, include_consumer=True))


@bp.get("/orders/<int:order_id>")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_VIEW)
def get_order(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        raise ApiError("not_found", "That order does not exist.", 404)
    return jsonify(
        {
            "data": serialize_order_detail(
                order, include_consumer=True, include_driver_contact=True
            )
        }
    )


@bp.get("/batches")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def list_batches():
    query = DeliveryBatch.query
    status = request.args.get("status")
    if status:
        if status not in domain.BATCH_STATUSES:
            raise ApiError("invalid_status", "Unknown batch status.", 422)
        query = query.filter(DeliveryBatch.status == status)
    rows = query.order_by(DeliveryBatch.planned_start.desc()).limit(MAX_ROWS).all()
    return _paginate(rows, serialize_batch_summary)


@bp.get("/batches/<int:batch_id>")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def get_batch(batch_id: int):
    batch = db.session.get(DeliveryBatch, batch_id)
    if batch is None:
        raise ApiError("not_found", "That batch does not exist.", 404)
    return jsonify({"data": serialize_batch(batch)})


# --------------------------------------------------------------------------- #
# Live operations
# --------------------------------------------------------------------------- #
@bp.get("/operations/live")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def live_operations():
    now = domain.utcnow()
    timeout = int(current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15))
    drivers = []
    for profile in DriverProfile.query.all():
        session = duty.active_session(profile)
        if session is None:
            continue
        last = (
            DriverLocationEvent.query.filter_by(driver_id=profile.id)
            .order_by(DriverLocationEvent.received_at.desc())
            .first()
        )
        location = (
            serialize_driver_location(last, timeout_minutes=timeout) if last else None
        )
        tracking = (
            "unavailable"
            if location is None
            else "live_recent"
            if location["is_recent"]
            else "stale"
        )
        batch = (
            DeliveryBatch.query.filter(
                DeliveryBatch.driver_id == profile.user_id,
                DeliveryBatch.status.in_((domain.BATCH_ASSIGNED, domain.BATCH_ACTIVE)),
            )
            .order_by(DeliveryBatch.id.desc())
            .first()
        )
        drivers.append(
            {
                "driver": {
                    "id": profile.user_id,
                    "full_name": profile.user.full_name if profile.user else None,
                    "phone": profile.user.phone if profile.user else None,
                },
                "duty": {
                    "status": session.status,
                    "label": domain.DUTY_LABELS.get(session.status, session.status),
                    "started_at": domain.iso(session.started_at),
                    "last_heartbeat_at": domain.iso(session.last_heartbeat_at),
                },
                "location": location,
                "tracking_status": tracking,
                "active_batch": serialize_batch_summary(batch) if batch else None,
            }
        )
    pending_pickups = Order.query.filter(
        Order.status.in_(
            (
                domain.ORDER_ASSIGNED,
                domain.ORDER_PICKUP_SCHEDULED,
                domain.ORDER_PICKUP_ARRIVED,
            )
        )
    ).count()
    in_transit = Order.query.filter(
        Order.status.in_(
            (
                domain.ORDER_PICKED_UP,
                domain.ORDER_IN_TRANSIT,
                domain.ORDER_OUT_FOR_DELIVERY,
                domain.ORDER_PROOF_PENDING,
            )
        )
    ).count()
    return jsonify(
        {
            "data": {
                "drivers": drivers,
                "counts": {
                    "drivers_on_duty": len(drivers),
                    "pending_pickups": pending_pickups,
                    "in_transit": in_transit,
                    "active_batches": DeliveryBatch.query.filter(
                        DeliveryBatch.status.in_(
                            (domain.BATCH_ASSIGNED, domain.BATCH_ACTIVE)
                        )
                    ).count(),
                    "open_exceptions": DeliveryException.query.filter_by(
                        status=domain.EXCEPTION_OPEN
                    ).count(),
                },
                "generated_at": domain.iso(now),
                "note": "Only latest reported on-duty locations are shown; stale and unavailable tracking are labelled.",
            }
        }
    )


# --------------------------------------------------------------------------- #
# Proof audit
# --------------------------------------------------------------------------- #
@bp.get("/proofs")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_PROOFS_VERIFY)
def list_proofs():
    rows = ProofMedia.query.order_by(ProofMedia.received_at.desc()).limit(MAX_ROWS).all()
    status = request.args.get("verification_status")
    if status:
        if status not in domain.PROOF_STATUSES:
            raise ApiError("invalid_status", "Unknown proof status.", 422)
        rows = [row for row in rows if row.verification_status == status]
    return _paginate(rows, serialize_proof_media)


@bp.patch("/proofs/<int:proof_id>/verify")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_PROOFS_VERIFY)
@rate_limit(60, 60, scope="admin-proof")
def verify_proof(proof_id: int):
    proof = db.session.get(ProofMedia, proof_id)
    if proof is None:
        raise ApiError("not_found", "That proof does not exist.", 404)
    data = json_body()
    v = Validator(data)
    status = v.choice("verification_status", domain.PROOF_STATUSES, required=True)
    note = v.string("note", max_length=1000)
    v.finish()
    proof.verification_status = status
    proof.verified_by_id = current_user().id
    proof.verified_at = domain.utcnow()
    if note:
        proof.notes = note
    audit(
        "admin.proof_reviewed",
        "proof_media",
        proof.id,
        actor=current_user(),
        summary=f"Proof #{proof.id} marked {status}",
        reason=note,
        event_metadata={"order_id": proof.order_id, "status": status},
    )
    db.session.commit()
    return jsonify({"data": serialize_proof_media(proof)})


# --------------------------------------------------------------------------- #
# Service areas
# --------------------------------------------------------------------------- #
@bp.get("/service-areas")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_SERVICE_AREAS_MANAGE)
def list_service_areas():
    rows = ServiceArea.query.order_by(ServiceArea.name).all()
    return _paginate(rows, lambda row: serialize_service_area(row, include_counts=True))


def _service_area_payload(data: dict, *, area: ServiceArea | None = None) -> dict:
    v = Validator(data)
    name = v.string("name", required=area is None, min_length=2, max_length=160)
    city = v.string("city", max_length=120)
    state = v.string("state", max_length=120)
    radius = v.number("radius_km", minimum=0.5, maximum=100)
    latitude = v.number("center_latitude", minimum=-90, maximum=90)
    longitude = v.number("center_longitude", minimum=-180, maximum=180)
    postal_codes = v.string("postal_codes", max_length=500)
    is_active = data.get("is_active")
    v.finish()
    return {
        "name": name,
        "city": city,
        "state": state,
        "radius_km": radius,
        "center_latitude": latitude,
        "center_longitude": longitude,
        "postal_codes": postal_codes,
        "is_active": is_active if isinstance(is_active, bool) else None,
    }


@bp.post("/service-areas")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_SERVICE_AREAS_MANAGE)
def create_service_area():
    data = json_body()
    payload = _service_area_payload(data)
    if ServiceArea.query.filter(db.func.lower(ServiceArea.name) == payload["name"].lower()).first():
        raise ApiError("service_area_exists", "A service area with that name already exists.", 409)
    area = ServiceArea(
        name=payload["name"],
        city=payload["city"] or "Kolkata",
        state=payload["state"] or "West Bengal",
        radius_km=payload["radius_km"] or 8,
        center_latitude=payload["center_latitude"],
        center_longitude=payload["center_longitude"],
        postal_codes=payload["postal_codes"] or "",
        is_active=payload["is_active"] if payload["is_active"] is not None else True,
    )
    db.session.add(area)
    db.session.flush()
    audit(
        "admin.service_area_created",
        "service_area",
        area.id,
        actor=current_user(),
        summary=f"Service area created: {area.name}",
    )
    db.session.commit()
    return jsonify({"data": serialize_service_area(area, include_counts=True)}), 201


@bp.patch("/service-areas/<int:area_id>")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_SERVICE_AREAS_MANAGE)
def update_service_area(area_id: int):
    area = db.session.get(ServiceArea, area_id)
    if area is None:
        raise ApiError("not_found", "That service area does not exist.", 404)
    payload = _service_area_payload(json_body(), area=area)
    if payload["name"]:
        area.name = payload["name"]
    for key in ("city", "state", "radius_km", "center_latitude", "center_longitude", "postal_codes"):
        if payload[key] is not None:
            setattr(area, key, payload[key])
    if payload["is_active"] is not None:
        area.is_active = payload["is_active"]
    audit(
        "admin.service_area_updated",
        "service_area",
        area.id,
        actor=current_user(),
        summary=f"Service area updated: {area.name}",
    )
    db.session.commit()
    return jsonify({"data": serialize_service_area(area, include_counts=True)})


# --------------------------------------------------------------------------- #
# Matching configuration and platform settings
# --------------------------------------------------------------------------- #
@bp.get("/matching-config")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_MATCHING_CONFIGURE)
def matching_config():
    stored = AdminSetting.query.filter_by(key=MATCHING_SETTINGS_KEY).first()
    return jsonify(
        {
            "data": {
                "effective": routing_config(),
                "overrides": (stored.value if stored else {}) or {},
                "bounds": {key: {"min": value[0], "max": value[1]} for key, value in MATCHING_BOUNDS.items()},
                "updated_at": domain.iso(stored.updated_at) if stored else None,
                "disclaimer": (
                    "These thresholds tune the deterministic insertion heuristic. "
                    "They are not presented as universally optimal."
                ),
            }
        }
    )


@bp.patch("/matching-config")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_MATCHING_CONFIGURE)
@rate_limit(30, 60, scope="admin-matching")
def update_matching_config():
    data = json_body()
    overrides = data.get("overrides")
    if not isinstance(overrides, dict):
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            422,
            fields={"overrides": "Provide an object of matching settings."},
        )
    cleaned: dict[str, float | int] = {}
    errors: dict[str, str] = {}
    for key, raw in overrides.items():
        if key not in MATCHING_BOUNDS:
            errors[key] = "Unknown matching setting."
            continue
        minimum, maximum = MATCHING_BOUNDS[key]
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors[key] = "Expected a number."
            continue
        if not minimum <= value <= maximum:
            errors[key] = f"Use a value between {minimum:g} and {maximum:g}."
            continue
        cleaned[key] = int(value) if float(value).is_integer() and isinstance(minimum, int) else value
    if errors:
        raise ApiError("validation_failed", "Some fields need attention.", 422, fields=errors)

    row = AdminSetting.query.filter_by(key=MATCHING_SETTINGS_KEY).first()
    merged = dict((row.value or {}) if row else {})
    merged.update(cleaned)
    if row is None:
        row = AdminSetting(key=MATCHING_SETTINGS_KEY, value=merged, description="Matching overrides")
        db.session.add(row)
    else:
        row.value = merged
        row.updated_by_id = current_user().id
    audit(
        "admin.matching_config_updated",
        "admin_setting",
        row.id,
        actor=current_user(),
        summary="Matching configuration updated",
        event_metadata={"overrides": cleaned},
    )
    db.session.commit()
    return jsonify(
        {
            "data": {
                "effective": routing_config(),
                "overrides": merged,
                "updated_at": domain.iso(row.updated_at),
            }
        }
    )


@bp.get("/settings")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_SETTINGS_MANAGE)
def list_settings():
    rows = AdminSetting.query.order_by(AdminSetting.key).all()
    return jsonify(
        {
            "data": [
                {
                    "key": row.key,
                    "value": row.value,
                    "description": row.description,
                    "updated_at": domain.iso(row.updated_at),
                    "updated_by": (
                        {"id": row.updated_by.id, "full_name": row.updated_by.full_name}
                        if row.updated_by
                        else None
                    ),
                }
                for row in rows
            ]
        }
    )


@bp.patch("/settings/<path:key>")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_SETTINGS_MANAGE)
def update_setting(key: str):
    data = json_body()
    if "value" not in data or not isinstance(data["value"], (dict, list, str, int, float, bool)):
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            422,
            fields={"value": "Provide a JSON value."},
        )
    description = Validator(data).string("description", max_length=500)
    row = AdminSetting.query.filter_by(key=key).first()
    if row is None:
        row = AdminSetting(key=key[:120], value=data["value"], description=description)
        db.session.add(row)
    else:
        row.value = data["value"]
        row.description = description or row.description
        row.updated_by_id = current_user().id
    audit(
        "admin.setting_updated",
        "admin_setting",
        getattr(row, "id", None),
        actor=current_user(),
        summary=f"Setting '{key}' updated",
        event_metadata={"key": key},
    )
    db.session.commit()
    return jsonify(
        {"data": {"key": key, "value": row.value, "updated_at": domain.iso(row.updated_at)}}
    )


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #
@bp.get("/audit")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_AUDIT_VIEW)
def audit_log():
    query = AuditLog.query
    action = (request.args.get("action") or "").strip()
    if action:
        query = query.filter(AuditLog.action.like(f"%{action}%"))
    role = request.args.get("role")
    if role:
        if role not in domain.ROLES:
            raise ApiError("invalid_role", "Unknown role filter.", 422)
        query = query.filter(AuditLog.actor_role == role)
    text = (request.args.get("q") or "").strip()
    if text:
        query = query.filter(AuditLog.summary.ilike(f"%{text}%"))
    rows = query.order_by(AuditLog.created_at.desc()).limit(MAX_ROWS).all()
    return _paginate(rows, serialize_audit_log)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
@bp.get("/exceptions")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_EXCEPTIONS_RESOLVE)
def list_exceptions():
    from ..serializers import serialize_delivery_exception

    query = DeliveryException.query
    status = request.args.get("status")
    if status:
        if status not in domain.EXCEPTION_STATUSES:
            raise ApiError("invalid_status", "Unknown exception status.", 422)
        query = query.filter(DeliveryException.status == status)
    rows = query.order_by(DeliveryException.created_at.desc()).limit(MAX_ROWS).all()
    return _paginate(rows, serialize_delivery_exception)


@bp.patch("/exceptions/<int:exception_id>")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_EXCEPTIONS_RESOLVE)
def resolve_exception(exception_id: int):
    from ..serializers import serialize_delivery_exception

    row = db.session.get(DeliveryException, exception_id)
    if row is None:
        raise ApiError("not_found", "That exception does not exist.", 404)
    data = json_body()
    v = Validator(data)
    status = v.choice(
        "status", (domain.EXCEPTION_RESOLVED, domain.EXCEPTION_REJECTED), required=True
    )
    note = v.string("resolution_note", required=True, min_length=5, max_length=1500)
    v.finish()
    row.status = status
    row.resolution_note = note
    row.resolved_by_id = current_user().id
    row.resolved_at = domain.utcnow()
    audit(
        "admin.exception_reviewed",
        "delivery_exception",
        row.id,
        actor=current_user(),
        summary=f"Exception #{row.id} {status}",
        reason=note,
    )
    db.session.commit()
    return jsonify({"data": serialize_delivery_exception(row)})

