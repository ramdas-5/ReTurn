"""Batch listing, detail, dispatch and execution endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request as http_request

from ..access import (
    assert_batch_access,
    batch_contacts_allowed,
    can_access_batch,
)
from ..domain import (
    ACTIVE_BATCH_STATUSES,
    ROLE_ADMIN,
    ROLE_PARTNER,
    iso,
)
from ..errors import ApiError
from ..models import BatchRequest, DeliveryBatch
from ..security import current_user, login_required, role_required
from ..serializers import (
    batch_code,
    serialize_batch,
    serialize_batch_for_customer,
    serialize_request,
)
from ..services import dispatch, matching
from ..validation import Validator, json_body

bp = Blueprint("batches", __name__, url_prefix="/api/v1/batches")


def _batch_out(batch: DeliveryBatch, user) -> dict:
    if user.role == ROLE_ADMIN:
        return serialize_batch(batch, include_contacts=True)
    if user.role == ROLE_PARTNER:
        payload = serialize_batch(
            batch, include_contacts=batch_contacts_allowed(user, batch)
        )
        eligible, reason = matching.partner_eligible_for_batch(batch, user.partner_profile)
        payload["eligibility"] = {
            "eligible": eligible,
            "reason": reason,
            "offered_to_me": batch.partner_id == user.id and batch.status == "offered",
            "can_accept": eligible and batch.status == "offered" and batch.partner_id == user.id,
        }
        return payload
    own_requests = [
        link.request
        for link in batch.request_links
        if link.released_at is None and link.request.customer_id == user.id
    ]
    if not own_requests:
        raise ApiError("forbidden", "You do not have access to that batch.", 403)
    return {
        "batch": serialize_batch_for_customer(batch, own_requests[0].id),
        "requests": [
            serialize_request(request, include_contact=True, include_batch=False)
            for request in own_requests
        ],
    }


@bp.get("")
@login_required
def list_batches():
    user = current_user()
    query = DeliveryBatch.query
    status_param = http_request.args.get("status")
    statuses = [item.strip() for item in (status_param or "").split(",") if item.strip()]
    if statuses:
        query = query.filter(DeliveryBatch.status.in_(statuses))
    scope = http_request.args.get("scope", "")

    if user.role == ROLE_ADMIN:
        query = query.order_by(DeliveryBatch.created_at.desc())
        rows = query.limit(200).all()
        return jsonify(
            {
                "data": [
                    {
                        **serialize_batch(row, include_stops=False, include_requests=False),
                        "request_count": len(
                            [link for link in row.request_links if link.released_at is None]
                        ),
                    }
                    for row in rows
                ]
            }
        )

    if user.role == ROLE_PARTNER:
        profile = user.partner_profile
        if profile is None:
            raise ApiError("partner_profile_missing", "Complete your partner profile first.", 409)
        if scope == "opportunities":
            offered = query.filter(
                DeliveryBatch.partner_id == user.id,
                DeliveryBatch.status == "offered",
            ).all()
            proposed = (
                DeliveryBatch.query.filter(
                    DeliveryBatch.status == "proposed", DeliveryBatch.partner_id.is_(None)
                )
                .order_by(DeliveryBatch.created_at.desc())
                .limit(40)
                .all()
            )
            rows = offered + [row for row in proposed if can_access_batch(user, row)]
            rows.sort(key=lambda row: row.created_at, reverse=True)
            return jsonify({"data": [_batch_out(row, user) for row in rows]})
        query = query.filter(DeliveryBatch.partner_id == user.id).order_by(
            DeliveryBatch.created_at.desc()
        )
        rows = query.limit(200).all()
        return jsonify({"data": [_batch_out(row, user) for row in rows]})

    # Customer: only batches containing their own requests, restricted payload.
    links = BatchRequest.query.filter(BatchRequest.released_at.is_(None)).all()
    own_batch_ids = sorted(
        {
            link.batch_id
            for link in links
            if link.request is not None and link.request.customer_id == user.id
        }
    )
    rows = (
        DeliveryBatch.query.filter(DeliveryBatch.id.in_(own_batch_ids or [0]))
        .order_by(DeliveryBatch.created_at.desc())
        .all()
    )
    data = []
    for row in rows:
        own = [
            link.request
            for link in row.request_links
            if link.released_at is None and link.request.customer_id == user.id
        ]
        if not own:
            continue
        data.append(serialize_batch_for_customer(row, own[0].id))
    return jsonify({"data": data})


@bp.get("/<int:batch_id>")
@login_required
def get_batch(batch_id: int):
    user = current_user()
    batch = DeliveryBatch.query.get(batch_id)
    if batch is None:
        raise ApiError("batch_not_found", "That batch does not exist.", 404)
    assert_batch_access(user, batch)
    return jsonify({"data": _batch_out(batch, user)})


@bp.post("/<int:batch_id>/offer")
@role_required(ROLE_ADMIN)
def offer(batch_id: int):
    data = json_body()
    v = Validator(data)
    partner_id = v.integer("partner_id", required=True, minimum=1)
    note = v.string("note", max_length=500)
    v.finish()
    batch = dispatch.offer_batch(current_user(), batch_id, partner_id, note)
    return jsonify({"data": serialize_batch(batch, include_contacts=True)})


@bp.post("/<int:batch_id>/decision")
@role_required(ROLE_PARTNER)
def decision(batch_id: int):
    data = json_body()
    v = Validator(data)
    choice = v.choice("decision", ("accept", "decline"), required=True)
    reason = v.string("reason", max_length=500)
    v.finish()
    batch = dispatch.decide_offer(current_user(), batch_id, choice, reason)
    return jsonify({"data": serialize_batch(batch, include_contacts=True)})


@bp.post("/<int:batch_id>/reassign")
@role_required(ROLE_ADMIN)
def reassign(batch_id: int):
    data = json_body()
    v = Validator(data)
    partner_id = v.integer("partner_id", required=True, minimum=1)
    reason = v.string("reason", required=True, min_length=5, max_length=500)
    v.finish()
    batch = dispatch.reassign_batch(current_user(), batch_id, partner_id, reason)
    return jsonify({"data": serialize_batch(batch, include_contacts=True)})


@bp.post("/<int:batch_id>/cancel")
@role_required(ROLE_ADMIN)
def cancel(batch_id: int):
    data = json_body()
    v = Validator(data)
    reason = v.string("reason", required=True, min_length=5, max_length=500)
    v.finish()
    batch = dispatch.cancel_batch(current_user(), batch_id, reason)
    return jsonify({"data": serialize_batch(batch, include_contacts=True)})


@bp.post("/<int:batch_id>/start")
@login_required
def start(batch_id: int):
    user = current_user()
    if user.role not in (ROLE_PARTNER, ROLE_ADMIN):
        raise ApiError("forbidden", "Only the assigned partner can start a route.", 403)
    batch = dispatch.start_batch(user, batch_id)
    return jsonify({"data": serialize_batch(batch, include_contacts=batch_contacts_allowed(user, batch))})


@bp.get("/<int:batch_id>/route")
@login_required
def route(batch_id: int):
    user = current_user()
    batch = DeliveryBatch.query.get(batch_id)
    if batch is None:
        raise ApiError("batch_not_found", "That batch does not exist.", 404)
    assert_batch_access(user, batch)
    payload = _batch_out(batch, user)
    if user.role == ROLE_PARTNER:
        payload["partner_profile"] = {
            "vehicle_type": user.partner_profile.vehicle_type
            if user.partner_profile
            else None,
            "max_weight_kg": float(user.partner_profile.max_weight_kg)
            if user.partner_profile
            else None,
        }
    return jsonify({"data": payload})


@bp.get("/<int:batch_id>/timeline")
@role_required(ROLE_ADMIN)
def timeline(batch_id: int):
    from ..models import AuditEvent
    from ..serializers import serialize_audit

    batch = DeliveryBatch.query.get(batch_id)
    if batch is None:
        raise ApiError("batch_not_found", "That batch does not exist.", 404)
    events = (
        AuditEvent.query.filter_by(entity_type="batch", entity_id=batch.id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )
    return jsonify(
        {
            "data": {
                "batch": serialize_batch(batch, include_contacts=True),
                "audit": [serialize_audit(event) for event in events],
                "updated_at": iso(batch.updated_at),
            }
        }
    )
