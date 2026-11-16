"""Manager dispatch API: operations summary, order queue, drivers, batches and
route-aware matching suggestions.

Every read and write is scoped server-side: a manager only sees orders whose
pickup lies inside their assigned service areas and drivers assigned to those
areas. Administrators may use the same endpoints across the platform. Dispatch
decisions always revalidate duty, verification, service area, capacity,
precedence, windows and deadlines — a suggestion never assigns work by itself.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from .. import domain
from ..access import assert_batch_access, can_view_batch, manager_covers_order
from ..errors import ApiError
from ..extensions import db
from ..models import (
    DeliveryBatch,
    DeliveryException,
    DriverLocationEvent,
    MatchingSuggestion,
    Order,
    ProofMedia,
    User,
    UserSession,
)
from ..security import (
    current_user,
    login_required,
    permission_required,
    rate_limit,
    require_password_changed,
    role_required,
)
from ..serializers import (
    serialize_assignment,
    serialize_batch,
    serialize_batch_summary,
    serialize_driver_location,
    serialize_driver_profile,
    serialize_duty_session,
    serialize_matching_suggestion,
    serialize_order_detail,
    serialize_order_summary,
    serialize_proof_media,
    serialize_vehicle,
)
from ..services import dispatch, duty
from ..services import matching
from ..services import orders as order_service
from ..services.audit import audit
from ..validation import Validator, json_body

bp = Blueprint("manager", __name__, url_prefix="/api/v1/manager")

REVIEW_QUEUE = (domain.ORDER_SUBMITTED, domain.ORDER_PENDING_REVIEW)
MAX_QUEUE_SCAN = 500
MAX_SCAN_ORDERS = 25
MAX_BATCH_ORDERS = 12


# --------------------------------------------------------------------------- #
# Scope helpers
# --------------------------------------------------------------------------- #
def _actor():
    user = current_user()
    if user.role == domain.ROLE_MANAGER and user.manager_profile is None:
        raise ApiError(
            "manager_profile_missing",
            "This manager account has no assigned service areas.",
            403,
        )
    return user


def _scoped_order(actor, order_id: int) -> Order:
    order = db.session.get(Order, order_id)
    if order is None:
        raise ApiError("not_found", "That order does not exist.", 404)
    if actor.role != domain.ROLE_ADMIN and not manager_covers_order(actor, order):
        raise ApiError("forbidden", "That order is outside your service areas.", 403)
    return order


def _scoped_batch(actor, batch_id: int) -> DeliveryBatch:
    batch = db.session.get(DeliveryBatch, batch_id)
    if batch is None:
        raise ApiError("not_found", "That batch does not exist.", 404)
    assert_batch_access(actor, batch)
    return batch


def _driver_for_assignment(actor, driver_id: int) -> User:
    driver = db.session.get(User, driver_id)
    if driver is None or driver.role != domain.ROLE_DRIVER:
        raise ApiError("not_found", "That delivery partner does not exist.", 404)
    if driver.id not in {row.id for row in dispatch.drivers_for_actor(actor)}:
        raise ApiError(
            "forbidden", "That delivery partner is outside your service areas.", 403
        )
    return driver


def _visible_orders(actor) -> list[Order]:
    """Recent orders the manager may dispatch (pickup inside their areas)."""
    rows = (
        Order.query.order_by(Order.created_at.desc()).limit(MAX_QUEUE_SCAN).all()
    )
    if actor.role == domain.ROLE_ADMIN:
        return rows
    return [row for row in rows if manager_covers_order(actor, row)]


def _visible_batches(actor) -> list[DeliveryBatch]:
    rows = (
        DeliveryBatch.query.order_by(DeliveryBatch.planned_start.desc())
        .limit(MAX_QUEUE_SCAN)
        .all()
    )
    return [row for row in rows if can_view_batch(actor, row)]


def _requested_orders(actor, order_ids, *, limit: int = MAX_BATCH_ORDERS) -> list[Order]:
    if not isinstance(order_ids, list) or not order_ids:
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            422,
            fields={"order_ids": "Select at least one order."},
        )
    try:
        ids = [int(value) for value in order_ids]
    except (TypeError, ValueError):
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            422,
            fields={"order_ids": "Expected integer order ids."},
        )
    if len(set(ids)) != len(ids):
        raise ApiError("batch_duplicate_order", "Each order can appear only once.", 422)
    if len(ids) > limit:
        raise ApiError(
            "batch_too_large", f"Keep batches to {limit} orders or fewer.", 422
        )
    return [_scoped_order(actor, order_id) for order_id in ids]


def _pagination():
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        per_page = 20
    return page, min(max(1, per_page), 100)


# --------------------------------------------------------------------------- #
# Driver monitoring helpers
# --------------------------------------------------------------------------- #
def _latest_location(profile) -> DriverLocationEvent | None:
    return (
        DriverLocationEvent.query.filter_by(driver_id=profile.id)
        .order_by(DriverLocationEvent.received_at.desc())
        .first()
    )


def _driver_payload(user, *, now: datetime | None = None) -> dict:
    now = now or domain.utcnow()
    profile = user.driver_profile
    session = duty.active_session(profile) if profile is not None else None
    is_live = bool(session is not None and duty.session_is_recent(session))
    location = _latest_location(profile) if profile is not None else None
    timeout = int(current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15))
    batch, plan = dispatch.active_batch_for_driver(user)
    load = dispatch.load_snapshot(user)
    return {
        "driver": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "status": user.status,
        },
        "profile": serialize_driver_profile(profile, include_user=False)
        if profile is not None
        else None,
        "duty": serialize_duty_session(session),
        "is_live": is_live,
        "duty_label": (
            domain.DUTY_LABELS.get(session.status, session.status) if session else "Off duty"
        ),
        "last_location": serialize_driver_location(
            location, timeout_minutes=timeout
        )
        if location is not None
        else None,
        "active_batch": serialize_batch_summary(batch) if batch is not None else None,
        "route_plan_id": plan.id if plan is not None else None,
        "load": load,
        "generated_at": domain.iso(now),
    }


def _live_payload(user, *, now: datetime | None = None) -> dict | None:
    profile = user.driver_profile
    if profile is None:
        return None
    session = duty.active_session(profile)
    if session is None or session.ended_at is not None:
        return None
    now = now or domain.utcnow()
    location = _latest_location(profile)
    timeout = int(current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15))
    serialized = (
        serialize_driver_location(location, timeout_minutes=timeout)
        if location is not None
        else None
    )
    if serialized is None:
        tracking_status = "unavailable"
        tracking_label = "Tracking unavailable"
    elif serialized["is_recent"]:
        tracking_status = "live_recent"
        tracking_label = "Live recent location"
    else:
        tracking_status = "stale"
        tracking_label = "Stale location"
    batch, plan = dispatch.active_batch_for_driver(user)
    return {
        "driver": {
            "id": user.id,
            "full_name": user.full_name,
            "phone": user.phone,
        },
        "duty": serialize_duty_session(session),
        "duty_label": domain.DUTY_LABELS.get(session.status, session.status),
        "location": serialized,
        "tracking_status": tracking_status,
        "tracking_label": tracking_label,
        "active_batch": serialize_batch_summary(batch) if batch is not None else None,
        "next_stop": (
            next(
                (
                    stop
                    for stop in plan.stops
                    if stop.status in (domain.STOP_PENDING, domain.STOP_ARRIVED)
                ),
                None,
            )
            if plan is not None
            else None
        ),
        "load": dispatch.load_snapshot(user),
        "generated_at": domain.iso(now),
    }


# --------------------------------------------------------------------------- #
# Operations summary
# --------------------------------------------------------------------------- #
@bp.get("/summary")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def summary():
    actor = _actor()
    now = domain.utcnow()
    day_start = duty.today_start()
    orders = _visible_orders(actor)
    driver_users = dispatch.drivers_for_actor(actor)
    drivers = [_driver_payload(user, now=now) for user in driver_users]

    def count(statuses):
        return sum(1 for order in orders if order.status in statuses)

    active = [order for order in orders if order.status in domain.ACTIVE_ORDER_STATUSES]
    delayed = [
        order
        for order in active
        if order.delivery_deadline is not None and order.delivery_deadline < now
    ]
    # Failed orders are terminal, so they are not in ACTIVE_ORDER_STATUSES, but
    # they still need a manager decision. Include them together with open proof
    # reviews and delayed active work.
    attention = [
        order
        for order in orders
        if order.status in (domain.ORDER_FAILED, domain.ORDER_PROOF_PENDING)
        or (order in active and order in delayed)
    ]

    batches = _visible_batches(actor)
    exceptions = (
        DeliveryException.query.filter_by(status=domain.EXCEPTION_OPEN)
        .filter(DeliveryException.order_id.in_([row.id for row in orders] or [-1]))
        .count()
    )
    driver_ids = [user.id for user in driver_users]
    logged_in = (
        db.session.query(UserSession.user_id)
        .filter(
            UserSession.user_id.in_(driver_ids or [-1]),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        .distinct()
        .count()
    )

    live_drivers = [row for row in drivers if row["is_live"]]
    statuses = [
        row["duty"]["status"] for row in drivers if row["is_live"] and row["duty"]
    ]
    on_duty_open = [row for row in drivers if row["duty"] is not None]
    active_batches = [
        batch
        for batch in batches
        if batch.status in (domain.BATCH_ASSIGNED, domain.BATCH_ACTIVE)
    ]

    return jsonify(
        {
            "data": {
                "manager": {
                    "id": actor.id,
                    "full_name": actor.full_name,
                    "role": actor.role,
                    "service_areas": (
                        [link.service_area.name for link in actor.manager_profile.service_areas]
                        if actor.manager_profile
                        else []
                    ),
                },
                "drivers": {
                    "total": len(driver_users),
                    "logged_in": logged_in,
                    "on_duty": len(on_duty_open),
                    "available": sum(
                        1
                        for status in statuses
                        if status in domain.ACCEPTING_WORK_STATUSES
                    ),
                    "busy": statuses.count(domain.DUTY_BUSY),
                    "on_break": statuses.count(domain.DUTY_ON_BREAK),
                    "offline": len(driver_users) - len(on_duty_open),
                    "with_active_batch": sum(
                        1 for row in drivers if row["active_batch"] is not None
                    ),
                    "live": len(live_drivers),
                },
                "orders": {
                    "new_today": sum(
                        1 for order in orders if order.created_at and order.created_at >= day_start
                    ),
                    "pending": count(REVIEW_QUEUE),
                    "awaiting_assignment": count((domain.ORDER_AWAITING_ASSIGNMENT,)),
                    "assigned": count(
                        (
                            domain.ORDER_ASSIGNED,
                            domain.ORDER_PICKUP_SCHEDULED,
                            domain.ORDER_PICKUP_ARRIVED,
                        )
                    ),
                    "in_progress": count(domain.IN_CUSTODY_STATUSES),
                    "active": len(active),
                    "delivered_today": sum(
                        1
                        for order in orders
                        if order.status == domain.ORDER_DELIVERED
                        and order.delivered_at is not None
                        and order.delivered_at >= day_start
                    ),
                    "delivered_total": count((domain.ORDER_DELIVERED,)),
                    "failed": count((domain.ORDER_FAILED,)),
                    "delayed": len(delayed),
                    "needs_attention": len(attention),
                },
                "batches": {
                    "active": sum(
                        1 for batch in active_batches if batch.status == domain.BATCH_ACTIVE
                    ),
                    "assigned": sum(
                        1 for batch in active_batches if batch.status == domain.BATCH_ASSIGNED
                    ),
                    "total": len(batches),
                },
                "exceptions": {"open": exceptions},
                "attention_orders": [serialize_order_summary(row) for row in attention[:5]],
                "generated_at": domain.iso(now),
            }
        }
    )


# --------------------------------------------------------------------------- #
# Order queue
# --------------------------------------------------------------------------- #
@bp.get("/orders")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_VIEW)
def list_orders():
    actor = _actor()
    orders = _visible_orders(actor)
    now = domain.utcnow()

    status_raw = request.args.get("status")
    if status_raw:
        statuses = [value.strip() for value in status_raw.split(",") if value.strip()]
        unknown = [value for value in statuses if value not in domain.ORDER_STATUSES]
        if unknown:
            raise ApiError(
                "invalid_status", "Unknown order status filter.", 422, details={"unknown": unknown}
            )
        orders = [order for order in orders if order.status in statuses]

    service_type = request.args.get("service_type")
    if service_type:
        if service_type not in domain.SERVICE_TYPES:
            raise ApiError("invalid_service_type", "Unknown service type.", 422)
        orders = [order for order in orders if order.service_type == service_type]

    area = (request.args.get("area") or "").strip().casefold()
    if area:
        orders = [
            order
            for order in orders
            if order.pickup_address and area in order.pickup_address.area.casefold()
        ]

    query_text = (request.args.get("q") or "").strip().casefold()
    if query_text:
        def matches(order) -> bool:
            consumer = order.consumer
            haystack = " ".join(
                value or ""
                for value in (
                    order.order_number,
                    consumer.full_name if consumer else "",
                    consumer.phone if consumer else "",
                    order.pickup_address.area if order.pickup_address else "",
                )
            ).casefold()
            return query_text in haystack

        orders = [order for order in orders if matches(order)]

    assignment_filter = request.args.get("assignment")
    if assignment_filter == "unassigned":
        orders = [order for order in orders if order.status == domain.ORDER_AWAITING_ASSIGNMENT]
    elif assignment_filter == "assigned":
        orders = [
            order
            for order in orders
            if order.status
            in (
                domain.ORDER_ASSIGNED,
                domain.ORDER_PICKUP_SCHEDULED,
                domain.ORDER_PICKUP_ARRIVED,
            )
        ]
    if request.args.get("overdue") in {"1", "true", "yes"}:
        orders = [
            order
            for order in orders
            if order.status in domain.ACTIVE_ORDER_STATUSES
            and order.delivery_deadline is not None
            and order.delivery_deadline < now
        ]

    page, per_page = _pagination()
    start = (page - 1) * per_page
    rows = orders[start : start + per_page]
    return jsonify(
        {
            "data": [
                serialize_order_summary(order, include_consumer=True) for order in rows
            ],
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": len(orders),
                "generated_at": domain.iso(now),
            },
        }
    )


@bp.get("/orders/<int:order_id>")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_VIEW)
def get_order(order_id: int):
    actor = _actor()
    order = _scoped_order(actor, order_id)
    data = serialize_order_detail(
        order, include_consumer=True, include_driver_contact=True
    )
    suggestions = (
        MatchingSuggestion.query.filter(
            MatchingSuggestion.order_id == order.id,
            MatchingSuggestion.status.in_(
                (domain.SUGGESTION_PENDING, domain.SUGGESTION_APPROVED)
            ),
        )
        .order_by(MatchingSuggestion.created_at.desc())
        .all()
    )
    data["suggestions"] = [
        serialize_matching_suggestion(row, include_order=False) for row in suggestions
    ]
    return jsonify({"data": data})


@bp.post("/orders/<int:order_id>/review")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_REVIEW)
@require_password_changed()
def review_order(order_id: int):
    actor = _actor()
    data = json_body()
    v = Validator(data)
    decision = v.choice("decision", ("approve", "reject"), required=True)
    reason = v.string("reason", max_length=500)
    v.finish()

    order = _scoped_order(actor, order_id)
    if order.status not in REVIEW_QUEUE:
        raise ApiError(
            "order_not_in_review",
            "Only a submitted or pending-review order can be reviewed.",
            409,
            details={"status": order.status},
        )

    if decision == "approve":
        order_service.record_status(
            order,
            domain.ORDER_AWAITING_ASSIGNMENT,
            actor=actor,
            source="manager",
            reason=reason or "Approved for scheduling",
        )
        order.approved_by_id = actor.id
        order.approved_at = domain.utcnow()
        audit(
            "dispatch.order_approved",
            "order",
            order.id,
            actor=actor,
            summary=f"Order {order.order_number} approved for scheduling",
            reason=reason,
        )
    else:
        if not reason or len(reason) < 5:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                422,
                fields={"reason": "Explain why the order is rejected (5+ characters)."},
            )
        order_service.cancel_order(order, actor, reason, source="manager")
        order.rejection_reason = reason
        audit(
            "dispatch.order_rejected",
            "order",
            order.id,
            actor=actor,
            summary=f"Order {order.order_number} rejected",
            reason=reason,
        )
    db.session.commit()
    return jsonify(
        {
            "data": {
                "order": serialize_order_detail(
                    order, include_consumer=True, include_driver_contact=True
                )
            }
        }
    )


@bp.post("/orders/<int:order_id>/assign")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_ASSIGN)
@require_password_changed()
@rate_limit(60, 60, scope="manager-assign")
def assign_order(order_id: int):
    actor = _actor()
    data = json_body()
    v = Validator(data)
    driver_id = v.integer("driver_id", required=True, minimum=1)
    vehicle_id = v.integer("vehicle_id", minimum=1)
    reason = v.string("reason", max_length=500)
    v.finish()

    order = _scoped_order(actor, order_id)
    driver = _driver_for_assignment(actor, driver_id)
    assignment = dispatch.assign_order(
        order,
        driver,
        actor=actor,
        vehicle_id=vehicle_id,
        source="manager",
        reason=reason,
    )
    db.session.commit()
    return jsonify(
        {
            "data": {
                "order": serialize_order_detail(
                    order, include_consumer=True, include_driver_contact=True
                ),
                "assignment": serialize_assignment(assignment),
            }
        }
    )


@bp.post("/orders/<int:order_id>/reassign")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_ASSIGN)
@require_password_changed()
@rate_limit(60, 60, scope="manager-reassign")
def reassign_order(order_id: int):
    actor = _actor()
    data = json_body()
    v = Validator(data)
    driver_id = v.integer("driver_id", required=True, minimum=1)
    vehicle_id = v.integer("vehicle_id", minimum=1)
    reason = v.string("reason", required=True, min_length=5, max_length=500)
    v.finish()

    order = _scoped_order(actor, order_id)
    driver = _driver_for_assignment(actor, driver_id)
    assignment = dispatch.reassign_order(
        order,
        driver,
        actor=actor,
        vehicle_id=vehicle_id,
        reason=reason,
    )
    db.session.commit()
    return jsonify(
        {
            "data": {
                "order": serialize_order_detail(
                    order, include_consumer=True, include_driver_contact=True
                ),
                "assignment": serialize_assignment(assignment),
            }
        }
    )


# --------------------------------------------------------------------------- #
# Driver monitoring
# --------------------------------------------------------------------------- #
@bp.get("/drivers")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_DRIVERS_VIEW)
def list_drivers():
    actor = _actor()
    now = domain.utcnow()
    rows = [_driver_payload(user, now=now) for user in dispatch.drivers_for_actor(actor)]
    return jsonify(
        {
            "data": rows,
            "meta": {"total": len(rows), "generated_at": domain.iso(now)},
        }
    )


@bp.get("/drivers/live")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def live_drivers():
    actor = _actor()
    now = domain.utcnow()
    rows = [
        payload
        for payload in (
            _live_payload(user, now=now) for user in dispatch.drivers_for_actor(actor)
        )
        if payload is not None
    ]
    return jsonify(
        {
            "data": rows,
            "meta": {
                "total": len(rows),
                "heartbeat_timeout_minutes": int(
                    current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15)
                ),
                "note": (
                    "Only the latest reported on-duty location is shown. "
                    "“Tracking unavailable” means no location has been reported."
                ),
                "generated_at": domain.iso(now),
            },
        }
    )


# --------------------------------------------------------------------------- #
# Batches
# --------------------------------------------------------------------------- #
def _candidate_payload(row: dict) -> dict:
    return {
        "driver": row["driver"],
        "compatible": row["compatible"],
        "blockers": row["blockers"],
        "reasons": row["reasons"],
        "vehicle": serialize_vehicle(row["vehicle"]) if row["vehicle"] else None,
        "capacity": row["capacity"],
        "load": row["snapshot"],
        "route": row["route"],
    }


@bp.post("/batches/proposal")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_BATCHES_MANAGE)
@rate_limit(30, 60, scope="manager-proposal")
def batch_proposal():
    actor = _actor()
    data = json_body()
    orders = _requested_orders(actor, data.get("order_ids"))
    candidates = [
        dispatch.batch_candidate(orders, driver)
        for driver in dispatch.drivers_for_actor(actor)
    ]
    candidates.sort(
        key=lambda row: (
            not row["compatible"],
            row["route"]["distance_km"] if row["route"] else float("inf"),
            row["driver"]["full_name"],
        )
    )
    return jsonify(
        {
            "data": {
                "orders": [serialize_order_summary(order) for order in orders],
                "order_count": len(orders),
                "compatible": any(row["compatible"] for row in candidates),
                "candidates": [_candidate_payload(row) for row in candidates],
                "generated_at": domain.iso(domain.utcnow()),
            }
        }
    )


@bp.get("/batches")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def list_batches():
    actor = _actor()
    status = request.args.get("status")
    batches = _visible_batches(actor)
    if status:
        if status not in domain.BATCH_STATUSES:
            raise ApiError("invalid_status", "Unknown batch status.", 422)
        batches = [batch for batch in batches if batch.status == status]
    page, per_page = _pagination()
    start = (page - 1) * per_page
    rows = batches[start : start + per_page]
    return jsonify(
        {
            "data": [serialize_batch_summary(batch) for batch in rows],
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": len(batches),
                "generated_at": domain.iso(domain.utcnow()),
            },
        }
    )


@bp.get("/batches/<int:batch_id>")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_OPS_VIEW)
def get_batch(batch_id: int):
    actor = _actor()
    batch = _scoped_batch(actor, batch_id)
    return jsonify({"data": serialize_batch(batch)})


@bp.post("/batches")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_BATCHES_MANAGE)
@require_password_changed()
@rate_limit(30, 60, scope="manager-batch")
def create_batch():
    actor = _actor()
    data = json_body()
    v = Validator(data)
    driver_id = v.integer("driver_id", required=True, minimum=1)
    vehicle_id = v.integer("vehicle_id", minimum=1)
    planned_start = v.datetime("planned_start")
    notes = v.string("notes", max_length=1000)
    v.finish()

    orders = _requested_orders(actor, data.get("order_ids"))
    driver = _driver_for_assignment(actor, driver_id)
    batch = dispatch.create_batch(
        orders,
        driver,
        actor=actor,
        vehicle_id=vehicle_id,
        planned_start=planned_start,
        notes=notes,
    )
    db.session.commit()
    return jsonify({"data": serialize_batch(batch)}), 201


@bp.post("/batches/<int:batch_id>/assign-driver")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_BATCHES_MANAGE)
@require_password_changed()
def reassign_batch(batch_id: int):
    actor = _actor()
    data = json_body()
    v = Validator(data)
    driver_id = v.integer("driver_id", required=True, minimum=1)
    reason = v.string("reason", required=True, min_length=5, max_length=500)
    v.finish()

    batch = _scoped_batch(actor, batch_id)
    driver = _driver_for_assignment(actor, driver_id)
    dispatch.assign_batch_driver(batch, driver, actor=actor, reason=reason)
    db.session.commit()
    return jsonify({"data": serialize_batch(batch)})


@bp.post("/batches/<int:batch_id>/cancel")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_BATCHES_MANAGE)
@require_password_changed()
def cancel_batch(batch_id: int):
    actor = _actor()
    data = json_body()
    v = Validator(data)
    reason = v.string("reason", required=True, min_length=5, max_length=500)
    v.finish()

    batch = _scoped_batch(actor, batch_id)
    dispatch.cancel_batch(batch, actor=actor, reason=reason)
    db.session.commit()
    return jsonify({"data": serialize_batch(batch)})


# --------------------------------------------------------------------------- #
# Route-aware matching
# --------------------------------------------------------------------------- #
def _evaluation_payload(evaluation: dict) -> dict:
    return {
        "driver": {
            "id": evaluation["driver"].id,
            "full_name": evaluation["driver"].full_name,
        },
        "compatible": evaluation["compatible"],
        "blockers": evaluation["blockers"],
        "reasons": evaluation["reasons"],
        "detour_km": evaluation["detour_km"],
        "added_duration_minutes": evaluation["added_duration_minutes"],
        "pickup_route_distance_km": evaluation["pickup_route_distance_km"],
        "current_distance_km": evaluation["current_distance_km"],
        "proposed_distance_km": evaluation["proposed_distance_km"],
        "distance_source": evaluation["distance_source"],
        "vehicle": (
            serialize_vehicle(evaluation["vehicle"]) if evaluation["vehicle"] else None
        ),
        "batch_id": evaluation["batch"].id if evaluation["batch"] else None,
    }


@bp.post("/matching/scan")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_BATCHES_MANAGE)
@require_password_changed()
@rate_limit(30, 60, scope="manager-match-scan")
def scan_matches():
    actor = _actor()
    data = json_body()
    if data.get("order_ids"):
        orders = _requested_orders(actor, data.get("order_ids"), limit=MAX_SCAN_ORDERS)
    else:
        orders = [
            order
            for order in _visible_orders(actor)
            if order.status == domain.ORDER_AWAITING_ASSIGNMENT
        ][:MAX_SCAN_ORDERS]
    for order in orders:
        if order.status != domain.ORDER_AWAITING_ASSIGNMENT:
            raise ApiError(
                "order_not_assignable",
                "Approve the order for scheduling before matching it.",
                409,
                details={"order_id": order.id, "status": order.status},
            )

    results = []
    for order in orders:
        outcome = matching.scan_order(order, actor)
        results.append(
            {
                "order": serialize_order_summary(order),
                "suggestions_created": len(outcome["created"]),
                "suggestion_ids": [row.id for row in outcome["created"]],
                "evaluations": [
                    _evaluation_payload(row) for row in outcome["evaluations"]
                ],
            }
        )
    db.session.commit()
    return jsonify(
        {
            "data": results,
            "meta": {
                "orders_scanned": len(results),
                "suggestions_created": sum(row["suggestions_created"] for row in results),
                "generated_at": domain.iso(domain.utcnow()),
                "algorithm": (
                    "deterministic pickup/delivery insertion on the driver's remaining route"
                ),
            },
        }
    )


@bp.get("/matching/suggestions")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_BATCHES_MANAGE)
def list_suggestions():
    actor = _actor()
    status = request.args.get("status", domain.SUGGESTION_PENDING)
    if status != "all" and status not in domain.SUGGESTION_STATUSES:
        raise ApiError("invalid_status", "Unknown suggestion status.", 422)
    order_id = request.args.get("order_id")
    query = MatchingSuggestion.query
    if status != "all":
        query = query.filter(MatchingSuggestion.status == status)
    if order_id:
        try:
            query = query.filter(MatchingSuggestion.order_id == int(order_id))
        except ValueError:
            raise ApiError("invalid_order_id", "Expected an integer order id.", 422)
    rows = query.order_by(MatchingSuggestion.created_at.desc()).limit(MAX_QUEUE_SCAN).all()
    if actor.role != domain.ROLE_ADMIN:
        visible = {order.id for order in _visible_orders(actor)}
        rows = [row for row in rows if row.order_id in visible]
    page, per_page = _pagination()
    start = (page - 1) * per_page
    return jsonify(
        {
            "data": [
                serialize_matching_suggestion(row) for row in rows[start : start + per_page]
            ],
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": len(rows),
                "status": status,
            },
        }
    )


def _visible_proofs(actor) -> list[ProofMedia]:
    rows = (
        ProofMedia.query.order_by(ProofMedia.received_at.desc()).limit(MAX_QUEUE_SCAN).all()
    )
    if actor.role == domain.ROLE_ADMIN:
        return rows
    return [row for row in rows if row.order_id in {o.id for o in _visible_orders(actor)}]


@bp.get("/proofs")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_PROOFS_VERIFY)
@rate_limit(120, 60, scope="manager-proofs")
def list_proofs():
    actor = _actor()
    rows = _visible_proofs(actor)
    status = request.args.get("verification_status")
    if status:
        if status not in domain.PROOF_STATUSES:
            raise ApiError("invalid_status", "Unknown proof status.", 422)
        rows = [row for row in rows if row.verification_status == status]
    page, per_page = _pagination()
    start = (page - 1) * per_page
    return jsonify(
        {
            "data": [serialize_proof_media(row) for row in rows[start : start + per_page]],
            "meta": {"page": page, "per_page": per_page, "total": len(rows)},
        }
    )


@bp.patch("/proofs/<int:proof_id>/verify")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_PROOFS_VERIFY)
@require_password_changed()
def verify_proof(proof_id: int):
    actor = _actor()
    proof = db.session.get(ProofMedia, proof_id)
    if proof is None or proof.id not in {row.id for row in _visible_proofs(actor)}:
        raise ApiError("not_found", "That proof does not exist in your scope.", 404)
    data = json_body()
    v = Validator(data)
    status = v.choice("verification_status", domain.PROOF_STATUSES, required=True)
    note = v.string("note", max_length=1000)
    v.finish()
    proof.verification_status = status
    proof.verified_by_id = actor.id
    proof.verified_at = domain.utcnow()
    if note:
        proof.notes = note
    audit(
        "dispatch.proof_reviewed",
        "proof_media",
        proof.id,
        actor=actor,
        summary=f"Proof #{proof.id} marked {status}",
        reason=note,
        event_metadata={"order_id": proof.order_id},
    )
    db.session.commit()
    return jsonify({"data": serialize_proof_media(proof)})


@bp.get("/exceptions")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_EXCEPTIONS_RESOLVE)
def list_exceptions():
    actor = _actor()
    from ..serializers import serialize_delivery_exception

    visible = {order.id for order in _visible_orders(actor)}
    rows = (
        DeliveryException.query.order_by(DeliveryException.created_at.desc())
        .limit(MAX_QUEUE_SCAN)
        .all()
    )
    if actor.role != domain.ROLE_ADMIN:
        rows = [row for row in rows if row.order_id in visible]
    status = request.args.get("status")
    if status:
        if status not in domain.EXCEPTION_STATUSES:
            raise ApiError("invalid_status", "Unknown exception status.", 422)
        rows = [row for row in rows if row.status == status]
    page, per_page = _pagination()
    start = (page - 1) * per_page
    return jsonify(
        {
            "data": [
                serialize_delivery_exception(row) for row in rows[start : start + per_page]
            ],
            "meta": {"page": page, "per_page": per_page, "total": len(rows)},
        }
    )


@bp.patch("/exceptions/<int:exception_id>")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_EXCEPTIONS_RESOLVE)
@require_password_changed()
def resolve_exception(exception_id: int):
    actor = _actor()
    from ..serializers import serialize_delivery_exception

    row = db.session.get(DeliveryException, exception_id)
    if row is None:
        raise ApiError("not_found", "That exception does not exist.", 404)
    _scoped_order(actor, row.order_id)
    data = json_body()
    v = Validator(data)
    status = v.choice(
        "status", (domain.EXCEPTION_RESOLVED, domain.EXCEPTION_REJECTED), required=True
    )
    note = v.string("resolution_note", required=True, min_length=5, max_length=1500)
    v.finish()
    row.status = status
    row.resolution_note = note
    row.resolved_by_id = actor.id
    row.resolved_at = domain.utcnow()
    audit(
        "dispatch.exception_reviewed",
        "delivery_exception",
        row.id,
        actor=actor,
        summary=f"Exception #{row.id} {status}",
        reason=note,
    )
    db.session.commit()
    return jsonify({"data": serialize_delivery_exception(row)})


@bp.get("/matching/suggestions/board")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_BATCHES_MANAGE)
def suggestion_board():
    """Grouped pending suggestions for the matching workspace."""
    actor = _actor()
    visible = {order.id for order in _visible_orders(actor)}
    rows = (
        MatchingSuggestion.query.filter(MatchingSuggestion.status == domain.SUGGESTION_PENDING)
        .order_by(MatchingSuggestion.created_at.desc())
        .limit(MAX_QUEUE_SCAN)
        .all()
    )
    rows = [row for row in rows if row.order_id in visible]
    return jsonify({"data": [serialize_matching_suggestion(row) for row in rows]})


def _scoped_suggestion(actor, suggestion_id: int) -> MatchingSuggestion:
    suggestion = db.session.get(MatchingSuggestion, suggestion_id)
    if suggestion is None:
        raise ApiError("not_found", "That suggestion does not exist.", 404)
    _scoped_order(actor, suggestion.order_id)
    return suggestion


@bp.post("/matching/suggestions/<int:suggestion_id>/approve")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_ASSIGN)
@require_password_changed()
@rate_limit(60, 60, scope="manager-suggestion-approve")
def approve_suggestion(suggestion_id: int):
    actor = _actor()
    suggestion = _scoped_suggestion(actor, suggestion_id)
    suggestion, assignment = matching.approve_suggestion(suggestion, actor)
    db.session.commit()
    return jsonify(
        {
            "data": {
                "suggestion": serialize_matching_suggestion(suggestion),
                "assignment": serialize_assignment(assignment),
                "order": serialize_order_detail(
                    suggestion.order, include_consumer=True, include_driver_contact=True
                ),
            }
        }
    )


@bp.post("/matching/suggestions/<int:suggestion_id>/reject")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
@permission_required(domain.PERM_ORDERS_ASSIGN)
@require_password_changed()
def reject_suggestion(suggestion_id: int):
    actor = _actor()
    data = json_body()
    v = Validator(data)
    note = v.string("reason", required=True, min_length=5, max_length=500)
    code = v.string("rejection_code", max_length=80)
    v.finish()
    suggestion = _scoped_suggestion(actor, suggestion_id)
    matching.reject_suggestion(suggestion, actor, note, code)
    db.session.commit()
    return jsonify({"data": serialize_matching_suggestion(suggestion)})
