"""Administrator customer management endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from ..domain import ROLE_ADMIN, ROLE_CUSTOMER, iso, utcnow
from ..errors import ApiError
from ..extensions import db
from ..models import DeliveryRequest, User
from ..security import current_user, role_required
from ..serializers import serialize_user
from ..services import dispatch
from ..validation import Validator, json_body

bp = Blueprint("customers", __name__, url_prefix="/api/v1/customers")


@bp.get("")
@role_required(ROLE_ADMIN)
def list_customers():
    search = (request.args.get("q") or "").strip()
    query = User.query.filter(User.role == ROLE_CUSTOMER)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    users = query.order_by(User.created_at.desc()).limit(200).all()
    request_counts = dict(
        db.session.query(DeliveryRequest.customer_id, func.count(DeliveryRequest.id))
        .group_by(DeliveryRequest.customer_id)
        .all()
    )
    return jsonify(
        {
            "data": [
                {
                    **serialize_user(user, include_private=True),
                    "request_count": int(request_counts.get(user.id, 0)),
                }
                for user in users
            ]
        }
    )


@bp.patch("/<int:user_id>")
@role_required(ROLE_ADMIN)
def update_customer(user_id: int):
    admin = current_user()
    user = User.query.get(user_id)
    if user is None or user.role != ROLE_CUSTOMER:
        raise ApiError("customer_not_found", "That customer account does not exist.", 404)
    data = json_body()
    v = Validator(data)
    if "name" in data:
        name = v.string("name", required=True, min_length=2, max_length=120)
        if name:
            user.name = name
    if "phone" in data:
        user.phone = v.string("phone", max_length=40) or None
    disabled = None
    if "disabled" in data:
        disabled = v.boolean("disabled", user.disabled_at is not None)
    v.finish()
    if disabled is not None:
        if disabled and user.id == admin.id:
            raise ApiError("invalid_action", "You cannot disable your own account.", 422)
        user.disabled_at = utcnow() if disabled else None
        dispatch.audit(
            admin.id,
            "customer.disabled" if disabled else "customer.enabled",
            "user",
            user.id,
            f"{'Disabled' if disabled else 'Re-enabled'} customer account {user.email}.",
        )
        if disabled:
            from ..models import UserSession

            UserSession.query.filter(
                UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
            ).update({"revoked_at": utcnow()})
    db.session.commit()
    return jsonify(
        {"data": {**serialize_user(user, include_private=True), "updated_at": iso(utcnow())}}
    )
