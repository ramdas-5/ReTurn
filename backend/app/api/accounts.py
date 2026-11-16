"""Account, profile and reference-data endpoints (users, addresses, service areas)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .. import domain
from ..errors import ApiError, paginate
from ..extensions import db
from ..models import (
    BusinessProfile,
    ConsumerProfile,
    DriverProfile,
    SavedAddress,
    ServiceArea,
    User,
    VehicleCapacityProfile,
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
    serialize_business_profile,
    serialize_capacity_profile,
    serialize_driver_profile,
    serialize_saved_address,
    serialize_service_area,
    serialize_user,
)
from ..services import accounts as account_service
from ..services.audit import audit
from ..services.reference import ensure_reference_data
from ..validation import Validator, json_body, pagination_args

bp = Blueprint("accounts", __name__, url_prefix="/api/v1")


# ------------------------------------------------------------------profile self
@bp.get("/users/me")
@login_required
def get_me():
    return jsonify({"data": {"user": serialize_user(current_user())}})


@bp.patch("/users/me")
@login_required
@require_password_changed()
def update_me():
    data = json_body()
    v = Validator(data)
    user = current_user()
    full_name = v.string("full_name", max_length=160)
    phone = v.string("phone", max_length=40)
    timezone_name = v.string("timezone_name", max_length=64)
    v.finish()

    if full_name is not None:
        if len(full_name) < 2:
            raise ApiError(
                "validation_failed", "Some fields need attention.", 422,
                fields={"full_name": "Use at least 2 characters."},
            )
        user.full_name = full_name
    if phone is not None:
        user.phone = phone
    if timezone_name is not None:
        user.timezone_name = timezone_name
    if "notify_email" in data:
        user.notify_email = bool(data["notify_email"])
    if "notify_in_app" in data:
        user.notify_in_app = bool(data["notify_in_app"])
    audit("account.profile_updated", "user", user.id, actor=user, summary="Profile updated")
    db.session.commit()
    return jsonify({"data": {"user": serialize_user(user)}})


# ------------------------------------------------------------------ business
@bp.get("/business-profiles/me")
@login_required
@role_required(domain.ROLE_CONSUMER)
def get_business_profile():
    user = current_user()
    return jsonify(
        {
            "data": {
                "business_profile": serialize_business_profile(user.business_profile),
                "account_type": user.consumer_profile.account_type
                if user.consumer_profile
                else "individual",
            }
        }
    )


@bp.put("/business-profiles/me")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
def upsert_business_profile():
    data = json_body()
    v = Validator(data)
    business_name = v.string("business_name", required=True, min_length=2, max_length=200)
    category = v.string("category", max_length=120)
    contact_phone = v.string("contact_phone", max_length=40)
    contact_email = v.email("contact_email", required=False)
    address_line = v.string("address_line", max_length=255)
    area = v.string("area", max_length=120)
    city = v.string("city", max_length=120)
    state = v.string("state", max_length=120)
    postal_code = v.string("postal_code", max_length=20)
    tax_id = v.string("tax_id", max_length=80)
    registration_number = v.string("registration_number", max_length=80)
    latitude = v.number("latitude", minimum=-90, maximum=90)
    longitude = v.number("longitude", minimum=-180, maximum=180)
    v.finish()

    user = current_user()
    profile = user.business_profile
    if profile is None:
        profile = BusinessProfile(user_id=user.id, business_name=business_name)
        db.session.add(profile)
    profile.business_name = business_name
    profile.category = category
    profile.contact_phone = contact_phone
    profile.contact_email = contact_email
    profile.address_line = address_line
    profile.area = area
    profile.city = city or "Kolkata"
    profile.state = state or "West Bengal"
    profile.postal_code = postal_code
    profile.latitude = latitude
    profile.longitude = longitude
    profile.tax_id = tax_id
    profile.registration_number = registration_number
    if user.consumer_profile is None:
        db.session.add(ConsumerProfile(user_id=user.id, account_type="business"))
    else:
        user.consumer_profile.account_type = "business"
    audit(
        "business_profile.updated",
        "business_profile",
        profile.id,
        actor=user,
        summary=f"Business profile saved: {business_name}",
    )
    db.session.commit()
    return jsonify({"data": {"business_profile": serialize_business_profile(profile)}})


# ------------------------------------------------------------- saved addresses
def _address_payload(data: dict, *, partial: bool = False) -> dict:
    v = Validator(data)
    label = v.string("label", required=not partial, max_length=120)
    contact_name = v.string("contact_name", max_length=160)
    contact_phone = v.string("contact_phone", max_length=40)
    address_line = v.string("address_line", required=not partial, max_length=255)
    address_line2 = v.string("address_line2", max_length=255)
    area = v.string("area", required=not partial, max_length=120)
    city = v.string("city", max_length=120)
    state = v.string("state", max_length=120)
    postal_code = v.string("postal_code", max_length=20)
    latitude = v.number("latitude", required=not partial, minimum=-90, maximum=90)
    longitude = v.number("longitude", required=not partial, minimum=-180, maximum=180)
    v.finish()
    payload = {
        "label": label,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "address_line": address_line,
        "address_line2": address_line2,
        "area": area,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "latitude": latitude,
        "longitude": longitude,
        "is_default_pickup": bool(data.get("is_default_pickup")),
    }
    return {key: value for key, value in payload.items() if value is not None or not partial}


@bp.get("/users/me/addresses")
@login_required
@role_required(domain.ROLE_CONSUMER)
def list_addresses():
    rows = (
        SavedAddress.query.filter_by(user_id=current_user().id)
        .order_by(SavedAddress.is_default_pickup.desc(), SavedAddress.created_at.desc())
        .all()
    )
    return jsonify({"data": [serialize_saved_address(row) for row in rows]})


@bp.post("/users/me/addresses")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
def create_address():
    user = current_user()
    if SavedAddress.query.filter_by(user_id=user.id).count() >= 20:
        raise ApiError("address_limit", "You can save up to 20 addresses.", 409)
    payload = _address_payload(json_body())
    missing = [
        field
        for field in ("label", "address_line", "area", "latitude", "longitude")
        if payload.get(field) in (None, "")
    ]
    if missing:
        raise ApiError(
            "validation_failed",
            "Some fields need attention.",
            422,
            fields={field: "This field is required." for field in missing},
        )
    if payload.get("is_default_pickup"):
        SavedAddress.query.filter_by(user_id=user.id, is_default_pickup=True).update(
            {"is_default_pickup": False}
        )
    row = SavedAddress(
        user_id=user.id,
        label=payload["label"],
        contact_name=payload.get("contact_name") or user.full_name,
        contact_phone=payload.get("contact_phone") or user.phone,
        address_line=payload["address_line"],
        address_line2=payload.get("address_line2"),
        area=payload["area"],
        city=payload.get("city") or "Kolkata",
        state=payload.get("state") or "West Bengal",
        postal_code=payload.get("postal_code"),
        latitude=payload["latitude"],
        longitude=payload["longitude"],
        is_default_pickup=payload.get("is_default_pickup", False),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"data": serialize_saved_address(row)}), 201


@bp.patch("/users/me/addresses/<int:address_id>")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
def update_address(address_id: int):
    user = current_user()
    row = db.session.get(SavedAddress, address_id)
    if row is None or row.user_id != user.id:
        raise ApiError("not_found", "That address does not exist.", 404)
    payload = _address_payload(json_body(), partial=True)
    if payload.get("is_default_pickup"):
        SavedAddress.query.filter_by(user_id=user.id, is_default_pickup=True).update(
            {"is_default_pickup": False}
        )
    for key, value in payload.items():
        setattr(row, key, value)
    db.session.commit()
    return jsonify({"data": serialize_saved_address(row)})


@bp.delete("/users/me/addresses/<int:address_id>")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
def delete_address(address_id: int):
    user = current_user()
    row = db.session.get(SavedAddress, address_id)
    if row is None or row.user_id != user.id:
        raise ApiError("not_found", "That address does not exist.", 404)
    db.session.delete(row)
    db.session.commit()
    return jsonify({"data": {"ok": True}})


# ---------------------------------------------------------------- provisioning
@bp.post("/users/managers")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_ACCOUNTS_MANAGE)
@rate_limit(20, 60 * 10, scope="create-manager")
def create_manager():
    data = json_body()
    v = Validator(data)
    full_name = v.string("full_name", required=True, min_length=2, max_length=160)
    email = v.email("email", required=True)
    phone = v.string("phone", required=True, min_length=6, max_length=40)
    contact_phone = v.string("contact_phone", max_length=40)
    employee_code = v.string("employee_code", max_length=40)
    notes = v.string("notes", max_length=500)
    area_ids = data.get("service_area_ids") or []
    permissions = v.string_list("permission_codes")
    v.finish()
    if not isinstance(area_ids, list):
        raise ApiError("validation_failed", "Some fields need attention.", 422,
                       fields={"service_area_ids": "Expected a list of ids."})
    try:
        area_ids = [int(value) for value in area_ids]
    except (TypeError, ValueError):
        raise ApiError("validation_failed", "Some fields need attention.", 422,
                       fields={"service_area_ids": "Expected integer ids."})
    payload = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "contact_phone": contact_phone,
        "employee_code": employee_code,
        "notes": notes,
        "service_area_ids": area_ids,
        "permission_codes": permissions,
    }
    result = account_service.create_manager(current_user(), payload)
    audit(
        "account.manager_created",
        "user",
        result["user"]["id"],
        actor=current_user(),
        summary=f"Manager created: {email}",
    )
    db.session.commit()
    return jsonify({"data": result}), 201


@bp.post("/users/drivers")
@login_required
@role_required(domain.ROLE_ADMIN, domain.ROLE_MANAGER)
@permission_required(domain.PERM_DRIVERS_MANAGE)
@rate_limit(30, 60 * 10, scope="create-driver")
def create_driver():
    data = json_body()
    v = Validator(data)
    full_name = v.string("full_name", required=True, min_length=2, max_length=160)
    email = v.email("email", required=True)
    phone = v.string("phone", required=True, min_length=6, max_length=40)
    license_number = v.string("license_number", max_length=80)
    license_expiry = v.string("license_expiry", max_length=20)
    verification_status = v.choice(
        "verification_status", domain.VERIFICATION_STATUSES, default=domain.VERIFICATION_PENDING
    )
    vehicle = data.get("vehicle") if isinstance(data.get("vehicle"), dict) else {}
    capacity_id = vehicle.get("capacity_profile_id")
    registration = vehicle.get("registration_number")
    if capacity_id is None:
        v.fail("vehicle.capacity_profile_id", "Choose a vehicle capacity profile.")
    if not registration:
        v.fail("vehicle.registration_number", "A registration number is required.")
    area_ids = data.get("service_area_ids") or []
    if not isinstance(area_ids, list) or not area_ids:
        v.fail("service_area_ids", "Select at least one service area.")
    v.finish()
    try:
        area_ids = [int(value) for value in area_ids]
        capacity_id = int(capacity_id)
    except (TypeError, ValueError):
        raise ApiError("validation_failed", "Some fields need attention.", 422,
                       fields={"service_area_ids": "Expected integer values."})

    payload = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "license_number": license_number,
        "license_expiry": license_expiry,
        "verification_status": verification_status,
        "service_area_ids": area_ids,
        "vehicle": {
            "capacity_profile_id": capacity_id,
            "registration_number": registration,
            "vehicle_type": vehicle.get("vehicle_type"),
            "make": vehicle.get("make"),
            "model": vehicle.get("model"),
            "color": vehicle.get("color"),
            "year": vehicle.get("year"),
        },
    }
    result = account_service.create_driver(current_user(), payload)
    audit(
        "account.driver_created",
        "user",
        result["user"]["id"],
        actor=current_user(),
        summary=f"Driver created: {email}",
    )
    db.session.commit()
    return jsonify({"data": result}), 201


@bp.get("/users")
@login_required
@role_required(domain.ROLE_ADMIN, domain.ROLE_MANAGER)
def list_users():
    actor = current_user()
    role = request.args.get("role") or ("driver" if actor.role == domain.ROLE_MANAGER else None)
    status = request.args.get("status")
    query_text = (request.args.get("q") or "").strip()
    if role and role not in domain.ROLES:
        raise ApiError("invalid_role", "Unknown role filter.", 422)
    if actor.role == domain.ROLE_MANAGER and role != domain.ROLE_DRIVER:
        raise ApiError("forbidden", "Managers can only list drivers.", 403)

    query = User.query
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    if query_text:
        like = f"%{query_text.lower()}%"
        query = query.filter(
            db.or_(
                db.func.lower(User.full_name).like(like),
                db.func.lower(User.email).like(like),
                db.func.lower(User.phone).like(like),
            )
        )
    if actor.role == domain.ROLE_MANAGER:
        from ..models import DriverServiceArea

        allowed = (
            [link.service_area_id for link in actor.manager_profile.service_areas]
            if actor.manager_profile
            else []
        )
        profile_ids = db.select(DriverServiceArea.driver_id).filter(
            DriverServiceArea.service_area_id.in_(allowed or [-1])
        )
        query = query.filter(
            User.id.in_(db.select(DriverProfile.user_id).filter(DriverProfile.id.in_(profile_ids)))
        )
    query = query.order_by(User.created_at.desc())
    page, per_page = pagination_args()
    return paginate(query, page, per_page, lambda user: serialize_user(user))


@bp.get("/users/<int:user_id>")
@login_required
@role_required(domain.ROLE_ADMIN, domain.ROLE_MANAGER)
def get_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("not_found", "That account does not exist.", 404)
    if not account_service.manager_can_view_user(current_user(), user):
        raise ApiError("forbidden", "That account is outside your scope.", 403)
    return jsonify({"data": {"user": serialize_user(user)}})


@bp.patch("/users/<int:user_id>/status")
@login_required
@role_required(domain.ROLE_ADMIN, domain.ROLE_MANAGER)
def update_user_status(user_id: int):
    data = json_body()
    v = Validator(data)
    status = v.choice(
        "status", (domain.USER_ACTIVE, domain.USER_SUSPENDED, domain.USER_DEACTIVATED),
        required=True,
    )
    reason = v.string("reason", max_length=500)
    v.finish()
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("not_found", "That account does not exist.", 404)
    account_service.set_user_status(current_user(), user, status, reason)
    audit(
        "account.status_changed",
        "user",
        user.id,
        actor=current_user(),
        summary=f"Account {status}: {user.email}",
        reason=reason,
    )
    db.session.commit()
    return jsonify({"data": {"user": serialize_user(user)}})


@bp.post("/users/<int:user_id>/resend-activation")
@login_required
@role_required(domain.ROLE_ADMIN, domain.ROLE_MANAGER)
def resend_activation(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("not_found", "That account does not exist.", 404)
    result = account_service.resend_activation(current_user(), user)
    audit(
        "account.activation_resent",
        "user",
        user.id,
        actor=current_user(),
        summary=f"Activation reissued for {user.email}",
    )
    db.session.commit()
    return jsonify({"data": result}), 201


@bp.patch("/users/<int:user_id>/driver-verification")
@login_required
@role_required(domain.ROLE_ADMIN, domain.ROLE_MANAGER)
@permission_required(domain.PERM_DRIVERS_VERIFY)
def verify_driver(user_id: int):
    data = json_body()
    v = Validator(data)
    status = v.choice(
        "verification_status",
        (domain.VERIFICATION_VERIFIED, domain.VERIFICATION_REJECTED, domain.VERIFICATION_PENDING),
        required=True,
    )
    note = v.string("note", max_length=500)
    v.finish()
    user = db.session.get(User, user_id)
    if user is None or user.role != domain.ROLE_DRIVER or user.driver_profile is None:
        raise ApiError("not_found", "That driver does not exist.", 404)
    if not account_service.manager_can_view_user(current_user(), user):
        raise ApiError("forbidden", "That driver is outside your service areas.", 403)
    profile = user.driver_profile
    profile.verification_status = status
    profile.verification_note = note
    if status == domain.VERIFICATION_VERIFIED:
        profile.verified_at = domain.utcnow()
        profile.verified_by_id = current_user().id
    audit(
        "driver.verification_changed",
        "driver_profile",
        profile.id,
        actor=current_user(),
        summary=f"Driver verification: {status}",
        reason=note,
    )
    db.session.commit()
    return jsonify({"data": {"driver_profile": serialize_driver_profile(profile)}})


# -------------------------------------------------------------- reference data
@bp.get("/service-areas")
@login_required
def list_service_areas():
    user = current_user()
    query = ServiceArea.query
    if user.role != domain.ROLE_ADMIN:
        query = query.filter_by(is_active=True)
    rows = query.order_by(ServiceArea.name).all()
    return jsonify(
        {"data": [serialize_service_area(row, include_counts=user.role == domain.ROLE_ADMIN) for row in rows]}
    )


@bp.get("/vehicle-capacity-profiles")
@login_required
@role_required(domain.ROLE_ADMIN, domain.ROLE_MANAGER)
def list_capacity_profiles():
    rows = (
        VehicleCapacityProfile.query.filter_by(is_active=True)
        .order_by(VehicleCapacityProfile.max_weight_kg)
        .all()
    )
    return jsonify({"data": [serialize_capacity_profile(row) for row in rows]})


@bp.post("/reference/ensure")
@login_required
@role_required(domain.ROLE_ADMIN)
@permission_required(domain.PERM_SETTINGS_MANAGE)
def ensure_reference():
    created = ensure_reference_data()
    db.session.commit()
    return jsonify({"data": created})
