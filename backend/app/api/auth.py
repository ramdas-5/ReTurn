"""Authentication: registration, sessions, activation and password recovery."""
from __future__ import annotations

import secrets

from flask import Blueprint, current_app, g, jsonify, request

from .. import domain
from ..errors import ApiError
from ..extensions import db
from ..models import BusinessProfile, ConsumerProfile, User
from ..security import (
    clear_session_cookies,
    consume_one_time_token,
    current_user,
    hash_password,
    issue_one_time_token,
    login_required,
    password_problem,
    rate_limit,
    revoke_current_session,
    set_csrf_cookie,
    start_session,
    verify_password,
)
from ..serializers import serialize_user
from ..services.audit import audit
from ..validation import Validator, json_body

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def _check_password(password: str, confirm: str | None, email: str | None = None) -> None:
    problem = password_problem(password, current_app.config.get("PASSWORD_MIN_LENGTH", 10))
    if problem:
        raise ApiError("weak_password", problem, 422, fields={"password": problem})
    if confirm is not None and password != confirm:
        raise ApiError(
            "password_mismatch",
            "The passwords do not match.",
            422,
            fields={"confirm_password": "The passwords do not match."},
        )
    local_part = (email or "").split("@")[0]
    if local_part and len(local_part) >= 4 and local_part.lower() in password.lower():
        raise ApiError(
            "weak_password",
            "Do not include your email address in the password.",
            422,
            fields={"password": "Choose a password unrelated to your email."},
        )


def _expose_tokens() -> bool:
    return bool(current_app.config.get("AUTH_EXPOSE_RESET_TOKENS"))


def _session_response(user, data: dict, status: int = 200):
    """Return one response that both carries the session cookie and the JSON body."""
    response = jsonify({"data": data})
    start_session(user, response)
    db.session.commit()
    payload = response.get_json()
    payload["data"]["csrf_token"] = g.session.csrf_token
    response.set_data(current_app.json.dumps(payload))
    response.status_code = status
    return response


@bp.get("/csrf")
def csrf():
    session = getattr(g, "session", None)
    if session is not None:
        token = session.csrf_token
    else:
        token = request.cookies.get(current_app.config["CSRF_COOKIE_NAME"])
        if not token:
            token = secrets.token_urlsafe(32)
    response = jsonify({"data": {"csrf_token": token}})
    set_csrf_cookie(response, token)
    return response


@bp.post("/register")
@rate_limit(8, 60 * 10, scope="register")
def register():
    data = json_body()
    v = Validator(data)
    full_name = v.string("full_name", required=True, min_length=2, max_length=160)
    email = v.email("email", required=True)
    phone = v.string("phone", required=True, min_length=6, max_length=40)
    password = v.string("password", required=True, min_length=8, max_length=200)
    confirm = v.string("confirm_password", required=True, min_length=8, max_length=200)
    account_type = v.choice(
        "account_type", ("individual", "business"), default="individual"
    )
    business = data.get("business") if isinstance(data.get("business"), dict) else {}
    if account_type == "business":
        if not str(business.get("business_name") or "").strip():
            v.fail("business.business_name", "Business name is required for a business account.")
    v.finish()

    if User.query.filter(db.func.lower(User.email) == email.lower()).first():
        raise ApiError("email_in_use", "An account already uses that email address.", 409)
    _check_password(password, confirm, email)

    consumer = User(
        email=email,
        full_name=full_name,
        phone=phone,
        role=domain.ROLE_CONSUMER,
        status=domain.USER_ACTIVE,
        password_hash=hash_password(password),
        activated_at=domain.utcnow(),
    )
    db.session.add(consumer)
    db.session.flush()
    db.session.add(ConsumerProfile(user_id=consumer.id, account_type=account_type))
    if account_type == "business":
        db.session.add(
            BusinessProfile(
                user_id=consumer.id,
                business_name=str(business.get("business_name")).strip()[:200],
                category=(business.get("category") or "")[:120] or None,
                contact_phone=(business.get("contact_phone") or phone)[:40],
                contact_email=(business.get("contact_email") or email)[:255],
                address_line=(business.get("address_line") or "")[:255] or None,
                area=(business.get("area") or "")[:120] or None,
                city=(business.get("city") or "Kolkata")[:120],
                state=(business.get("state") or "West Bengal")[:120],
                postal_code=(business.get("postal_code") or "")[:20] or None,
                tax_id=(business.get("tax_id") or "")[:80] or None,
            )
        )
    audit(
        "auth.register",
        "user",
        consumer.id,
        actor=consumer,
        summary=f"Consumer registered ({account_type})",
    )
    db.session.flush()

    return _session_response(consumer, {"user": serialize_user(consumer)}, status=201)


@bp.post("/login")
@rate_limit(10, 60, scope="login")
def login():
    data = json_body()
    v = Validator(data)
    email = v.email("email", required=True)
    password = v.string("password", required=True, min_length=1, max_length=200)
    v.finish()

    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    if user is None or not verify_password(user.password_hash, password):
        audit(
            "auth.login_failed",
            "user",
            getattr(user, "id", None),
            actor=None,
            summary=f"Failed sign-in for {email}",
        )
        db.session.commit()
        raise ApiError("invalid_credentials", "Email or password is incorrect.", 401)

    if user.status == domain.USER_SUSPENDED:
        raise ApiError(
            "account_suspended",
            "This account is suspended. Contact ReTurn support.",
            403,
        )
    if user.status == domain.USER_DEACTIVATED:
        raise ApiError("account_deactivated", "This account has been deactivated.", 403)
    if user.status == domain.USER_PENDING_ACTIVATION:
        raise ApiError(
            "account_pending_activation",
            "This account has not been activated yet. Use the activation link or code.",
            403,
        )

    audit("auth.login", "user", user.id, actor=user, summary="Signed in")
    return _session_response(user, {"user": serialize_user(user)})


@bp.post("/logout")
@login_required
def logout():
    user = current_user()
    audit("auth.logout", "user", user.id, actor=user, summary="Signed out")
    revoke_current_session()
    db.session.commit()
    response = jsonify({"data": {"ok": True}})
    return clear_session_cookies(response)


@bp.get("/me")
@login_required
def me():
    user = current_user()
    session = getattr(g, "session", None)
    return jsonify(
        {
            "data": {
                "user": serialize_user(user),
                "csrf_token": session.csrf_token if session else None,
            }
        }
    )


@bp.post("/password")
@login_required
def change_password():
    data = json_body()
    v = Validator(data)
    current = v.string("current_password", required=True, max_length=200)
    new = v.string("new_password", required=True, max_length=200)
    confirm = v.string("confirm_password", required=True, max_length=200)
    v.finish()

    user = current_user()
    if not verify_password(user.password_hash, current):
        raise ApiError(
            "current_password_invalid",
            "Your current password is incorrect.",
            422,
            fields={"current_password": "Incorrect password."},
        )
    _check_password(new, confirm, user.email)
    if new == current:
        raise ApiError("password_reused", "Choose a password you have not just used.", 422)

    user.password_hash = hash_password(new)
    user.password_changed_at = domain.utcnow()
    user.must_change_password = False
    if user.status == domain.USER_PENDING_ACTIVATION:
        user.status = domain.USER_ACTIVE
        user.activated_at = domain.utcnow()
    audit("auth.password_changed", "user", user.id, actor=user, summary="Password changed")
    db.session.commit()
    return jsonify({"data": {"ok": True}})


@bp.post("/forgot-password")
@rate_limit(5, 60 * 15, scope="forgot")
def forgot_password():
    data = json_body()
    v = Validator(data)
    email = v.email("email", required=True)
    v.finish()

    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    token = None
    if user is not None and user.status != domain.USER_DEACTIVATED:
        token = issue_one_time_token(user, "password_reset", ttl_hours=2)
        audit(
            "auth.password_reset_requested",
            "user",
            user.id,
            actor=user,
            summary="Password reset requested",
        )
        db.session.commit()

    payload = {
        "data": {
            "ok": True,
            "message": "If that email has an account, reset instructions have been issued.",
        }
    }
    if token and _expose_tokens():
        payload["data"]["reset_token"] = token
        payload["data"]["delivery"] = "development_only"
        payload["data"]["expires_in_hours"] = 2
    return jsonify(payload), 202


@bp.post("/reset-password")
@rate_limit(10, 60 * 15, scope="reset")
def reset_password():
    data = json_body()
    v = Validator(data)
    token = v.string("token", required=True, min_length=10, max_length=200)
    new = v.string("new_password", required=True, max_length=200)
    confirm = v.string("confirm_password", required=True, max_length=200)
    v.finish()

    row = consume_one_time_token(token, "password_reset")
    if row is None:
        raise ApiError(
            "token_invalid", "That reset link is invalid or has expired.", 400
        )
    user = db.session.get(User, row.user_id)
    if user is None or user.status == domain.USER_DEACTIVATED:
        raise ApiError("token_invalid", "That reset link is invalid or has expired.", 400)
    _check_password(new, confirm, user.email)
    user.password_hash = hash_password(new)
    user.password_changed_at = domain.utcnow()
    user.must_change_password = False
    from ..models import UserSession

    UserSession.query.filter_by(user_id=user.id, revoked_at=None).update(
        {"revoked_at": domain.utcnow()}
    )
    audit(
        "auth.password_reset_completed",
        "user",
        user.id,
        actor=user,
        summary="Password reset completed",
    )
    db.session.commit()
    return jsonify({"data": {"ok": True}})


@bp.post("/activate")
@rate_limit(10, 60 * 15, scope="activate")
def activate():
    data = json_body()
    v = Validator(data)
    token = v.string("token", required=True, min_length=10, max_length=200)
    new = v.string("new_password", required=True, max_length=200)
    confirm = v.string("confirm_password", required=True, max_length=200)
    v.finish()

    row = consume_one_time_token(token, "activation")
    if row is None:
        raise ApiError(
            "token_invalid", "That activation link is invalid or has expired.", 400
        )
    user = db.session.get(User, row.user_id)
    if user is None or user.status != domain.USER_PENDING_ACTIVATION:
        raise ApiError("token_invalid", "That activation link is no longer valid.", 400)
    _check_password(new, confirm, user.email)

    user.password_hash = hash_password(new)
    user.password_changed_at = domain.utcnow()
    user.must_change_password = False
    user.status = domain.USER_ACTIVE
    user.activated_at = domain.utcnow()
    audit("auth.activated", "user", user.id, actor=user, summary="Account activated")

    return _session_response(user, {"user": serialize_user(user)})


@bp.post("/resend-activation")
@rate_limit(5, 60 * 15, scope="resend")
def resend_activation_public():
    """Generic endpoint: never reveals whether an account exists."""
    data = json_body()
    v = Validator(data)
    email = v.email("email", required=True)
    v.finish()
    user = User.query.filter(db.func.lower(User.email) == email.lower()).first()
    token = None
    if user is not None and user.status == domain.USER_PENDING_ACTIVATION:
        token = issue_one_time_token(user, "activation")
        db.session.commit()
    payload = {
        "data": {
            "ok": True,
            "message": "If that account needs activation, a new code has been issued.",
        }
    }
    if token and _expose_tokens():
        payload["data"]["activation_token"] = token
        payload["data"]["delivery"] = "development_only"
    return jsonify(payload), 202
