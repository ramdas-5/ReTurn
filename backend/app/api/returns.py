"""Reverse logistics: consumer return requests.

Returns are orders with `service_type='return'` plus a persisted ReturnRequest
row. They share the same state machine, tracking, proof and cancellation rules as
forward deliveries, but never assume a single central warehouse: the consumer
chooses an authorised business, warehouse or returns-centre destination.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .. import domain
from ..errors import ApiError
from ..extensions import db
from ..models import Order
from ..security import (
    current_user,
    login_required,
    rate_limit,
    require_password_changed,
    role_required,
)
from ..serializers import serialize_order_detail, serialize_order_summary
from .orders import cancel_order as cancel_order_view
from .orders import create_order_request, visible_orders_query

bp = Blueprint("returns", __name__, url_prefix="/api/v1/returns")


@bp.post("")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
@rate_limit(30, 60, scope="create-return")
def create_return():
    return create_order_request(force_service_type=domain.SERVICE_RETURN)


@bp.get("")
@login_required
@role_required(domain.ROLE_CONSUMER)
def list_returns():
    query = visible_orders_query(current_user()).filter(
        Order.service_type == domain.SERVICE_RETURN
    )
    status = request.args.get("status")
    if status:
        query = query.filter(Order.status == status)
    query = query.order_by(Order.created_at.desc())
    return jsonify(
        {"data": [serialize_order_summary(order) for order in query.limit(100).all()]}
    )


@bp.get("/<int:return_id>")
@login_required
@role_required(domain.ROLE_CONSUMER)
def get_return(return_id: int):
    order = db.session.get(Order, return_id)
    if (
        order is None
        or order.consumer_id != current_user().id
        or order.service_type != domain.SERVICE_RETURN
    ):
        raise ApiError("not_found", "That return request does not exist.", 404)
    return jsonify({"data": serialize_order_detail(order)})


@bp.post("/<int:return_id>/cancel")
@login_required
@role_required(domain.ROLE_CONSUMER)
@require_password_changed()
def cancel_return(return_id: int):
    order = db.session.get(Order, return_id)
    if (
        order is None
        or order.consumer_id != current_user().id
        or order.service_type != domain.SERVICE_RETURN
    ):
        raise ApiError("not_found", "That return request does not exist.", 404)
    return cancel_order_view(return_id)
