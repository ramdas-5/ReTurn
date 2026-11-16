"""Authentication, sessions, CSRF, RBAC and rate limiting."""
from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from functools import wraps
from typing import Callable

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app, g, request

from .domain import utcnow
from .errors import ApiError
from .extensions import db

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


# --------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def password_problem(password: str, min_length: int = 10) -> str | None:
    if len(password) < min_length:
        return f"Use at least {min_length} characters."
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        return "Include at least one letter and one number."
    return None


def generate_temporary_password(length: int = 14) -> str:
    """Readable one-time credential: letters, digits and a symbol."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    while True:
        body = "".join(secrets.choice(alphabet) for _ in range(length - 2))
        candidate = f"{body}{secrets.choice('23456789')}{secrets.choice('!@#$%')}"
        if password_problem(candidate) is None:
            return candidate


# ---------------------------------------------------------------- one-time tokens
def issue_one_time_token(user, purpose: str, ttl_hours: int = 168) -> str:
    """Create a single-use token for activation or password reset."""
    from datetime import timedelta

    from flask import has_request_context

    from .models import OneTimeToken

    ip = request.remote_addr if has_request_context() else None
    OneTimeToken.query.filter_by(user_id=user.id, purpose=purpose, used_at=None).update(
        {"used_at": utcnow()}
    )
    raw = secrets.token_urlsafe(32)
    row = OneTimeToken(
        user_id=user.id,
        token_hash=_token_hash(raw),
        purpose=purpose,
        expires_at=utcnow() + timedelta(hours=ttl_hours),
        requested_ip=ip,
    )
    db.session.add(row)
    db.session.flush()
    return raw


def consume_one_time_token(raw: str, purpose: str):
    from .models import OneTimeToken

    if not raw:
        return None
    row = OneTimeToken.query.filter_by(token_hash=_token_hash(raw), purpose=purpose).first()
    if row is None or row.used_at is not None:
        return None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return None
    row.used_at = utcnow()
    return row


# ---------------------------------------------------------------------- sessions
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(user, response):
    """Create a server-side session and attach the HttpOnly cookie to `response`."""
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    from .models import UserSession

    session = UserSession(
        user_id=user.id,
        token_hash=_token_hash(raw_token),
        csrf_token=csrf_token,
        user_agent=(request.user_agent.string or "")[:255],
        ip_address=(request.remote_addr or "")[:64],
        expires_at=utcnow() + current_app.config["SESSION_TTL"],
    )
    db.session.add(session)
    user.last_login_at = utcnow()
    db.session.flush()

    response.set_cookie(
        current_app.config["SESSION_COOKIE_NAME"],
        raw_token,
        httponly=True,
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        samesite=current_app.config["SESSION_COOKIE_SAMESITE"],
        max_age=int(current_app.config["SESSION_TTL"].total_seconds()),
        path="/",
    )
    set_csrf_cookie(response, csrf_token)
    g.session = session
    g.user = user
    return session


def set_csrf_cookie(response, token: str):
    response.set_cookie(
        current_app.config["CSRF_COOKIE_NAME"],
        token,
        httponly=False,  # readable by the same-origin client by design
        secure=current_app.config["SESSION_COOKIE_SECURE"],
        samesite="Lax",
        max_age=int(current_app.config["SESSION_TTL"].total_seconds()),
        path="/",
    )


def revoke_current_session():
    session = getattr(g, "session", None)
    if session is not None:
        session.revoked_at = utcnow()
        db.session.add(session)
    g.session = None
    g.user = None


def _clear_cookie(response, name: str):
    response.delete_cookie(name, path="/", samesite="Lax")


def clear_session_cookies(response):
    _clear_cookie(response, current_app.config["SESSION_COOKIE_NAME"])
    _clear_cookie(response, current_app.config["CSRF_COOKIE_NAME"])
    return response


def load_session():
    """Resolve the session cookie into `g.session` / `g.user`."""
    g.session = None
    g.user = None
    token = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"])
    if not token:
        return
    from .models import UserSession

    session = UserSession.query.filter_by(token_hash=_token_hash(token)).first()
    if session is None or session.revoked_at is not None:
        return
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return
    user = session.user
    if user is None or user.disabled_at is not None:
        return
    if user.status != "active":
        return
    g.session = session
    g.user = user


def current_user():
    return getattr(g, "user", None)


def require_csrf():
    token = request.headers.get("X-CSRF-Token") or request.headers.get("X-CSRFToken")
    cookie_token = request.cookies.get(current_app.config["CSRF_COOKIE_NAME"])
    if not token or not cookie_token or not secrets.compare_digest(token, cookie_token):
        raise ApiError(
            "csrf_failed",
            "A valid CSRF token is required. Reload the page and try again.",
            403,
        )
    session = getattr(g, "session", None)
    if session is not None and not secrets.compare_digest(token, session.csrf_token):
        raise ApiError("csrf_failed", "Your security token expired. Sign in again.", 403)


def validate_csrf():
    if request.path.startswith("/api/v1") and request.method not in _SAFE_METHODS:
        require_csrf()


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            raise ApiError("authentication_required", "Please sign in to continue.", 401)
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    def decorator(view: Callable):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user.role not in roles:
                raise ApiError(
                    "forbidden",
                    "Your account does not have permission for this action.",
                    403,
                )
            return view(*args, **kwargs)

        return wrapped

    return decorator


def permission_required(*codes: str):
    """Require every listed granular permission (see `domain.user_permissions`)."""

    def decorator(view: Callable):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                raise ApiError("authentication_required", "Please sign in to continue.", 401)
            from .domain import has_permission

            missing = [code for code in codes if not has_permission(user, code)]
            if missing:
                raise ApiError(
                    "forbidden",
                    "Your account does not have permission for this action.",
                    403,
                    details={"missing_permissions": missing},
                )
            return view(*args, **kwargs)

        return wrapped

    return decorator


def require_consumer_profile(user=None):
    user = user or current_user()
    profile = getattr(user, "consumer_profile", None) if user is not None else None
    if profile is None:
        raise ApiError("consumer_profile_missing", "Complete your consumer profile first.", 409)
    return profile


def require_driver_profile(user=None):
    user = user or current_user()
    profile = getattr(user, "driver_profile", None) if user is not None else None
    if profile is None:
        raise ApiError("driver_profile_missing", "This account has no driver profile.", 409)
    return profile


def require_password_changed():
    """Accounts created with a temporary password must set a new one first."""

    def decorator(view: Callable):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is not None and user.must_change_password:
                raise ApiError(
                    "password_change_required",
                    "Change your temporary password before continuing.",
                    403,
                )
            return view(*args, **kwargs)

        return wrapped

    return decorator


# ------------------------------------------------------------------- rate limits
_limiter_buckets: dict[str, deque] = defaultdict(deque)
_limiter_lock = time.monotonic  # keeps imports minimal; single-process dev limiter


def rate_limit(limit: int, window_seconds: int = 60, scope: str = "default"):
    """Small in-process sliding window limiter (documented as single-process)."""

    def decorator(view: Callable):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_app.config.get("RATE_LIMIT_ENABLED", True):
                return view(*args, **kwargs)
            key = f"{scope}:{request.remote_addr or 'unknown'}:{getattr(current_user(), 'id', 'anon')}"
            now = time.monotonic()
            bucket = _limiter_buckets[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = int(window_seconds - (now - bucket[0])) + 1
                raise ApiError(
                    "rate_limited",
                    f"Too many attempts. Try again in {retry} seconds.",
                    429,
                    details={"retry_after_seconds": retry},
                )
            bucket.append(now)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def reset_rate_limits():  # pragma: no cover - test helper
    _limiter_buckets.clear()
