"""Issue reporting and resolution for consumers, drivers, managers and admins.

Issues are append-only reports with an audited resolution. They never silently
change an order's execution status; delivery evidence rules stay authoritative.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from .. import domain
from ..access import can_view_order, manager_covers_order
from ..errors import ApiError, paginate
from ..extensions import db
from ..models import DriverAssignment, IssueReport, Order
from ..security import current_user, login_required, rate_limit, role_required
from ..services.audit import audit
from ..services.notifications import ORDER_EXCEPTION, notify_responsible_managers
from ..validation import Validator, json_body, pagination_args

bp = Blueprint("issues", __name__, url_prefix="/api/v1/issues")

CATEGORIES = ("delivery", "parcel", "pickup", "account", "other")
SEVERITIES = ("low", "medium", "high")


def serialize_issue(row: IssueReport) -> dict:
    return {
        "id": row.id,
        "category": row.category,
        "severity": row.severity,
        "subject": row.subject,
        "description": row.description,
        "status": row.status,
        "resolution_note": row.resolution_note,
        "order_id": row.order_id,
        "order_number": row.order.order_number if row.order else None,
        "batch_id": row.batch_id,
        "reporter": (
            {"id": row.reporter.id, "full_name": row.reporter.full_name, "role": row.reporter.role}
            if row.reporter
            else None
        ),
        "resolved_by": (
            {"id": row.resolved_by.id, "full_name": row.resolved_by.full_name}
            if row.resolved_by
            else None
        ),
        "resolved_at": domain.iso(row.resolved_at),
        "created_at": domain.iso(row.created_at),
        "updated_at": domain.iso(row.updated_at),
    }


def _visible(user) -> list[IssueReport]:
    rows = IssueReport.query.order_by(IssueReport.created_at.desc()).limit(500).all()
    if user.role == domain.ROLE_ADMIN:
        return rows
    if user.role == domain.ROLE_MANAGER:
        return [
            row
            for row in rows
            if row.reporter_id == user.id
            or (row.order is not None and manager_covers_order(user, row.order))
        ]
    if user.role == domain.ROLE_CONSUMER:
        return [
            row
            for row in rows
            if row.reporter_id == user.id
            or (row.order is not None and row.order.consumer_id == user.id)
        ]
    if user.role == domain.ROLE_DRIVER:
        assigned = {
            row_.order_id
            for row_ in DriverAssignment.query.filter_by(driver_id=user.id).all()
        }
        return [row for row in rows if row.reporter_id == user.id or row.order_id in assigned]
    return []


@bp.get("")
@login_required
def list_issues():
    rows = _visible(current_user())
    status = request.args.get("status")
    if status:
        if status not in ("open", "in_review", "resolved", "rejected"):
            raise ApiError("invalid_status", "Unknown issue status.", 422)
        rows = [row for row in rows if row.status == status]
    page, per_page = pagination_args()
    start = (page - 1) * per_page
    return jsonify(
        {
            "data": [serialize_issue(row) for row in rows[start : start + per_page]],
            "meta": {"page": page, "per_page": per_page, "total": len(rows)},
        }
    )


@bp.post("")
@login_required
@role_required(domain.ROLE_CONSUMER, domain.ROLE_DRIVER)
@rate_limit(20, 60, scope="create-issue")
def create_issue():
    user = current_user()
    data = json_body()
    v = Validator(data)
    category = v.choice("category", CATEGORIES, default="other")
    severity = v.choice("severity", SEVERITIES, default="medium")
    subject = v.string("subject", required=True, min_length=4, max_length=200)
    description = v.string("description", required=True, min_length=10, max_length=1500)
    order_id = v.integer("order_id", minimum=1)
    v.finish()

    order = None
    if order_id is not None:
        order = db.session.get(Order, order_id)
        if order is None or not can_view_order(user, order):
            raise ApiError("not_found", "That order does not exist.", 404)

    row = IssueReport(
        order_id=order.id if order else None,
        reporter_id=user.id,
        category=category,
        severity=severity,
        subject=subject,
        description=description,
        status="open",
    )
    db.session.add(row)
    db.session.flush()
    audit(
        "issue.reported",
        "issue_report",
        row.id,
        actor=user,
        summary=f"Issue reported: {subject}",
        reason=description,
    )
    if order is not None:
        address = order.pickup_address
        notify_responsible_managers(
            ORDER_EXCEPTION,
            f"Issue on {order.order_number}",
            f"{severity.upper()} · {subject}",
            area_name=address.area if address else None,
            latitude=address.latitude if address else None,
            longitude=address.longitude if address else None,
            link=f"/manager/orders/{order.id}",
            event_data={"order_id": order.id, "issue_id": row.id},
        )
    db.session.commit()
    return jsonify({"data": serialize_issue(row)}), 201


@bp.patch("/<int:issue_id>")
@login_required
@role_required(domain.ROLE_MANAGER, domain.ROLE_ADMIN)
def resolve_issue(issue_id: int):
    user = current_user()
    row = db.session.get(IssueReport, issue_id)
    if row is None:
        raise ApiError("not_found", "That issue does not exist.", 404)
    if user.role == domain.ROLE_MANAGER and not (
        row.order is not None and manager_covers_order(user, row.order)
    ):
        raise ApiError("forbidden", "That issue is outside your service areas.", 403)
    data = json_body()
    v = Validator(data)
    status = v.choice("status", ("in_review", "resolved", "rejected"), required=True)
    note = v.string("resolution_note", required=True, min_length=5, max_length=1500)
    v.finish()
    row.status = status
    row.resolution_note = note
    if status in ("resolved", "rejected"):
        row.resolved_by_id = user.id
        row.resolved_at = domain.utcnow()
    audit(
        "issue.reviewed",
        "issue_report",
        row.id,
        actor=user,
        summary=f"Issue #{row.id} {status}",
        reason=note,
    )
    db.session.commit()
    return jsonify({"data": serialize_issue(row)})
