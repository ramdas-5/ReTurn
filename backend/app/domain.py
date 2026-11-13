"""Domain constants, status machines and small helpers.

Statuses are the authoritative vocabulary used by the API, the matching engine
and the UI. Transitions are validated server-side before any write.
"""
from __future__ import annotations

from datetime import datetime, timezone

# ---------------------------------------------------------------- roles / types
ROLE_CUSTOMER = "customer"
ROLE_PARTNER = "partner"
ROLE_ADMIN = "admin"
ROLES = (ROLE_CUSTOMER, ROLE_PARTNER, ROLE_ADMIN)

SERVICE_RETURN = "return"
SERVICE_PARCEL = "parcel"
SERVICE_TYPES = (SERVICE_RETURN, SERVICE_PARCEL)

# ------------------------------------------------------------------- statuses
REQUEST_PENDING = "pending_matching"
REQUEST_BATCHED = "batched"
REQUEST_ASSIGNED = "assigned"
REQUEST_IN_PROGRESS = "in_progress"
REQUEST_COMPLETED = "completed"
REQUEST_CANCELLED = "cancelled"
REQUEST_FAILED = "failed"

REQUEST_STATUSES = (
    REQUEST_PENDING,
    REQUEST_BATCHED,
    REQUEST_ASSIGNED,
    REQUEST_IN_PROGRESS,
    REQUEST_COMPLETED,
    REQUEST_CANCELLED,
    REQUEST_FAILED,
)

ACTIVE_REQUEST_STATUSES = (
    REQUEST_PENDING,
    REQUEST_BATCHED,
    REQUEST_ASSIGNED,
    REQUEST_IN_PROGRESS,
)

BATCH_PROPOSED = "proposed"
BATCH_OFFERED = "offered"
BATCH_ACCEPTED = "accepted"
BATCH_IN_PROGRESS = "in_progress"
BATCH_COMPLETED = "completed"
BATCH_DECLINED = "declined"
BATCH_CANCELLED = "cancelled"

BATCH_STATUSES = (
    BATCH_PROPOSED,
    BATCH_OFFERED,
    BATCH_ACCEPTED,
    BATCH_IN_PROGRESS,
    BATCH_COMPLETED,
    BATCH_DECLINED,
    BATCH_CANCELLED,
)

ACTIVE_BATCH_STATUSES = (BATCH_PROPOSED, BATCH_OFFERED, BATCH_ACCEPTED, BATCH_IN_PROGRESS)

PARCEL_PENDING = "pending"
PARCEL_ASSIGNED = "assigned"
PARCEL_PARTNER_ACCEPTED = "partner_accepted"
PARCEL_PICKUP_ARRIVED = "pickup_arrived"
PARCEL_PICKED_UP = "picked_up"
PARCEL_IN_TRANSIT = "in_transit"
PARCEL_DELIVERED = "delivered"
PARCEL_FAILED = "failed"

PARCEL_STATUSES = (
    PARCEL_PENDING,
    PARCEL_ASSIGNED,
    PARCEL_PARTNER_ACCEPTED,
    PARCEL_PICKUP_ARRIVED,
    PARCEL_PICKED_UP,
    PARCEL_IN_TRANSIT,
    PARCEL_DELIVERED,
    PARCEL_FAILED,
)

# Parcel transitions are strictly ordered. A parcel can never be delivered
# before it has been picked up.
PARCEL_TRANSITIONS: dict[str, tuple[str, ...]] = {
    PARCEL_PENDING: (PARCEL_ASSIGNED,),
    PARCEL_ASSIGNED: (PARCEL_PARTNER_ACCEPTED, PARCEL_FAILED),
    PARCEL_PARTNER_ACCEPTED: (PARCEL_PICKUP_ARRIVED, PARCEL_FAILED),
    PARCEL_PICKUP_ARRIVED: (PARCEL_PICKED_UP, PARCEL_FAILED),
    PARCEL_PICKED_UP: (PARCEL_IN_TRANSIT, PARCEL_FAILED),
    PARCEL_IN_TRANSIT: (PARCEL_DELIVERED, PARCEL_FAILED),
    PARCEL_DELIVERED: (),
    PARCEL_FAILED: (),
}

PARCEL_TERMINAL_STATUSES = (PARCEL_DELIVERED, PARCEL_FAILED)

# -------------------------------------------------------------- event catalog
PARCEL_EVENT_TYPES = (
    PARCEL_ASSIGNED,
    PARCEL_PARTNER_ACCEPTED,
    PARCEL_PICKUP_ARRIVED,
    PARCEL_PICKED_UP,
    PARCEL_IN_TRANSIT,
    PARCEL_DELIVERED,
    PARCEL_FAILED,
)

STOP_PICKUP = "pickup"
STOP_DROPOFF = "dropoff"
STOP_KINDS = (STOP_PICKUP, STOP_DROPOFF)

STOP_PENDING = "pending"
STOP_ARRIVED = "arrived"
STOP_DONE = "done"
STOP_SKIPPED = "skipped"

HANDLING_FLAGS = ("fragile", "restricted", "liquid")
SIZE_CLASSES = ("small", "medium", "large")

PARTNER_PENDING = "pending"
PARTNER_VERIFIED = "verified"
PARTNER_REJECTED = "rejected"
VERIFICATION_STATUSES = (PARTNER_PENDING, PARTNER_VERIFIED, PARTNER_REJECTED)

AVAILABILITY_AVAILABLE = "available"
AVAILABILITY_UNAVAILABLE = "unavailable"
AVAILABILITY_ON_ROUTE = "on_route"
AVAILABILITY_OPTIONS = (AVAILABILITY_AVAILABLE, AVAILABILITY_UNAVAILABLE, AVAILABILITY_ON_ROUTE)

VEHICLE_TYPES = ("bike", "car", "van", "truck")

ISSUE_CATEGORIES = (
    "delivery_failure",
    "damaged_parcel",
    "address_problem",
    "capacity_problem",
    "route_problem",
    "other",
)
ISSUE_SEVERITIES = ("low", "medium", "high")
ISSUE_OPEN = "open"
ISSUE_IN_REVIEW = "in_review"
ISSUE_RESOLVED = "resolved"
ISSUE_STATUSES = (ISSUE_OPEN, ISSUE_IN_REVIEW, ISSUE_RESOLVED)

ASSIGNMENT_OFFERED = "offered"
ASSIGNMENT_ACCEPTED = "accepted"
ASSIGNMENT_DECLINED = "declined"
ASSIGNMENT_REASSIGNED = "reassigned"
ASSIGNMENT_REVOKED = "revoked"

MATCHING_REASONS = {
    "already_reserved": "The request is already reserved in another active batch.",
    "window_conflict": "The ordered route cannot reach this pickup inside its pickup window.",
    "deadline_missed": "The delivery deadline would be missed after inserting this stop.",
    "capacity_exceeded": "Vehicle weight or volume capacity is exceeded at some point on the route.",
    "handling_incompatible": "Handling requirements are incompatible with the other parcels or the vehicle.",
    "pickup_radius": "The pickup is outside the configured pickup radius for this group.",
    "service_area": "The partner does not operate in this service area.",
    "destination_missing": "A request has an unresolved pickup or destination location.",
    "insufficient_savings": "The combined route does not save enough distance over separate trips.",
    "no_eligible_partner": "No verified and eligible partner is available for this group.",
    "group_size": "The group would exceed the configured maximum batch size.",
    "restricted_exclusive": "Restricted parcels require a dedicated vehicle and cannot share a batch.",
    "route_infeasible": "No valid stop ordering satisfies all constraints.",
    "not_pending": "The request is not awaiting matching.",
    "unknown": "The grouping is not feasible.",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def request_code(raw_id: int | None) -> str:
    return f"RTN-REQ-{1000 + int(raw_id or 0)}"


def batch_code(raw_id: int | None) -> str:
    return f"RTN-BAT-{200 + int(raw_id or 0)}"


def parcel_code(raw_id: int | None) -> str:
    return f"RTN-PCL-{3000 + int(raw_id or 0)}"


def can_transition_parcel(current: str, target: str) -> bool:
    return target in PARCEL_TRANSITIONS.get(current, ())


def normalise_handling(flags: list[str] | None) -> list[str]:
    if not flags:
        return []
    seen: list[str] = []
    for flag in flags:
        value = str(flag).strip().lower()
        if value in HANDLING_FLAGS and value not in seen:
            seen.append(value)
    return seen
