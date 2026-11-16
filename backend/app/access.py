"""Ownership and scope checks. All authorization is enforced here, server-side."""
from __future__ import annotations

from .domain import ROLE_ADMIN, ROLE_CONSUMER, ROLE_DRIVER, ROLE_MANAGER, is_active_order
from .errors import ApiError
from .models import BatchOrder, DriverAssignment, Order


def _service_area_rows(user):
    profile = getattr(user, "manager_profile", None)
    if profile is None:
        return []
    return [link.service_area for link in profile.service_areas if link.service_area is not None]


def _area_match(service_area, area_name: str | None, lat, lng) -> bool:
    if area_name and service_area.name.casefold() == area_name.casefold():
        return True
    if area_name and area_name.casefold() in (service_area.postal_codes or "").casefold():
        return True
    if lat is not None and lng is not None and service_area.center_latitude is not None:
        from .services.routing import haversine_km

        distance = haversine_km(
            float(service_area.center_latitude),
            float(service_area.center_longitude),
            float(lat),
            float(lng),
        )
        if distance <= float(service_area.radius_km or 0):
            return True
    return False


def manager_covers_order(user, order: Order) -> bool:
    address = order.pickup_address
    if address is None:
        return False
    return any(
        _area_match(area, address.area, address.latitude, address.longitude)
        for area in _service_area_rows(user)
    )


def manager_covers_point(user, area_name: str | None, lat, lng) -> bool:
    return any(_area_match(area, area_name, lat, lng) for area in _service_area_rows(user))


def manager_covers_area_name(user, area_name: str | None) -> bool:
    return any(_area_match(area, area_name, None, None) for area in _service_area_rows(user))


def can_view_order(user, order: Order) -> bool:
    if user is None:
        return False
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_CONSUMER:
        return order.consumer_id == user.id
    if user.role == ROLE_MANAGER:
        return manager_covers_order(user, order)
    if user.role == ROLE_DRIVER:
        assignment = (
            DriverAssignment.query.filter_by(order_id=order.id, driver_id=user.id)
            .order_by(DriverAssignment.assigned_at.desc())
            .first()
        )
        return assignment is not None
    return False


def assert_order_access(user, order: Order):
    if not can_view_order(user, order):
        raise ApiError("forbidden", "You do not have access to that order.", 403)


def assert_consumer_owns(user, order: Order):
    if user is None or order.consumer_id != user.id:
        raise ApiError("forbidden", "You do not have access to that order.", 403)


def can_view_batch(user, batch) -> bool:
    if user is None:
        return False
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_DRIVER:
        return batch.driver_id == user.id
    if user.role == ROLE_MANAGER:
        if batch.manager_id == user.id:
            return True
        order_ids = [
            link.order
            for link in BatchOrder.query.filter_by(batch_id=batch.id)
            .filter(BatchOrder.removed_at.is_(None))
            .all()
        ]
        return any(manager_covers_order(user, order) for order in order_ids if order)
    if user.role == ROLE_CONSUMER:
        return any(
            link.order is not None and link.order.consumer_id == user.id
            for link in BatchOrder.query.filter_by(batch_id=batch.id)
            .filter(BatchOrder.removed_at.is_(None))
            .all()
        )
    return False


def assert_batch_access(user, batch):
    if not can_view_batch(user, batch):
        raise ApiError("forbidden", "You do not have access to that batch.", 403)


def consumer_can_cancel(order: Order) -> bool:
    return is_active_order(order.status) and order.status not in {
        "picked_up",
        "in_transit",
        "out_for_delivery",
        "delivery_proof_pending",
        "return_in_progress",
    }
