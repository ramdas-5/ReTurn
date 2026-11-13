"""Ownership and role-scoped access helpers (authorization lives in Flask)."""
from __future__ import annotations

from .domain import ROLE_ADMIN, ROLE_PARTNER
from .errors import ApiError
from .models import BatchRequest, DeliveryBatch, DeliveryRequest


def partner_user_id_for_request(request: DeliveryRequest) -> int | None:
    link = (
        BatchRequest.query.filter(
            BatchRequest.request_id == request.id, BatchRequest.released_at.is_(None)
        )
        .join(DeliveryBatch, DeliveryBatch.id == BatchRequest.batch_id)
        .first()
    )
    return link.batch.partner_id if link and link.batch else None


def partner_has_history_with_request(user_id: int, request: DeliveryRequest) -> bool:
    links = BatchRequest.query.filter(BatchRequest.request_id == request.id).all()
    return any(link.batch and link.batch.partner_id == user_id for link in links)


def can_access_request(user, request: DeliveryRequest) -> bool:
    if user is None:
        return False
    if user.role == ROLE_ADMIN:
        return True
    if request.customer_id == user.id:
        return True
    if user.role == ROLE_PARTNER:
        return (
            partner_user_id_for_request(request) == user.id
            or partner_has_history_with_request(user.id, request)
        )
    return False


def assert_request_access(user, request: DeliveryRequest):
    if not can_access_request(user, request):
        raise ApiError("forbidden", "You do not have access to that request.", 403)


def can_access_batch(user, batch: DeliveryBatch) -> bool:
    if user is None:
        return False
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_PARTNER:
        if batch.partner_id == user.id:
            return True
        if batch.status == "proposed":
            from .services.matching import partner_eligible_for_batch

            eligible, _ = partner_eligible_for_batch(batch, user.partner_profile)
            return eligible
        return False
    return any(
        link.request.customer_id == user.id
        for link in batch.request_links
        if link.released_at is None
    )


def assert_batch_access(user, batch: DeliveryBatch):
    if not can_access_batch(user, batch):
        raise ApiError("forbidden", "You do not have access to that batch.", 403)


def batch_contacts_allowed(user, batch: DeliveryBatch) -> bool:
    if user is None:
        return False
    if user.role == ROLE_ADMIN:
        return True
    if user.role == ROLE_PARTNER:
        return batch.partner_id == user.id and batch.status in {
            "accepted",
            "in_progress",
            "completed",
        }
    return False


def customer_request_ids(user_id: int) -> list[int]:
    return [
        row[0]
        for row in DeliveryRequest.query.with_entities(DeliveryRequest.id)
        .filter(DeliveryRequest.customer_id == user_id)
        .all()
    ]
