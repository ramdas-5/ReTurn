"""Real service availability.

Everything reported here is derived from persisted data: active service areas,
verified driver profiles, declared weekly availability windows and live duty
sessions. The platform never invents drivers, pickup slots or exact times. When
no driver is available the answer is an honest "no driver available for the
requested time" with the reasons attached.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

from .. import domain
from ..extensions import db
from ..models import (
    DriverAssignment,
    DriverAvailability,
    DriverDutySession,
    DriverProfile,
    Order,
    ServiceArea,
    User,
)
from .routing import haversine_km


# --------------------------------------------------------------------------- #
# Service areas
# --------------------------------------------------------------------------- #
def active_service_areas() -> list[ServiceArea]:
    return (
        ServiceArea.query.filter_by(is_active=True)
        .order_by(ServiceArea.name)
        .all()
    )


def _point_in_area(area: ServiceArea, lat: float, lng: float) -> bool:
    if area.center_latitude is None or area.center_longitude is None:
        return False
    distance = haversine_km(
        float(area.center_latitude),
        float(area.center_longitude),
        float(lat),
        float(lng),
    )
    return distance <= float(area.radius_km or 0)


def area_for_point(
    area_name: str | None, lat: float | None, lng: float | None
) -> ServiceArea | None:
    """Match a name first, then the nearest active area whose radius contains the pin."""
    areas = active_service_areas()
    if area_name:
        wanted = area_name.strip().casefold()
        for area in areas:
            if area.name.casefold() == wanted:
                return area
        # Postal codes are a secondary, honest match when they are configured.
        for area in areas:
            codes = {code.strip() for code in (area.postal_code_list or [])}
            if area_name.strip() in codes:
                return area
    if lat is None or lng is None:
        return None
    best: tuple[float, ServiceArea] | None = None
    for area in areas:
        if not _point_in_area(area, float(lat), float(lng)):
            continue
        distance = haversine_km(
            float(area.center_latitude),
            float(area.center_longitude),
            float(lat),
            float(lng),
        )
        if best is None or distance < best[0]:
            best = (distance, area)
    return best[1] if best else None


def area_snapshot(area: ServiceArea | None) -> dict | None:
    if area is None:
        return None
    return {
        "id": area.id,
        "name": area.name,
        "city": area.city,
        "state": area.state,
        "radius_km": float(area.radius_km) if area.radius_km is not None else None,
    }


def driver_covers_area(profile: DriverProfile, area: ServiceArea) -> bool:
    for link in profile.service_areas:
        linked = link.service_area
        if linked is not None and linked.id == area.id:
            return True
    return False


def driver_covers_point(
    profile: DriverProfile, area_name: str | None, lat: float | None, lng: float | None
) -> bool:
    for link in profile.service_areas:
        linked = link.service_area
        if linked is None or not linked.is_active:
            continue
        if area_name and linked.name.casefold() == area_name.strip().casefold():
            return True
        if lat is not None and lng is not None and _point_in_area(linked, float(lat), float(lng)):
            return True
    return False


# --------------------------------------------------------------------------- #
# Duty sessions
# --------------------------------------------------------------------------- #
def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=domain.UTC)
    return value.astimezone(domain.UTC)


def duty_is_live(session: DriverDutySession, now: datetime | None = None) -> bool:
    if session.ended_at is not None:
        return False
    if session.status not in domain.ACCEPTING_WORK_STATUSES:
        return False
    now = now or domain.utcnow()
    heartbeat = session.last_heartbeat_at or session.started_at
    if heartbeat is None:
        return False
    timeout = int(current_app.config.get("DUTY_HEARTBEAT_TIMEOUT_MINUTES", 15))
    return _as_utc(heartbeat) >= now - timedelta(minutes=timeout)


def live_duty_sessions(now: datetime | None = None) -> list[DriverDutySession]:
    now = now or domain.utcnow()
    rows = (
        DriverDutySession.query.filter(DriverDutySession.ended_at.is_(None))
        .filter(DriverDutySession.status.in_(domain.ACCEPTING_WORK_STATUSES))
        .order_by(DriverDutySession.started_at)
        .all()
    )
    return [row for row in rows if duty_is_live(row, now)]


def _verified_active_profile(profile: DriverProfile | None) -> bool:
    if profile is None:
        return False
    user = profile.user
    return (
        profile.verification_status == domain.VERIFICATION_VERIFIED
        and user is not None
        and user.status == domain.USER_ACTIVE
        and user.disabled_at is None
    )


def _on_duty_profiles(
    *, area_name: str | None = None, lat: float | None = None, lng: float | None = None
) -> list[DriverProfile]:
    sessions = live_duty_sessions()
    profiles: list[DriverProfile] = []
    for session in sessions:
        profile = session.driver
        if not _verified_active_profile(profile):
            continue
        if area_name is not None or lat is not None:
            if not driver_covers_point(profile, area_name, lat, lng):
                continue
        profiles.append(profile)
    return profiles


# --------------------------------------------------------------------------- #
# Declared weekly availability
# --------------------------------------------------------------------------- #
def _timezone():
    name = current_app.config.get("DEFAULT_TIMEZONE", "Asia/Kolkata")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:  # pragma: no cover - platform tzdata missing
        return ZoneInfo("UTC")


def windows_overlap(
    windows: list[DriverAvailability], start: datetime, end: datetime
) -> bool:
    """Check a requested UTC window against weekly local-time availability slots."""
    if not windows or end <= start:
        return False
    tz = _timezone()
    start_local = _as_utc(start).astimezone(tz)
    end_local = _as_utc(end).astimezone(tz)
    day = start_local.date()
    last_day = end_local.date()
    while day <= last_day:
        weekday = day.weekday()
        for window in windows:
            if not window.is_active or window.weekday != weekday:
                continue
            slot_start = datetime.combine(day, window.start_time, tz)
            slot_end = datetime.combine(day, window.end_time, tz)
            if slot_end <= slot_start:
                continue
            if slot_start <= end_local and start_local <= slot_end:
                return True
        day += timedelta(days=1)
    return False


def _scheduled_profiles(
    area: ServiceArea | None, start: datetime | None, end: datetime | None
) -> list[DriverProfile]:
    if start is None or end is None:
        return []
    profiles = (
        DriverProfile.query.filter_by(verification_status=domain.VERIFICATION_VERIFIED)
        .join(User, User.id == DriverProfile.user_id)
        .filter(User.status == domain.USER_ACTIVE, User.disabled_at.is_(None))
        .all()
    )
    matched: list[DriverProfile] = []
    for profile in profiles:
        if area is not None and not driver_covers_area(profile, area):
            continue
        windows = [row for row in profile.availability if row.is_active]
        if windows_overlap(windows, start, end):
            matched.append(profile)
    return matched


# --------------------------------------------------------------------------- #
# Workload
# --------------------------------------------------------------------------- #
def active_workload(driver_user_id: int) -> int:
    """Orders currently held by this driver (not terminal, still assigned)."""
    return (
        db.session.query(Order.id)
        .join(DriverAssignment, DriverAssignment.order_id == Order.id)
        .filter(
            DriverAssignment.driver_id == driver_user_id,
            DriverAssignment.status == "active",
            Order.status.notin_(domain.TERMINAL_ORDER_STATUSES),
        )
        .count()
    )


# --------------------------------------------------------------------------- #
# Combined answer
# --------------------------------------------------------------------------- #
def check(
    *,
    pickup_area: str | None = None,
    pickup_lat: float | None = None,
    pickup_lng: float | None = None,
    delivery_area: str | None = None,
    delivery_lat: float | None = None,
    delivery_lng: float | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict:
    pickup = area_for_point(pickup_area, pickup_lat, pickup_lng)
    delivery = area_for_point(delivery_area, delivery_lat, delivery_lng)

    reasons: list[str] = []
    if pickup is None:
        reasons.append("pickup_outside_service_area")
    if delivery is None:
        reasons.append("delivery_outside_service_area")

    on_duty: list[DriverProfile] = []
    scheduled: list[DriverProfile] = []
    if pickup is not None:
        on_duty = _on_duty_profiles(
            area_name=pickup.name, lat=pickup_lat, lng=pickup_lng
        )
        scheduled = _scheduled_profiles(pickup, window_start, window_end)
        if not on_duty and not scheduled:
            reasons.append("no_driver_available")

    if not pickup or not delivery:
        label = "Not serviceable"
    elif len(on_duty) >= 2:
        label = "Available"
    elif len(on_duty) == 1:
        label = "Limited availability"
    elif scheduled:
        label = "Scheduled availability for this slot"
    else:
        label = "No driver available for the requested time"

    return {
        "serviceable": pickup is not None and delivery is not None,
        "available": bool(on_duty or scheduled),
        "availability_label": label,
        "pickup_area": area_snapshot(pickup),
        "delivery_area": area_snapshot(delivery),
        "drivers_on_duty": len(on_duty),
        "drivers_scheduled": len(scheduled),
        "reasons": reasons,
        "checked_at": domain.iso(domain.utcnow()),
        "disclaimer": (
            "Availability is calculated from active service areas, verified driver "
            "schedules and live duty sessions. A driver is only committed after the "
            "order is reviewed and assigned by a manager."
        ),
    }
