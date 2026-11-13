"""Admin matching preview and commit endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..domain import ROLE_ADMIN, iso
from ..errors import ApiError
from ..models import MatchingRun, PartnerProfile
from ..security import current_user, rate_limit, role_required
from ..serializers import serialize_batch, serialize_user
from ..services import matching
from ..services.dispatch import commit_batch
from ..validation import Validator, json_body

bp = Blueprint("matching", __name__, url_prefix="/api/v1/matching")


def _params_from(data: dict) -> dict:
    v = Validator(data)
    params = {}
    if data.get("params") is not None:
        raw = data["params"]
        if not isinstance(raw, dict):
            raise ApiError("validation_failed", "params must be an object.", 422)
        pv = Validator(raw)
        for key in (
            "max_group_size",
            "max_pickup_radius_km",
            "max_detour_km",
            "min_savings_pct",
            "service_minutes",
            "avg_speed_kmh",
            "road_factor",
        ):
            if key in raw:
                if key in {"max_group_size", "service_minutes"}:
                    params[key] = pv.integer(key, minimum=1, maximum=10)
                else:
                    params[key] = pv.number(key, minimum=0.1, maximum=500)
        pv.finish()
    return {key: value for key, value in params.items() if value is not None}


@bp.post("/preview")
@role_required(ROLE_ADMIN)
@rate_limit(12, 60, scope="matching_preview")
def preview():
    data = json_body()
    request_ids = None
    if data.get("request_ids") is not None:
        raw = data["request_ids"]
        if not isinstance(raw, list) or not raw:
            raise ApiError("validation_failed", "request_ids must be a non-empty list.", 422)
        try:
            request_ids = [int(item) for item in raw]
        except (TypeError, ValueError):
            raise ApiError("validation_failed", "request_ids must be integers.", 422)
    params = _params_from(data)
    result = matching.preview_matching(
        request_ids=request_ids, params=params, actor_id=current_user().id
    )
    return jsonify({"data": result})


@bp.post("/commit")
@role_required(ROLE_ADMIN)
@rate_limit(10, 60, scope="matching_commit")
def commit():
    data = json_body()
    v = Validator(data)
    raw_ids = data.get("request_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise ApiError("validation_failed", "Select at least one request.", 422)
    try:
        request_ids = [int(item) for item in raw_ids]
    except (TypeError, ValueError):
        raise ApiError("validation_failed", "request_ids must be integers.", 422)
    partner_id = v.integer("partner_id", minimum=1)
    preview_run_id = v.integer("preview_run_id", minimum=1)
    note = v.string("note", max_length=500)
    params = _params_from(data)
    v.finish()
    batch = commit_batch(
        current_user(),
        request_ids,
        partner_id=partner_id,
        params=params,
        preview_run_id=preview_run_id,
        note=note,
    )
    return (
        jsonify({"data": serialize_batch(batch, include_contacts=True)}),
        201,
    )


@bp.get("/runs")
@role_required(ROLE_ADMIN)
def runs():
    rows = MatchingRun.query.order_by(MatchingRun.created_at.desc()).limit(30).all()
    return jsonify(
        {
            "data": [
                {
                    "id": run.id,
                    "actor": serialize_user(run.actor) if run.actor else None,
                    "created_at": iso(run.created_at),
                    "params": run.params,
                    "group_count": len((run.result or {}).get("groups", [])),
                    "pending_count": (run.result or {}).get("pending_count", 0),
                    "distance_source": (run.result or {}).get("distance_source"),
                }
                for run in rows
            ]
        }
    )


@bp.get("/runs/<int:run_id>")
@role_required(ROLE_ADMIN)
def run_detail(run_id: int):
    run = MatchingRun.query.get(run_id)
    if run is None:
        raise ApiError("run_not_found", "That matching run does not exist.", 404)
    return jsonify(
        {
            "data": {
                "id": run.id,
                "created_at": iso(run.created_at),
                "params": run.params,
                "result": run.result,
                "actor": serialize_user(run.actor) if run.actor else None,
            }
        }
    )


@bp.get("/eligible-partners")
@role_required(ROLE_ADMIN)
def eligible_partners():
    from ..serializers import serialize_partner_profile

    profiles = PartnerProfile.query.order_by(PartnerProfile.verification_status.asc()).all()
    return jsonify({"data": [serialize_partner_profile(profile) for profile in profiles]})
