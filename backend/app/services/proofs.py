"""Server-side proof validation for pickup and delivery evidence.

The client supplies a freshly captured photograph, coordinates and a capture
time. The server never trusts those blindly: it enforces a maximum capture age
(measured against the server clock at receipt), a maximum GPS accuracy and a
maximum distance from the stop, then stores its own receipt timestamp.

A gallery upload cannot silently satisfy the requirement: a request that claims
a non-camera source is rejected, and the claim is recorded on the audit trail.
The remaining honest boundary is that a modified client can lie about the
camera source; server-side freshness, assignment, session and location checks
still apply.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from flask import current_app

from .. import domain
from ..errors import ApiError
from .routing import haversine_km

NON_CAMERA_SOURCES = {"gallery", "file", "upload", "filesystem", "screenshot"}


def _decimal(value, places: str = "0.000001") -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value)).quantize(Decimal(places))


def distance_meters(lat1, lng1, lat2, lng2) -> float:
    return haversine_km(float(lat1), float(lng1), float(lat2), float(lng2)) * 1000.0


def validate_capture(
    *,
    kind: str,
    captured_at: datetime | None,
    latitude: float | None,
    longitude: float | None,
    accuracy_m: float | None,
    reference_lat: float | None,
    reference_lng: float | None,
    capture_source: str | None,
) -> dict:
    """Return the validated evidence envelope, or raise a corrective `ApiError`."""
    now = domain.utcnow()
    reasons: list[str] = []
    corrective: list[str] = []

    if capture_source and capture_source.strip().lower() in NON_CAMERA_SOURCES:
        reasons.append("capture_source_not_camera")
        corrective.append("Capture a new photograph with the device camera.")

    require_gps = bool(current_app.config.get("PROOF_REQUIRE_GPS", True))
    if latitude is None or longitude is None:
        if require_gps:
            reasons.append("gps_required")
            corrective.append(
                "Allow location access and retry while standing at the stop."
            )
    else:
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            reasons.append("gps_out_of_range")
            corrective.append("Capture the location again.")

    accuracy = accuracy_m
    max_accuracy = float(current_app.config.get("PROOF_MAX_ACCURACY_METERS", 250))
    if require_gps:
        if accuracy is None:
            reasons.append("accuracy_required")
            corrective.append("Share the location accuracy reported by the device.")
        elif accuracy > max_accuracy:
            reasons.append("accuracy_too_low")
            corrective.append(
                f"Wait for a GPS fix accurate to {max_accuracy:g} m or better."
            )

    distance = None
    radius = float(current_app.config.get("PROOF_GPS_RADIUS_METERS", 400))
    if (
        latitude is not None
        and longitude is not None
        and reference_lat is not None
        and reference_lng is not None
    ):
        distance = round(
            distance_meters(latitude, longitude, reference_lat, reference_lng), 1
        )
        if distance > radius:
            reasons.append("too_far_from_stop")
            corrective.append(
                f"Move within {radius:g} m of the {kind} address and retry."
            )

    max_age = int(current_app.config.get("PROOF_MAX_CAPTURE_AGE_MINUTES", 20))
    effective_capture = captured_at
    if captured_at is not None:
        if captured_at > now + timedelta(minutes=2):
            reasons.append("capture_time_in_future")
            corrective.append("Check the device clock and capture the proof again.")
        elif captured_at < now - timedelta(minutes=max_age):
            reasons.append("capture_too_old")
            corrective.append(
                f"Capture a fresh photograph now (within {max_age} minutes)."
            )
    else:
        effective_capture = now

    if reasons:
        raise ApiError(
            "proof_invalid",
            "The proof could not be validated. Follow the corrective steps and retry.",
            422,
            details={
                "kind": kind,
                "reasons": reasons,
                "corrective_actions": corrective,
                "max_capture_age_minutes": max_age,
                "gps_radius_meters": radius,
                "max_accuracy_meters": max_accuracy,
            },
        )

    return {
        "kind": kind,
        "captured_at": effective_capture,
        "server_received_at": now,
        "latitude": _decimal(latitude),
        "longitude": _decimal(longitude),
        "accuracy_m": _decimal(accuracy, "0.01") if accuracy is not None else None,
        "distance_from_stop_m": _decimal(distance, "0.01") if distance is not None else None,
        "capture_source": (capture_source or "device_camera")[:40],
        "verification_status": domain.PROOF_VALID,
    }
