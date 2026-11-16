"""Phase 5: manager dispatch, driver monitoring, batches and on-route matching."""
from __future__ import annotations

from datetime import timedelta

from app import domain
from app.extensions import db
from app.models import (
    BatchOrder,
    DeliveryBatch,
    DriverAssignment,
    DriverDutySession,
    DriverLocationEvent,
    DriverProfile,
    DriverServiceArea,
    ManagerProfile,
    ManagerServiceArea,
    MatchingSuggestion,
    Notification,
    Order,
    RoutePlan,
    ServiceArea,
    Vehicle,
    VehicleCapacityProfile,
)
from app.services.orders import create_order, record_status
from tests.conftest import make_user

P1 = {"latitude": 22.58, "longitude": 88.41}
D1 = {"latitude": 22.62, "longitude": 88.41}
P2 = {"latitude": 22.60, "longitude": 88.41}
D2 = {"latitude": 22.63, "longitude": 88.41}
FAR = {"latitude": 22.58, "longitude": 88.49}


# --------------------------------------------------------------------------- #
# Fixtures helpers
# --------------------------------------------------------------------------- #
def _area(name="Salt Lake", *, lat=22.60, lng=88.41, radius=6):
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


def _manager(email="manager@example.com", areas=()):
    user = make_user(email, role="manager")
    profile = ManagerProfile(user_id=user.id, employee_code=f"M-{user.id}")
    db.session.add(profile)
    db.session.flush()
    for area in areas:
        db.session.add(ManagerServiceArea(manager_id=profile.id, service_area_id=area.id))
    db.session.commit()
    return user


def _driver(
    email="driver@example.com",
    area=None,
    *,
    vehicle_type="car",
    duty=True,
    duty_status=domain.DUTY_AVAILABLE,
    heartbeat_age_minutes=0,
    verified=True,
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
    capacity = VehicleCapacityProfile.query.filter_by(vehicle_type=vehicle_type).first()
    vehicle = Vehicle(
        driver_id=profile.id,
        capacity_profile_id=capacity.id,
        vehicle_type=vehicle_type,
        registration_number=f"WB-{user.id}-{vehicle_type}",
        verification_status=domain.VERIFICATION_VERIFIED,
        is_active=True,
    )
    db.session.add(vehicle)
    session_row = None
    if duty:
        now = domain.utcnow()
        session_row = DriverDutySession(
            driver_id=profile.id,
            status=duty_status,
            started_at=now - timedelta(hours=1),
            last_heartbeat_at=now - timedelta(minutes=heartbeat_age_minutes),
        )
        db.session.add(session_row)
    db.session.commit()
    return user, profile, vehicle


def _locate(profile, point, *, age_minutes=0):
    now = domain.utcnow()
    db.session.add(
        DriverLocationEvent(
            driver_id=profile.id,
            latitude=point["latitude"],
            longitude=point["longitude"],
            accuracy_m=10,
            recorded_at=now - timedelta(minutes=age_minutes),
            received_at=now - timedelta(minutes=age_minutes),
        )
    )
    db.session.commit()


def _order(
    consumer,
    pickup,
    delivery,
    *,
    area_name="Salt Lake",
    weight_kg=2.5,
    dimensions=(30, 20, 10),
    name="Parcel",
):
    now = domain.utcnow()
    start = (now - timedelta(minutes=2)).replace(microsecond=0)
    payload = {
        "service_type": "parcel",
        "pickup": {
            "contact_name": "Riya Sen",
            "contact_phone": "9830000001",
            "address_line": "12 Lake Road",
            "area": area_name,
            "city": "Kolkata",
            **pickup,
        },
        "delivery": {
            "contact_name": "Amit Das",
            "contact_phone": "9830000002",
            "address_line": "44 Park Street",
            "area": "Salt Lake",
            "city": "Kolkata",
            **delivery,
        },
        "parcel": {
            "name": name,
            "category": "general",
            "quantity": 1,
            "weight_kg": weight_kg,
            "length_cm": dimensions[0],
            "width_cm": dimensions[1],
            "height_cm": dimensions[2],
        },
        "pickup_window_start": start.isoformat(),
        "pickup_window_end": (start + timedelta(hours=3)).isoformat(),
        "delivery_deadline": (start + timedelta(days=1)).isoformat(),
    }
    order = create_order(consumer, payload)
    db.session.commit()
    return order


def _approve(order):
    record_status(order, domain.ORDER_AWAITING_ASSIGNMENT, source="test")
    db.session.commit()
    return order


# --------------------------------------------------------------------------- #
# Scope
# --------------------------------------------------------------------------- #
def test_manager_queue_is_scoped_to_service_areas(session, db, reference_data):
    salt = _area("Salt Lake")
    _area("New Town", lat=22.58, lng=88.49, radius=4)
    manager = _manager(areas=[salt])
    consumer = make_user("consumer@example.com")
    inside = _order(consumer, P1, D1)
    outside = _order(consumer, FAR, D1, area_name="New Town")

    session.login(manager.email)
    listing = session.get("/api/v1/manager/orders")
    assert listing.status_code == 200, listing.get_json()
    ids = {row["id"] for row in listing.get_json()["data"]}
    assert inside.id in ids
    assert outside.id not in ids
    assert listing.get_json()["meta"]["total"] == 1

    hidden = session.get(f"/api/v1/manager/orders/{outside.id}")
    assert hidden.status_code == 403
    blocked = session.post(
        f"/api/v1/manager/orders/{outside.id}/review", {"decision": "approve"}
    )
    assert blocked.status_code == 403

    driver, _profile, _vehicle = _driver(area=salt)
    session.logout()
    session.login(driver.email)
    assert session.get("/api/v1/manager/orders").status_code == 403
    assert session.get("/api/v1/manager/summary").status_code == 403


# --------------------------------------------------------------------------- #
# Review and manual assignment
# --------------------------------------------------------------------------- #
def test_order_review_approves_or_rejects_with_reasons(session, db, reference_data):
    area = _area()
    manager = _manager(areas=[area])
    consumer = make_user("consumer@example.com")
    approved_order = _order(consumer, P1, D1)
    rejected_order = _order(consumer, P2, D2)

    session.login(manager.email)
    approved = session.post(
        f"/api/v1/manager/orders/{approved_order.id}/review",
        {"decision": "approve", "reason": "Address and parcel confirmed"},
    )
    assert approved.status_code == 200, approved.get_json()
    assert approved.get_json()["data"]["order"]["status"] == domain.ORDER_AWAITING_ASSIGNMENT
    db.session.refresh(approved_order)
    assert approved_order.approved_at is not None
    assert approved_order.approved_by_id == manager.id

    missing_reason = session.post(
        f"/api/v1/manager/orders/{rejected_order.id}/review", {"decision": "reject"}
    )
    assert missing_reason.status_code == 422
    assert "reason" in missing_reason.get_json()["error"]["fields"]

    rejected = session.post(
        f"/api/v1/manager/orders/{rejected_order.id}/review",
        {"decision": "reject", "reason": "Pickup address could not be verified"},
    )
    assert rejected.status_code == 200, rejected.get_json()
    assert rejected.get_json()["data"]["order"]["status"] == domain.ORDER_CANCELLED
    db.session.refresh(rejected_order)
    assert rejected_order.cancellation_reason == "Pickup address could not be verified"

    already_reviewed = session.post(
        f"/api/v1/manager/orders/{approved_order.id}/review", {"decision": "approve"}
    )
    assert already_reviewed.status_code == 409
    assert already_reviewed.get_json()["error"]["code"] == "order_not_in_review"


def test_manual_assignment_enforces_duty_and_notifies_the_driver(
    session, db, reference_data
):
    area = _area()
    manager = _manager(areas=[area])
    consumer = make_user("consumer@example.com")
    order = _order(consumer, P1, D1)
    _approve(order)
    off_duty, _p1, _v1 = _driver("offduty@example.com", area, duty=False)
    on_duty, _p2, _v2 = _driver("onduty@example.com", area)

    session.login(manager.email)
    blocked = session.post(
        f"/api/v1/manager/orders/{order.id}/assign", {"driver_id": off_duty.id}
    )
    assert blocked.status_code == 409, blocked.get_json()
    error = blocked.get_json()["error"]
    assert error["code"] == "driver_not_eligible"
    codes = {row["code"] for row in error["details"]["blockers"]}
    assert "driver_off_duty" in codes
    assert DriverAssignment.query.count() == 0

    assigned = session.post(
        f"/api/v1/manager/orders/{order.id}/assign",
        {"driver_id": on_duty.id, "reason": "Closest available car"},
    )
    assert assigned.status_code == 200, assigned.get_json()
    payload = assigned.get_json()["data"]
    assert payload["order"]["status"] == domain.ORDER_ASSIGNED
    assert payload["assignment"]["driver"]["id"] == on_duty.id
    assignment = DriverAssignment.query.filter_by(order_id=order.id).one()
    assert assignment.status == "active"
    assert assignment.assigned_by_id == manager.id
    assert Notification.query.filter_by(user_id=on_duty.id).count() == 1


# --------------------------------------------------------------------------- #
# Batches
# --------------------------------------------------------------------------- #
def test_batch_proposal_and_creation_enforce_vehicle_capacity(
    session, db, reference_data
):
    area = _area()
    manager = _manager(areas=[area])
    consumer = make_user("consumer@example.com")
    heavy = _order(consumer, P1, D1, weight_kg=40, dimensions=(80, 50, 45), name="Desk")
    _approve(heavy)
    bike, _bp, _bv = _driver("bike@example.com", area, vehicle_type="bike")
    van, _vp, _vv = _driver("van@example.com", area, vehicle_type="van")

    session.login(manager.email)
    proposal = session.post(
        "/api/v1/manager/batches/proposal", {"order_ids": [heavy.id]}
    )
    assert proposal.status_code == 200, proposal.get_json()
    data = proposal.get_json()["data"]
    by_driver = {row["driver"]["id"]: row for row in data["candidates"]}
    assert by_driver[bike.id]["compatible"] is False
    bike_codes = {row["code"] for row in by_driver[bike.id]["blockers"]}
    assert "vehicle_capacity_exceeded" in bike_codes
    assert by_driver[van.id]["compatible"] is True
    assert data["compatible"] is True

    rejected = session.post(
        "/api/v1/manager/batches", {"order_ids": [heavy.id], "driver_id": bike.id}
    )
    assert rejected.status_code == 409
    assert rejected.get_json()["error"]["code"] == "driver_not_eligible"

    created = session.post(
        "/api/v1/manager/batches", {"order_ids": [heavy.id], "driver_id": van.id}
    )
    assert created.status_code == 201, created.get_json()
    batch = created.get_json()["data"]
    assert batch["status"] == domain.BATCH_ASSIGNED
    assert batch["driver"]["id"] == van.id
    assert batch["route_plan"]["stops"]
    row = db.session.get(DeliveryBatch, batch["id"])
    assert BatchOrder.query.filter_by(batch_id=row.id).count() == 1
    assert DriverAssignment.query.filter_by(batch_id=row.id, status="active").count() == 1
    db.session.refresh(heavy)
    assert heavy.status == domain.ORDER_ASSIGNED


def test_batch_can_be_reassigned_with_a_reason_and_rebuilds_the_route(
    session, db, reference_data
):
    area = _area()
    manager = _manager(areas=[area])
    consumer = make_user("consumer@example.com")
    order = _order(consumer, P1, D1)
    _approve(order)
    first, _fp, _fv = _driver("first@example.com", area)
    second, _sp, _sv = _driver("second@example.com", area)

    session.login(manager.email)
    created = session.post(
        "/api/v1/manager/batches", {"order_ids": [order.id], "driver_id": first.id}
    )
    assert created.status_code == 201, created.get_json()
    batch_id = created.get_json()["data"]["id"]

    no_reason = session.post(
        f"/api/v1/manager/batches/{batch_id}/assign-driver",
        {"driver_id": second.id},
    )
    assert no_reason.status_code == 422

    moved = session.post(
        f"/api/v1/manager/batches/{batch_id}/assign-driver",
        {"driver_id": second.id, "reason": "First driver vehicle unavailable"},
    )
    assert moved.status_code == 200, moved.get_json()
    assert moved.get_json()["data"]["driver"]["id"] == second.id
    batch = db.session.get(DeliveryBatch, batch_id)
    assert batch.driver_id == second.id
    active = DriverAssignment.query.filter_by(order_id=order.id, status="active").one()
    assert active.driver_id == second.id
    old = DriverAssignment.query.filter_by(order_id=order.id, status="reassigned").one()
    assert old.driver_id == first.id
    plans = RoutePlan.query.filter_by(batch_id=batch_id).all()
    assert max(plan.version for plan in plans) >= 2
    assert sum(1 for plan in plans if plan.status == domain.ROUTE_ACTIVE) == 1


# --------------------------------------------------------------------------- #
# Route-aware matching
# --------------------------------------------------------------------------- #
def test_on_route_order_produces_an_explainable_suggestion_that_extends_the_route(
    session, db, reference_data
):
    area = _area()
    manager = _manager(areas=[area])
    driver, profile, _vehicle = _driver(area=area)
    _locate(profile, P1)
    consumer = make_user("consumer@example.com")
    first = _order(consumer, P1, D1)
    _approve(first)

    session.login(manager.email)
    created = session.post(
        "/api/v1/manager/batches", {"order_ids": [first.id], "driver_id": driver.id}
    )
    assert created.status_code == 201, created.get_json()
    batch_id = created.get_json()["data"]["id"]

    session.logout()
    session.login(driver.email)
    started = session.post(f"/api/v1/driver/batches/{batch_id}/start", {})
    assert started.status_code == 200, started.get_json()

    second = _order(consumer, P2, D2, name="Documents")
    _approve(second)

    session.logout()
    session.login(manager.email)
    scan = session.post(
        "/api/v1/manager/matching/scan", {"order_ids": [second.id]}
    )
    assert scan.status_code == 200, scan.get_json()
    result = scan.get_json()["data"][0]
    assert result["suggestions_created"] == 1, result
    evaluation = next(
        row for row in result["evaluations"] if row["driver"]["id"] == driver.id
    )
    assert evaluation["compatible"] is True, evaluation["blockers"]
    assert 0 <= evaluation["detour_km"] < 6
    assert evaluation["proposed_distance_km"] > evaluation["current_distance_km"]

    suggestions = session.get(
        f"/api/v1/manager/matching/suggestions?order_id={second.id}"
    )
    assert suggestions.status_code == 200
    rows = suggestions.get_json()["data"]
    assert len(rows) == 1
    suggestion = rows[0]
    assert suggestion["status"] == domain.SUGGESTION_PENDING
    assert suggestion["driver"]["id"] == driver.id
    assert suggestion["reasons"]
    assert suggestion["detour_km"] < 6
    sequence = suggestion["proposed_sequence"]
    pickup_index = next(
        row["sequence"]
        for row in sequence
        if row["order_id"] == second.id and row["kind"] == domain.STOP_PICKUP
    )
    delivery_index = next(
        row["sequence"]
        for row in sequence
        if row["order_id"] == second.id and row["kind"] == domain.STOP_DELIVERY
    )
    assert pickup_index < delivery_index

    approved = session.post(
        f"/api/v1/manager/matching/suggestions/{suggestion['id']}/approve"
    )
    assert approved.status_code == 200, approved.get_json()
    payload = approved.get_json()["data"]
    assert payload["suggestion"]["status"] == domain.SUGGESTION_APPROVED
    assert payload["order"]["status"] == domain.ORDER_ASSIGNED
    assert payload["assignment"]["driver"]["id"] == driver.id
    db.session.refresh(second)
    assert second.status == domain.ORDER_ASSIGNED
    assert BatchOrder.query.filter_by(batch_id=batch_id).filter(
        BatchOrder.removed_at.is_(None)
    ).count() == 2
    plans = RoutePlan.query.filter_by(batch_id=batch_id).order_by(RoutePlan.version).all()
    assert [plan.version for plan in plans] == [1, 2]
    assert plans[0].status == domain.ROUTE_SUPERSEDED
    assert plans[1].status == domain.ROUTE_ACTIVE
    assert any(stop.order_id == second.id for stop in plans[1].stops)
    assert MatchingSuggestion.query.filter_by(order_id=second.id).one().status == (
        domain.SUGGESTION_APPROVED
    )


def test_matching_reports_capacity_dimension_and_duty_rejections(
    session, db, reference_data
):
    area = _area()
    manager = _manager(areas=[area])
    bike, _bp, _bv = _driver("bike@example.com", area, vehicle_type="bike")
    off_duty, _op, _ov = _driver("off@example.com", area, duty=False)
    consumer = make_user("consumer@example.com")
    heavy = _order(consumer, P1, D1, weight_kg=40, dimensions=(80, 50, 45))
    _approve(heavy)

    session.login(manager.email)
    scan = session.post("/api/v1/manager/matching/scan", {"order_ids": [heavy.id]})
    assert scan.status_code == 200, scan.get_json()
    result = scan.get_json()["data"][0]
    assert result["suggestions_created"] == 0
    evaluations = {row["driver"]["id"]: row for row in result["evaluations"]}
    bike_codes = {row["code"] for row in evaluations[bike.id]["blockers"]}
    assert "vehicle_capacity_exceeded" in bike_codes
    assert "parcel_dimension_exceeded" in bike_codes
    off_codes = {row["code"] for row in evaluations[off_duty.id]["blockers"]}
    assert "driver_off_duty" in off_codes

    oversized = _order(consumer, P1, D1, weight_kg=3, dimensions=(200, 30, 20))
    _approve(oversized)
    scan = session.post(
        "/api/v1/manager/matching/scan", {"order_ids": [oversized.id]}
    )
    assert scan.status_code == 200
    result = scan.get_json()["data"][0]
    bike_evaluation = next(
        row for row in result["evaluations"] if row["driver"]["id"] == bike.id
    )
    bike_codes = {row["code"] for row in bike_evaluation["blockers"]}
    assert "parcel_dimension_exceeded" in bike_codes
    assert session.get(
        f"/api/v1/manager/matching/suggestions?order_id={heavy.id}"
    ).get_json()["data"] == []
    assert MatchingSuggestion.query.count() == 0


def test_suggestion_rejection_requires_a_reason_and_blocks_approval(
    session, db, reference_data
):
    area = _area()
    manager = _manager(areas=[area])
    driver, profile, _vehicle = _driver(area=area)
    _locate(profile, P1)
    consumer = make_user("consumer@example.com")
    first = _order(consumer, P1, D1)
    _approve(first)

    session.login(manager.email)
    created = session.post(
        "/api/v1/manager/batches", {"order_ids": [first.id], "driver_id": driver.id}
    )
    batch_id = created.get_json()["data"]["id"]
    session.logout()
    session.login(driver.email)
    session.post(f"/api/v1/driver/batches/{batch_id}/start", {})

    second = _order(consumer, P2, D2)
    _approve(second)
    session.logout()
    session.login(manager.email)
    scan = session.post("/api/v1/manager/matching/scan", {"order_ids": [second.id]})
    suggestion_id = scan.get_json()["data"][0]["suggestion_ids"][0]

    no_reason = session.post(
        f"/api/v1/manager/matching/suggestions/{suggestion_id}/reject", {}
    )
    assert no_reason.status_code == 422
    rejected = session.post(
        f"/api/v1/manager/matching/suggestions/{suggestion_id}/reject",
        {"reason": "Driver is already at the end of a long shift"},
    )
    assert rejected.status_code == 200
    assert rejected.get_json()["data"]["status"] == domain.SUGGESTION_REJECTED
    assert rejected.get_json()["data"]["rejection_code"] == "manager_rejected"

    approve = session.post(
        f"/api/v1/manager/matching/suggestions/{suggestion_id}/approve"
    )
    assert approve.status_code == 409
    assert approve.get_json()["error"]["code"] == "suggestion_not_pending"


# --------------------------------------------------------------------------- #
# Monitoring
# --------------------------------------------------------------------------- #
def test_dashboard_and_live_tracking_report_only_real_driver_state(
    session, db, reference_data
):
    area = _area()
    manager = _manager(areas=[area])
    live, live_profile, _lv = _driver("live@example.com", area)
    stale, stale_profile, _sv = _driver("stale@example.com", area)
    _driver("offduty@example.com", area, duty=False)
    _locate(live_profile, P1)
    _locate(stale_profile, P2, age_minutes=90)
    consumer = make_user("consumer@example.com")
    _order(consumer, P1, D1)
    _approve(_order(consumer, P2, D2))

    session.login(manager.email)
    summary = session.get("/api/v1/manager/summary")
    assert summary.status_code == 200, summary.get_json()
    data = summary.get_json()["data"]
    assert data["drivers"]["total"] == 3
    assert data["drivers"]["on_duty"] == 2
    assert data["drivers"]["offline"] == 1
    assert data["drivers"]["available"] == 2
    assert data["orders"]["pending"] == 1
    assert data["orders"]["awaiting_assignment"] == 1

    monitoring = session.get("/api/v1/manager/drivers")
    assert monitoring.status_code == 200
    rows = {row["driver"]["id"]: row for row in monitoring.get_json()["data"]}
    assert rows[live.id]["is_live"] is True
    assert rows[live.id]["last_location"]["is_recent"] is True

    tracking = session.get("/api/v1/manager/drivers/live")
    assert tracking.status_code == 200
    tracked = {row["driver"]["id"]: row for row in tracking.get_json()["data"]}
    assert tracked[live.id]["tracking_status"] == "live_recent"
    assert tracked[stale.id]["tracking_status"] == "stale"
    assert len(tracked) == 2  # off-duty drivers are not part of live tracking

    session.logout()
    session.login(consumer.email)
    assert session.get("/api/v1/manager/drivers/live").status_code == 403
    assert session.get("/api/v1/manager/summary").status_code == 403


def test_scan_requires_an_approved_order(session, db, reference_data):
    area = _area()
    manager = _manager(areas=[area])
    consumer = make_user("consumer@example.com")
    order = _order(consumer, P1, D1)

    session.login(manager.email)
    response = session.post(
        "/api/v1/manager/matching/scan", {"order_ids": [order.id]}
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "order_not_assignable"
    assert db.session.get(Order, order.id).status == domain.ORDER_PENDING_REVIEW
