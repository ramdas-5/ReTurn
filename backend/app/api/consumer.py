"""Consumer dashboard summary. Every figure is counted from stored rows."""
from __future__ import annotations

from flask import Blueprint, jsonify

from .. import domain
from ..extensions import db
from ..models import Notification, Order, SavedAddress
from ..security import current_user, login_required, role_required
from ..serializers import serialize_notification, serialize_order_summary
from ..validation import Validator, json_body

bp = Blueprint("consumer", __name__, url_prefix="/api/v1/consumer")

AWAITING_REVIEW = (domain.ORDER_SUBMITTED, domain.ORDER_PENDING_REVIEW)
AWAITING_ASSIGNMENT = (domain.ORDER_AWAITING_ASSIGNMENT,)
IN_PROGRESS = (
    domain.ORDER_ASSIGNED,
    domain.ORDER_PICKUP_SCHEDULED,
    domain.ORDER_PICKUP_ARRIVED,
    domain.ORDER_PICKED_UP,
    domain.ORDER_IN_TRANSIT,
    domain.ORDER_OUT_FOR_DELIVERY,
    domain.ORDER_PROOF_PENDING,
    domain.ORDER_RETURN_IN_PROGRESS,
)


@bp.get("/summary")
@login_required
@role_required(domain.ROLE_CONSUMER)
def summary():
    user = current_user()
    base = Order.query.filter(Order.consumer_id == user.id)

    counts = {
        "total": base.count(),
        "awaiting_review": base.filter(Order.status.in_(AWAITING_REVIEW)).count(),
        "awaiting_assignment": base.filter(
            Order.status.in_(AWAITING_ASSIGNMENT)
        ).count(),
        "in_progress": base.filter(Order.status.in_(IN_PROGRESS)).count(),
        "delivered": base.filter(Order.status == domain.ORDER_DELIVERED).count(),
        "returned": base.filter(Order.status == domain.ORDER_RETURNED).count(),
        "cancelled": base.filter(Order.status == domain.ORDER_CANCELLED).count(),
        "returns": base.filter(Order.service_type == domain.SERVICE_RETURN).count(),
    }

    active = (
        base.filter(Order.status.in_(domain.ACTIVE_ORDER_STATUSES))
        .order_by(Order.created_at.desc())
        .limit(5)
        .all()
    )
    recent_orders = (
        base.order_by(Order.created_at.desc()).limit(5).all()
    )
    unread = Notification.query.filter_by(user_id=user.id, read_at=None).count()
    notifications = (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )

    return jsonify(
        {
            "data": {
                "counts": counts,
                "active_orders": [serialize_order_summary(order) for order in active],
                "recent_orders": [
                    serialize_order_summary(order) for order in recent_orders
                ],
                "notifications": {
                    "unread": unread,
                    "latest": [serialize_notification(row) for row in notifications],
                },
                "profile": {
                    "account_type": (
                        user.consumer_profile.account_type
                        if user.consumer_profile
                        else "individual"
                    ),
                    "has_business_profile": user.business_profile is not None,
                    "saved_addresses": SavedAddress.query.filter_by(
                        user_id=user.id
                    ).count(),
                },
            }
        }
    )


@bp.patch("/notification-preferences")
@login_required
@role_required(domain.ROLE_CONSUMER)
def notification_preferences():
    data = json_body()
    Validator(data).finish()
    user = current_user()
    if "notify_email" in data:
        user.notify_email = bool(data["notify_email"])
    if "notify_in_app" in data:
        user.notify_in_app = bool(data["notify_in_app"])
    db.session.commit()
    return jsonify(
        {
            "data": {
                "notify_email": user.notify_email,
                "notify_in_app": user.notify_in_app,
            }
        }
    )
