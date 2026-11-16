"""Domain vocabulary, state machines, permissions and small helpers.

Everything the API, the matching engine and the UI agree on lives here. Status
transitions are validated server-side before any write.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Roles and permissions
# --------------------------------------------------------------------------- #
ROLE_CONSUMER = "consumer"
ROLE_DRIVER = "driver"
ROLE_MANAGER = "manager"
ROLE_ADMIN = "admin"
ROLES = (ROLE_CONSUMER, ROLE_DRIVER, ROLE_MANAGER, ROLE_ADMIN)
SELF_REGISTER_ROLES = (ROLE_CONSUMER,)

USER_ACTIVE = "active"
USER_PENDING_ACTIVATION = "pending_activation"
USER_SUSPENDED = "suspended"
USER_DEACTIVATED = "deactivated"
USER_STATUSES = (USER_ACTIVE, USER_PENDING_ACTIVATION, USER_SUSPENDED, USER_DEACTIVATED)

PERM_ORDERS_VIEW = "orders.view"
PERM_ORDERS_REVIEW = "orders.review"
PERM_ORDERS_ASSIGN = "orders.assign"
PERM_BATCHES_MANAGE = "batches.manage"
PERM_DRIVERS_VIEW = "drivers.view"
PERM_DRIVERS_MANAGE = "drivers.manage"
PERM_DRIVERS_VERIFY = "drivers.verify"
PERM_PROOFS_VERIFY = "proofs.verify"
PERM_EXCEPTIONS_RESOLVE = "exceptions.resolve"
PERM_ANALYTICS_VIEW = "analytics.view"
PERM_OPS_VIEW = "ops.view"
PERM_ACCOUNTS_MANAGE = "accounts.manage"
PERM_VEHICLES_MANAGE = "vehicles.manage"
PERM_SERVICE_AREAS_MANAGE = "service_areas.manage"
PERM_MATCHING_CONFIGURE = "matching.configure"
PERM_SETTINGS_MANAGE = "settings.manage"
PERM_AUDIT_VIEW = "audit.view"

PERMISSION_CATALOG = {
    PERM_ORDERS_VIEW: "View orders and parcel details",
    PERM_ORDERS_REVIEW: "Approve orders for scheduling",
    PERM_ORDERS_ASSIGN: "Assign and reassign drivers",
    PERM_BATCHES_MANAGE: "Create and manage batches and routes",
    PERM_DRIVERS_VIEW: "View driver profiles and availability",
    PERM_DRIVERS_MANAGE: "Create, suspend and manage drivers",
    PERM_DRIVERS_VERIFY: "Verify driver identity and vehicle documents",
    PERM_PROOFS_VERIFY: "Review pickup and delivery proof",
    PERM_EXCEPTIONS_RESOLVE: "Resolve delivery exceptions and issues",
    PERM_ANALYTICS_VIEW: "View operational analytics",
    PERM_OPS_VIEW: "View live operations",
    PERM_ACCOUNTS_MANAGE: "Manage user accounts",
    PERM_VEHICLES_MANAGE: "Manage vehicles and capacity profiles",
    PERM_SERVICE_AREAS_MANAGE: "Manage service areas",
    PERM_MATCHING_CONFIGURE: "Configure matching rules",
    PERM_SETTINGS_MANAGE: "Manage platform settings",
    PERM_AUDIT_VIEW: "View audit logs",
}

ROLE_DEFAULT_PERMISSIONS = {
    ROLE_CONSUMER: frozenset(),
    ROLE_DRIVER: frozenset(),
    ROLE_MANAGER: frozenset(
        {
            PERM_ORDERS_VIEW,
            PERM_ORDERS_REVIEW,
            PERM_ORDERS_ASSIGN,
            PERM_BATCHES_MANAGE,
            PERM_DRIVERS_VIEW,
            PERM_DRIVERS_MANAGE,
            PERM_DRIVERS_VERIFY,
            PERM_PROOFS_VERIFY,
            PERM_EXCEPTIONS_RESOLVE,
            PERM_ANALYTICS_VIEW,
            PERM_OPS_VIEW,
        }
    ),
    ROLE_ADMIN: frozenset(PERMISSION_CATALOG.keys()),
}


def user_permissions(user) -> set[str]:
    """Effective permission codes. Admin implicitly holds everything."""
    if user is None:
        return set()
    if user.role == ROLE_ADMIN:
        return set(PERMISSION_CATALOG.keys())
    granted = ROLE_DEFAULT_PERMISSIONS.get(user.role, frozenset())
    extra = {p.permission_code for p in getattr(user, "extra_permissions", ()) or ()}
    return set(granted) | extra


def has_permission(user, code: str) -> bool:
    return code in user_permissions(user)


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
SERVICE_PARCEL = "parcel"
SERVICE_RETURN = "return"
SERVICE_TYPES = (SERVICE_PARCEL, SERVICE_RETURN)

ORDER_DRAFT = "draft"
ORDER_SUBMITTED = "submitted"
ORDER_PENDING_REVIEW = "pending_review"
ORDER_AWAITING_ASSIGNMENT = "awaiting_assignment"
ORDER_ASSIGNED = "assigned"
ORDER_PICKUP_SCHEDULED = "pickup_scheduled"
ORDER_PICKUP_ARRIVED = "pickup_arrived"
ORDER_PICKED_UP = "picked_up"
ORDER_IN_TRANSIT = "in_transit"
ORDER_OUT_FOR_DELIVERY = "out_for_delivery"
ORDER_PROOF_PENDING = "delivery_proof_pending"
ORDER_DELIVERED = "delivered"
ORDER_FAILED = "delivery_failed"
ORDER_RETURN_IN_PROGRESS = "return_in_progress"
ORDER_RETURNED = "returned"
ORDER_CANCELLED = "cancelled"

ORDER_STATUSES = (
    ORDER_DRAFT,
    ORDER_SUBMITTED,
    ORDER_PENDING_REVIEW,
    ORDER_AWAITING_ASSIGNMENT,
    ORDER_ASSIGNED,
    ORDER_PICKUP_SCHEDULED,
    ORDER_PICKUP_ARRIVED,
    ORDER_PICKED_UP,
    ORDER_IN_TRANSIT,
    ORDER_OUT_FOR_DELIVERY,
    ORDER_PROOF_PENDING,
    ORDER_DELIVERED,
    ORDER_FAILED,
    ORDER_RETURN_IN_PROGRESS,
    ORDER_RETURNED,
    ORDER_CANCELLED,
)

ORDER_STATUS_LABELS = {
    ORDER_DRAFT: "Draft",
    ORDER_SUBMITTED: "Submitted",
    ORDER_PENDING_REVIEW: "Pending review",
    ORDER_AWAITING_ASSIGNMENT: "Awaiting assignment",
    ORDER_ASSIGNED: "Driver assigned",
    ORDER_PICKUP_SCHEDULED: "Pickup scheduled",
    ORDER_PICKUP_ARRIVED: "Pickup arrived",
    ORDER_PICKED_UP: "Picked up",
    ORDER_IN_TRANSIT: "In transit",
    ORDER_OUT_FOR_DELIVERY: "Out for delivery",
    ORDER_PROOF_PENDING: "Delivery proof pending",
    ORDER_DELIVERED: "Delivered",
    ORDER_FAILED: "Delivery issue",
    ORDER_RETURN_IN_PROGRESS: "Return in progress",
    ORDER_RETURNED: "Returned",
    ORDER_CANCELLED: "Cancelled",
}

ACTIVE_ORDER_STATUSES = (
    ORDER_SUBMITTED,
    ORDER_PENDING_REVIEW,
    ORDER_AWAITING_ASSIGNMENT,
    ORDER_ASSIGNED,
    ORDER_PICKUP_SCHEDULED,
    ORDER_PICKUP_ARRIVED,
    ORDER_PICKED_UP,
    ORDER_IN_TRANSIT,
    ORDER_OUT_FOR_DELIVERY,
    ORDER_PROOF_PENDING,
    ORDER_RETURN_IN_PROGRESS,
)

TERMINAL_ORDER_STATUSES = (ORDER_DELIVERED, ORDER_RETURNED, ORDER_CANCELLED)

# Statuses in which a driver physically holds the parcel and the order is on a route.
IN_CUSTODY_STATUSES = (
    ORDER_PICKED_UP,
    ORDER_IN_TRANSIT,
    ORDER_OUT_FOR_DELIVERY,
    ORDER_PROOF_PENDING,
    ORDER_RETURN_IN_PROGRESS,
)

ORDER_TRANSITIONS: dict[str, set[str]] = {
    ORDER_DRAFT: {ORDER_SUBMITTED, ORDER_CANCELLED},
    ORDER_SUBMITTED: {ORDER_PENDING_REVIEW, ORDER_AWAITING_ASSIGNMENT, ORDER_CANCELLED},
    ORDER_PENDING_REVIEW: {ORDER_AWAITING_ASSIGNMENT, ORDER_CANCELLED},
    ORDER_AWAITING_ASSIGNMENT: {ORDER_ASSIGNED, ORDER_CANCELLED},
    ORDER_ASSIGNED: {ORDER_PICKUP_SCHEDULED, ORDER_AWAITING_ASSIGNMENT, ORDER_CANCELLED},
    ORDER_PICKUP_SCHEDULED: {
        ORDER_PICKUP_ARRIVED,
        ORDER_AWAITING_ASSIGNMENT,
        ORDER_CANCELLED,
    },
    ORDER_PICKUP_ARRIVED: {
        ORDER_PICKED_UP,
        ORDER_AWAITING_ASSIGNMENT,
        ORDER_FAILED,
    },
    ORDER_PICKED_UP: {ORDER_IN_TRANSIT, ORDER_OUT_FOR_DELIVERY, ORDER_FAILED},
    ORDER_IN_TRANSIT: {ORDER_OUT_FOR_DELIVERY, ORDER_FAILED},
    ORDER_OUT_FOR_DELIVERY: {ORDER_PROOF_PENDING, ORDER_DELIVERED, ORDER_FAILED},
    ORDER_PROOF_PENDING: {ORDER_DELIVERED, ORDER_FAILED},
    ORDER_DELIVERED: {ORDER_RETURN_IN_PROGRESS},
    ORDER_FAILED: {ORDER_AWAITING_ASSIGNMENT, ORDER_CANCELLED},
    ORDER_RETURN_IN_PROGRESS: {ORDER_RETURNED, ORDER_FAILED},
    ORDER_RETURNED: set(),
    ORDER_CANCELLED: set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in ORDER_TRANSITIONS.get(current, set())


def is_active_order(status: str) -> bool:
    return status in ACTIVE_ORDER_STATUSES


# --------------------------------------------------------------------------- #
# Batches and routes
# --------------------------------------------------------------------------- #
BATCH_DRAFT = "draft"
BATCH_PROPOSED = "proposed"
BATCH_ASSIGNED = "assigned"
BATCH_ACTIVE = "active"
BATCH_COMPLETED = "completed"
BATCH_CANCELLED = "cancelled"
BATCH_STATUSES = (
    BATCH_DRAFT,
    BATCH_PROPOSED,
    BATCH_ASSIGNED,
    BATCH_ACTIVE,
    BATCH_COMPLETED,
    BATCH_CANCELLED,
)

BATCH_STATUS_LABELS = {
    BATCH_DRAFT: "Draft",
    BATCH_PROPOSED: "Proposed",
    BATCH_ASSIGNED: "Assigned",
    BATCH_ACTIVE: "In progress",
    BATCH_COMPLETED: "Completed",
    BATCH_CANCELLED: "Cancelled",
}

BATCH_TRANSITIONS = {
    BATCH_DRAFT: {BATCH_PROPOSED, BATCH_ASSIGNED, BATCH_CANCELLED},
    BATCH_PROPOSED: {BATCH_ASSIGNED, BATCH_CANCELLED},
    BATCH_ASSIGNED: {BATCH_ACTIVE, BATCH_CANCELLED, BATCH_PROPOSED},
    BATCH_ACTIVE: {BATCH_COMPLETED, BATCH_CANCELLED},
    BATCH_COMPLETED: set(),
    BATCH_CANCELLED: set(),
}

ROUTE_DRAFT = "draft"
ROUTE_ACTIVE = "active"
ROUTE_SUPERSEDED = "superseded"
ROUTE_STATUSES = (ROUTE_DRAFT, ROUTE_ACTIVE, ROUTE_SUPERSEDED)

STOP_PICKUP = "pickup"
STOP_DELIVERY = "delivery"
STOP_KINDS = (STOP_PICKUP, STOP_DELIVERY)
STOP_PENDING = "pending"
STOP_ARRIVED = "arrived"
STOP_COMPLETED = "completed"
STOP_SKIPPED = "skipped"
STOP_FAILED = "failed"
STOP_STATUSES = (STOP_PENDING, STOP_ARRIVED, STOP_COMPLETED, STOP_SKIPPED, STOP_FAILED)


# --------------------------------------------------------------------------- #
# Drivers / duty
# --------------------------------------------------------------------------- #
DUTY_AVAILABLE = "available"
DUTY_ON_DUTY = "on_duty"
DUTY_ON_BREAK = "on_break"
DUTY_BUSY = "busy"
DUTY_UNAVAILABLE = "unavailable"
DUTY_STATUSES = (DUTY_AVAILABLE, DUTY_ON_DUTY, DUTY_ON_BREAK, DUTY_BUSY, DUTY_UNAVAILABLE)
ACCEPTING_WORK_STATUSES = (DUTY_AVAILABLE, DUTY_ON_DUTY)

DUTY_LABELS = {
    DUTY_AVAILABLE: "Available",
    DUTY_ON_DUTY: "On duty",
    DUTY_ON_BREAK: "On break",
    DUTY_BUSY: "Busy",
    DUTY_UNAVAILABLE: "Unavailable",
}

VEHICLE_TYPES = ("bike", "scooter", "car", "van", "truck")

VERIFICATION_PENDING = "pending"
VERIFICATION_VERIFIED = "verified"
VERIFICATION_REJECTED = "rejected"
VERIFICATION_NOT_REQUIRED = "not_required"
VERIFICATION_STATUSES = (
    VERIFICATION_PENDING,
    VERIFICATION_VERIFIED,
    VERIFICATION_REJECTED,
    VERIFICATION_NOT_REQUIRED,
)


# --------------------------------------------------------------------------- #
# Proof and exceptions
# --------------------------------------------------------------------------- #
PROOF_PICKUP = "pickup"
PROOF_DELIVERY = "delivery"
PROOF_TYPES = (PROOF_PICKUP, PROOF_DELIVERY)
PROOF_VALID = "valid"
PROOF_PENDING = "pending_verification"
PROOF_REJECTED = "rejected"
PROOF_STATUSES = (PROOF_VALID, PROOF_PENDING, PROOF_REJECTED)

EXCEPTION_TYPES = (
    "parcel_missing",
    "parcel_damaged",
    "recipient_unavailable",
    "address_not_found",
    "access_denied",
    "refused_delivery",
    "proof_capture_failed",
    "proof_rejected",
    "vehicle_breakdown",
    "other",
)

EXCEPTION_OPEN = "open"
EXCEPTION_RESOLVED = "resolved"
EXCEPTION_REJECTED = "rejected"
EXCEPTION_STATUSES = (EXCEPTION_OPEN, EXCEPTION_RESOLVED, EXCEPTION_REJECTED)

RETURN_APPROVAL_PENDING = "pending"
RETURN_APPROVAL_APPROVED = "approved"
RETURN_APPROVAL_REJECTED = "rejected"
RETURN_APPROVAL_NOT_REQUIRED = "not_required"
RETURN_APPROVAL_STATUSES = (
    RETURN_APPROVAL_PENDING,
    RETURN_APPROVAL_APPROVED,
    RETURN_APPROVAL_REJECTED,
    RETURN_APPROVAL_NOT_REQUIRED,
)

RETURN_DESTINATION_TYPES = ("business", "warehouse", "returns_center", "other")

# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
SUGGESTION_PENDING = "pending"
SUGGESTION_APPROVED = "approved"
SUGGESTION_REJECTED = "rejected"
SUGGESTION_EXPIRED = "expired"
SUGGESTION_SUPERSEDED = "superseded"
SUGGESTION_STATUSES = (
    SUGGESTION_PENDING,
    SUGGESTION_APPROVED,
    SUGGESTION_REJECTED,
    SUGGESTION_EXPIRED,
    SUGGESTION_SUPERSEDED,
)

MATCHING_REJECTION_REASONS = {
    "vehicle_capacity_exceeded": "The additional parcel exceeds the vehicle's weight or volume capacity.",
    "parcel_dimension_exceeded": "The parcel is larger than the vehicle can carry.",
    "pickup_too_far_from_route": "The pickup point is too far from the driver's active route.",
    "route_detour_too_large": "Adding this order would cause a detour above the configured limit.",
    "delivery_deadline_conflict": "The delivery deadline cannot be met without delaying committed orders.",
    "pickup_window_conflict": "The pickup window does not overlap the driver's route schedule.",
    "driver_not_available": "The driver is not currently accepting work.",
    "driver_off_duty": "The driver is off duty.",
    "driver_on_break": "The driver is on a break.",
    "service_area_unsupported": "The pickup or delivery point is outside the driver's service areas.",
    "handling_restriction_conflict": "The parcel requires handling the vehicle is not equipped for.",
    "workload_limit_exceeded": "The driver already has the maximum safe workload.",
    "no_active_route": "The driver has no active route to extend.",
    "no_compatible_driver": "No on-duty driver can serve this request.",
    "route_recalculation_failed": "The proposed route could not be recalculated safely.",
    "driver_not_verified": "The driver's identity and vehicle have not been verified.",
    "vehicle_missing": "The driver has no active vehicle to carry the parcel.",
    "vehicle_not_verified": "The driver's vehicle is not verified for operations.",
    "driver_has_active_batch": "The driver already has an assigned or active batch.",
    "order_not_assignable": "The order is not in a state that can be assigned.",
    "order_already_assigned": "The order already has an active driver assignment.",
}


def rejection_label(code: str) -> str:
    return MATCHING_REJECTION_REASONS.get(code, code.replace("_", " ").capitalize())


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
ORDER_NUMBER_BASE = 100000
BATCH_NUMBER_BASE = 5000


def order_number(order_id: int) -> str:
    return f"RT-{ORDER_NUMBER_BASE + order_id}"


def batch_number(batch_id: int) -> str:
    return f"B-{BATCH_NUMBER_BASE + batch_id}"


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a <= end_b and start_b <= end_a


def add_minutes(value: datetime, minutes: float) -> datetime:
    return value + timedelta(minutes=minutes)


def weekday_monday_zero(value: datetime) -> int:
    return value.weekday()
