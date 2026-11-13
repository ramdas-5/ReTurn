"""Authentication, session and profile endpoints."""
from __future__ import annotations

import secrets

from flask import Blueprint, g, jsonify, request

from ..domain import ROLE_CUSTOMER, ROLE_PARTNER, iso, utcnow
from ..errors import ApiError
from ..extensions import db
from ..models import PartnerProfile, User
from ..security import (
    current_user,
    clear_session_cookies,
    hash_password,
    login_required,
    password_problem,
    rate_limit,
    revoke_current_session,
    set_csrf_cookie,
    start_session,
    verify_password,
)
from ..serializers import serialize_partner_profile, serialize_user
from ..validation import Validator, json_body

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@bp.get("/csrf")
def csrf_token():
    """Bootstrap/inspect the CSRF token for this browser (safe, idempotent)."""
    session = getattr(g, "session", None)
    if session is not None:
        token = session.csrf_token
    else:
        token = request.cookies.get("rt_csrf") or secrets.token_urlsafe(32)
    response = jsonify({"data": {"csrf_token": token}})
    set_csrf_cookie(response, token)
    return response


@bp.post("/register")
@rate_limit(5, 3600, scope="register")
def register():
    data = json_body()
    v = Validator(data)
    name = v.string("name", required=True, min_length=2, max_length=120)
    email = v.email("email", required=True)
    password = v.string("password", required=True, min_length=8, max_length=128)
    role = v.choice("role", (ROLE_CUSTOMER, ROLE_PARTNER), required=True, default=ROLE_CUSTOMER)
    phone = v.string("phone", max_length=40, required=False)
    city = v.string("service_area", max_length=120, required=False)
    company_name = v.string("company_name", max_length=160, required=False)
    vehicle_type = v.choice("vehicle_type", ("bike", "car", "van", "truck"), default="van")
    v.finish()

    problem = password_problem(password or "")
    if problem:
        raise ApiError("weak_password", problem, 422, fields={"password": problem})
    if User.query.filter_by(email=email).first():
        raise ApiError(
            "email_taken",
            "An account with that email already exists.",
            409,
            fields={"email": "This email is already registered."},
        )

    user = User(
        name=name,
        email=email,
        phone=phone,
        role=role,
        password_hash=hash_password(password or ""),
    )
    db.session.add(user)
    db.session.flush()
    if role == ROLE_PARTNER:
        db.session.add(
            PartnerProfile(
                user_id=user.id,
                company_name=company_name or f"{name} — independent courier",
                vehicle_type=vehicle_type or "van",
                service_areas=city or "",
                verification_status="pending",
            )
        )
    db.session.flush()
    response = jsonify(
        {
            "data": {
                "user": serialize_user(user, include_private=True),
                "partner_profile": (
                    serialize_partner_profile(user.partner_profile)
                    if user.partner_profile
                    else None
                ),
                "notice": (
                    "Your partner account is pending administrator verification. You can complete your profile meanwhile."
                    if role == ROLE_PARTNER
                    else "Account created. You can create your first request."
                ),
            }
        }
    )
    start_session(user, response)
    db.session.commit()
    return response, 201


@bp.post("/login")
@rate_limit(10, 60, scope="login")
def login():
    data = json_body()
    v = Validator(data)
    email = v.email("email", required=True)
    password = v.string("password", required=True, min_length=1, max_length=128)
    v.finish()
    user = User.query.filter_by(email=email).first()
    if user is None or not verify_password(user.password_hash, password or ""):
        raise ApiError("invalid_credentials", "Email or password is incorrect.", 401)
    if user.disabled_at is not None:
        raise ApiError("account_disabled", "This account is disabled. Contact an administrator.", 403)
    response = jsonify(
        {
            "data": {
                "user": serialize_user(user, include_private=True),
                "partner_profile": (
                    serialize_partner_profile(user.partner_profile)
                    if user.partner_profile
                    else None
                ),
            }
        }
    )
    start_session(user, response)
    db.session.commit()
    return response


@bp.post("/logout")
def logout():
    user = current_user()
    revoke_current_session()
    db.session.commit()
    response = jsonify({"data": {"signed_out": True, "user_id": user.id if user else None}})
    clear_session_cookies(response)
    return response


@bp.get("/me")
@login_required
def me():
    user = current_user()
    data = {
        "user": serialize_user(user, include_private=True),
        "partner_profile": (
            serialize_partner_profile(user.partner_profile) if user.partner_profile else None
        ),
        "capabilities": _capabilities(user),
        "csrf_token": g.session.csrf_token if getattr(g, "session", None) else None,
    }
    response = jsonify({"data": data})
    if getattr(g, "session", None):
        set_csrf_cookie(response, g.session.csrf_token)
    return response


@bp.patch("/me")
@login_required
def update_me():
    user = current_user()
    data = json_body()
    v = Validator(data)
    if "name" in data:
        name = v.string("name", required=True, min_length=2, max_length=120)
        if name:
            user.name = name
    if "phone" in data:
        user.phone = v.string("phone", max_length=40) or None
    if "timezone" in data:
        user.timezone_name = v.choice(
            "timezone", ("Asia/Kolkata", "UTC"), default=user.timezone_name
        )
    if "notify_email" in data:
        user.notify_email = v.boolean("notify_email", user.notify_email)
    if "notify_in_app" in data:
        user.notify_in_app = v.boolean("notify_in_app", user.notify_in_app)
    new_password = data.get("new_password")
    if new_password:
        current_password = data.get("current_password")
        if not current_password or not verify_password(user.password_hash, str(current_password)):
            raise ApiError(
                "invalid_password",
                "Your current password is incorrect.",
                422,
                fields={"current_password": "Incorrect current password."},
            )
        problem = password_problem(str(new_password))
        if problem:
            raise ApiError("weak_password", problem, 422, fields={"new_password": problem})
        user.password_hash = hash_password(str(new_password))
    v.finish()
    db.session.commit()
    return jsonify(
        {
            "data": {
                "user": serialize_user(user, include_private=True),
                "partner_profile": (
                    serialize_partner_profile(user.partner_profile)
                    if user.partner_profile
                    else None
                ),
                "updated_at": iso(utcnow()),
            }
        }
    )


def _capabilities(user: User) -> dict:
    return {
        "create_request": user.role == ROLE_CUSTOMER,
        "admin": user.role == "admin",
        "partner": user.role == ROLE_PARTNER,
        "email_verified_placeholder": False,
    }
