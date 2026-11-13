"""In-app notifications for the signed-in user."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..domain import iso, utcnow
from ..errors import ApiError
from ..extensions import db
from ..models import Notification
from ..security import current_user, login_required
from ..serializers import serialize_notification

bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")


@bp.get("")
@login_required
def list_notifications():
    user = current_user()
    limit = min(max(int(request.args.get("limit", "20")), 1), 50)
    query = Notification.query.filter_by(user_id=user.id)
    unread_only = request.args.get("unread") in {"1", "true"}
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    rows = query.order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count = Notification.query.filter(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    ).count()
    return jsonify(
        {
            "data": [serialize_notification(row) for row in rows],
            "meta": {"unread_count": unread_count},
        }
    )


@bp.patch("/<int:notification_id>")
@login_required
def mark_read(notification_id: int):
    user = current_user()
    notification = Notification.query.get(notification_id)
    if notification is None or notification.user_id != user.id:
        raise ApiError("notification_not_found", "That notification does not exist.", 404)
    if notification.read_at is None:
        notification.read_at = utcnow()
        db.session.commit()
    return jsonify(
        {
            "data": {
                "notification": serialize_notification(notification),
                "read_at": iso(notification.read_at),
            }
        }
    )


@bp.post("/read-all")
@login_required
def mark_all_read():
    user = current_user()
    updated = Notification.query.filter(
        Notification.user_id == user.id, Notification.read_at.is_(None)
    ).update({"read_at": utcnow()})
    db.session.commit()
    return jsonify({"data": {"marked_read": int(updated)}})
