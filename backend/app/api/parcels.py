"""Parcel-level tracking and status updates."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..access import assert_request_access, batch_contacts_allowed
from ..domain import PARCEL_EVENT_TYPES, PARCEL_TRANSITIONS, ROLE_ADMIN, ROLE_PARTNER, iso
from ..errors import ApiError
from ..models import Parcel, TrackingEvent
from ..security import current_user, login_required, rate_limit, role_required
from ..serializers import serialize_parcel, serialize_tracking_event
from ..services import dispatch
from ..validation import Validator, json_body

bp = Blueprint("parcels", __name__, url_prefix="/api/v1/parcels")


def _parcel_or_404(parcel_id: int) -> Parcel:
    parcel = Parcel.query.get(parcel_id)
    if parcel is None:
        raise ApiError("parcel_not_found", "That parcel does not exist.", 404)
    return parcel


@bp.get("/<int:parcel_id>/tracking")
@login_required
def tracking(parcel_id: int):
    user = current_user()
    parcel = _parcel_or_404(parcel_id)
    assert_request_access(user, parcel.request)
    events = (
        TrackingEvent.query.filter_by(parcel_id=parcel.id)
        .order_by(TrackingEvent.created_at.asc(), TrackingEvent.id.asc())
        .all()
    )
    return jsonify(
        {
            "data": {
                "parcel": serialize_parcel(parcel),
                "allowed_next": list(PARCEL_TRANSITIONS.get(parcel.status, ())),
                "events": [serialize_tracking_event(event) for event in events],
                "updated_at": iso(parcel.updated_at),
            }
        }
    )


@bp.post("/<int:parcel_id>/events")
@role_required(ROLE_PARTNER, ROLE_ADMIN)
@rate_limit(120, 60, scope="parcel_event")
def create_event(parcel_id: int):
    user = current_user()
    data = json_body()
    v = Validator(data)
    event_type = v.choice("event_type", PARCEL_EVENT_TYPES, required=True)
    notes = v.string("notes", max_length=500)
    v.finish()
    parcel, batch = dispatch.update_parcel_status(user, parcel_id, event_type, notes)
    payload = serialize_parcel(parcel, include_events=True)
    payload["batch"] = {
        "id": batch.id,
        "status": batch.status,
        "completed_at": iso(batch.completed_at),
    }
    return jsonify({"data": payload})
