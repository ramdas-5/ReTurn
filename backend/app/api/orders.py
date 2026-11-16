"""Consumer ordering: parcel intake, returns, tracking, cancellation and media.

The rules implemented here mirror the specification:

* one exterior parcel photograph is part of normal booking, with a written
  exception process for inaccessible cameras;
* availability is reported from real service areas, schedules and duty sessions;
* a consumer can never pick or assign a driver;
* submission moves the order through the domain state machine into manager review;
* every read is scoped to the account that owns the order.
"""
from __future__ import annotations

import json
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request
from werkzeug.datastructures import FileStorage

from .. import domain
from ..access import assert_order_access, can_view_order, consumer_can_cancel
from ..errors import ApiError, paginate
from ..extensions import db
from ..models import (
    DeliveryProof,
    DriverAssignment,
    Order,
    ParcelImage,
    PickupAddress,
    SavedAddress,
)
from ..security import (
    current_user,
    login_required,
    rate_limit,
    require_password_changed,
    role_required,
)
from ..serializers import (
    serialize_assignment,
    serialize_order_detail,
    serialize_order_summary,
    serialize_proof,
    serialize_status_history,
)
from ..services import availability
from ..services import orders as order_service
from ..services.audit import audit
from ..services.notifications import (
    ORDER_STATUS,
    ORDER_SUBMITTED,
    notify_admins,
    notify_responsible_managers,
    notify_user,
)
from ..services.storage import save_image
from ..validation import Validator, json_body, pagination_args

bp = Blueprint("orders", __name__, url_prefix="/api/v1")


# --------------------------------------------------------------------------- #
# Payload parsing
# --------------------------------------------------------------------------- #
def _multipart_request() -> bool:
    return bool(request.content_type and request.content_type.startswith("multipart/form-data"))


def _request_payload() -> tuple[dict, list[FileStorage]]:
    if not _multipart_request():
        return json_body(), []

    raw = request.form.get("payload")
    if not raw:
        raise ApiError(
            "invalid_payload",
            "Send the order as a JSON 'payload' form field together with the photo.",
            400,
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise ApiError("invalid_json", "The 'payload' form field is not valid JSON.", 400)
    if not isinstance(data, dict):
        raise ApiError("invalid_json", "The 'payload' form field must be a JSON object.", 400)

    uploads: list[FileStorage] = []
    for field in ("photo", "image", "photos", "images"):
        for upload in request.files.getlist(field):
            if upload is not None and upload.filename and upload not in uploads:
                uploads.append(upload)
    max_images = int(current_app.config.get("MAX_PARCEL_IMAGES", 5))
    if len(uploads) > max_images:
        raise ApiError(
            "too_many_images", f"Attach at most {max_images} parcel photographs.", 422
        )
    return data, uploads


def _merge_errors(destination: Validator, prefix: str, source: Validator) -> None:
    for key, message in source.errors.items():
        destination.fail(f"{prefix}.{key}", message)


def _saved_address_payload(raw: dict, owner) -> dict | None:
    address_id = raw.get("address_id") or raw.get("saved_address_id")
    if address_id in (None, ""):
        return None
    try:
        address_id = int(address_id)
    except (TypeError, ValueError):
        return None
    saved = db.session.get(SavedAddress, address_id)
    if saved is None or saved.user_id != owner.id:
        return None
    return {
        "contact_name": saved.contact_name or owner.full_name,
        "contact_phone": saved.contact_phone or owner.phone,
        "address_line": saved.address_line,
        "address_line2": saved.address_line2,
        "area": saved.area,
        "city": saved.city,
        "state": saved.state,
        "postal_code": saved.postal_code,
        "latitude": float(saved.latitude) if saved.latitude is not None else None,
        "longitude": float(saved.longitude) if saved.longitude is not None else None,
        "instructions": None,
    }


def _address_payload(v: Validator, key: str, owner):
    raw = v.data.get(key)
    if not isinstance(raw, dict):
        v.fail(key, "Provide address details.")
        return None

    saved = _saved_address_payload(raw, owner)
    if saved is not None:
        missing = [
            field
            for field in (
                "contact_name",
                "contact_phone",
                "address_line",
                "area",
                "latitude",
                "longitude",
            )
            if saved.get(field) in (None, "")
        ]
        if missing:
            v.fail(
                key,
                "That saved address is incomplete. Edit it or enter the address manually.",
            )
            return None
        return saved
    if raw.get("address_id") not in (None, ""):
        v.fail(f"{key}.address_id", "That saved address does not exist.")
        return None

    sub = Validator(raw)
    payload = {
        "contact_name": sub.string("contact_name", required=True, min_length=2, max_length=160),
        "contact_phone": sub.string("contact_phone", required=True, min_length=6, max_length=40),
        "address_line": sub.string("address_line", required=True, min_length=3, max_length=255),
        "address_line2": sub.string("address_line2", max_length=255),
        "area": sub.string("area", required=True, min_length=2, max_length=120),
        "city": sub.string("city", max_length=120),
        "state": sub.string("state", max_length=120),
        "postal_code": sub.string("postal_code", max_length=20),
        "latitude": sub.number("latitude", required=True, minimum=-90, maximum=90),
        "longitude": sub.number("longitude", required=True, minimum=-180, maximum=180),
        "instructions": sub.string("instructions", max_length=500),
    }
    _merge_errors(v, key, sub)
    return None if sub.errors else payload


def _parcel_payload(v: Validator):
    raw = v.data.get("parcel")
    if not isinstance(raw, dict):
        v.fail("parcel", "Provide parcel details.")
        return None
    sub = Validator(raw)
    payload = {
        "name": sub.string("name", required=True, min_length=2, max_length=160),
        "description": sub.string("description", max_length=1000),
        "category": sub.string("category", max_length=60) or "general",
        "quantity": sub.integer("quantity", default=1, minimum=1, maximum=999),
        "weight_kg": sub.number("weight_kg", required=True, minimum=0.05, maximum=2000),
        "length_cm": sub.number("length_cm", required=True, minimum=1, maximum=500),
        "width_cm": sub.number("width_cm", required=True, minimum=1, maximum=500),
        "height_cm": sub.number("height_cm", required=True, minimum=1, maximum=500),
        "is_fragile": sub.boolean("is_fragile"),
        "handling_flags": sub.string_list(
            "handling_flags",
            options=("fragile", "keep_upright", "keep_dry", "temperature_sensitive", "restricted"),
        ),
        "declared_value_inr": sub.number(
            "declared_value_inr", minimum=0, maximum=10_000_000
        ),
        "photo_exception_reason": sub.string(
            "photo_exception_reason", max_length=500
        ),
    }
    _merge_errors(v, "parcel", sub)
    return None if sub.errors else payload


def _contact_payload(v: Validator, key: str, fallback: dict | None):
    raw = v.data.get(key)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        v.fail(key, "Provide contact details.")
        return {}
    sub = Validator(raw)
    payload = {
        "name": sub.string("name", max_length=160),
        "phone": sub.string("phone", max_length=40),
        "email": sub.email("email", required=False),
    }
    _merge_errors(v, key, sub)
    return payload


def _return_payload(v: Validator):
    raw = v.data.get("return_details")
    if not isinstance(raw, dict):
        v.fail("return_details", "Provide the return details.")
        return None
    sub = Validator(raw)
    payload = {
        "product_name": sub.string("product_name", max_length=160),
        "original_order_reference": sub.string("original_order_reference", max_length=120),
        "reason": sub.string("reason", required=True, min_length=5, max_length=1000),
        "return_authorization_reference": sub.string(
            "return_authorization_reference", max_length=120
        ),
        "merchant_name": sub.string("merchant_name", max_length=200),
        "destination_type": sub.choice(
            "destination_type",
            domain.RETURN_DESTINATION_TYPES,
            default="business",
        ),
        "authorization_confirmed": sub.boolean("authorization_confirmed"),
        "merchant_approval_required": sub.boolean("merchant_approval_required", default=True),
        "merchant_business_profile_id": sub.integer("merchant_business_profile_id", minimum=1),
        "condition_notes": sub.string("condition_notes", max_length=1000),
    }
    _merge_errors(v, "return_details", sub)
    return None if sub.errors else payload


def _build_payload(data: dict, consumer, *, force_service_type: str | None):
    v = Validator(data)
    service_type = force_service_type or v.choice(
        "service_type", domain.SERVICE_TYPES, default=domain.SERVICE_PARCEL
    )

    pickup = _address_payload(v, "pickup", consumer)
    delivery = _address_payload(v, "delivery", consumer)
    parcel = _parcel_payload(v)
    sender = _contact_payload(v, "sender", pickup)
    recipient = _contact_payload(v, "recipient", delivery)
    return_details = (
        _return_payload(v) if service_type == domain.SERVICE_RETURN else None
    )

    window_start = v.datetime("pickup_window_start", required=True)
    window_end = v.datetime("pickup_window_end", required=True)
    deadline = v.datetime("delivery_deadline", required=True)
    priority = v.integer("priority", default=0, minimum=0, maximum=2) or 0
    service_notes = v.string("service_notes", max_length=1000)
    special_requirements = v.string("special_requirements", max_length=500)
    business_order_reference = v.string("business_order_reference", max_length=120)
    declared_value_inr = v.number("declared_value_inr", minimum=0, maximum=10_000_000)
    v.finish()

    if window_start is not None and window_start < domain.utcnow() - timedelta(minutes=30):
        raise ApiError(
            "pickup_window_in_past",
            "Choose a pickup window that starts in the future.",
            422,
            fields={"pickup_window_start": "This pickup window has already passed."},
        )
    if window_start and window_end and window_end <= window_start:
        raise ApiError(
            "invalid_pickup_window",
            "The pickup window end must be after its start.",
            422,
            fields={"pickup_window_end": "Choose a later end time."},
        )
    if window_end and deadline and deadline <= window_end:
        raise ApiError(
            "invalid_deadline",
            "The delivery deadline must be after the pickup window.",
            422,
            fields={"delivery_deadline": "Choose a deadline after pickup."},
        )

    return {
        "service_type": service_type,
        "pickup": pickup,
        "delivery": delivery,
        "parcel": parcel,
        "sender": sender,
        "recipient": recipient,
        "pickup_window_start": window_start,
        "pickup_window_end": window_end,
        "delivery_deadline": deadline,
        "priority": priority,
        "service_notes": service_notes,
        "special_requirements": special_requirements,
        "business_order_reference": business_order_reference,
        "declared_value_inr": declared_value_inr,
        "business_profile_id": (
            consumer.business_profile.id if consumer.business_profile else None
        ),
        "return_details": return_details,
        "is_demo": False,
    }


def _assert_service_area(payload: dict) -> dict:
    if not current_app.config.get("REQUIRE_SERVICE_AREA_FOR_ORDERS", True):
        return {}
    info = availability.check(
        pickup_area=payload["pickup"]["area"],
        pickup_lat=payload["pickup"]["latitude"],
        pickup_lng=payload["pickup"]["longitude"],
        delivery_area=payload["delivery"]["area"],
        delivery_lat=payload["delivery"]["latitude"],
        delivery_lng=payload["delivery"]["longitude"],
        window_start=payload["pickup_window_start"],
        window_end=payload["pickup_window_end"],
    )
    if not info["serviceable"]:
        fields = {}
        if "pickup_outside_service_area" in info["reasons"]:
            fields["pickup.area"] = "We do not yet serve this pickup area."
        if "delivery_outside_service_area" in info["reasons"]:
            fields["delivery.area"] = "We do not yet serve this delivery area."
        raise ApiError(
            "area_not_serviceable",
            "That route is outside our current service areas.",
            422,
            fields=fields,
            details=info,
        )
    return info


def _attach_photo(order: Order, upload: FileStorage, uploader) -> ParcelImage:
    asset = save_image(upload, uploaded_by=uploader, error_prefix="parcel_photo")
    image = ParcelImage(
        order_id=order.id,
        media_id=asset.id,
        image_kind="exterior",
        is_primary=True,
        captured_at=domain.utcnow(),
        uploaded_by_id=uploader.id,
    )
    db.session.add(image)
    return image


def create_order_request(*, force_service_type: str | None = None):
    consumer = current_user()
    data, uploads = _request_payload()
    payload = _build_payload(data, consumer, force_service_type=force_service_type)

    photo_required = bool(current_app.config.get("PARCEL_PHOTO_REQUIRED", True))
    exception_reason = payload["parcel"]["photo_exception_reason"]
    if not uploads and photo_required:
        minimum = int(current_app.config.get("PARCEL_PHOTO_MIN_EXCEPTION_CHARS", 12))
        if not exception_reason:
            raise ApiError(
                "parcel_photo_required",
                "Add one exterior photograph of the parcel, or record why it cannot be taken.",
                422,
                fields={"photo": "Attach a parcel photograph or provide an exception reason."},
            )
        if len(exception_reason) < minimum:
            raise ApiError(
                "parcel_photo_exception_too_short",
                "Describe the photo exception in a little more detail.",
                422,
                fields={
                    "parcel.photo_exception_reason": (
                        f"Use at least {minimum} characters."
                    )
                },
            )
    if uploads and exception_reason:
        raise ApiError(
            "parcel_photo_conflict",
            "Attach a photograph or record an exception, not both.",
            422,
            fields={"parcel.photo_exception_reason": "Remove the exception note."},
        )

    _assert_service_area(payload)

    order = order_service.create_order(consumer, payload)
    db.session.flush()

    for upload in uploads:
        _attach_photo(order, upload, consumer)

    audit(
        "order.created",
        "order",
        order.id,
        actor=consumer,
        summary=f"{payload['service_type'].title()} order {order.order_number} submitted",
        event_metadata={
            "service_type": payload["service_type"],
            "photo_attached": bool(uploads),
            "photo_exception": bool(exception_reason),
        },
    )
    notify_user(
        consumer,
        ORDER_SUBMITTED,
        f"Order {order.order_number} received",
        "We received your request. A manager will review it and match a driver.",
        link=f"/consumer/orders/{order.id}",
        event_data={"order_id": order.id, "order_number": order.order_number},
    )
    notified = notify_responsible_managers(
        ORDER_STATUS,
        f"New {payload['service_type']} order {order.order_number}",
        (
            f"Pickup in {payload['pickup']['area']} → "
            f"{payload['delivery']['area']}. Review and assign a compatible driver."
        ),
        area_name=payload["pickup"]["area"],
        latitude=payload["pickup"]["latitude"],
        longitude=payload["pickup"]["longitude"],
        link=f"/manager/orders/{order.id}",
        event_data={"order_id": order.id, "order_number": order.order_number},
    )
    if not notified:
        notify_admins(
            ORDER_STATUS,
            f"New order {order.order_number} needs a manager",
            (
                f"No manager service area covers {payload['pickup']['area']}. "
                "Configure a service area or review this order directly."
            ),
            link=f"/admin/orders/{order.id}",
            event_data={"order_id": order.id, "order_number": order.order_number},
        )
    db.session.commit()

    return jsonify({"data": serialize_order_detail(order)}), 201


# --------------------------------------------------------------------------- #
# Intake
# --------------------------------------------------------------------------- #
@bp.post("/orders")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
@rate_limit(30, 60, scope="create-order")
def create_order():
    return create_order_request()


@bp.get("/availability")
@login_required
def availability_check():
    def number_arg(name: str):
        raw = request.args.get(name)
        if raw in (None, ""):
            return None
        try:
            return float(raw)
        except ValueError:
            raise ApiError("invalid_coordinate", f"'{name}' must be a number.", 422)

    def datetime_arg(name: str):
        raw = request.args.get(name)
        if raw in (None, ""):
            return None
        try:
            return domain.parse_datetime(raw)
        except ValueError:
            raise ApiError("invalid_datetime", f"'{name}' must be ISO-8601.", 422)

    return jsonify(
        {
            "data": availability.check(
                pickup_area=request.args.get("pickup_area"),
                pickup_lat=number_arg("pickup_latitude"),
                pickup_lng=number_arg("pickup_longitude"),
                delivery_area=request.args.get("delivery_area"),
                delivery_lat=number_arg("delivery_latitude"),
                delivery_lng=number_arg("delivery_longitude"),
                window_start=datetime_arg("window_start"),
                window_end=datetime_arg("window_end"),
            )
        }
    )


# --------------------------------------------------------------------------- #
# Listing and detail
# --------------------------------------------------------------------------- #
def visible_orders_query(user):
    query = Order.query
    if user.role == domain.ROLE_CONSUMER:
        return query.filter(Order.consumer_id == user.id)
    if user.role == domain.ROLE_DRIVER:
        return (
            query.join(DriverAssignment, DriverAssignment.order_id == Order.id)
            .filter(DriverAssignment.driver_id == user.id)
            .distinct()
        )
    if user.role == domain.ROLE_MANAGER:
        profile = user.manager_profile
        areas = [
            link.service_area
            for link in (profile.service_areas if profile else [])
            if link.service_area is not None
        ]
        names = [area.name.casefold() for area in areas]
        if not names:
            return query.filter(db.false())
        return query.join(
            PickupAddress, PickupAddress.id == Order.pickup_address_id
        ).filter(db.func.lower(PickupAddress.area).in_(names))
    return query


def _apply_filters(query):
    status = request.args.get("status")
    if status:
        wanted = [part.strip() for part in status.split(",") if part.strip()]
        unknown = [value for value in wanted if value not in domain.ORDER_STATUSES]
        if unknown:
            raise ApiError(
                "invalid_status", "Unknown order status filter.", 422,
                details={"unknown": unknown},
            )
        query = query.filter(Order.status.in_(wanted))

    service_type = request.args.get("service_type")
    if service_type:
        if service_type not in domain.SERVICE_TYPES:
            raise ApiError("invalid_service_type", "Unknown service type.", 422)
        query = query.filter(Order.service_type == service_type)

    text = (request.args.get("q") or "").strip()
    if text:
        query = query.filter(
            db.func.lower(Order.order_number).like(f"%{text.lower()}%")
        )

    window = request.args.get("window")
    if window == "active":
        query = query.filter(Order.status.in_(domain.ACTIVE_ORDER_STATUSES))
    elif window == "completed":
        query = query.filter(Order.status == domain.ORDER_DELIVERED)
    elif window == "cancelled":
        query = query.filter(Order.status == domain.ORDER_CANCELLED)

    return query


@bp.get("/orders")
@login_required
def list_orders():
    query = _apply_filters(visible_orders_query(current_user()))
    query = query.order_by(Order.created_at.desc())
    page, per_page = pagination_args()
    return paginate(query, page, per_page, lambda order: serialize_order_summary(order))


@bp.get("/orders/<int:order_id>")
@login_required
def get_order(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        raise ApiError("not_found", "That order does not exist.", 404)
    assert_order_access(current_user(), order)
    return jsonify({"data": serialize_order_detail(order)})


@bp.get("/orders/<int:order_id>/tracking")
@login_required
def track_order(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        raise ApiError("not_found", "That order does not exist.", 404)
    assert_order_access(current_user(), order)

    active = order_service.active_assignment(order)
    batch = order_service.current_batch(order)
    history = sorted(order.status_history, key=lambda row: row.created_at)
    timeline = [serialize_status_history(row) for row in history]
    delivery_proof = DeliveryProof.query.filter_by(order_id=order.id).first()

    data = {
        "order_id": order.id,
        "order_number": order.order_number,
        "service_type": order.service_type,
        "status": order.status,
        "status_label": domain.ORDER_STATUS_LABELS.get(order.status, order.status),
        "is_closed": order.status in domain.TERMINAL_ORDER_STATUSES,
        "timeline": timeline,
        "current_step": timeline[-1] if timeline else None,
        "assigned_driver": serialize_assignment(active),
        "batch": (
            {
                "id": batch.id,
                "batch_number": batch.batch_number,
                "status": batch.status,
                "status_label": domain.BATCH_STATUS_LABELS.get(batch.status, batch.status),
            }
            if batch
            else None
        ),
        "pickup": {
            "area": order.pickup_address.area if order.pickup_address else None,
            "window_start": domain.iso(order.pickup_window_start),
            "window_end": domain.iso(order.pickup_window_end),
        },
        "delivery": {
            "area": order.delivery_address.area if order.delivery_address else None,
            "deadline": domain.iso(order.delivery_deadline),
            "delivered_at": domain.iso(order.delivered_at),
        },
        "delivery_proof": serialize_proof(delivery_proof, kind="delivery")
        if delivery_proof
        else None,
    }
    return jsonify({"data": data})


# --------------------------------------------------------------------------- #
# Cancellation and images
# --------------------------------------------------------------------------- #
@bp.post("/orders/<int:order_id>/cancel")
@login_required
@require_password_changed()
def cancel_order(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None:
        raise ApiError("not_found", "That order does not exist.", 404)
    actor = current_user()
    assert_order_access(actor, order)

    body = json_body()
    v = Validator(body)
    reason = v.string("reason", required=True, min_length=5, max_length=500)
    v.finish()

    if actor.role == domain.ROLE_CONSUMER:
        if not consumer_can_cancel(order):
            raise ApiError(
                "order_in_custody",
                "The parcel is already with a driver. Contact support instead.",
                409,
            )
        source = "consumer"
    elif actor.role == domain.ROLE_MANAGER:
        if not can_view_order(actor, order):
            raise ApiError("forbidden", "That order is outside your service areas.", 403)
        source = "manager"
    elif actor.role == domain.ROLE_ADMIN:
        source = "admin"
    else:
        raise ApiError("forbidden", "You cannot cancel this order.", 403)

    order_service.cancel_order(order, actor, reason, source=source)
    audit(
        "order.cancelled",
        "order",
        order.id,
        actor=actor,
        summary=f"Order {order.order_number} cancelled",
        reason=reason,
    )
    notify_user(
        order.consumer,
        ORDER_STATUS,
        f"Order {order.order_number} cancelled",
        f"Cancellation reason: {reason}",
        link=f"/consumer/orders/{order.id}",
        event_data={"order_id": order.id, "status": order.status},
    )
    db.session.commit()
    return jsonify({"data": serialize_order_detail(order)})


@bp.post("/orders/<int:order_id>/images")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
def add_order_image(order_id: int):
    order = db.session.get(Order, order_id)
    if order is None or order.consumer_id != current_user().id:
        raise ApiError("not_found", "That order does not exist.", 404)
    if order.status in domain.IN_CUSTODY_STATUSES or order.status in domain.TERMINAL_ORDER_STATUSES:
        raise ApiError(
            "order_not_editable",
            "Photographs can only be added before the parcel is collected.",
            409,
        )

    upload = (
        request.files.get("photo")
        or request.files.get("image")
        or request.files.get("file")
    )
    if upload is None or not upload.filename:
        raise ApiError(
            "parcel_photo_required",
            "Attach an image file in the 'photo' field.",
            422,
            fields={"photo": "Choose an image."},
        )
    max_images = int(current_app.config.get("MAX_PARCEL_IMAGES", 5))
    if len(order.images) >= max_images:
        raise ApiError(
            "too_many_images", f"An order can keep at most {max_images} photographs.", 409
        )

    wants_primary = str(request.form.get("is_primary", "")).strip().lower() in {
        "1", "true", "yes", "on",
    }
    make_primary = wants_primary or not order.images
    if make_primary:
        ParcelImage.query.filter_by(order_id=order.id).update({"is_primary": False})

    asset = save_image(upload, uploaded_by=current_user(), error_prefix="parcel_photo")
    image = ParcelImage(
        order_id=order.id,
        media_id=asset.id,
        image_kind=(request.form.get("image_kind") or "exterior")[:40],
        is_primary=make_primary,
        captured_at=domain.utcnow(),
        uploaded_by_id=current_user().id,
    )
    db.session.add(image)
    audit(
        "order.image_added",
        "order",
        order.id,
        actor=current_user(),
        summary=f"Parcel photograph added to {order.order_number}",
    )
    db.session.commit()
    return jsonify({"data": serialize_order_detail(order)}), 201
