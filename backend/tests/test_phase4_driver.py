"""Phase 4: driver duty, location, route, pickup and delivery proof."""
from __future__ import annotations

from datetime import timedelta

from app import domain
from app.extensions import db
from app.models import (
    BatchOrder,
    DeliveryBatch,
    DeliveryException,
    DeliveryProof,
    DriverAssignment,
    DriverDutySession,
    DriverLocationEvent,
    DriverProfile,
    DriverServiceArea,
    Order,
    PickupProof,
    RoutePlan,
    RouteStop,
    ServiceArea,
    Vehicle,
    VehicleCapacityProfile,
)
from app.services.orders import create_order, record_status
from tests.conftest import make_user

PICKUP = {"latitude": 22.58, "longitude": 88.41}
DELIVERY = {"latitude": 22.59, "longitude": 88.42}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _service_area(name="Salt Lake", *, lat=22.58, lng=88.41, radius=15):
    area = ServiceArea(
        name=name,
        city="Kolkata",
        state="West Bengal",
        postal_codes="700091",
        center_latitude=lat,
        center_longitude=lng,
        radius_km=radius,
    )
    db.session.add(area)
    db.session.commit()
    return area


def _driver(
    email="arjun@example.com",
    *,
    area=None,
    verified=True,
    duty=True,
    heartbeat_age_minutes=0,
    vehicle=False,
):
    user = make_user(email, role="driver")
    profile = DriverProfile(
        user_id=user.id,
        verification_status=(
            domain.VERIFICATION_VERIFIED if verified else domain.VERIFICATION_PENDING
        ),
    )
    db.session.add(profile)
    db.session.flush()
    if area is not None:
        db.session.add(DriverServiceArea(driver_id=profile.id, service_area_id=area.id))

    vehicle_row = None
    if vehicle:
        capacity = VehicleCapacityProfile.query.filter_by(vehicle_type="car").first()
        vehicle_row = Vehicle(
            driver_id=profile.id,
            capacity_profile_id=capacity.id,
            vehicle_type="car",
            registration_number="WB-04-AB-1234",
            verification_status=domain.VERIFICATION_VERIFIED,
            is_active=True,
        )
        db.session.add(vehicle_row)

    session_row = None
    if duty:
        now = domain.utcnow()
        session_row = DriverDutySession(
            driver_id=profile.id,
            status=domain.DUTY_AVAILABLE,
            started_at=now - timedelta(hours=1),
            last_heartbeat_at=now - timedelta(minutes=heartbeat_age_minutes),
        )
        db.session.add(session_row)
    db.session.commit()
    return user, profile, session_row, vehicle_row


def _order_payload():
    now = domain.utcnow()
    start = (now + timedelta(hours=1)).replace(microsecond=0)
    return {
        "service_type": "parcel",
        "pickup": {
            "contact_name": "Riya Sen",
            "contact_phone": "9830000001",
            "address_line": "12 Lake Road",
            "area": "Salt Lake",
            "city": "Kolkata",
            **PICKUP,
        },
        "delivery": {
            "contact_name": "Amit Das",
            "contact_phone": "9830000002",
            "address_line": "44 Park Street",
            "area": "Salt Lake",
            "city": "Kolkata",
            **DELIVERY,
        },
        "parcel": {
            "name": "Textbooks",
            "description": "Three hardcover books",
            "category": "books",
            "quantity": 1,
            "weight_kg": 2.5,
            "length_cm": 30,
            "width_cm": 20,
            "height_cm": 10,
            "is_fragile": False,
        },
        "pickup_window_start": start.isoformat(),
        "pickup_window_end": (start + timedelta(hours=2)).isoformat(),
        "delivery_deadline": (start + timedelta(days=1)).isoformat(),
        "service_notes": "Ring twice",
    }


def _make_order(consumer, **overrides):
    order = create_order(consumer, _order_payload())
    for key, value in overrides.items():
        setattr(order, key, value)
    db.session.commit()
    return order


def _advance(order, *statuses, actor=None):
    for status in statuses:
        record_status(order, status, actor=actor, source="test")
    db.session.commit()
    return order


def _assign(order, driver_user, *, manager=None, batch=None, vehicle=None):
    if order.status == domain.ORDER_PENDING_REVIEW:
        _advance(order, domain.ORDER_AWAITING_ASSIGNMENT)
    if order.status == domain.ORDER_AWAITING_ASSIGNMENT:
        _advance(order, domain.ORDER_ASSIGNED)
    assignment = DriverAssignment(
        order_id=order.id,
        driver_id=driver_user.id,
        assigned_by_id=manager.id if manager else None,
        batch_id=batch.id if batch else None,
        vehicle_id=vehicle.id if vehicle else None,
        status="active",
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


def _batch_for(orders, driver_user, *, manager=None, area=None, vehicle=None):
    now = domain.utcnow()
    batch = DeliveryBatch(
        batch_number=f"RTB-TEST-{driver_user.id}",
        status=domain.BATCH_ASSIGNED,
        driver_id=driver_user.id,
        manager_id=manager.id if manager else None,
        vehicle_id=vehicle.id if vehicle else None,
        service_area_id=area.id if area else None,
        planned_start=now,
        planned_end=now + timedelta(hours=4),
        distance_km=4.2,
        duration_minutes=25,
        distance_source="estimated",
        geometry_source="estimated",
        algorithm="insertion heuristic",
        explanation={"note": "test route"},
    )
    db.session.add(batch)
    db.session.flush()

    plan = RoutePlan(
        batch_id=batch.id,
        version=1,
        status=domain.ROUTE_ACTIVE,
        distance_km=4.2,
        duration_minutes=25,
        distance_source="estimated",
        geometry_source="estimated",
        metrics={"stop_count": len(orders) * 2},
        activated_at=now,
    )
    db.session.add(plan)
    db.session.flush()

    sequence = 1
    for order in orders:
        db.session.add(BatchOrder(batch_id=batch.id, order_id=order.id))
        for kind, address in (
            (domain.STOP_PICKUP, order.pickup_address),
            (domain.STOP_DELIVERY, order.delivery_address),
        ):
            db.session.add(
                RouteStop(
                    route_plan_id=plan.id,
                    order_id=order.id,
                    kind=kind,
                    sequence=sequence,
                    label=f"{kind.title()} {order.order_number}",
                    contact_name=address.contact_name,
                    contact_phone=address.contact_phone,
                    address_line=address.address_line,
                    area=address.area,
                    city=address.city,
                    latitude=address.latitude,
                    longitude=address.longitude,
                    planned_arrival=now + timedelta(minutes=sequence * 10),
                    planned_departure=now + timedelta(minutes=sequence * 10 + 6),
                    status=domain.STOP_PENDING,
                )
            )
            sequence += 1
    db.session.commit()
    return batch, plan


def _capture_form(**overrides):
    now = domain.utcnow()
    form = {
        "latitude": str(DELIVERY["latitude"]),
        "longitude": str(DELIVERY["longitude"]),
        "accuracy_m": "12",
        "captured_at": now.isoformat(),
        "capture_source": "device_camera",
        "recipient_name": "Amit Das",
        "notes": "Handed to recipient at the door.",
    }
    form.update(overrides)
    return form


# --------------------------------------------------------------------------- #
# Duty and location
# --------------------------------------------------------------------------- #
def test_duty_requires_verification_and_tracks_heartbeats(session, db, reference_data):
    _area = _service_area()
    user, profile, _session_row, _vehicle = _driver(verified=False, duty=False)
    session.login(user.email)

    blocked = session.post("/api/v1/driver/duty/start", {"status": "available"})
    assert blocked.status_code == 403
    assert blocked.get_json()["error"]["code"] == "driver_not_verified"

    profile.verification_status = domain.VERIFICATION_VERIFIED
    db.session.commit()
    started = session.post(
        "/api/v1/driver/duty/start",
        {"status": "available", "device_label": "Pixel 8", **PICKUP},
    )
    assert started.status_code == 201, started.get_json()
    duty = started.get_json()["data"]
    assert duty["status"] == "available"
    assert duty["ended_at"] is None
    assert duty["start_location"]["latitude"] == PICKUP["latitude"]

    status_response = session.get("/api/v1/driver/duty")
    assert status_response.status_code == 200
    assert status_response.get_json()["data"]["is_live"] is True

    changed = session.post("/api/v1/driver/duty/status", {"status": "on_break"})
    assert changed.status_code == 200
    assert changed.get_json()["data"]["status"] == "on_break"

    invalid = session.post("/api/v1/driver/duty/status", {"status": "sleeping"})
    assert invalid.status_code == 422

    heartbeat = session.post(
        "/api/v1/driver/duty/heartbeat",
        {"latitude": 22.581, "longitude": 88.411, "accuracy_m": 8},
    )
    assert heartbeat.status_code == 200
    assert DriverLocationEvent.query.count() == 1

    ended = session.post(
        "/api/v1/driver/duty/end",
        {"reason": "Shift complete", **PICKUP},
    )
    assert ended.status_code == 200
    assert ended.get_json()["data"]["ended_at"] is not None
    assert ended.get_json()["data"]["end_location"]["latitude"] == PICKUP["latitude"]

    again = session.post("/api/v1/driver/duty/end", {})
    assert again.status_code == 409
    assert again.get_json()["error"]["code"] == "not_on_duty"


def test_duty_end_is_blocked_while_parcels_are_assigned(session, db, reference_data):
    area = _service_area()
    driver, _profile, duty_row, _vehicle = _driver(area=area)
    consumer = make_user("consumer@example.com")
    order = _make_order(consumer)
    _assign(order, driver)

    session.login(driver.email)
    response = session.post("/api/v1/driver/duty/end", {"reason": "Leaving"})
    assert response.status_code == 409
    error = response.get_json()["error"]
    assert error["code"] == "active_assignments"
    assert error["details"]["active_assignments"] == 1
    assert db.session.get(DriverDutySession, duty_row.id).ended_at is None


def test_location_requires_consent_and_a_live_session(session, db, reference_data):
    user, _profile, _duty, _vehicle = _driver()
    session.login(user.email)

    no_consent = session.post("/api/v1/driver/location", {**PICKUP, "accuracy_m": 10})
    assert no_consent.status_code == 403
    assert no_consent.get_json()["error"]["code"] == "location_consent_required"

    accepted = session.post(
        "/api/v1/driver/location",
        {"consent_granted": True, **PICKUP, "accuracy_m": 10},
    )
    assert accepted.status_code == 201, accepted.get_json()
    payload = accepted.get_json()["data"]
    assert payload["is_recent"] is True
    assert payload["status_label"] == "Live recent location"
    assert DriverLocationEvent.query.count() == 1

    session.post("/api/v1/driver/duty/end", {})
    stopped = session.post(
        "/api/v1/driver/location",
        {"consent_granted": True, **PICKUP, "accuracy_m": 10},
    )
    assert stopped.status_code == 409
    assert stopped.get_json()["error"]["code"] == "not_on_duty"

    stale_user, _stale_profile, _stale_duty, _vehicle = _driver(
        email="stale@example.com", heartbeat_age_minutes=120
    )
    session.logout()
    session.login(stale_user.email)
    stale = session.post(
        "/api/v1/driver/location",
        {"consent_granted": True, **PICKUP, "accuracy_m": 10},
    )
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "duty_session_stale"


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def test_summary_uses_real_counts_and_history(session, db, reference_data):
    area = _service_area()
    driver, profile, _duty, vehicle = _driver(area=area, vehicle=True)
    consumer = make_user("consumer@example.com")
    active_order = _make_order(consumer)
    _assign(active_order, driver, vehicle=vehicle)

    delivered = _make_order(consumer)
    delivered_assignment = _assign(delivered, driver, vehicle=vehicle)
    _advance(
        delivered,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
        domain.ORDER_IN_TRANSIT,
        domain.ORDER_OUT_FOR_DELIVERY,
        domain.ORDER_DELIVERED,
        actor=driver,
    )
    delivered.delivered_at = domain.utcnow()
    delivered_assignment.status = "completed"
    delivered_assignment.ended_at = domain.utcnow()
    profile.completed_deliveries = 1
    db.session.commit()

    session.login(driver.email)
    located = session.post(
        "/api/v1/driver/location",
        {"consent_granted": True, "latitude": 22.581, "longitude": 88.411, "accuracy_m": 6},
    )
    assert located.status_code == 201

    response = session.get("/api/v1/driver/summary")
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]

    assert data["driver"]["full_name"] == driver.full_name
    assert data["driver"]["completed_deliveries"] == 1
    assert data["vehicle"]["registration_number"] == vehicle.registration_number
    assert data["counts"]["assigned_orders"] == 1
    assert data["counts"]["total_parcels_assigned"] == 1
    assert data["counts"]["remaining_deliveries"] == 1
    assert data["counts"]["pending_pickups"] == 1
    assert data["counts"]["completed_today"] == 1
    assert data["counts"]["completed_total"] == 1
    assert data["counts"]["failed_orders"] == 0
    assert data["last_location"]["is_recent"] is True
    assert data["last_location"]["accuracy_m"] == 6
    # No batch exists, so the route distance is not invented.
    assert data["today"]["route_distance_km"] is None
    assert data["next_stop"]["source"] == "schedule"
    assert data["next_stop"]["kind"] == "pickup"
    assert any(
        row["order_number"] == active_order.order_number for row in data["activity"]
    )
    assert data["generated_at"] is not None


# --------------------------------------------------------------------------- #
# Pickup and delivery proof
# --------------------------------------------------------------------------- #
def test_pickup_and_delivery_require_valid_proof(session, db, reference_data):
    area = _service_area()
    driver, profile, _duty, vehicle = _driver(area=area, vehicle=True)
    consumer = make_user("consumer@example.com")
    order = _make_order(consumer)
    batch, _plan = _batch_for([order], driver, area=area, vehicle=vehicle)
    assignment = _assign(order, driver, batch=batch, vehicle=vehicle)

    session.login(driver.email)
    started = session.post(f"/api/v1/driver/batches/{batch.id}/start", {})
    assert started.status_code == 200

    detail = session.get(f"/api/v1/driver/assignments/{order.id}")
    assert detail.status_code == 200
    assert "accept_assignment" in detail.get_json()["data"]["actions"]
    assert detail.get_json()["data"]["proof_requirements"]["delivery_photo_required"] is True

    accepted = session.post(f"/api/v1/driver/orders/{order.id}/accept", {})
    assert accepted.status_code == 200
    assert accepted.get_json()["data"]["assignment"]["accepted_at"] is not None

    arrived = session.post(f"/api/v1/driver/orders/{order.id}/arrived-pickup", {})
    assert arrived.status_code == 200
    assert arrived.get_json()["data"]["status"] == domain.ORDER_PICKUP_ARRIVED

    pickup = session.post(
        f"/api/v1/driver/orders/{order.id}/pickup",
        {**PICKUP, "accuracy_m": 9, "capture_source": "device_camera"},
    )
    assert pickup.status_code == 200, pickup.get_json()
    assert pickup.get_json()["data"]["status"] == domain.ORDER_PICKED_UP

    departed = session.post(f"/api/v1/driver/orders/{order.id}/depart", {})
    assert departed.status_code == 200
    assert departed.get_json()["data"]["status"] == domain.ORDER_IN_TRANSIT

    out = session.post(f"/api/v1/driver/orders/{order.id}/out-for-delivery", {})
    assert out.status_code == 200
    assert out.get_json()["data"]["status"] == domain.ORDER_OUT_FOR_DELIVERY

    missing = session.post(
        f"/api/v1/driver/orders/{order.id}/delivery-proof",
        {"latitude": DELIVERY["latitude"], "longitude": DELIVERY["longitude"]},
    )
    assert missing.status_code == 422
    assert missing.get_json()["error"]["code"] == "delivery_proof_required"

    gallery = session.post_file(
        f"/api/v1/driver/orders/{order.id}/delivery-proof",
        form=_capture_form(capture_source="gallery"),
    )
    assert gallery.status_code == 422
    error = gallery.get_json()["error"]
    assert error["code"] == "proof_invalid"
    assert "capture_source_not_camera" in error["details"]["reasons"]
    assert error["details"]["corrective_actions"]

    delivered = session.post_file(
        f"/api/v1/driver/orders/{order.id}/delivery-proof",
        form=_capture_form(),
    )
    assert delivered.status_code == 200, delivered.get_json()
    assert delivered.get_json()["data"]["status"] == domain.ORDER_DELIVERED

    db.session.refresh(order)
    assert order.status == domain.ORDER_DELIVERED
    assert order.delivered_at is not None
    proof = DeliveryProof.query.filter_by(order_id=order.id).one()
    assert proof.status == domain.PROOF_VALID
    assert proof.recipient_name == "Amit Das"
    assert proof.proof_media.captured_at is not None
    assert abs(float(proof.proof_media.distance_from_stop_m)) < 5
    assert PickupProof.query.count() == 0  # pickup photo is optional in this workflow
    assert db.session.get(DriverAssignment, assignment.id).status == "completed"
    db.session.refresh(profile)
    assert profile.completed_deliveries == 1

    db.session.refresh(batch)
    assert batch.status == domain.BATCH_COMPLETED
    assert batch.completed_at is not None
    stops = RouteStop.query.filter_by(route_plan_id=batch.route_plans[0].id).all()
    assert {stop.status for stop in stops} == {domain.STOP_COMPLETED}


def test_delivery_proof_rejects_stale_distant_or_imprecise_captures(
    session, db, reference_data
):
    area = _service_area()
    driver, _profile, _duty, _vehicle = _driver(area=area)
    consumer = make_user("consumer@example.com")
    order = _make_order(consumer)
    _assign(order, driver)
    _advance(
        order,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
        domain.ORDER_IN_TRANSIT,
        domain.ORDER_OUT_FOR_DELIVERY,
        actor=driver,
    )

    session.login(driver.email)
    path = f"/api/v1/driver/orders/{order.id}/delivery-proof"

    stale = session.post_file(
        path,
        form=_capture_form(
            captured_at=(domain.utcnow() - timedelta(minutes=90)).isoformat()
        ),
    )
    assert stale.status_code == 422
    assert "capture_too_old" in stale.get_json()["error"]["details"]["reasons"]

    distant = session.post_file(
        path,
        form=_capture_form(latitude="22.70", longitude="88.55"),
    )
    assert distant.status_code == 422
    assert "too_far_from_stop" in distant.get_json()["error"]["details"]["reasons"]

    imprecise = session.post_file(path, form=_capture_form(accuracy_m="900"))
    assert imprecise.status_code == 422
    assert "accuracy_too_low" in imprecise.get_json()["error"]["details"]["reasons"]

    db.session.refresh(order)
    assert order.status == domain.ORDER_OUT_FOR_DELIVERY
    assert DeliveryProof.query.count() == 0


def test_exception_parks_order_in_proof_pending_without_faking_delivery(
    session, db, reference_data
):
    area = _service_area()
    driver, _profile, _duty, _vehicle = _driver(area=area)
    consumer = make_user("consumer@example.com")
    order = _make_order(consumer)
    _assign(order, driver)
    _advance(
        order,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
        domain.ORDER_IN_TRANSIT,
        domain.ORDER_OUT_FOR_DELIVERY,
        actor=driver,
    )

    session.login(driver.email)
    response = session.post(
        f"/api/v1/driver/orders/{order.id}/exception",
        {
            "exception_type": "proof_capture_failed",
            "description": "Camera failed at the door, so no photograph could be taken.",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()["data"]
    assert data["order"]["status"] == domain.ORDER_PROOF_PENDING
    assert data["exception"]["status"] == domain.EXCEPTION_OPEN
    assert DeliveryException.query.filter_by(order_id=order.id).count() == 1
    assert DeliveryProof.query.count() == 0

    db.session.refresh(order)
    assert order.status == domain.ORDER_PROOF_PENDING

    delivered = session.post_file(
        f"/api/v1/driver/orders/{order.id}/delivery-proof",
        form=_capture_form(notes="Recovered camera and captured proof."),
    )
    assert delivered.status_code == 200, delivered.get_json()
    assert delivered.get_json()["data"]["status"] == domain.ORDER_DELIVERED


# --------------------------------------------------------------------------- #
# Isolation
# --------------------------------------------------------------------------- #
def test_driver_cannot_act_on_another_drivers_assignment(session, db, reference_data):
    area = _service_area()
    owner, _owner_profile, _owner_duty, owner_vehicle = _driver(
        email="owner@example.com", area=area, vehicle=True
    )
    other, _other_profile, _other_duty, _other_vehicle = _driver(
        email="other@example.com", area=area
    )
    consumer = make_user("consumer@example.com")
    order = _make_order(consumer)
    batch, _plan = _batch_for([order], owner, area=area, vehicle=owner_vehicle)
    _assign(order, owner, batch=batch, vehicle=owner_vehicle)

    session.login(other.email)
    assert session.get(f"/api/v1/driver/assignments/{order.id}").status_code == 404
    for path in (
        f"/api/v1/driver/orders/{order.id}/accept",
        f"/api/v1/driver/orders/{order.id}/pickup",
        f"/api/v1/driver/batches/{batch.id}/start",
    ):
        assert session.post(path, {}).status_code == 404
    assert session.get(f"/api/v1/driver/batches/{batch.id}").status_code == 404


# --------------------------------------------------------------------------- #
# Batches and route
# --------------------------------------------------------------------------- #
def test_batch_route_exposes_real_estimated_geometry_and_completion_gate(
    session, db, reference_data
):
    area = _service_area()
    driver, _profile, _duty, vehicle = _driver(area=area, vehicle=True)
    consumer = make_user("consumer@example.com")
    first = _make_order(consumer)
    second = _make_order(consumer)
    batch, plan = _batch_for([first, second], driver, area=area, vehicle=vehicle)
    _assign(first, driver, batch=batch, vehicle=vehicle)
    _assign(second, driver, batch=batch, vehicle=vehicle)

    session.login(driver.email)
    listing = session.get("/api/v1/driver/batches")
    assert listing.status_code == 200
    assert listing.get_json()["meta"]["total"] == 1
    summary = listing.get_json()["data"][0]
    assert summary["order_count"] == 2
    assert summary["pickup_count"] == 2
    assert summary["delivery_count"] == 2
    assert summary["completed_stops"] == 0
    assert summary["total_stops"] == 4
    assert summary["distance_km"] == 4.2
    assert summary["distance_source"] == "estimated"

    detail = session.get(f"/api/v1/driver/batches/{batch.id}")
    assert detail.status_code == 200
    payload = detail.get_json()["data"]
    assert payload["geometry_source"] == "estimated"
    assert payload["route_plan"]["id"] == plan.id
    assert len(payload["route_plan"]["stops"]) == 4
    assert all(
        stop["navigation_url"].startswith("https://www.google.com/maps/dir/?api=1")
        for stop in payload["route_plan"]["stops"]
    )
    assert [stop["sequence"] for stop in payload["route_plan"]["stops"]] == [1, 2, 3, 4]

    started = session.post(f"/api/v1/driver/batches/{batch.id}/start", {})
    assert started.status_code == 200
    assert started.get_json()["data"]["status"] == domain.BATCH_ACTIVE

    blocked = session.post(f"/api/v1/driver/batches/{batch.id}/complete", {})
    assert blocked.status_code == 409
    assert blocked.get_json()["error"]["code"] == "batch_has_open_orders"

    for order in (first, second):
        _advance(
            order,
            domain.ORDER_PICKUP_SCHEDULED,
            domain.ORDER_PICKUP_ARRIVED,
            domain.ORDER_PICKED_UP,
            domain.ORDER_IN_TRANSIT,
            domain.ORDER_OUT_FOR_DELIVERY,
            domain.ORDER_DELIVERED,
            actor=driver,
        )

    completed = session.post(f"/api/v1/driver/batches/{batch.id}/complete", {})
    assert completed.status_code == 200
    assert completed.get_json()["data"]["status"] == domain.BATCH_COMPLETED
    assert completed.get_json()["data"]["completed_at"] is not None
