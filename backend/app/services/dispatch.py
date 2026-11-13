"""Notifications, audits and the dispatch/execution command service."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app

from ..domain import (
    ASSIGNMENT_ACCEPTED,
    ASSIGNMENT_DECLINED,
    ASSIGNMENT_OFFERED,
    ASSIGNMENT_REASSIGNED,
    ASSIGNMENT_REVOKED,
    BATCH_ACCEPTED,
    BATCH_COMPLETED,
    BATCH_DECLINED,
    BATCH_IN_PROGRESS,
    BATCH_OFFERED,
    BATCH_PROPOSED,
    BATCH_CANCELLED,
    PARCEL_ASSIGNED,
    PARCEL_DELIVERED,
    PARCEL_FAILED,
    PARCEL_IN_TRANSIT,
    PARCEL_PARTNER_ACCEPTED,
    PARCEL_PENDING,
    PARCEL_PICKED_UP,
    PARCEL_PICKUP_ARRIVED,
    PARCEL_TERMINAL_STATUSES,
    PARTNER_VERIFIED,
    REQUEST_ASSIGNED,
    REQUEST_BATCHED,
    REQUEST_CANCELLED,
    REQUEST_COMPLETED,
    REQUEST_FAILED,
    REQUEST_IN_PROGRESS,
    REQUEST_PENDING,
    ROLE_ADMIN,
    ROLE_PARTNER,
    can_transition_parcel,
    iso,
    parcel_code,
    request_code,
    utcnow,
)
from ..errors import ApiError
from ..extensions import db
from ..models import (
    AuditEvent,
    BatchAssignment,
    BatchRequest,
    BatchStop,
    DeliveryBatch,
    DeliveryRequest,
    IssueReport,
    Notification,
    PartnerProfile,
    TrackingEvent,
    User,
)
from ..serializers import serialize_batch
from . import matching, routing


# --------------------------------------------------------------------- helpers
def parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def notify(user_id: int, notification_type: str, title: str, body: str, link: str | None = None):
    db.session.add(
        Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            body=body,
            link=link,
        )
    )


def notify_request_customer(request: DeliveryRequest, notification_type: str, title: str, body: str):
    notify(
        request.customer_id,
        notification_type,
        title,
        body,
        link=f"/customer/requests/{request.id}",
    )


def notify_admins(notification_type: str, title: str, body: str, link: str | None = None):
    admins = User.query.filter(User.role == ROLE_ADMIN, User.disabled_at.is_(None)).all()
    for admin in admins:
        notify(admin.id, notification_type, title, body, link)


def audit(
    actor_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    summary: str,
    *,
    reason: str | None = None,
    metadata: dict | None = None,
):
    db.session.add(
        AuditEvent(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            summary=summary,
            reason=reason,
            event_metadata=metadata or {},
        )
    )


def active_link_for_request(request_id: int) -> BatchRequest | None:
    return BatchRequest.query.filter(
        BatchRequest.request_id == request_id, BatchRequest.released_at.is_(None)
    ).first()


def batch_for_request(request: DeliveryRequest) -> DeliveryBatch | None:
    link = active_link_for_request(request.id)
    return link.batch if link else None


def _batch_or_404(batch_id: int, *, lock: bool = False) -> DeliveryBatch:
    query = DeliveryBatch.query
    if lock:
        query = query.with_for_update()
    batch = query.filter(DeliveryBatch.id == batch_id).first()
    if batch is None:
        raise ApiError("batch_not_found", "That batch does not exist.", 404)
    return batch


def _partner_profile_for(user_id: int) -> PartnerProfile:
    profile = PartnerProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        raise ApiError("partner_not_found", "No delivery partner profile exists for that account.", 404)
    return profile


def _assert_partner_user(user: User) -> PartnerProfile:
    if user.role != ROLE_PARTNER:
        raise ApiError("forbidden", "Only delivery partners can perform this action.", 403)
    return _partner_profile_for(user.id)


def _release_reservations(batch: DeliveryBatch, reason: str):
    now = utcnow()
    for link in batch.request_links:
        if link.released_at is None:
            link.released_at = now
            request = link.request
            if request.status in {REQUEST_BATCHED, REQUEST_ASSIGNED}:
                request.status = REQUEST_PENDING
                request.updated_at = now
                if request.parcel and request.parcel.status not in PARCEL_TERMINAL_STATUSES:
                    request.parcel.status = PARCEL_PENDING
    for stop in batch.stops:
        if stop.status in {"pending", "arrived"}:
            stop.status = "skipped"
    batch.status = BATCH_CANCELLED
    batch.cancelled_reason = reason
    batch.updated_at = now


def _verify_partner_for_group(profile: PartnerProfile, requests: list[DeliveryRequest]):
    if profile.verification_status != PARTNER_VERIFIED:
        raise ApiError(
            "partner_not_verified",
            "Only verified partners can be assigned batches.",
            409,
        )
    if profile.availability != "available":
        raise ApiError(
            "partner_unavailable",
            "That partner is not currently available for new batches.",
            409,
        )
    flags = {
        flag
        for request in requests
        if request.parcel
        for flag in (request.parcel.handling_flags or "").split(",")
        if flag
    }
    if "fragile" in flags and not profile.accepts_fragile:
        raise ApiError("handling_incompatible", "Partner vehicle does not accept fragile parcels.", 409)
    if "restricted" in flags and not profile.accepts_restricted:
        raise ApiError("handling_incompatible", "Partner is not authorised for restricted items.", 409)
    areas = set()
    for request in requests:
        for location in (request.pickup_location, request.destination_location):
            if location and location.area:
                areas.add(location.area)
    if profile.service_area_list and not areas.issubset(set(profile.service_area_list)):
        missing = sorted(areas - set(profile.service_area_list))
        raise ApiError(
            "service_area",
            f"Partner does not operate in: {', '.join(missing)}.",
            409,
        )


# ------------------------------------------------------------------ commit batch
def commit_batch(
    actor: User,
    request_ids: list[int],
    *,
    partner_id: int | None = None,
    params: dict | None = None,
    preview_run_id: int | None = None,
    note: str | None = None,
) -> DeliveryBatch:
    profile = None
    if partner_id is not None:
        profile = _partner_profile_for(partner_id)
        if profile.user is None or profile.user.role != ROLE_PARTNER:
            raise ApiError("partner_not_found", "That account is not a delivery partner.", 404)

    try:
        group, matrix = matching.quote_selected_requests(
            request_ids, partner_profile=profile, params=params
        )
    except matching.InfeasibleGroup as exc:
        raise ApiError(
            "infeasible_group",
            exc.message,
            409,
            details={"reason_code": exc.reason, **exc.details},
        ) from exc

    if profile is not None:
        requests = DeliveryRequest.query.filter(DeliveryRequest.id.in_(request_ids)).all()
        _verify_partner_for_group(profile, requests)

    # Lock the selected requests to prevent concurrent double booking.
    locked = (
        DeliveryRequest.query.filter(DeliveryRequest.id.in_(request_ids))
        .with_for_update()
        .order_by(DeliveryRequest.id)
        .all()
    )
    if len(locked) != len(set(request_ids)):
        raise ApiError("not_pending", "One or more selected requests no longer exist.", 409)
    for request in locked:
        if request.status != REQUEST_PENDING:
            raise ApiError(
                "request_already_batched",
                f"{request_code(request.id)} was claimed by another batch. Refresh the queue.",
                409,
            )
        if active_link_for_request(request.id) is not None:
            raise ApiError(
                "request_already_batched",
                f"{request_code(request.id)} already has an active reservation.",
                409,
            )

    status = BATCH_OFFERED if profile else BATCH_PROPOSED
    batch = DeliveryBatch(
        status=status,
        partner_id=profile.user_id if profile else None,
        matching_run_id=preview_run_id,
        created_by_id=actor.id,
        distance_km=group["distance_km"],
        duration_minutes=group["duration_minutes"],
        baseline_km=group["baseline_km"],
        savings_km=group["savings_km"],
        savings_percent=group["savings_percent"],
        distance_source=group["distance_source"],
        geometry_source="estimated",
        route_method="Pickup-and-delivery insertion heuristic (rule-based)",
        explanation={
            "included_reasons": group["included_reasons"],
            "distance_source_label": group["distance_source_label"],
            "routing_notes": group["routing_notes"],
            "detour_km": group["detour_km"],
            "minimum_savings_pct": group["minimum_savings_pct"],
            "note": note,
        },
        assumptions=group["assumptions"],
        load_profile=group["load_profile"],
        offered_at=utcnow() if profile else None,
    )
    db.session.add(batch)
    db.session.flush()

    stop_locations = []
    for index, stop in enumerate(group["stops"], start=1):
        db.session.add(
            BatchStop(
                batch_id=batch.id,
                request_id=stop["request_id"],
                kind=stop["kind"],
                sequence=index,
                location_id=stop["location_id"],
                planned_arrival=parse_iso(stop["arrival"]),
                planned_departure=parse_iso(stop["departure"]),
                service_minutes=int(group["service_minutes"]),
                leg_distance_km=stop["leg_distance_km"],
                leg_duration_minutes=int(round(stop["leg_duration_minutes"])),
                load_weight_kg=stop["load_weight_kg"],
                load_volume_m3=stop["load_volume_m3"],
            )
        )
        stop_locations.append(stop["location"])

    for request in locked:
        db.session.add(BatchRequest(batch_id=batch.id, request_id=request.id))
        request.status = REQUEST_BATCHED
        request.updated_at = utcnow()

    settings = matching.settings_from_params(params)
    geometry, geometry_source = routing.route_geometry(
        [
            {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
            }
            for location in stop_locations
        ],
        settings,
    )
    batch.geometry = geometry
    batch.geometry_source = geometry_source

    if profile is not None:
        db.session.add(
            BatchAssignment(
                batch_id=batch.id,
                partner_id=profile.user_id,
                actor_id=actor.id,
                action=ASSIGNMENT_OFFERED,
                reason=note,
            )
        )
        notify(
            profile.user_id,
            "batch_offered",
            f"New batch offer {batch.code}",
            f"{len(locked)} parcels with an estimated {float(batch.savings_km):.1f} km saving. Review and accept or decline.",
            f"/partner/batches/{batch.id}",
        )
    for request in locked:
        notify_request_customer(
            request,
            "batch_proposed",
            "Your request is in a proposed shared batch",
            f"{request_code(request.id)} is reserved in {batch.code}. "
            + ("The batch has been offered to a verified partner." if profile else "Dispatch will offer it to a verified partner."),
        )
    audit(
        actor.id,
        "batch.created",
        "batch",
        batch.id,
        f"Created {batch.code} with {len(locked)} request(s), estimated {float(batch.savings_percent):.1f}% saving.",
        metadata={
            "request_ids": [request.id for request in locked],
            "partner_id": profile.user_id if profile else None,
            "distance_source": group["distance_source"],
        },
    )
    if profile is not None:
        audit(
            actor.id,
            "batch.offered",
            "batch",
            batch.id,
            f"Offered {batch.code} to {profile.user.name}.",
            reason=note,
        )
    try:
        db.session.commit()
    except Exception as exc:  # unique active-reservation index
        db.session.rollback()
        raise ApiError(
            "request_already_batched",
            "A selected request was claimed by another batch. Refresh and try again.",
            409,
        ) from exc
    return batch


# ----------------------------------------------------------------------- offers
def offer_batch(actor: User, batch_id: int, partner_id: int, note: str | None = None) -> DeliveryBatch:
    batch = _batch_or_404(batch_id, lock=True)
    if batch.status not in {BATCH_PROPOSED, BATCH_DECLINED}:
        raise ApiError(
            "invalid_batch_state",
            "Only proposed or declined batches can be offered. Use reassignment for active batches.",
            409,
        )
    profile = _partner_profile_for(partner_id)
    eligible, reason = matching.partner_eligible_for_batch(batch, profile)
    if not eligible:
        raise ApiError("partner_ineligible", reason or "Partner is not eligible.", 409)

    batch.status = BATCH_OFFERED
    batch.partner_id = profile.user_id
    batch.offered_at = utcnow()
    batch.declined_reason = None
    batch.version += 1
    db.session.add(
        BatchAssignment(
            batch_id=batch.id,
            partner_id=profile.user_id,
            actor_id=actor.id,
            action=ASSIGNMENT_OFFERED,
            reason=note,
        )
    )
    notify(
        profile.user_id,
        "batch_offered",
        f"New batch offer {batch.code}",
        f"Review {len(batch.stops)} stops and accept or decline.",
        f"/partner/batches/{batch.id}",
    )
    for link in batch.request_links:
        if link.released_at is None:
            notify_request_customer(
                link.request,
                "batch_offered",
                "A partner has been offered your shared batch",
                f"{batch.code} is awaiting partner acceptance.",
            )
    audit(
        actor.id,
        "batch.offered",
        "batch",
        batch.id,
        f"Offered {batch.code} to {profile.user.name}.",
        reason=note,
    )
    db.session.commit()
    return batch


def decide_offer(user: User, batch_id: int, decision: str, reason: str | None = None) -> DeliveryBatch:
    profile = _assert_partner_user(user)
    batch = _batch_or_404(batch_id, lock=True)
    if batch.status != BATCH_OFFERED or batch.partner_id != user.id:
        raise ApiError(
            "invalid_batch_state",
            "This offer is not awaiting your decision.",
            409,
        )
    if decision == "accept":
        if profile.verification_status != PARTNER_VERIFIED:
            raise ApiError("partner_not_verified", "Your account is not verified yet.", 403)
        if profile.availability != "available":
            raise ApiError("partner_unavailable", "Set your availability to available first.", 409)
        eligible, eligibility_reason = matching.partner_eligible_for_batch(batch, profile)
        if not eligible:
            raise ApiError("partner_ineligible", eligibility_reason or "Batch no longer fits your vehicle.", 409)
        batch.status = BATCH_ACCEPTED
        batch.accepted_at = utcnow()
        batch.version += 1
        db.session.add(
            BatchAssignment(
                batch_id=batch.id,
                partner_id=user.id,
                actor_id=user.id,
                action=ASSIGNMENT_ACCEPTED,
            )
        )
        for link in batch.request_links:
            if link.released_at is not None:
                continue
            request = link.request
            request.status = REQUEST_ASSIGNED
            request.updated_at = utcnow()
            if request.parcel and request.parcel.status == PARCEL_PENDING:
                request.parcel.status = PARCEL_PARTNER_ACCEPTED
                request.parcel.updated_at = utcnow()
                db.session.add(
                    TrackingEvent(
                        parcel_id=request.parcel.id,
                        request_id=request.id,
                        event_type=PARCEL_PARTNER_ACCEPTED,
                        actor_id=user.id,
                        notes="Partner accepted the batch assignment.",
                    )
                )
            notify_request_customer(
                request,
                "batch_accepted",
                "A verified partner accepted your batch",
                f"{batch.code} will be executed by {user.name}. Track each parcel status in your request.",
            )
        notify_admins(
            "batch_accepted",
            f"{batch.code} accepted",
            f"{user.name} accepted the batch. Route execution can begin.",
            f"/admin/batches",
        )
        audit(
            user.id,
            "batch.accepted",
            "batch",
            batch.id,
            f"Partner {user.name} accepted {batch.code}.",
        )
    elif decision == "decline":
        batch.status = BATCH_DECLINED
        batch.declined_reason = reason or "Declined by partner."
        batch.partner_id = None
        batch.version += 1
        db.session.add(
            BatchAssignment(
                batch_id=batch.id,
                partner_id=user.id,
                actor_id=user.id,
                action=ASSIGNMENT_DECLINED,
                reason=reason,
            )
        )
        notify_admins(
            "batch_declined",
            f"{batch.code} declined",
            f"{user.name} declined the offer: {reason or 'no reason provided'}",
            "/admin/batches",
        )
        for link in batch.request_links:
            if link.released_at is None:
                notify_request_customer(
                    link.request,
                    "batch_declined",
                    "Partner declined the offer",
                    f"{batch.code} will be re-offered to another verified partner. Your request stays reserved.",
                )
        audit(
            user.id,
            "batch.declined",
            "batch",
            batch.id,
            f"Partner {user.name} declined {batch.code}.",
            reason=reason,
        )
    else:
        raise ApiError("invalid_decision", "Decision must be accept or decline.", 422)
    db.session.commit()
    return batch


def reassign_batch(actor: User, batch_id: int, partner_id: int, reason: str) -> DeliveryBatch:
    if not reason or len(reason.strip()) < 5:
        raise ApiError("reason_required", "A reassignment reason of at least 5 characters is required.", 422)
    batch = _batch_or_404(batch_id, lock=True)
    if batch.status in {BATCH_IN_PROGRESS, BATCH_COMPLETED, BATCH_CANCELLED}:
        raise ApiError(
            "invalid_batch_state",
            "A batch in progress or finished cannot be reassigned.",
            409,
        )
    profile = _partner_profile_for(partner_id)
    eligible, eligibility_reason = matching.partner_eligible_for_batch(batch, profile)
    if not eligible:
        raise ApiError("partner_ineligible", eligibility_reason or "Partner is not eligible.", 409)
    previous_partner_id = batch.partner_id
    batch.partner_id = profile.user_id
    batch.status = BATCH_OFFERED
    batch.offered_at = utcnow()
    batch.accepted_at = None
    batch.declined_reason = None
    batch.version += 1
    db.session.add(
        BatchAssignment(
            batch_id=batch.id,
            partner_id=profile.user_id,
            actor_id=actor.id,
            action=ASSIGNMENT_REASSIGNED,
            reason=reason,
        )
    )
    for link in batch.request_links:
        if link.released_at is not None:
            continue
        link.request.status = REQUEST_BATCHED
        if link.request.parcel and link.request.parcel.status in {
            PARCEL_PARTNER_ACCEPTED,
            PARCEL_ASSIGNED,
        }:
            link.request.parcel.status = PARCEL_ASSIGNED
            db.session.add(
                TrackingEvent(
                    parcel_id=link.request.parcel.id,
                    request_id=link.request.id,
                    event_type=PARCEL_ASSIGNED,
                    actor_id=actor.id,
                    notes=f"Reassigned to {profile.user.name}.",
                )
            )
        notify_request_customer(
            link.request,
            "batch_reassigned",
            "Your batch was reassigned",
            f"{batch.code} now awaits acceptance from another verified partner.",
        )
    notify(
        profile.user_id,
        "batch_offered",
        f"Batch {batch.code} assigned to you",
        "An administrator assigned this batch to you. Review and accept it.",
        f"/partner/batches/{batch.id}",
    )
    if previous_partner_id:
        notify(
            previous_partner_id,
            "batch_reassigned",
            f"{batch.code} was reassigned",
            "This batch is no longer assigned to you.",
            "/partner/batches",
        )
    audit(
        actor.id,
        "batch.reassigned",
        "batch",
        batch.id,
        f"Reassigned {batch.code} to {profile.user.name}.",
        reason=reason,
        metadata={"previous_partner_id": previous_partner_id},
    )
    db.session.commit()
    return batch


def start_batch(actor: User, batch_id: int) -> DeliveryBatch:
    batch = _batch_or_404(batch_id, lock=True)
    if actor.role == ROLE_PARTNER and batch.partner_id != actor.id:
        raise ApiError("forbidden", "This batch is not assigned to you.", 403)
    if actor.role not in {ROLE_PARTNER, ROLE_ADMIN}:
        raise ApiError("forbidden", "Only the assigned partner can start this route.", 403)
    if batch.status != BATCH_ACCEPTED:
        raise ApiError("invalid_batch_state", "Only accepted batches can be started.", 409)
    batch.status = BATCH_IN_PROGRESS
    batch.started_at = utcnow()
    for link in batch.request_links:
        if link.released_at is None:
            link.request.status = REQUEST_IN_PROGRESS
            link.request.updated_at = utcnow()
            notify_request_customer(
                link.request,
                "route_started",
                "Your parcel route has started",
                f"The partner started {batch.code}. Parcel-level updates will appear in your timeline.",
            )
    audit(actor.id, "batch.started", "batch", batch.id, f"Route started for {batch.code}.")
    db.session.commit()
    return batch


def cancel_batch(actor: User, batch_id: int, reason: str) -> DeliveryBatch:
    if not reason or len(reason.strip()) < 5:
        raise ApiError("reason_required", "A cancellation reason of at least 5 characters is required.", 422)
    batch = _batch_or_404(batch_id, lock=True)
    if batch.status in {BATCH_IN_PROGRESS, BATCH_COMPLETED, BATCH_CANCELLED}:
        raise ApiError(
            "invalid_batch_state",
            "In-progress, completed or cancelled batches cannot be cancelled here.",
            409,
        )
    previous_partner_id = batch.partner_id
    _release_reservations(batch, reason)
    db.session.add(
        BatchAssignment(
            batch_id=batch.id,
            partner_id=previous_partner_id,
            actor_id=actor.id,
            action=ASSIGNMENT_REVOKED,
            reason=reason,
        )
    )
    for link in batch.request_links:
        notify_request_customer(
            link.request,
            "batch_cancelled",
            "A proposed shared batch was withdrawn",
            f"{batch.code} was cancelled: {reason}. Your request is available for matching again.",
        )
    if previous_partner_id:
        notify(
            previous_partner_id,
            "batch_cancelled",
            f"{batch.code} was cancelled",
            f"An administrator cancelled the assignment: {reason}",
            "/partner/batches",
        )
    audit(
        actor.id,
        "batch.cancelled",
        "batch",
        batch.id,
        f"Cancelled {batch.code} and released {len(batch.request_links)} request(s).",
        reason=reason,
    )
    db.session.commit()
    return batch


# ----------------------------------------------------------------------- requests
def cancel_request(actor: User, request: DeliveryRequest, reason: str | None) -> DeliveryRequest:
    now = utcnow()
    batch = batch_for_request(request)
    if request.status == REQUEST_PENDING:
        request.status = REQUEST_CANCELLED
        request.cancelled_at = now
        request.cancellation_reason = reason
        request.updated_at = now
        if request.parcel and request.parcel.status not in PARCEL_TERMINAL_STATUSES:
            request.parcel.status = PARCEL_FAILED
        audit(
            actor.id,
            "request.cancelled",
            "request",
            request.id,
            f"Cancelled {request_code(request.id)}.",
            reason=reason,
        )
        db.session.commit()
        return request
    if request.status == REQUEST_BATCHED and batch is not None and batch.status == BATCH_PROPOSED:
        _release_reservations(batch, f"Proposal dissolved after customer cancellation: {reason or 'customer request'}")
        for link in batch.request_links:
            if link.request_id == request.id:
                continue
            notify_request_customer(
                link.request,
                "batch_cancelled",
                "A proposed shared batch was withdrawn",
                "Another parcel was cancelled, so the proposal was dissolved. Your request is available for matching again.",
            )
        request.status = REQUEST_CANCELLED
        request.cancelled_at = now
        request.cancellation_reason = reason
        request.updated_at = now
        audit(
            actor.id,
            "request.cancelled",
            "request",
            request.id,
            f"Cancelled {request_code(request.id)} and dissolved proposal {batch.code}.",
            reason=reason,
        )
        db.session.commit()
        return request
    raise ApiError(
        "cancellation_not_allowed",
        "This request can no longer be cancelled online because a partner is already engaged. "
        "Report an issue and support will help.",
        409,
    )


# ------------------------------------------------------------------------ parcels
def _active_batch_for_parcel(parcel):
    request = parcel.request
    link = active_link_for_request(request.id)
    if link is None:
        return None
    return link.batch


def update_parcel_status(
    actor: User, parcel_id: int, event_type: str, notes: str | None = None
) -> tuple[object, DeliveryBatch | None]:
    from ..models import Parcel

    parcel = Parcel.query.filter(Parcel.id == parcel_id).with_for_update().first()
    if parcel is None:
        raise ApiError("parcel_not_found", "That parcel does not exist.", 404)
    batch = _active_batch_for_parcel(parcel)
    if actor.role == ROLE_PARTNER:
        if batch is None or batch.partner_id != actor.id:
            raise ApiError("forbidden", "This parcel is not on one of your accepted batches.", 403)
    elif actor.role != ROLE_ADMIN:
        raise ApiError("forbidden", "Only the assigned partner can update parcel status.", 403)
    if batch is None:
        raise ApiError("batch_not_found", "This parcel is not assigned to an active batch.", 409)
    if batch.status == BATCH_COMPLETED:
        raise ApiError(
            "invalid_batch_state",
            "This batch is already completed; parcel status is final.",
            409,
        )
    if batch.status != BATCH_IN_PROGRESS:
        raise ApiError("invalid_batch_state", "Start the route before updating parcel status.", 409)
    if not can_transition_parcel(parcel.status, event_type):
        raise ApiError(
            "invalid_transition",
            f"A parcel in '{parcel.status}' cannot move to '{event_type}'.",
            409,
            details={"current_status": parcel.status, "allowed": list(_allowed(parcel.status))},
        )
    if event_type == PARCEL_FAILED and not (notes and len(notes.strip()) >= 5):
        raise ApiError("reason_required", "Describe the problem before marking a parcel failed.", 422)

    now = utcnow()
    parcel.status = event_type
    parcel.updated_at = now
    request = parcel.request
    db.session.add(
        TrackingEvent(
            parcel_id=parcel.id,
            request_id=request.id,
            event_type=event_type,
            actor_id=actor.id,
            notes=notes,
        )
    )

    pickup_stop = next(
        (stop for stop in batch.stops if stop.request_id == request.id and stop.kind == "pickup"), None
    )
    dropoff_stop = next(
        (stop for stop in batch.stops if stop.request_id == request.id and stop.kind == "dropoff"), None
    )
    if event_type == PARCEL_PICKUP_ARRIVED and pickup_stop:
        pickup_stop.status = "arrived"
    if event_type == PARCEL_PICKED_UP and pickup_stop:
        pickup_stop.status = "done"
        pickup_stop.completed_at = now
    if event_type == PARCEL_DELIVERED and dropoff_stop:
        dropoff_stop.status = "done"
        dropoff_stop.completed_at = now
    if event_type == PARCEL_FAILED and dropoff_stop:
        dropoff_stop.status = "skipped"

    if event_type in {PARCEL_PICKUP_ARRIVED, PARCEL_PICKED_UP, PARCEL_IN_TRANSIT}:
        request.status = REQUEST_IN_PROGRESS
    elif event_type == PARCEL_DELIVERED:
        request.status = REQUEST_COMPLETED
    elif event_type == PARCEL_FAILED:
        request.status = REQUEST_FAILED
        request.failure_reason = notes
        db.session.add(
            IssueReport(
                request_id=request.id,
                batch_id=batch.id,
                reporter_id=actor.id,
                category="delivery_failure",
                severity="high",
                description=notes or "Parcel could not be delivered.",
                status="open",
            )
        )
        notify_admins(
            "issue_created",
            "Delivery issue needs review",
            f"{request_code(request.id)} was marked failed: {notes}",
            "/admin/issues",
        )
    request.updated_at = now

    if event_type == PARCEL_DELIVERED:
        notify_request_customer(
            request,
            "parcel_delivered",
            f"Parcel {parcel_code(parcel.id)} delivered",
            f"Your parcel was marked delivered at {now.astimezone().strftime('%H:%M')} local time.",
        )
    elif event_type == PARCEL_PICKED_UP:
        notify_request_customer(
            request,
            "parcel_picked_up",
            "Parcel collected",
            f"{parcel_code(parcel.id)} was collected by the partner.",
        )

    all_terminal = all(
        link.request.parcel is None or link.request.parcel.status in PARCEL_TERMINAL_STATUSES
        for link in batch.request_links
        if link.released_at is None
    )
    if all_terminal:
        batch.status = BATCH_COMPLETED
        batch.completed_at = now
        notify_admins(
            "batch_completed",
            f"{batch.code} completed",
            "All parcels reached a terminal state.",
            "/admin/batches",
        )
        audit(actor.id, "batch.completed", "batch", batch.id, f"{batch.code} completed with all parcels resolved.")
    audit(
        actor.id,
        f"parcel.{event_type}",
        "parcel",
        parcel.id,
        f"{parcel_code(parcel.id)} moved to {event_type}.",
        reason=notes,
        metadata={"batch_id": batch.id, "request_id": request.id},
    )
    db.session.commit()
    return parcel, batch


def _allowed(current: str):
    from ..domain import PARCEL_TRANSITIONS

    return PARCEL_TRANSITIONS.get(current, ())


def serialize_committed_batch(batch: DeliveryBatch) -> dict:
    return serialize_batch(batch, include_contacts=False, include_requests=True)


def issue_created_for_batch(batch: DeliveryBatch) -> bool:
    return bool(IssueReport.query.filter_by(batch_id=batch.id, status="open").first())


def app_config_summary() -> dict:
    return {
        "fuel_l_per_km": current_app.config["SUSTAINABILITY_FUEL_L_PER_KM"],
        "kg_co2e_per_litre": current_app.config["SUSTAINABILITY_KG_CO2E_PER_LITRE"],
    }


__all__ = [
    "commit_batch",
    "offer_batch",
    "decide_offer",
    "reassign_batch",
    "start_batch",
    "cancel_batch",
    "cancel_request",
    "update_parcel_status",
    "notify",
    "notify_request_customer",
    "notify_admins",
    "audit",
    "batch_for_request",
    "active_link_for_request",
    "parse_iso",
    "iso",
]
