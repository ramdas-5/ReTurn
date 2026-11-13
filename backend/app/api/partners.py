"""Partner profile management and admin verification."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..domain import (
    AVAILABILITY_OPTIONS,
    BATCH_COMPLETED,
    ROLE_ADMIN,
    ROLE_PARTNER,
    VEHICLE_TYPES,
    iso,
    utcnow,
)
from ..errors import ApiError
from ..extensions import db
from ..models import DeliveryBatch, PartnerProfile, User
from ..security import current_user, login_required, require_partner_profile, role_required
from ..serializers import serialize_partner_profile, serialize_user
from ..services import dispatch
from ..validation import Validator, json_body

bp = Blueprint("partners", __name__, url_prefix="/api/v1/partners")


@bp.get("/me")
@role_required(ROLE_PARTNER)
def get_me():
    user = current_user()
    profile = require_partner_profile(user)
    batches = DeliveryBatch.query.filter_by(partner_id=user.id).all()
    completed = [batch for batch in batches if batch.status == BATCH_COMPLETED]
    active = [
        batch
        for batch in batches
        if batch.status in {"offered", "accepted", "in_progress"}
    ]
    return jsonify(
        {
            "data": {
                "profile": serialize_partner_profile(profile),
                "stats": {
                    "assigned_batches": len(batches),
                    "active_batches": len(active),
                    "completed_batches": len(completed),
                    "completed_parcels": sum(
                        len([link for link in batch.request_links if link.released_at is None])
                        for batch in completed
                    ),
                },
                "updated_at": iso(profile.updated_at),
            }
        }
    )


@bp.patch("/me")
@role_required(ROLE_PARTNER)
def update_me():
    user = current_user()
    profile = require_partner_profile(user)
    data = json_body()
    v = Validator(data)
    if "company_name" in data:
        profile.company_name = v.string(
            "company_name", required=True, min_length=2, max_length=160
        )
    if "vehicle_type" in data:
        profile.vehicle_type = v.choice("vehicle_type", VEHICLE_TYPES, default=profile.vehicle_type)
    if "max_weight_kg" in data:
        profile.max_weight_kg = v.number("max_weight_kg", required=True, minimum=1, maximum=200)
    if "max_volume_m3" in data:
        profile.max_volume_m3 = v.number("max_volume_m3", required=True, minimum=0.01, maximum=5)
    if "accepts_fragile" in data:
        profile.accepts_fragile = v.boolean("accepts_fragile", profile.accepts_fragile)
    if "accepts_restricted" in data:
        profile.accepts_restricted = v.boolean("accepts_restricted", profile.accepts_restricted)
    if "availability" in data:
        profile.availability = v.choice(
            "availability", AVAILABILITY_OPTIONS, default=profile.availability
        )
    if "service_areas" in data:
        areas = data.get("service_areas")
        if isinstance(areas, str):
            areas = [item.strip() for item in areas.split(",") if item.strip()]
        if not isinstance(areas, list) or not all(isinstance(item, str) for item in areas):
            raise ApiError("validation_failed", "service_areas must be a list of area names.", 422)
        cleaned = []
        for area in areas:
            area = area.strip()
            if area and area not in cleaned:
                cleaned.append(area[:120])
        profile.service_areas = ", ".join(cleaned)
    if "operating_start_hour" in data:
        profile.operating_start_hour = v.integer(
            "operating_start_hour", minimum=0, maximum=23
        )
    if "operating_end_hour" in data:
        profile.operating_end_hour = v.integer("operating_end_hour", minimum=1, maximum=24)
    if "phone" in data:
        user.phone = v.string("phone", max_length=40) or None
    v.finish()
    if profile.operating_start_hour >= profile.operating_end_hour:
        raise ApiError(
            "validation_failed",
            "Operating end hour must be after the start hour.",
            422,
            fields={"operating_end_hour": "End must be after start."},
        )
    profile.updated_at = utcnow()
    dispatch.audit(
        user.id,
        "partner.profile_updated",
        "partner",
        profile.id,
        f"{user.name} updated vehicle, capacity or availability settings.",
    )
    db.session.commit()
    return jsonify({"data": {"profile": serialize_partner_profile(profile)}})


@bp.get("")
@role_required(ROLE_ADMIN)
def list_partners():
    status = request.args.get("verification_status")
    query = PartnerProfile.query
    if status:
        query = query.filter(PartnerProfile.verification_status == status)
    profiles = query.order_by(PartnerProfile.created_at.desc()).all()
    return jsonify({"data": [serialize_partner_profile(profile) for profile in profiles]})


@bp.patch("/<int:user_id>/verify")
@role_required(ROLE_ADMIN)
def verify(user_id: int):
    admin = current_user()
    profile = PartnerProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        raise ApiError("partner_not_found", "That delivery partner does not exist.", 404)
    data = json_body()
    v = Validator(data)
    decision = v.choice("decision", ("verified", "rejected", "pending"), required=True)
    note = v.string("note", max_length=500)
    if decision == "rejected" and not note:
        raise ApiError(
            "reason_required",
            "Add a short reason when rejecting a partner.",
            422,
            fields={"note": "Explain what needs to change."},
        )
    v.finish()
    profile.verification_status = decision
    profile.verification_note = note
    profile.verified_at = utcnow() if decision == "verified" else None
    profile.verified_by_id = admin.id if decision == "verified" else None
    dispatch.audit(
        admin.id,
        f"partner.{decision}",
        "partner",
        profile.id,
        f"Partner {profile.user.name} verification set to {decision}.",
        reason=note,
    )
    dispatch.notify(
        profile.user_id,
        "partner_verification",
        f"Verification status: {decision}",
        note or f"An administrator set your partner verification status to {decision}.",
        "/partner/profile",
    )
    db.session.commit()
    return jsonify({"data": {"profile": serialize_partner_profile(profile)}})


@bp.get("/<int:user_id>")
@role_required(ROLE_ADMIN)
def get_partner(user_id: int):
    profile = PartnerProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        raise ApiError("partner_not_found", "That delivery partner does not exist.", 404)
    return jsonify({"data": {"profile": serialize_partner_profile(profile)}})
