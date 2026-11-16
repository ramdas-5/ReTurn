"""Driver duty sessions, heartbeats and location consent.

Being signed in is not the same as being on duty: matching only considers live
duty sessions. Location events are stored only while a duty session is open and
only when the client explicitly confirms permission. No position is invented.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import current_app

from .. import domain
from ..errors import ApiError
from ..extensions import db
from ..models import DriverDutySession, DriverLocationEvent, DriverProfile
from .availability import duty_is_live


def driver_profile(user) -> DriverProfile:
    profile = getattr(user, "driver_profile", None)
    if profile is None:
        raise ApiError("driver_profile_missing", "This account has no driver profile.", 403)
    return profile


def active_session(profile: DriverProfile) -> DriverDutySession | None:
    return (
        DriverDutySession.query.filter_by(driver_id=profile.id)
        .filter(DriverDutySession.ended_at.is_(None))
        .order_by(DriverDutySession.started_at.desc())
        .first()
    )


def require_open_session(profile: DriverProfile, *, require_live: bool = True) -> DriverDutySession:
    session = active_session(profile)
    if session is None:
        raise ApiError(
            "not_on_duty",
            "Start a duty session before doing field work.",
            409,
        )
    if require_live and not duty_is_live(session):
        raise ApiError(
            "duty_session_stale",
            "Your duty session has gone quiet. Send a heartbeat and try again.",
            409,
            details={
                "last_heartbeat_at": domain.iso(session.last_heartbeat_at),
                "timeout_minutes": int(
                    current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15)
                ),
            },
        )
    return session


def start_session(
    profile: DriverProfile,
    *,
    status: str,
    device_label: str | None,
    latitude: float | None,
    longitude: float | None,
) -> DriverDutySession:
    if profile.verification_status != domain.VERIFICATION_VERIFIED:
        raise ApiError(
            "driver_not_verified",
            "A manager must verify your identity and vehicle before you can go on duty.",
            403,
        )
    if status not in (domain.DUTY_AVAILABLE, domain.DUTY_ON_DUTY):
        raise ApiError(
            "invalid_duty_status", "Start duty as available or on duty.", 422
        )
    if active_session(profile) is not None:
        raise ApiError("already_on_duty", "You already have an open duty session.", 409)

    now = domain.utcnow()
    session = DriverDutySession(
        driver_id=profile.id,
        status=status,
        started_at=now,
        last_heartbeat_at=now,
        device_label=(device_label or None),
        start_latitude=latitude,
        start_longitude=longitude,
    )
    db.session.add(session)
    db.session.flush()
    return session


def change_status(session: DriverDutySession, status: str) -> DriverDutySession:
    if status not in domain.DUTY_STATUSES:
        raise ApiError(
            "invalid_duty_status", "Choose a valid duty status.", 422
        )
    if session.ended_at is not None:
        raise ApiError("duty_session_ended", "That duty session has ended.", 409)
    session.status = status
    session.last_heartbeat_at = domain.utcnow()
    return session


def heartbeat(
    session: DriverDutySession,
    *,
    latitude: float | None,
    longitude: float | None,
    accuracy_m: float | None,
) -> DriverDutySession:
    if session.ended_at is not None:
        raise ApiError("duty_session_ended", "That duty session has ended.", 409)
    session.last_heartbeat_at = domain.utcnow()
    if latitude is not None and longitude is not None:
        record_location(
            session,
            latitude=latitude,
            longitude=longitude,
            accuracy_m=accuracy_m,
            source="heartbeat",
        )
    return session


def record_location(
    session: DriverDutySession,
    *,
    latitude: float,
    longitude: float,
    accuracy_m: float | None = None,
    heading_degrees: float | None = None,
    speed_kmh: float | None = None,
    recorded_at: datetime | None = None,
    source: str = "browser_geolocation",
    batch_id: int | None = None,
) -> DriverLocationEvent:
    if session.ended_at is not None:
        raise ApiError("duty_session_ended", "That duty session has ended.", 409)
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise ApiError("invalid_coordinates", "Those coordinates are out of range.", 422)

    now = domain.utcnow()
    event = DriverLocationEvent(
        driver_id=session.driver_id,
        duty_session_id=session.id,
        batch_id=batch_id,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
        heading_degrees=heading_degrees,
        speed_kmh=speed_kmh,
        recorded_at=recorded_at or now,
        received_at=now,
        source=(source or "browser_geolocation")[:40],
    )
    db.session.add(event)
    session.last_heartbeat_at = now
    return event


def end_session(
    session: DriverDutySession,
    *,
    reason: str | None,
    latitude: float | None,
    longitude: float | None,
    active_workload: int,
) -> DriverDutySession:
    if session.ended_at is not None:
        raise ApiError("duty_session_ended", "That duty session has already ended.", 409)
    if active_workload:
        raise ApiError(
            "active_assignments",
            (
                "Finish or hand back your assigned parcels before ending duty. "
                "Ask a manager to reassign them."
            ),
            409,
            details={"active_assignments": active_workload},
        )
    now = domain.utcnow()
    session.ended_at = now
    session.ended_reason = (reason or "Driver ended duty")[:120]
    session.last_heartbeat_at = now
    if latitude is not None and longitude is not None:
        session.end_latitude = latitude
        session.end_longitude = longitude
    return session


def today_start() -> datetime:
    now = domain.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def session_is_recent(session: DriverDutySession) -> bool:
    timeout = int(current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15))
    heartbeat_at = session.last_heartbeat_at or session.started_at
    if heartbeat_at is None:
        return False
    if heartbeat_at.tzinfo is None:
        heartbeat_at = heartbeat_at.replace(tzinfo=domain.UTC)
    return heartbeat_at >= domain.utcnow() - timedelta(minutes=timeout)
