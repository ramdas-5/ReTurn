"""Order creation and lifecycle services.

State changes happen only through `record_status`, which enforces the domain
transition table and writes an append-only history row.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from .. import domain
from ..errors import ApiError
from ..extensions import db
from ..models import (
    Contact,
    DeliveryAddress,
    Order,
    OrderStatusHistory,
    ParcelDetail,
    PickupAddress,
    ReturnRequest,
)


def _money(value) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def order_for_number(number: str) -> Order | None:
    return Order.query.filter_by(order_number=number.strip().upper()).first()


def create_order(consumer, payload: dict) -> Order:
    """Create an order and its immutable address/parcel snapshots.

    `payload` is validated by the API layer. This function only persists.
    """
    pickup = payload["pickup"]
    delivery = payload["delivery"]
    sender = payload.get("sender") or {}
    recipient = payload.get("recipient") or {}
    parcel_data = payload["parcel"]
    window_start: datetime = payload["pickup_window_start"]
    window_end: datetime = payload["pickup_window_end"]
    deadline: datetime = payload["delivery_deadline"]

    if window_end <= window_start:
        raise ApiError("invalid_pickup_window", "The pickup window end must be after its start.")
    if deadline <= window_end:
        raise ApiError(
            "invalid_deadline", "The delivery deadline must be after the pickup window."
        )

    pickup_address = PickupAddress(
        contact_name=pickup["contact_name"],
        contact_phone=pickup["contact_phone"],
        address_line=pickup["address_line"],
        address_line2=pickup.get("address_line2"),
        area=pickup["area"],
        city=pickup.get("city") or "Kolkata",
        state=pickup.get("state") or "West Bengal",
        postal_code=pickup.get("postal_code"),
        latitude=pickup["latitude"],
        longitude=pickup["longitude"],
        instructions=pickup.get("instructions"),
    )
    delivery_address = DeliveryAddress(
        contact_name=delivery["contact_name"],
        contact_phone=delivery["contact_phone"],
        address_line=delivery["address_line"],
        address_line2=delivery.get("address_line2"),
        area=delivery["area"],
        city=delivery.get("city") or "Kolkata",
        state=delivery.get("state") or "West Bengal",
        postal_code=delivery.get("postal_code"),
        latitude=delivery["latitude"],
        longitude=delivery["longitude"],
        instructions=delivery.get("instructions"),
    )
    sender_contact = Contact(
        name=sender.get("name") or pickup["contact_name"],
        phone=sender.get("phone") or pickup["contact_phone"],
        email=sender.get("email"),
    )
    recipient_contact = Contact(
        name=recipient.get("name") or delivery["contact_name"],
        phone=recipient.get("phone") or delivery["contact_phone"],
        email=recipient.get("email"),
    )
    db.session.add_all(
        [pickup_address, delivery_address, sender_contact, recipient_contact]
    )
    db.session.flush()

    order = Order(
        order_number=f"PENDING-{uuid4().hex[:12].upper()}",  # replaced after flush
        consumer_id=consumer.id,
        created_by_id=consumer.id,
        business_profile_id=payload.get("business_profile_id"),
        service_type=payload.get("service_type") or domain.SERVICE_PARCEL,
        status=domain.ORDER_DRAFT,
        pickup_address_id=pickup_address.id,
        delivery_address_id=delivery_address.id,
        sender_contact_id=sender_contact.id,
        recipient_contact_id=recipient_contact.id,
        pickup_window_start=window_start,
        pickup_window_end=window_end,
        delivery_deadline=deadline,
        priority=int(payload.get("priority") or 0),
        service_notes=payload.get("service_notes"),
        special_requirements=payload.get("special_requirements"),
        business_order_reference=payload.get("business_order_reference"),
        declared_value_inr=_money(payload.get("declared_value_inr")),
        is_demo=bool(payload.get("is_demo")),
    )
    db.session.add(order)
    db.session.flush()
    order.order_number = domain.order_number(order.id)

    weight = Decimal(str(parcel_data["weight_kg"]))
    length = Decimal(str(parcel_data["length_cm"]))
    width = Decimal(str(parcel_data["width_cm"]))
    height = Decimal(str(parcel_data["height_cm"]))
    volume = (length * width * height) / Decimal("1000000")

    parcel = ParcelDetail(
        order_id=order.id,
        name=parcel_data["name"],
        description=parcel_data.get("description"),
        category=parcel_data.get("category") or "general",
        quantity=int(parcel_data.get("quantity") or 1),
        weight_kg=weight,
        length_cm=length,
        width_cm=width,
        height_cm=height,
        volume_m3=volume,
        is_fragile=bool(parcel_data.get("is_fragile")),
        handling_flags=",".join(parcel_data.get("handling_flags") or []),
        declared_value_inr=_money(parcel_data.get("declared_value_inr")),
        photo_exception_reason=parcel_data.get("photo_exception_reason"),
    )
    db.session.add(parcel)

    if order.service_type == domain.SERVICE_RETURN:
        return_data = payload.get("return_details") or {}
        db.session.add(
            ReturnRequest(
                order_id=order.id,
                product_name=return_data.get("product_name") or parcel_data["name"],
                original_order_reference=return_data.get("original_order_reference"),
                reason=return_data.get("reason") or "Customer return",
                return_authorization_reference=return_data.get(
                    "return_authorization_reference"
                ),
                merchant_name=return_data.get("merchant_name"),
                merchant_business_profile_id=return_data.get("merchant_business_profile_id"),
                destination_type=return_data.get("destination_type") or "business",
                authorization_confirmed=bool(return_data.get("authorization_confirmed")),
                approval_status=(
                    domain.RETURN_APPROVAL_PENDING
                    if return_data.get("merchant_approval_required")
                    else domain.RETURN_APPROVAL_NOT_REQUIRED
                ),
            )
        )

    record_status(
        order,
        domain.ORDER_SUBMITTED,
        actor=consumer,
        source="consumer",
        reason="Order submitted",
        event_metadata={"service_type": order.service_type},
    )
    record_status(
        order,
        domain.ORDER_PENDING_REVIEW,
        actor=None,
        source="system",
        reason="Queued for manager review",
    )
    return order


def record_status(
    order: Order,
    to_status: str,
    *,
    actor=None,
    source: str = "system",
    reason: str | None = None,
    event_metadata: dict | None = None,
) -> OrderStatusHistory:
    current = order.status
    if current != to_status and not domain.can_transition(current, to_status):
        raise ApiError(
            "invalid_status_transition",
            f"An order in '{current}' cannot move to '{to_status}'.",
            409,
            details={"from": current, "to": to_status},
        )
    if current != to_status:
        order.status = to_status
    if to_status in (domain.ORDER_DELIVERED, domain.ORDER_RETURNED):
        order.delivered_at = domain.utcnow()
    history = OrderStatusHistory(
        order_id=order.id,
        from_status=current,
        to_status=to_status,
        actor_id=getattr(actor, "id", None),
        source=source,
        reason=reason,
        event_metadata=event_metadata or {},
    )
    db.session.add(history)
    return history


def cancel_order(order: Order, actor, reason: str, *, source: str = "manager") -> Order:
    if order.status in domain.TERMINAL_ORDER_STATUSES:
        raise ApiError("order_not_cancellable", "This order is already closed.", 409)
    if order.status in domain.IN_CUSTODY_STATUSES:
        raise ApiError(
            "order_in_custody",
            "The parcel is already with a driver. Report a delivery exception instead.",
            409,
        )
    record_status(
        order,
        domain.ORDER_CANCELLED,
        actor=actor,
        source=source,
        reason=reason,
    )
    order.cancelled_at = domain.utcnow()
    order.cancelled_by_id = getattr(actor, "id", None)
    order.cancellation_reason = reason[:500]
    return order


def active_assignment(order: Order):
    from ..models import DriverAssignment

    return (
        DriverAssignment.query.filter_by(order_id=order.id, status="active")
        .order_by(DriverAssignment.assigned_at.desc())
        .first()
    )


def current_batch(order: Order):
    from ..models import BatchOrder

    link = (
        BatchOrder.query.filter_by(order_id=order.id)
        .filter(BatchOrder.removed_at.is_(None))
        .first()
    )
    return link.batch if link else None
