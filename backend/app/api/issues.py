"""Issue reporting and resolution."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..access import assert_request_access, partner_user_id_for_request
from ..domain import (
    ISSUE_CATEGORIES,
    ISSUE_OPEN,
    ISSUE_SEVERITIES,
    ISSUE_STATUSES,
    ROLE_ADMIN,
    ROLE_CUSTOMER,
    ROLE_PARTNER,
    iso,
    utcnow,
)
from ..errors import ApiError
from ..extensions import db
from ..models import BatchRequest, DeliveryBatch, DeliveryRequest, IssueReport
from ..security import current_user, login_required, role_required
from ..serializers import serialize_issue
from ..services import dispatch
from ..validation import Validator, json_body

bp = Blueprint("issues", __name__, url_prefix="/api/v1/issues")


@bp.get("")
@login_required
def list_issues():
    user = current_user()
    query = IssueReport.query
    if user.role == ROLE_ADMIN:
        pass
    elif user.role == ROLE_CUSTOMER:
        request_ids = [
            row[0]
            for row in db.session.query(DeliveryRequest.id)
            .filter(DeliveryRequest.customer_id == user.id)
            .all()
        ]
        query = query.filter(
            or_(
                IssueReport.reporter_id == user.id,
                IssueReport.request_id.in_(request_ids or [0]),
            )
        )
    elif user.role == ROLE_PARTNER:
        batch_ids = [
            row[0]
            for row in db.session.query(DeliveryBatch.id)
            .filter(DeliveryBatch.partner_id == user.id)
            .all()
        ]
        query = query.filter(
            or_(
                IssueReport.reporter_id == user.id,
                IssueReport.batch_id.in_(batch_ids or [0]),
            )
        )
    status = request.args.get("status")
    if status in ISSUE_STATUSES:
        query = query.filter(IssueReport.status == status)
    severity = request.args.get("severity")
    if severity in ISSUE_SEVERITIES:
        query = query.filter(IssueReport.severity == severity)
    rows = query.order_by(IssueReport.created_at.desc()).limit(200).all()
    return jsonify(
        {
            "data": [
                serialize_issue(row, include_contacts=user.role == ROLE_ADMIN)
                for row in rows
            ]
        }
    )


@bp.post("")
@login_required
def create_issue():
    user = current_user()
    data = json_body()
    v = Validator(data)
    request_id = v.integer("request_id", required=True, minimum=1)
    category = v.choice("category", ISSUE_CATEGORIES, required=True, default="other")
    severity = v.choice("severity", ISSUE_SEVERITIES, required=True, default="medium")
    description = v.string("description", required=True, min_length=10, max_length=1500)
    v.finish()

    delivery_request = DeliveryRequest.query.get(request_id)
    if delivery_request is None:
        raise ApiError("request_not_found", "That request does not exist.", 404)
    assert_request_access(user, delivery_request)
    link = BatchRequest.query.filter(
        BatchRequest.request_id == delivery_request.id, BatchRequest.released_at.is_(None)
    ).first()
    batch_id = link.batch_id if link else None
    issue = IssueReport(
        request_id=delivery_request.id,
        batch_id=batch_id,
        reporter_id=user.id,
        category=category,
        severity=severity,
        description=description,
        status=ISSUE_OPEN,
    )
    db.session.add(issue)
    dispatch.notify_admins(
        "issue_created",
        "New issue reported",
        f"{delivery_request.code}: {description[:140]}",
        "/admin/issues",
    )
    if user.role == ROLE_CUSTOMER and batch_id:
        partner_id = partner_user_id_for_request(delivery_request)
        if partner_id:
            dispatch.notify(
                partner_id,
                "issue_created",
                "Customer reported an issue",
                f"{delivery_request.code}: {description[:140]}",
                f"/partner/batches/{batch_id}",
            )
    dispatch.audit(
        user.id,
        "issue.created",
        "issue",
        None,
        f"Issue reported on {delivery_request.code}.",
        reason=description[:300],
    )
    db.session.commit()
    return jsonify({"data": serialize_issue(issue)}), 201


@bp.patch("/<int:issue_id>")
@role_required(ROLE_ADMIN)
def resolve_issue(issue_id: int):
    admin = current_user()
    issue = IssueReport.query.get(issue_id)
    if issue is None:
        raise ApiError("issue_not_found", "That issue does not exist.", 404)
    data = json_body()
    v = Validator(data)
    status = v.choice("status", ISSUE_STATUSES, required=True)
    note = v.string("resolution_note", max_length=1000)
    v.finish()
    if status == "resolved" and not note:
        raise ApiError(
            "reason_required",
            "Add a resolution note before closing an issue.",
            422,
            fields={"resolution_note": "Describe how the issue was resolved."},
        )
    issue.status = status
    if status == "resolved":
        issue.resolution_note = note
        issue.resolved_by_id = admin.id
        issue.resolved_at = utcnow()
    else:
        issue.resolution_note = note or issue.resolution_note
        issue.resolved_at = None
        issue.resolved_by_id = None
    dispatch.audit(
        admin.id,
        "issue.resolved" if status == "resolved" else "issue.updated",
        "issue",
        issue.id,
        f"Issue #{issue.id} set to {status}.",
        reason=note,
    )
    if issue.reporter_id:
        dispatch.notify(
            issue.reporter_id,
            "issue_updated",
            f"Issue update: {status.replace('_', ' ')}",
            note or "An administrator updated your reported issue.",
            f"/customer/requests/{issue.request_id}" if issue.request_id else None,
        )
    db.session.commit()
    return jsonify(
        {
            "data": {
                **serialize_issue(issue, include_contacts=True),
                "updated_at": iso(issue.updated_at),
            }
        }
    )
