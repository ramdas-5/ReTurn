"""Account provisioning and account-state management.

Rules enforced here (not only in the UI):

* only an administrator creates managers or administrators;
* managers create drivers only inside their own service areas;
* drivers can never be created by public registration;
* temporary passwords are generated, hashed and shown once to the creator;
* activation happens through a single-use token and a password change.
"""
from __future__ import annotations

from datetime import date

from .. import domain
from ..access import manager_covers_area_name
from ..errors import ApiError
from ..extensions import db
from ..models import (
    DriverProfile,
    DriverServiceArea,
    ManagerProfile,
    ManagerServiceArea,
    ServiceArea,
    User,
    Vehicle,
    VehicleCapacityProfile,
)
from ..security import (
    generate_temporary_password,
    hash_password,
    issue_one_time_token,
    password_problem,
)
from ..serializers import serialize_user


def _assert_unique_email(email: str) -> None:
    if User.query.filter(db.func.lower(User.email) == email.lower()).first() is not None:
        raise ApiError("email_in_use", "An account already uses that email address.", 409)


def _service_areas(area_ids: list[int]) -> list[ServiceArea]:
    if not area_ids:
        raise ApiError(
            "service_area_required", "Select at least one service area.", 422,
            fields={"service_area_ids": "Select at least one service area."},
        )
    areas = ServiceArea.query.filter(ServiceArea.id.in_(area_ids)).all()
    if len(areas) != len(set(area_ids)):
        raise ApiError("service_area_invalid", "One or more service areas do not exist.", 422)
    return areas


def _manager_scope(manager: User) -> list[ServiceArea]:
    profile = manager.manager_profile
    if profile is None:
        return []
    return [link.service_area for link in profile.service_areas if link.service_area]


def _assert_areas_in_scope(actor: User, areas: list[ServiceArea]) -> None:
    if actor.role == domain.ROLE_ADMIN:
        return
    allowed_ids = {area.id for area in _manager_scope(actor)}
    if actor.role != domain.ROLE_MANAGER or any(area.id not in allowed_ids for area in areas):
        raise ApiError(
            "forbidden_service_area",
            "You can only manage drivers inside your assigned service areas.",
            403,
        )


def _assert_manager_can_manage_driver(actor: User, driver: User) -> None:
    if actor.role == domain.ROLE_ADMIN:
        return
    if actor.role != domain.ROLE_MANAGER:
        raise ApiError("forbidden", "Only managers or administrators can manage drivers.", 403)
    profile = driver.driver_profile
    allowed_ids = {area.id for area in _manager_scope(actor)}
    driver_ids = {link.service_area_id for link in profile.service_areas} if profile else set()
    if not driver_ids or not driver_ids.issubset(allowed_ids):
        raise ApiError(
            "outside_service_area", "That driver is outside your service areas.", 403
        )


def _temporary_credential() -> tuple[str, str]:
    password = generate_temporary_password()
    return password, hash_password(password)


def create_manager(actor: User, payload: dict) -> dict:
    if actor.role != domain.ROLE_ADMIN:
        raise ApiError("forbidden", "Only an administrator can create managers.", 403)
    _assert_unique_email(payload["email"])
    areas = _service_areas(payload.get("service_area_ids") or [])
    permissions = payload.get("permission_codes") or []
    unknown = [code for code in permissions if code not in domain.PERMISSION_CATALOG]
    if unknown:
        raise ApiError(
            "permission_invalid",
            "Unknown permission codes.",
            422,
            details={"unknown": unknown},
        )

    temp_password, password_hash = _temporary_credential()
    user = User(
        email=payload["email"].lower(),
        full_name=payload["full_name"],
        phone=payload.get("phone"),
        role=domain.ROLE_MANAGER,
        status=domain.USER_PENDING_ACTIVATION,
        password_hash=password_hash,
        must_change_password=True,
    )
    db.session.add(user)
    db.session.flush()

    profile = ManagerProfile(
        user_id=user.id,
        employee_code=payload.get("employee_code"),
        contact_phone=payload.get("contact_phone") or payload.get("phone"),
        notes=payload.get("notes"),
        created_by_id=actor.id,
    )
    db.session.add(profile)
    db.session.flush()
    for area in areas:
        db.session.add(ManagerServiceArea(manager_id=profile.id, service_area_id=area.id))
    for code in permissions:
        db.session.add(
            UserPermissionRow(user_id=user.id, permission_code=code, granted_by_id=actor.id)
        )

    token = issue_one_time_token(user, "activation")
    db.session.flush()
    return {
        "user": serialize_user(user),
        "temporary_password": temp_password,
        "activation_token": token,
        "activation_expires_in_hours": 168,
        "credential_delivery": "manual",
    }


def create_driver(actor: User, payload: dict) -> dict:
    if actor.role not in (domain.ROLE_ADMIN, domain.ROLE_MANAGER):
        raise ApiError("forbidden", "Only managers or administrators can create drivers.", 403)
    _assert_unique_email(payload["email"])
    areas = _service_areas(payload.get("service_area_ids") or [])
    _assert_areas_in_scope(actor, areas)

    vehicle_data = payload.get("vehicle") or {}
    capacity_id = vehicle_data.get("capacity_profile_id")
    capacity = db.session.get(VehicleCapacityProfile, capacity_id) if capacity_id else None
    if capacity is None or not capacity.is_active:
        raise ApiError(
            "capacity_profile_invalid", "Select an active vehicle capacity profile.", 422
        )
    vehicle_type = vehicle_data.get("vehicle_type") or capacity.vehicle_type
    if vehicle_type != capacity.vehicle_type:
        raise ApiError(
            "vehicle_type_mismatch",
            "The vehicle type must match the selected capacity profile.",
            422,
            fields={"vehicle.vehicle_type": f"Expected {capacity.vehicle_type}."},
        )
    registration = (vehicle_data.get("registration_number") or "").strip().upper()
    if not registration:
        raise ApiError(
            "registration_required",
            "A vehicle registration number is required.",
            422,
            fields={"vehicle.registration_number": "This field is required."},
        )
    if Vehicle.query.filter(db.func.upper(Vehicle.registration_number) == registration).first():
        raise ApiError(
            "registration_in_use",
            "That vehicle registration is already registered.",
            409,
        )

    license_expiry = vehicle_data.get("license_expiry") or payload.get("license_expiry")
    if isinstance(license_expiry, str) and license_expiry:
        try:
            license_expiry = date.fromisoformat(license_expiry)
        except ValueError:
            raise ApiError("license_expiry_invalid", "Use a valid ISO date.", 422)

    temp_password, password_hash = _temporary_credential()
    user = User(
        email=payload["email"].lower(),
        full_name=payload["full_name"],
        phone=payload.get("phone"),
        role=domain.ROLE_DRIVER,
        status=domain.USER_PENDING_ACTIVATION,
        password_hash=password_hash,
        must_change_password=True,
    )
    db.session.add(user)
    db.session.flush()

    profile = DriverProfile(
        user_id=user.id,
        license_number=payload.get("license_number"),
        license_expiry=license_expiry,
        verification_status=payload.get("verification_status") or domain.VERIFICATION_PENDING,
        created_by_id=actor.id,
    )
    db.session.add(profile)
    db.session.flush()
    for area in areas:
        db.session.add(DriverServiceArea(driver_id=profile.id, service_area_id=area.id))
    vehicle = Vehicle(
        driver_id=profile.id,
        capacity_profile_id=capacity.id,
        vehicle_type=vehicle_type,
        registration_number=registration,
        make=vehicle_data.get("make"),
        model=vehicle_data.get("model"),
        color=vehicle_data.get("color"),
        year=vehicle_data.get("year"),
        verification_status=payload.get("verification_status") or domain.VERIFICATION_PENDING,
    )
    db.session.add(vehicle)
    token = issue_one_time_token(user, "activation")
    db.session.flush()
    return {
        "user": serialize_user(user),
        "temporary_password": temp_password,
        "activation_token": token,
        "activation_expires_in_hours": 168,
        "credential_delivery": "manual",
    }


def resend_activation(actor: User, user: User) -> dict:
    if user.role == domain.ROLE_CONSUMER:
        raise ApiError("not_required", "Consumers do not need an activation token.", 409)
    if actor.role == domain.ROLE_MANAGER:
        _assert_manager_can_manage_driver(actor, user)
    elif actor.role != domain.ROLE_ADMIN:
        raise ApiError("forbidden", "You cannot resend activation for that account.", 403)
    if user.status != domain.USER_PENDING_ACTIVATION:
        raise ApiError("already_active", "That account is not awaiting activation.", 409)
    token = issue_one_time_token(user, "activation")
    return {
        "user_id": user.id,
        "activation_token": token,
        "activation_expires_in_hours": 168,
        "credential_delivery": "manual",
    }


def set_user_status(actor: User, user: User, status: str, reason: str | None = None) -> User:
    if status not in (domain.USER_ACTIVE, domain.USER_SUSPENDED, domain.USER_DEACTIVATED):
        raise ApiError("invalid_status", "Choose active, suspended or deactivated.", 422)
    if user.id == actor.id:
        raise ApiError("cannot_modify_self", "You cannot change your own account status.", 409)
    if actor.role == domain.ROLE_MANAGER:
        if user.role != domain.ROLE_DRIVER:
            raise ApiError("forbidden", "Managers can only change driver accounts.", 403)
        _assert_manager_can_manage_driver(actor, user)
    elif actor.role != domain.ROLE_ADMIN:
        raise ApiError("forbidden", "You cannot change account status.", 403)
    if user.role == domain.ROLE_ADMIN and status != domain.USER_ACTIVE:
        remaining = User.query.filter(
            User.role == domain.ROLE_ADMIN,
            User.status == domain.USER_ACTIVE,
            User.id != user.id,
        ).count()
        if remaining == 0:
            raise ApiError(
                "last_admin", "At least one active administrator must remain.", 409
            )

    user.status = status
    if status == domain.USER_ACTIVE:
        user.disabled_at = None
        user.disabled_reason = None
    else:
        user.disabled_at = domain.utcnow()
        user.disabled_reason = (reason or "Account disabled")[:500]
        _revoke_sessions(user.id)
    return user


def _revoke_sessions(user_id: int) -> None:
    from ..models import UserSession

    now = domain.utcnow()
    UserSession.query.filter_by(user_id=user_id, revoked_at=None).update({"revoked_at": now})


def manager_can_view_user(actor: User, user: User) -> bool:
    if actor.role == domain.ROLE_ADMIN:
        return True
    if actor.role != domain.ROLE_MANAGER:
        return False
    if user.role == domain.ROLE_DRIVER:
        profile = user.driver_profile
        allowed = {area.id for area in _manager_scope(actor)}
        driver_areas = {link.service_area_id for link in profile.service_areas} if profile else set()
        return bool(driver_areas) and driver_areas.issubset(allowed)
    if user.id == actor.id:
        return True
    return False


# Imported lazily to keep the module's public surface tidy.
from ..models import UserPermission as UserPermissionRow  # noqa: E402
