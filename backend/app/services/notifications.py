"""In-app notifications (persisted; the client polls the authenticated feed)."""
from __future__ import annotations

from ..extensions import db
from ..models import Notification, User

# Notification types -----------------------------------------------------------
ORDER_SUBMITTED = "order_submitted"
ORDER_ASSIGNED = "order_assigned"
ORDER_PICKED_UP = "order_picked_up"
ORDER_IN_TRANSIT = "order_in_transit"
ORDER_OUT_FOR_DELIVERY = "order_out_for_delivery"
ORDER_DELIVERED = "order_delivered"
ORDER_EXCEPTION = "order_exception"
ORDER_STATUS = "order_status"
BATCH_ASSIGNED = "batch_assigned"
ROUTE_UPDATED = "route_updated"
MATCHING_OPPORTUNITY = "matching_opportunity"
DRIVER_UNAVAILABLE = "driver_unavailable"
PROOF_PROBLEM = "proof_problem"
ACCOUNT_VERIFICATION = "account_verification"
SECURITY_EVENT = "security_event"


def notify(
    user_id: int,
    notification_type: str,
    title: str,
    body: str,
    *,
    link: str | None = None,
    event_data: dict | None = None,
) -> Notification:
    row = Notification(
        user_id=user_id,
        type=notification_type,
        title=title[:160],
        body=body[:600],
        link=(link or None),
        event_data=event_data or {},
    )
    db.session.add(row)
    return row


def notify_user(user, notification_type: str, title: str, body: str, **kwargs):
    if user is None:
        return None
    return notify(user.id, notification_type, title, body, **kwargs)


def notify_managers(notification_type: str, title: str, body: str, **kwargs) -> int:
    managers = User.query.filter_by(role="manager", status="active").all()
    for manager in managers:
        notify(manager.id, notification_type, title, body, **kwargs)
    return len(managers)


def notify_responsible_managers(
    notification_type: str,
    title: str,
    body: str,
    *,
    area_name: str | None = None,
    latitude=None,
    longitude=None,
    exclude_ids: set[int] | None = None,
    **kwargs,
) -> int:
    """Notify only managers whose service areas cover the pickup point.

    Falls back to the caller when nobody covers it, so a manager is never
    silently left out of the queue for an area the platform accepted.
    """
    from ..access import manager_covers_point

    managers = User.query.filter_by(role="manager", status="active").all()
    excluded = exclude_ids or set()
    matched = [
        manager
        for manager in managers
        if manager.id not in excluded
        and manager_covers_point(manager, area_name, latitude, longitude)
    ]
    for manager in matched:
        notify(manager.id, notification_type, title, body, **kwargs)
    return len(matched)


def notify_admins(notification_type: str, title: str, body: str, **kwargs) -> int:
    admins = User.query.filter_by(role="admin", status="active").all()
    for admin in admins:
        notify(admin.id, notification_type, title, body, **kwargs)
    return len(admins)


def notify_driver(driver_user_id: int, notification_type: str, title: str, body: str, **kwargs):
    return notify(driver_user_id, notification_type, title, body, **kwargs)
