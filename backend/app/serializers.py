"""JSON serializers. Contact data is only exposed when the caller is authorized."""
from __future__ import annotations

from .domain import (
    ACTIVE_BATCH_STATUSES,
    BATCH_COMPLETED,
    PARCEL_TERMINAL_STATUSES,
    REQUEST_CANCELLED,
    REQUEST_COMPLETED,
    batch_code,
    iso,
    parcel_code,
    request_code,
    utcnow,
)


def _float(value):
    return float(value) if value is not None else None


def serialize_user(user, *, include_private: bool = False) -> dict:
    data = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "timezone": user.timezone_name,
        "created_at": iso(user.created_at),
        "disabled": user.disabled_at is not None,
    }
    if include_private:
        data.update(
            {
                "phone": user.phone,
                "notify_email": user.notify_email,
                "notify_in_app": user.notify_in_app,
                "last_login_at": iso(user.last_login_at),
                "disabled_at": iso(user.disabled_at),
            }
        )
    return data


def serialize_location(location) -> dict | None:
    if location is None:
        return None
    return {
        "id": location.id,
        "label": location.label,
        "address_line": location.address_line,
        "area": location.area,
        "city": location.city,
        "postal_code": location.postal_code,
        "latitude": _float(location.latitude),
        "longitude": _float(location.longitude),
        "source": location.source,
        "is_sample": location.is_sample,
    }


def serialize_parcel(parcel, *, include_events: bool = False) -> dict | None:
    if parcel is None:
        return None
    data = {
        "id": parcel.id,
        "code": parcel_code(parcel.id),
        "tracking_number": parcel.tracking_number,
        "description": parcel.description,
        "category": parcel.category,
        "weight_kg": _float(parcel.weight_kg),
        "volume_m3": _float(parcel.volume_m3),
        "size_class": parcel.size_class,
        "handling": parcel.handling_list,
        "status": parcel.status,
        "declared_value_inr": _float(parcel.declared_value_inr),
        "updated_at": iso(parcel.updated_at),
    }
    if include_events:
        data["events"] = [serialize_tracking_event(event) for event in parcel_events(parcel)]
    return data


def parcel_events(parcel):
    from .models import TrackingEvent

    return (
        TrackingEvent.query.filter_by(parcel_id=parcel.id)
        .order_by(TrackingEvent.created_at.asc(), TrackingEvent.id.asc())
        .all()
    )


def serialize_tracking_event(event) -> dict:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "notes": event.notes,
        "created_at": iso(event.created_at),
        "actor_name": event.actor.name if event.actor else "ReTurn system",
        "actor_role": event.actor.role if event.actor else "system",
    }


def serialize_partner_profile(profile, *, include_user: bool = True) -> dict:
    user = profile.user
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "name": user.name if user else None,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "company_name": profile.company_name,
        "vehicle_type": profile.vehicle_type,
        "max_weight_kg": _float(profile.max_weight_kg),
        "max_volume_m3": _float(profile.max_volume_m3),
        "accepts_fragile": profile.accepts_fragile,
        "accepts_restricted": profile.accepts_restricted,
        "service_areas": profile.service_area_list,
        "availability": profile.availability,
        "verification_status": profile.verification_status,
        "verification_note": profile.verification_note,
        "verified_at": iso(profile.verified_at),
        "operating_hours": {
            "start_hour": profile.operating_start_hour,
            "end_hour": profile.operating_end_hour,
        },
        "created_at": iso(profile.created_at),
        "user": serialize_user(user, include_private=include_user) if user else None,
    }


def serialize_batch_summary(batch) -> dict:
    return {
        "id": batch.id,
        "code": batch_code(batch.id),
        "status": batch.status,
        "partner_id": batch.partner_id,
        "partner_name": batch.partner.name if batch.partner else None,
        "distance_km": _float(batch.distance_km),
        "baseline_km": _float(batch.baseline_km),
        "savings_km": _float(batch.savings_km),
        "savings_percent": _float(batch.savings_percent),
        "distance_source": batch.distance_source,
        "created_at": iso(batch.created_at),
        "stop_count": len(batch.stops),
    }


def serialize_stop(stop, *, include_request: bool = True) -> dict:
    data = {
        "id": stop.id,
        "sequence": stop.sequence,
        "kind": stop.kind,
        "status": stop.status,
        "request_id": stop.request_id,
        "planned_arrival": iso(stop.planned_arrival),
        "planned_departure": iso(stop.planned_departure),
        "service_minutes": stop.service_minutes,
        "leg_distance_km": _float(stop.leg_distance_km),
        "leg_duration_minutes": stop.leg_duration_minutes,
        "load_weight_kg": _float(stop.load_weight_kg),
        "load_volume_m3": _float(stop.load_volume_m3),
        "completed_at": iso(stop.completed_at),
        "notes": stop.notes,
        "location": serialize_location(stop.location),
    }
    if include_request and stop.request:
        data["request"] = {
            "id": stop.request.id,
            "code": request_code(stop.request.id),
            "type": stop.request.type,
            "status": stop.request.status,
            "parcel_id": stop.request.parcel.id if stop.request.parcel else None,
            "parcel_code": parcel_code(stop.request.parcel.id) if stop.request.parcel else None,
            "parcel_status": stop.request.parcel.status if stop.request.parcel else None,
            "parcel_description": stop.request.parcel.description if stop.request.parcel else None,
            "weight_kg": _float(stop.request.parcel.weight_kg) if stop.request.parcel else None,
        }
    return data


def serialize_batch(
    batch,
    *,
    include_stops: bool = True,
    include_requests: bool = True,
    include_contacts: bool = False,
    include_timeline: bool = True,
) -> dict:
    data = {
        **serialize_batch_summary(batch),
        "duration_minutes": batch.duration_minutes,
        "geometry": batch.geometry,
        "geometry_source": batch.geometry_source,
        "route_method": batch.route_method,
        "explanation": batch.explanation or {},
        "assumptions": batch.assumptions or [],
        "load_profile": batch.load_profile or [],
        "offered_at": iso(batch.offered_at),
        "accepted_at": iso(batch.accepted_at),
        "started_at": iso(batch.started_at),
        "completed_at": iso(batch.completed_at),
        "declined_reason": batch.declined_reason,
        "cancelled_reason": batch.cancelled_reason,
        "partner": (
            {
                "id": batch.partner.id,
                "name": batch.partner.name,
                "phone": batch.partner.phone if include_contacts else None,
                "email": batch.partner.email if include_contacts else None,
            }
            if batch.partner
            else None
        ),
        "stops": [serialize_stop(stop, include_request=include_requests) for stop in batch.stops]
        if include_stops
        else [],
    }
    if include_requests:
        data["requests"] = [
            serialize_request(
                link.request,
                include_contact=include_contacts,
                include_customer=True,
                include_batch=False,
            )
            for link in batch.request_links
            if link.released_at is None
        ]
    if include_timeline:
        data["assignment_history"] = [
            {
                "id": item.id,
                "action": item.action,
                "partner_id": item.partner_id,
                "partner_name": item.partner.name if item.partner else None,
                "actor_name": item.actor.name if item.actor else "ReTurn system",
                "reason": item.reason,
                "created_at": iso(item.created_at),
            }
            for item in batch.assignments
        ]
    return data


def serialize_batch_for_customer(batch, request_id: int) -> dict:
    """Batch context for one customer's request; never exposes other customers."""
    own_stops = [stop for stop in batch.stops if stop.request_id == request_id]
    return {
        "id": batch.id,
        "code": batch_code(batch.id),
        "status": batch.status,
        "distance_km": _float(batch.distance_km),
        "savings_percent": _float(batch.savings_percent),
        "distance_source": batch.distance_source,
        "partner": (
            {"name": batch.partner.name, "phone": batch.partner.phone, "email": batch.partner.email}
            if batch.partner and batch.status not in {"proposed"}
            else None
        ),
        "stops": [serialize_stop(stop, include_request=False) for stop in own_stops],
        "parcel_count": len([link for link in batch.request_links if link.released_at is None]),
        "estimated": True,
    }


def serialize_request(
    req,
    *,
    include_contact: bool = False,
    include_batch: bool = True,
    include_customer: bool = False,
) -> dict:
    batch_link = next(
        (link for link in req.batch_links if link.released_at is None),
        None,
    )
    batch = batch_link.batch if batch_link else None
    data = {
        "id": req.id,
        "code": request_code(req.id),
        "type": req.type,
        "status": req.status,
        "created_at": iso(req.created_at),
        "updated_at": iso(req.updated_at),
        "pickup_window_start": iso(req.pickup_window_start),
        "pickup_window_end": iso(req.pickup_window_end),
        "delivery_deadline": iso(req.delivery_deadline),
        "notes": req.notes,
        "pickup": serialize_location(req.pickup_location),
        "destination": serialize_location(req.destination_location),
        "parcel": serialize_parcel(req.parcel),
        "return_detail": (
            {
                "authorized_hub_name": req.return_detail.authorized_hub_name,
                "return_reference": req.return_detail.return_reference,
                "retailer": req.return_detail.retailer,
            }
            if req.return_detail
            else None
        ),
        "recipient": (
            {
                "name": req.recipient_detail.recipient_name,
                "phone": req.recipient_detail.recipient_phone if include_contact else None,
                "instructions": req.recipient_detail.delivery_instructions,
            }
            if req.recipient_detail
            else None
        ),
        "customer": (
            {
                "id": req.customer.id,
                "name": req.customer.name,
                "phone": req.customer.phone if include_contact else None,
                "email": req.customer.email if include_contact else None,
            }
            if include_customer
            else None
        ),
        "cancelled_at": iso(req.cancelled_at),
        "cancellation_reason": req.cancellation_reason,
        "failure_reason": req.failure_reason,
        "next_step": request_next_step(req),
        "batch": (
            serialize_batch_for_customer(batch, req.id)
            if batch
            else None
        )
        if include_batch
        else (
            serialize_batch_summary(batch) if batch else None
        ),
    }
    return data


def serialize_issue(issue, *, include_contacts: bool = False) -> dict:
    return {
        "id": issue.id,
        "category": issue.category,
        "severity": issue.severity,
        "status": issue.status,
        "description": issue.description,
        "resolution_note": issue.resolution_note,
        "created_at": iso(issue.created_at),
        "updated_at": iso(issue.updated_at),
        "resolved_at": iso(issue.resolved_at),
        "reporter": serialize_user(issue.reporter) if issue.reporter else None,
        "resolved_by": (
            {"id": issue.resolved_by.id, "name": issue.resolved_by.name}
            if issue.resolved_by
            else None
        ),
        "request": (
            {
                "id": issue.request.id,
                "code": request_code(issue.request.id),
                "type": issue.request.type,
                "status": issue.request.status,
                "customer_name": issue.request.customer.name if include_contacts else None,
            }
            if issue.request
            else None
        ),
        "batch": (
            {"id": issue.batch.id, "code": batch_code(issue.batch.id), "status": issue.batch.status}
            if issue.batch
            else None
        ),
    }


def serialize_notification(notification) -> dict:
    return {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "link": notification.link,
        "read_at": iso(notification.read_at),
        "created_at": iso(notification.created_at),
    }


def serialize_audit(event) -> dict:
    return {
        "id": event.id,
        "action": event.action,
        "entity_type": event.entity_type,
        "entity_id": event.entity_id,
        "summary": event.summary,
        "reason": event.reason,
        "metadata": event.event_metadata,
        "actor_name": event.actor.name if event.actor else "ReTurn system",
        "actor_role": event.actor.role if event.actor else "system",
        "created_at": iso(event.created_at),
    }


def request_next_step(req) -> str:
    if req.status == REQUEST_CANCELLED:
        return "This request was cancelled."
    if req.status == REQUEST_COMPLETED:
        return "Journey complete. The delivery record is in your history."
    if req.status == "failed":
        return "A delivery issue was recorded. Our team will review it."
    if req.status == "in_progress":
        return "Your parcel is on its route. Check the tracking timeline for updates."
    if req.status == "assigned":
        return "A verified partner accepted this batch and will collect the parcel."
    if req.status == "batched":
        return "Reserved in a proposed batch. Waiting for dispatch and partner acceptance."
    return "Waiting for compatible requests; grouping is not guaranteed."


def batch_is_active(batch) -> bool:
    return batch.status in ACTIVE_BATCH_STATUSES


def parcel_is_terminal(parcel) -> bool:
    return parcel.status in PARCEL_TERMINAL_STATUSES


def batch_is_finished(batch) -> bool:
    return batch.status == BATCH_COMPLETED


def now_iso() -> str:
    return iso(utcnow())
