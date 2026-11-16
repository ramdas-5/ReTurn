"""API serializers. Every value returned to the client passes through here."""
from __future__ import annotations

from datetime import datetime

from . import domain


def _float(value):
    return float(value) if value is not None else None


def _iso(value: datetime | None) -> str | None:
    return domain.iso(value)


def _media_url(asset) -> str | None:
    if asset is None:
        return None
    from .services.storage import media_url

    return media_url(asset)


def active_duty_session(user):
    from .models import DriverDutySession

    profile = getattr(user, "driver_profile", None)
    if profile is None:
        return None
    return (
        DriverDutySession.query.filter_by(driver_id=profile.id)
        .filter(DriverDutySession.ended_at.is_(None))
        .first()
    )


def serialize_service_area(area, *, include_counts: bool = False) -> dict:
    data = {
        "id": area.id,
        "name": area.name,
        "city": area.city,
        "state": area.state,
        "postal_codes": area.postal_code_list,
        "center": {
            "latitude": _float(area.center_latitude),
            "longitude": _float(area.center_longitude),
        },
        "radius_km": _float(area.radius_km),
        "is_active": area.is_active,
    }
    if include_counts:
        data["manager_count"] = len(area.managers) if hasattr(area, "managers") else 0
        data["driver_count"] = len(area.drivers) if hasattr(area, "drivers") else 0
    return data


def serialize_capacity_profile(profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "vehicle_type": profile.vehicle_type,
        "max_weight_kg": _float(profile.max_weight_kg),
        "max_volume_m3": _float(profile.max_volume_m3),
        "max_dimensions_cm": {
            "length": _float(profile.max_length_cm),
            "width": _float(profile.max_width_cm),
            "height": _float(profile.max_height_cm),
        },
        "max_parcels": profile.max_parcels,
        "supports_fragile": profile.supports_fragile,
        "supports_restricted": profile.supports_restricted,
        "is_active": profile.is_active,
    }


def serialize_vehicle(vehicle, *, include_capacity: bool = True) -> dict:
    data = {
        "id": vehicle.id,
        "vehicle_type": vehicle.vehicle_type,
        "registration_number": vehicle.registration_number,
        "make": vehicle.make,
        "model": vehicle.model,
        "color": vehicle.color,
        "year": vehicle.year,
        "verification_status": vehicle.verification_status,
        "is_active": vehicle.is_active,
        "capacity_profile_id": vehicle.capacity_profile_id,
    }
    if include_capacity and vehicle.capacity_profile is not None:
        data["capacity"] = serialize_capacity_profile(vehicle.capacity_profile)
    return data


def serialize_business_profile(profile) -> dict | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "business_name": profile.business_name,
        "category": profile.category,
        "contact_phone": profile.contact_phone,
        "contact_email": profile.contact_email,
        "address_line": profile.address_line,
        "area": profile.area,
        "city": profile.city,
        "state": profile.state,
        "postal_code": profile.postal_code,
        "location": {
            "latitude": _float(profile.latitude),
            "longitude": _float(profile.longitude),
        },
        "logo_url": _media_url(profile.logo),
        "tax_id": profile.tax_id,
        "registration_number": profile.registration_number,
        "verification_status": profile.verification_status,
        "verified_at": _iso(profile.verified_at),
    }


def serialize_consumer_profile(profile) -> dict | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "account_type": profile.account_type,
        "company_role": profile.company_role,
    }


def serialize_driver_profile(profile, *, include_user: bool = True) -> dict | None:
    if profile is None:
        return None
    user = profile.user
    duty = active_duty_session(user)
    data = {
        "id": profile.id,
        "verification_status": profile.verification_status,
        "verification_note": profile.verification_note,
        "verified_at": _iso(profile.verified_at),
        "license_number": profile.license_number,
        "license_expiry": profile.license_expiry.isoformat() if profile.license_expiry else None,
        "rating": _float(profile.rating),
        "completed_deliveries": profile.completed_deliveries,
        "created_at": _iso(profile.created_at),
        "duty_status": duty.status if duty else "off_duty",
        "duty_session": (
            {
                "id": duty.id,
                "status": duty.status,
                "started_at": _iso(duty.started_at),
                "last_heartbeat_at": _iso(duty.last_heartbeat_at),
            }
            if duty
            else None
        ),
        "service_areas": [
            serialize_service_area(link.service_area)
            for link in profile.service_areas
            if link.service_area
        ],
        "vehicles": [serialize_vehicle(vehicle) for vehicle in profile.vehicles],
    }
    if include_user:
        data["user"] = serialize_user(user, include_profile=False)
    return data


def serialize_manager_profile(profile) -> dict | None:
    if profile is None:
        return None
    return {
        "id": profile.id,
        "employee_code": profile.employee_code,
        "contact_phone": profile.contact_phone,
        "notes": profile.notes,
        "service_areas": [
            serialize_service_area(link.service_area)
            for link in profile.service_areas
            if link.service_area
        ],
    }


def serialize_user(
    user,
    *,
    include_profile: bool = True,
    include_permissions: bool = True,
    include_private: bool = True,
) -> dict | None:
    if user is None:
        return None
    data = {
        "id": user.id,
        "full_name": user.full_name,
        "role": user.role,
        "role_label": user.display_role,
        "status": user.status,
        "avatar_url": user.avatar_url,
        "created_at": _iso(user.created_at),
    }
    if include_private:
        data.update(
            {
                "email": user.email,
                "phone": user.phone,
                "timezone_name": user.timezone_name,
                "must_change_password": user.must_change_password,
                "mfa_enabled": user.mfa_enabled,
                "last_login_at": _iso(user.last_login_at),
                "notify_email": user.notify_email,
                "notify_in_app": user.notify_in_app,
            }
        )
    if include_permissions:
        data["permissions"] = sorted(domain.user_permissions(user))
    if include_profile:
        if user.role == domain.ROLE_CONSUMER:
            data["consumer_profile"] = serialize_consumer_profile(user.consumer_profile)
            data["business_profile"] = serialize_business_profile(user.business_profile)
        elif user.role == domain.ROLE_DRIVER:
            data["driver_profile"] = serialize_driver_profile(user.driver_profile, include_user=False)
        elif user.role == domain.ROLE_MANAGER:
            data["manager_profile"] = serialize_manager_profile(user.manager_profile)
    return data


def serialize_notification(row) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "link": row.link,
        "data": row.event_data or {},
        "read_at": _iso(row.read_at),
        "created_at": _iso(row.created_at),
    }


def serialize_saved_address(address) -> dict:
    return {
        "id": address.id,
        "label": address.label,
        "contact_name": address.contact_name,
        "contact_phone": address.contact_phone,
        "address_line": address.address_line,
        "address_line2": address.address_line2,
        "area": address.area,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "latitude": _float(address.latitude),
        "longitude": _float(address.longitude),
        "is_default_pickup": address.is_default_pickup,
    }


def serialize_audit_log(row) -> dict:
    return {
        "id": row.id,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "summary": row.summary,
        "reason": row.reason,
        "actor": (
            {"id": row.actor.id, "full_name": row.actor.full_name, "role": row.actor.role}
            if row.actor
            else None
        ),
        "ip_address": row.ip_address,
        "created_at": _iso(row.created_at),
        "metadata": row.event_metadata or {},
    }


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
def _address_snapshot(address) -> dict | None:
    if address is None:
        return None
    return {
        "contact_name": address.contact_name,
        "contact_phone": address.contact_phone,
        "address_line": address.address_line,
        "address_line2": address.address_line2,
        "area": address.area,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "latitude": _float(address.latitude),
        "longitude": _float(address.longitude),
        "instructions": address.instructions,
    }


def _parcel_payload(parcel) -> dict | None:
    if parcel is None:
        return None
    return {
        "name": parcel.name,
        "description": parcel.description,
        "category": parcel.category,
        "quantity": parcel.quantity,
        "weight_kg": _float(parcel.weight_kg),
        "dimensions_cm": {
            "length": _float(parcel.length_cm),
            "width": _float(parcel.width_cm),
            "height": _float(parcel.height_cm),
        },
        "volume_m3": _float(parcel.volume_m3),
        "is_fragile": parcel.is_fragile,
        "handling": parcel.handling_list,
        "declared_value_inr": _float(parcel.declared_value_inr),
        "photo_exception_reason": parcel.photo_exception_reason,
    }


def serialize_parcel_image(image) -> dict:
    return {
        "id": image.id,
        "kind": image.image_kind,
        "is_primary": image.is_primary,
        "url": _media_url(image.media),
        "captured_at": _iso(image.captured_at),
        "created_at": _iso(image.created_at),
    }


def serialize_return_request(return_request) -> dict | None:
    if return_request is None:
        return None
    return {
        "product_name": return_request.product_name,
        "original_order_reference": return_request.original_order_reference,
        "reason": return_request.reason,
        "return_authorization_reference": return_request.return_authorization_reference,
        "merchant_name": return_request.merchant_name,
        "destination_type": return_request.destination_type,
        "authorization_confirmed": return_request.authorization_confirmed,
        "approval_status": return_request.approval_status,
        "approved_at": _iso(return_request.approved_at),
        "received_at": _iso(return_request.received_at),
        "condition_notes": return_request.condition_notes,
        "refund_status": return_request.refund_status,
    }


def serialize_assignment(assignment, *, include_driver_contact: bool = True) -> dict | None:
    if assignment is None:
        return None
    driver = assignment.driver
    data = {
        "id": assignment.id,
        "status": assignment.status,
        "assigned_at": _iso(assignment.assigned_at),
        "accepted_at": _iso(assignment.accepted_at),
        "ended_at": _iso(assignment.ended_at),
        "vehicle": serialize_vehicle(assignment.vehicle) if assignment.vehicle else None,
        "driver": None,
    }
    if driver is not None:
        data["driver"] = {
            "id": driver.id,
            "full_name": driver.full_name,
        }
        if include_driver_contact:
            data["driver"]["phone"] = driver.phone
    return data


def serialize_proof(proof, *, kind: str) -> dict | None:
    if proof is None:
        return None
    media = proof.proof_media
    asset = media.media if media else None
    return {
        "id": proof.id,
        "kind": kind,
        "status": proof.status,
        "captured_at": _iso(media.captured_at if media else None),
        "server_received_at": _iso(proof.server_received_at),
        "recipient_name": getattr(proof, "recipient_name", None),
        "image_url": _media_url(asset),
        "location": (
            {
                "latitude": _float(media.latitude),
                "longitude": _float(media.longitude),
                "accuracy_m": _float(media.accuracy_m),
            }
            if media
            else None
        ),
    }


def serialize_order_summary(order, *, include_consumer: bool = False) -> dict:
    active = None
    for assignment in order.assignments:
        if assignment.status == "active":
            active = assignment
            break
    data = {
        "id": order.id,
        "order_number": order.order_number,
        "service_type": order.service_type,
        "service_label": "Return" if order.service_type == domain.SERVICE_RETURN else "Parcel",
        "status": order.status,
        "status_label": domain.ORDER_STATUS_LABELS.get(order.status, order.status),
        "priority": order.priority,
        "is_demo": order.is_demo,
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "pickup": {
            "area": order.pickup_address.area if order.pickup_address else None,
            "city": order.pickup_address.city if order.pickup_address else None,
            "window_start": _iso(order.pickup_window_start),
            "window_end": _iso(order.pickup_window_end),
        },
        "delivery": {
            "area": order.delivery_address.area if order.delivery_address else None,
            "city": order.delivery_address.city if order.delivery_address else None,
            "deadline": _iso(order.delivery_deadline),
        },
        "parcel": {
            "name": order.parcel.name if order.parcel else None,
            "weight_kg": _float(order.parcel.weight_kg) if order.parcel else None,
        },
        "has_photo": any(image.is_primary for image in order.images),
        "assigned_driver": serialize_assignment(active) if active else None,
    }
    if include_consumer and order.consumer is not None:
        data["consumer"] = {
            "id": order.consumer.id,
            "full_name": order.consumer.full_name,
            "phone": order.consumer.phone,
            "email": order.consumer.email,
            "account_type": (
                order.consumer.consumer_profile.account_type
                if order.consumer.consumer_profile
                else "individual"
            ),
        }
    return data


def serialize_status_history(row) -> dict:
    return {
        "id": row.id,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "to_label": domain.ORDER_STATUS_LABELS.get(row.to_status, row.to_status),
        "source": row.source,
        "reason": row.reason,
        "metadata": row.event_metadata or {},
        "actor": (
            {"id": row.actor.id, "full_name": row.actor.full_name, "role": row.actor.role}
            if row.actor
            else None
        ),
        "created_at": _iso(row.created_at),
    }


def serialize_order_detail(
    order,
    *,
    include_consumer: bool = False,
    include_driver_contact: bool = True,
    include_proofs: bool = True,
    include_history: bool = True,
) -> dict:
    from .models import BatchOrder, DeliveryProof, PickupProof

    data = serialize_order_summary(order, include_consumer=include_consumer)
    data.update(
        {
            "pickup_address": _address_snapshot(order.pickup_address),
            "delivery_address": _address_snapshot(order.delivery_address),
            "parcel": _parcel_payload(order.parcel),
            "return_request": serialize_return_request(order.return_request),
            "images": [serialize_parcel_image(image) for image in order.images],
            "business": serialize_business_profile(order.business_profile),
            "business_order_reference": order.business_order_reference,
            "service_notes": order.service_notes,
            "special_requirements": order.special_requirements,
            "assignment": serialize_assignment(
                next((a for a in order.assignments if a.status == "active"), None),
                include_driver_contact=include_driver_contact,
            ),
            "assignment_history": [
                serialize_assignment(row, include_driver_contact=include_driver_contact)
                for row in sorted(order.assignments, key=lambda row: row.assigned_at, reverse=True)
            ],
            "batch": None,
            "delivered_at": _iso(order.delivered_at),
            "cancelled_at": _iso(order.cancelled_at),
            "cancellation_reason": order.cancellation_reason,
            "failure_reason": order.failure_reason,
        }
    )

    link = (
        BatchOrder.query.filter_by(order_id=order.id)
        .filter(BatchOrder.removed_at.is_(None))
        .first()
    )
    if link and link.batch:
        batch = link.batch
        data["batch"] = {
            "id": batch.id,
            "batch_number": batch.batch_number,
            "status": batch.status,
            "status_label": domain.BATCH_STATUS_LABELS.get(batch.status, batch.status),
            "planned_start": _iso(batch.planned_start),
            "planned_end": _iso(batch.planned_end),
        }
    if include_proofs:
        data["pickup_proof"] = serialize_proof(
            PickupProof.query.filter_by(order_id=order.id).first(), kind="pickup"
        )
        data["delivery_proof"] = serialize_proof(
            DeliveryProof.query.filter_by(order_id=order.id).first(), kind="delivery"
        )
    if include_history:
        data["status_history"] = [
            serialize_status_history(row)
            for row in sorted(order.status_history, key=lambda row: row.created_at)
        ]
    return data


# --------------------------------------------------------------------------- #
# Driver: duty, locations, routes and exceptions
# --------------------------------------------------------------------------- #
def serialize_duty_session(session) -> dict | None:
    if session is None:
        return None
    return {
        "id": session.id,
        "status": session.status,
        "status_label": domain.DUTY_LABELS.get(session.status, session.status),
        "started_at": _iso(session.started_at),
        "ended_at": _iso(session.ended_at),
        "ended_reason": session.ended_reason,
        "last_heartbeat_at": _iso(session.last_heartbeat_at),
        "device_label": session.device_label,
        "start_location": {
            "latitude": _float(session.start_latitude),
            "longitude": _float(session.start_longitude),
        },
        "end_location": {
            "latitude": _float(session.end_latitude),
            "longitude": _float(session.end_longitude),
        },
    }


def serialize_driver_location(row, *, timeout_minutes: int = 15) -> dict:
    from datetime import timedelta as _timedelta

    received = row.received_at
    if received is not None:
        if received.tzinfo is None:
            received = received.replace(tzinfo=domain.UTC)
        fresh = received >= domain.utcnow() - _timedelta(minutes=timeout_minutes)
    else:  # pragma: no cover - received_at is non-null in the schema
        fresh = False
    return {
        "id": row.id,
        "driver_profile_id": row.driver_id,
        "duty_session_id": row.duty_session_id,
        "batch_id": row.batch_id,
        "latitude": _float(row.latitude),
        "longitude": _float(row.longitude),
        "accuracy_m": _float(row.accuracy_m),
        "heading_degrees": _float(row.heading_degrees),
        "speed_kmh": _float(row.speed_kmh),
        "recorded_at": _iso(row.recorded_at),
        "received_at": _iso(row.received_at),
        "source": row.source,
        "is_recent": fresh,
        "status_label": "Live recent location" if fresh else "Stale location",
    }


def _navigation_url(latitude, longitude) -> str | None:
    if latitude is None or longitude is None:
        return None
    return (
        "https://www.google.com/maps/dir/?api=1&destination="
        f"{_float(latitude)},{_float(longitude)}"
    )


def serialize_route_stop(stop) -> dict:
    order = stop.order
    return {
        "id": stop.id,
        "kind": stop.kind,
        "sequence": stop.sequence,
        "label": stop.label,
        "contact_name": stop.contact_name,
        "contact_phone": stop.contact_phone,
        "address": {
            "address_line": stop.address_line,
            "area": stop.area,
            "city": stop.city,
            "postal_code": stop.postal_code,
            "latitude": _float(stop.latitude),
            "longitude": _float(stop.longitude),
        },
        "planned_arrival": _iso(stop.planned_arrival),
        "planned_departure": _iso(stop.planned_departure),
        "service_minutes": stop.service_minutes,
        "leg_distance_km": _float(stop.leg_distance_km),
        "leg_duration_minutes": _float(stop.leg_duration_minutes),
        "load_weight_kg": _float(stop.load_weight_kg),
        "load_volume_m3": _float(stop.load_volume_m3),
        "status": stop.status,
        "arrived_at": _iso(stop.arrived_at),
        "completed_at": _iso(stop.completed_at),
        "notes": stop.notes,
        "order": (
            {
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "status_label": domain.ORDER_STATUS_LABELS.get(order.status, order.status),
            }
            if order
            else None
        ),
        "navigation_url": _navigation_url(stop.latitude, stop.longitude),
    }


def serialize_route_plan(plan, *, include_stops: bool = True) -> dict:
    return {
        "id": plan.id,
        "version": plan.version,
        "status": plan.status,
        "algorithm": plan.algorithm,
        "distance_km": _float(plan.distance_km),
        "duration_minutes": plan.duration_minutes,
        "distance_source": plan.distance_source,
        "geometry": plan.geometry,
        "geometry_source": plan.geometry_source,
        "metrics": plan.metrics or {},
        "created_at": _iso(plan.created_at),
        "activated_at": _iso(plan.activated_at),
        "stops": [serialize_route_stop(stop) for stop in plan.stops]
        if include_stops
        else [],
    }


def active_route_plan(batch):
    if batch is None:
        return None
    for plan in batch.route_plans:
        if plan.status == domain.ROUTE_ACTIVE:
            return plan
    return batch.route_plans[-1] if batch.route_plans else None


def serialize_batch_summary(batch) -> dict:
    links = [link for link in batch.order_links if link.removed_at is None]
    orders = [link.order for link in links if link.order is not None]
    plan = active_route_plan(batch)
    stops = plan.stops if plan else []
    return {
        "id": batch.id,
        "batch_number": batch.batch_number,
        "status": batch.status,
        "status_label": domain.BATCH_STATUS_LABELS.get(batch.status, batch.status),
        "driver": (
            {"id": batch.driver.id, "full_name": batch.driver.full_name}
            if batch.driver
            else None
        ),
        "vehicle": serialize_vehicle(batch.vehicle) if batch.vehicle else None,
        "service_area": serialize_service_area(batch.service_area)
        if batch.service_area
        else None,
        "planned_start": _iso(batch.planned_start),
        "planned_end": _iso(batch.planned_end),
        "started_at": _iso(batch.started_at),
        "completed_at": _iso(batch.completed_at),
        "order_count": len(orders),
        "pickup_count": sum(1 for stop in stops if stop.kind == domain.STOP_PICKUP),
        "delivery_count": sum(1 for stop in stops if stop.kind == domain.STOP_DELIVERY),
        "completed_stops": sum(
            1 for stop in stops if stop.status == domain.STOP_COMPLETED
        ),
        "total_stops": len(stops),
        "distance_km": _float(batch.distance_km),
        "duration_minutes": batch.duration_minutes,
        "distance_source": batch.distance_source,
        "geometry_source": batch.geometry_source,
        "algorithm": batch.algorithm,
        "route_plan_id": plan.id if plan else None,
    }


def serialize_batch(batch, *, include_orders: bool = True) -> dict:
    data = serialize_batch_summary(batch)
    plan = active_route_plan(batch)
    data["route_plan"] = serialize_route_plan(plan) if plan else None
    data["geometry"] = batch.geometry
    data["explanation"] = batch.explanation or {}
    data["notes"] = batch.notes
    if include_orders:
        links = [link for link in batch.order_links if link.removed_at is None]
        data["orders"] = [
            serialize_order_summary(link.order) for link in links if link.order is not None
        ]
    return data


def serialize_proof_media(row) -> dict:
    asset = row.media
    return {
        "id": row.id,
        "order_id": row.order_id,
        "order_number": row.order.order_number if row.order else None,
        "service_type": row.order.service_type if row.order else None,
        "order_status": row.order.status if row.order else None,
        "driver": (
            {"id": row.driver.id, "full_name": row.driver.full_name}
            if row.driver
            else None
        ),
        "proof_type": row.proof_type,
        "verification_status": row.verification_status,
        "captured_at": _iso(row.captured_at),
        "received_at": _iso(row.received_at),
        "location": {
            "latitude": _float(row.latitude),
            "longitude": _float(row.longitude),
            "accuracy_m": _float(row.accuracy_m),
            "distance_from_stop_m": _float(row.distance_from_stop_m),
        },
        "image_url": _media_url(asset),
        "notes": row.notes,
        "verified_at": _iso(row.verified_at),
        "verified_by": (
            {"id": row.verified_by.id, "full_name": row.verified_by.full_name}
            if row.verified_by
            else None
        ),
    }


def serialize_matching_suggestion(row, *, include_order: bool = True) -> dict:
    data = {
        "id": row.id,
        "status": row.status,
        "score": _float(row.score),
        "detour_km": _float(row.detour_km),
        "added_duration_minutes": _float(row.added_duration_minutes),
        "distance_source": row.distance_source,
        "capacity_snapshot": row.capacity_snapshot or {},
        "reasons": row.reasons or [],
        "blockers": row.blockers or [],
        "proposed_sequence": row.proposed_sequence or [],
        "batch_id": row.batch_id,
        "route_plan_id": row.route_plan_id,
        "driver": (
            {
                "id": row.driver.id,
                "full_name": row.driver.full_name,
                "phone": row.driver.phone,
                "email": row.driver.email,
            }
            if row.driver
            else None
        ),
        "reviewed_by": (
            {"id": row.reviewed_by.id, "full_name": row.reviewed_by.full_name}
            if row.reviewed_by
            else None
        ),
        "reviewed_at": _iso(row.reviewed_at),
        "decision_note": row.decision_note,
        "rejection_code": row.rejection_code,
        "expires_at": _iso(row.expires_at),
        "created_at": _iso(row.created_at),
    }
    if include_order and row.order is not None:
        data["order"] = serialize_order_summary(row.order, include_consumer=True)
    return data


def serialize_delivery_exception(row) -> dict:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "order_number": row.order.order_number if row.order else None,
        "driver": (
            {"id": row.driver.id, "full_name": row.driver.full_name}
            if row.driver
            else None
        ),
        "batch_id": row.batch_id,
        "exception_type": row.exception_type,
        "description": row.description,
        "status": row.status,
        "resolution_note": row.resolution_note,
        "resolved_by": (
            {"id": row.resolved_by.id, "full_name": row.resolved_by.full_name}
            if row.resolved_by
            else None
        ),
        "resolved_at": _iso(row.resolved_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
