"""Request creation, listing, detail, cancellation and tracking."""
from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, jsonify, request as http_request
from sqlalchemy import or_

from ..access import assert_request_access, batch_contacts_allowed, partner_user_id_for_request
from ..domain import (
    HANDLING_FLAGS,
    REQUEST_CANCELLED,
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_PARTNER,
    SERVICE_PARCEL,
    SERVICE_RETURN,
    SERVICE_TYPES,
    SIZE_CLASSES,
    batch_code,
    iso,
    request_code,
    utcnow,
)
from ..errors import ApiError
from ..extensions import db
from ..models import (
    BatchRequest,
    DeliveryRequest,
    Location,
    Parcel,
    RecipientDetail,
    ReturnDetail,
    TrackingEvent,
    User,
)
from ..security import current_user, login_required, rate_limit
from ..serializers import (
    serialize_batch,
    serialize_location,
    serialize_request,
    serialize_tracking_event,
)
from ..services import dispatch
from ..validation import Validator, json_body, pagination_args
from ..errors import paginate

bp = Blueprint("requests", __name__, url_prefix="/api/v1/requests")


def _resolve_location(raw: dict | None, label_prefix: str) -> Location:
    if raw is None:
        raise ApiError("validation_failed", "A location is required.", 422)
    if "location_id" in raw:
        location = Location.query.get(raw["location_id"])
        if location is None:
            raise ApiError("location_not_found", "That saved sample location was not found.", 404)
        return location
    return Location(
        label=raw["label"],
        address_line=raw["address_line"],
        area=raw["area"],
        city=raw["city"],
        postal_code=raw.get("postal_code"),
        latitude=raw["latitude"],
        longitude=raw["longitude"],
        source="customer_pin",
        is_sample=False,
    )


@bp.post("")
@login_required
@rate_limit(20, 300, scope="request_create")
def create_request():
    user = current_user()
    if user.role != ROLE_CUSTOMER:
        raise ApiError("forbidden", "Only customer accounts can create delivery requests.", 403)
    data = json_body()
    v = Validator(data)
    service_type = v.choice("type", SERVICE_TYPES, required=True)
    pickup_raw = v.location("pickup")
    destination_raw = v.location("destination")
    window_start = v.datetime("pickup_window_start", required=True)
    window_end = v.datetime("pickup_window_end", required=True)
    deadline = v.datetime("delivery_deadline", required=True)
    notes = v.string("notes", max_length=1000, required=False)

    parcel_raw = data.get("parcel") or {}
    if not isinstance(parcel_raw, dict):
        raise ApiError("validation_failed", "Parcel details are invalid.", 422)
    pv = Validator(parcel_raw)
    description = pv.string("description", required=True, min_length=3, max_length=255)
    category = pv.string("category", max_length=80) or "general"
    weight = pv.number("weight_kg", required=True, minimum=0.05, maximum=150)
    volume = pv.number("volume_m3", required=True, minimum=0.001, maximum=1.5)
    size_class = pv.choice("size_class", SIZE_CLASSES, default="small")
    handling = pv.string_list("handling", options=HANDLING_FLAGS)
    declared_value = pv.number("declared_value_inr", minimum=0, maximum=500000)
    pv.finish()

    return_raw = data.get("return") or {}
    recipient_raw = data.get("recipient") or {}
    hub_name = None
    return_reference = None
    retailer = None
    recipient_name = None
    recipient_phone = None
    instructions = None
    if service_type == SERVICE_RETURN:
        rv = Validator(return_raw if isinstance(return_raw, dict) else {})
        hub_name = rv.string("authorized_hub_name", required=True, min_length=3, max_length=160)
        return_reference = rv.string("return_reference", max_length=120, required=False)
        retailer = rv.string("retailer", max_length=160, required=False)
        rv.finish()
    else:
        rv = Validator(recipient_raw if isinstance(recipient_raw, dict) else {})
        recipient_name = rv.string("name", required=True, min_length=2, max_length=160)
        recipient_phone = rv.string("phone", max_length=40, required=False)
        instructions = rv.string("instructions", max_length=500, required=False)
        rv.finish()

    v.finish()
    now = utcnow()
    if window_end <= window_start:
        raise ApiError(
            "validation_failed",
            "The pickup window must end after it starts.",
            422,
            fields={"pickup_window_end": "End must be after the start."},
        )
    if window_end <= now:
        raise ApiError(
            "validation_failed",
            "The pickup window must end in the future.",
            422,
            fields={"pickup_window_end": "Choose a future pickup window."},
        )
    if deadline < window_start:
        raise ApiError(
            "validation_failed",
            "The delivery deadline cannot be earlier than the pickup window.",
            422,
            fields={"delivery_deadline": "Choose a deadline after the pickup window starts."},
        )

    pickup = _resolve_location(pickup_raw, "pickup")
    destination = _resolve_location(destination_raw, "destination")
    db.session.add_all([pickup, destination])
    db.session.flush()

    delivery_request = DeliveryRequest(
        customer_id=user.id,
        type=service_type,
        pickup_location_id=pickup.id,
        destination_location_id=destination.id,
        pickup_window_start=window_start,
        pickup_window_end=window_end,
        delivery_deadline=deadline,
        status="pending_matching",
        notes=notes,
    )
    db.session.add(delivery_request)
    db.session.flush()
    parcel = Parcel(
        request_id=delivery_request.id,
        description=description,
        category=category,
        weight_kg=weight,
        volume_m3=volume,
        size_class=size_class,
        handling_flags=",".join(handling),
        declared_value_inr=declared_value,
        tracking_number=f"RTN-TRK-{900000 + delivery_request.id}",
        status="pending",
    )
    db.session.add(parcel)
    if service_type == SERVICE_RETURN:
        db.session.add(
            ReturnDetail(
                request_id=delivery_request.id,
                authorized_hub_name=hub_name or destination.label,
                return_reference=return_reference,
                retailer=retailer,
            )
        )
    else:
        db.session.add(
            RecipientDetail(
                request_id=delivery_request.id,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                delivery_instructions=instructions,
            )
        )
    db.session.flush()
    db.session.add(
        TrackingEvent(
            parcel_id=parcel.id,
            request_id=delivery_request.id,
            event_type="request_created",
            actor_id=user.id,
            notes="Request submitted. Waiting for compatible requests.",
        )
    )
    dispatch.notify(
        user.id,
        "request_created",
        "Request received",
        f"{request_code(delivery_request.id)} is waiting for matching. Grouping is not guaranteed.",
        f"/customer/requests/{delivery_request.id}",
    )
    dispatch.notify_admins(
        "request_created",
        "New request awaiting matching",
        f"{request_code(delivery_request.id)} ({service_type}) was submitted by {user.name}.",
        "/admin/requests",
    )
    db.session.commit()
    return (
        jsonify(
            {
                "data": serialize_request(
                    delivery_request, include_contact=True, include_batch=True
                )
            }
        ),
        201,
    )


@bp.get("")
@login_required
def list_requests():
    user = current_user()
    page, per_page = pagination_args()
    query = DeliveryRequest.query
    if user.role == ROLE_CUSTOMER:
        query = query.filter(DeliveryRequest.customer_id == user.id)
    elif user.role == ROLE_PARTNER:
        from ..models import DeliveryBatch

        batch_ids = [
            row[0]
            for row in db.session.query(DeliveryBatch.id)
            .filter(DeliveryBatch.partner_id == user.id)
            .all()
        ]
        request_ids = [
            row[0]
            for row in db.session.query(BatchRequest.request_id)
            .filter(BatchRequest.batch_id.in_(batch_ids or [0]))
            .all()
        ]
        query = query.filter(DeliveryRequest.id.in_(request_ids or [0]))
    elif user.role != ROLE_ADMIN:
        raise ApiError("forbidden", "Unsupported role.", 403)

    statuses = [item.strip() for item in http_request.args.get("status", "").split(",") if item.strip()]
    if statuses:
        query = query.filter(DeliveryRequest.status.in_(statuses))
    service_type = http_request.args.get("type")
    if service_type in SERVICE_TYPES:
        query = query.filter(DeliveryRequest.type == service_type)
    search = (http_request.args.get("q") or "").strip()
    if search:
        conditions = [
            DeliveryRequest.notes.ilike(f"%{search}%"),
            DeliveryRequest.pickup_location.has(Location.area.ilike(f"%{search}%")),
            DeliveryRequest.destination_location.has(Location.area.ilike(f"%{search}%")),
            DeliveryRequest.customer.has(
                or_(User.name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%"))
            ),
            DeliveryRequest.parcel.has(Parcel.description.ilike(f"%{search}%")),
            DeliveryRequest.parcel.has(Parcel.tracking_number.ilike(f"%{search}%")),
        ]
        if search.upper().startswith("RTN-REQ-"):
            try:
                target = int(search.split("-")[-1]) - 1000
                conditions.append(DeliveryRequest.id == target)
            except ValueError:
                pass
        query = query.filter(or_(*conditions))
    query = query.order_by(DeliveryRequest.created_at.desc(), DeliveryRequest.id.desc())

    include_contact = user.role in (ROLE_ADMIN, ROLE_CUSTOMER)

    def serializer(row):
        return serialize_request(
            row,
            include_contact=include_contact
            or (user.role == ROLE_PARTNER and partner_user_id_for_request(row) == user.id),
            include_customer=user.role in (ROLE_ADMIN, ROLE_PARTNER),
        )

    return jsonify(*paginate(query, page, per_page, serializer))


@bp.get("/<int:request_id>")
@login_required
def get_request(request_id: int):
    user = current_user()
    delivery_request = DeliveryRequest.query.get(request_id)
    if delivery_request is None:
        raise ApiError("request_not_found", "That request does not exist.", 404)
    assert_request_access(user, delivery_request)
    include_contact = user.role in (ROLE_ADMIN, ROLE_CUSTOMER) or (
        user.role == ROLE_PARTNER and partner_user_id_for_request(delivery_request) == user.id
    )
    payload = serialize_request(
        delivery_request,
        include_contact=include_contact,
        include_customer=user.role in (ROLE_ADMIN, ROLE_PARTNER),
    )
    payload["tracking"] = [
        serialize_tracking_event(event)
        for event in TrackingEvent.query.filter_by(request_id=delivery_request.id)
        .order_by(TrackingEvent.created_at.asc(), TrackingEvent.id.asc())
        .all()
    ]
    link = BatchRequest.query.filter(
        BatchRequest.request_id == delivery_request.id, BatchRequest.released_at.is_(None)
    ).first()
    if link and user.role in (ROLE_ADMIN, ROLE_PARTNER):
        contacts = user.role == ROLE_ADMIN or batch_contacts_allowed(user, link.batch)
        payload["batch_detail"] = serialize_batch(
            link.batch, include_contacts=contacts, include_requests=True
        )
    return jsonify({"data": payload})


@bp.post("/<int:request_id>/cancel")
@login_required
def cancel_request(request_id: int):
    user = current_user()
    delivery_request = DeliveryRequest.query.get(request_id)
    if delivery_request is None:
        raise ApiError("request_not_found", "That request does not exist.", 404)
    if user.role != ROLE_ADMIN and delivery_request.customer_id != user.id:
        raise ApiError("forbidden", "You can only cancel your own requests.", 403)
    data = http_request.get_json(silent=True) or {}
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ApiError("validation_failed", "Provide a text reason.", 422)
    updated = dispatch.cancel_request(user, delivery_request, reason)
    return jsonify({"data": serialize_request(updated, include_contact=True)})


@bp.get("/<int:request_id>/tracking")
@login_required
def tracking(request_id: int):
    user = current_user()
    delivery_request = DeliveryRequest.query.get(request_id)
    if delivery_request is None:
        raise ApiError("request_not_found", "That request does not exist.", 404)
    assert_request_access(user, delivery_request)
    events = (
        TrackingEvent.query.filter_by(request_id=delivery_request.id)
        .order_by(TrackingEvent.created_at.asc(), TrackingEvent.id.asc())
        .all()
    )
    return jsonify(
        {
            "data": {
                "request_id": delivery_request.id,
                "code": request_code(delivery_request.id),
                "status": delivery_request.status,
                "parcel_status": delivery_request.parcel.status if delivery_request.parcel else None,
                "tracking_number": delivery_request.parcel.tracking_number
                if delivery_request.parcel
                else None,
                "events": [serialize_tracking_event(event) for event in events],
                "updated_at": iso(delivery_request.updated_at),
            }
        }
    )
