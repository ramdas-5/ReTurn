"""In-app notification feed (the client polls this authenticated endpoint)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .. import domain
from ..errors import ApiError, paginate
from ..extensions import db
from ..models import Notification
from ..security import current_user, login_required
from ..serializers import serialize_notification
from ..validation import pagination_args

bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")


@bp.get("")
@login_required
def list_notifications():
    query = Notification.query.filter_by(user_id=current_user().id)
    if request.args.get("unread") in {"1", "true", "yes"}:
        query = query.filter(Notification.read_at.is_(None))
    query = query.order_by(Notification.created_at.desc())
    page, per_page = pagination_args()
    return paginate(query, page, per_page, serialize_notification)


@bp.get("/unread-count")
@login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=current_user().id, read_at=None
    ).count()
    return jsonify({"data": {"unread": count}})


@bp.post("/<int:notification_id>/read")
@login_required
def mark_read(notification_id: int):
    row = db.session.get(Notification, notification_id)
    if row is None or row.user_id != current_user().id:
        raise ApiError("not_found", "That notification does not exist.", 404)
    if row.read_at is None:
        row.read_at = domain.utcnow()
        db.session.commit()
    return jsonify({"data": serialize_notification(row)})


@bp.post("/read-all")
@login_required
def mark_all_read():
    now = domain.utcnow()
    updated = Notification.query.filter_by(
        user_id=current_user().id, read_at=None
    ).update({"read_at": now})
    db.session.commit()
    return jsonify({"data": {"marked_read": updated}})
