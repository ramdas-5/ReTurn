"""Administrator operations overview and audit feed."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..domain import ROLE_ADMIN
from ..models import AuditEvent, DeliveryBatch, DeliveryRequest, PartnerProfile, User
from ..security import role_required
from ..serializers import serialize_audit, serialize_batch
from ..services import analytics

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


@bp.get("/overview")
@role_required(ROLE_ADMIN)
def overview():
    summary = analytics.summary()
    pending_partners = (
        PartnerProfile.query.filter_by(verification_status="pending")
        .order_by(PartnerProfile.created_at.asc())
        .limit(6)
        .all()
    )
    from ..serializers import serialize_partner_profile

    recent_audit = (
        AuditEvent.query.order_by(AuditEvent.created_at.desc()).limit(12).all()
    )
    active_batches = (
        DeliveryBatch.query.filter(
            DeliveryBatch.status.in_(["proposed", "offered", "accepted", "in_progress"])
        )
        .order_by(DeliveryBatch.created_at.desc())
        .limit(6)
        .all()
    )
    return jsonify(
        {
            "data": {
                **summary,
                "pending_partners": [
                    serialize_partner_profile(profile) for profile in pending_partners
                ],
                "recent_audit": [serialize_audit(event) for event in recent_audit],
                "active_batches": [
                    serialize_batch(batch, include_stops=False, include_requests=True)
                    for batch in active_batches
                ],
            }
        }
    )


@bp.get("/audit")
@role_required(ROLE_ADMIN)
def audit_feed():
    entity_type = request.args.get("entity_type")
    query = AuditEvent.query
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    rows = query.order_by(AuditEvent.created_at.desc()).limit(100).all()
    return jsonify({"data": [serialize_audit(row) for row in rows]})


@bp.get("/queues")
@role_required(ROLE_ADMIN)
def queues():
    pending = (
        DeliveryRequest.query.filter_by(status="pending_matching")
        .order_by(DeliveryRequest.created_at.asc())
        .limit(50)
        .all()
    )
    from ..serializers import serialize_request

    return jsonify(
        {
            "data": {
                "pending_requests": [serialize_request(row, include_customer=True) for row in pending],
                "pending_partners": [
                    {
                        "user_id": profile.user_id,
                        "name": profile.user.name,
                        "company_name": profile.company_name,
                        "vehicle_type": profile.vehicle_type,
                        "verification_status": profile.verification_status,
                    }
                    for profile in PartnerProfile.query.filter_by(
                        verification_status="pending"
                    ).all()
                ],
            }
        }
    )
