"""Phase 6: administration, audit, analytics, issues and driver profile."""
from __future__ import annotations

from datetime import timedelta

from app import domain
from app.extensions import db
from app.models import (
    DeliveryException,
    DriverProfile,
    DriverServiceArea,
    MediaAsset,
    ManagerProfile,
    ManagerServiceArea,
    Order,
    ProofMedia,
    ServiceArea,
    Vehicle,
    VehicleCapacityProfile,
)
from app.services.orders import create_order
from tests.conftest import make_user


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


def _admin(email="admin@example.com"):
    return make_user(email, role="admin")


def _manager(area):
    user = make_user("manager@example.com", role="manager")
    profile = ManagerProfile(user_id=user.id, employee_code=f"M-{user.id}")
    db.session.add(profile)
    db.session.flush()
    db.session.add(
        ManagerServiceArea(manager_id=profile.id, service_area_id=area.id)
    )
    db.session.commit()
    return user


def _driver(area, email="driver@example.com"):
    user = make_user(email, role="driver")
    profile = DriverProfile(
        user_id=user.id, verification_status=domain.VERIFICATION_VERIFIED
    )
    db.session.add(profile)
    db.session.flush()
    db.session.add(
        DriverServiceArea(driver_id=profile.id, service_area_id=area.id)
    )
    capacity = VehicleCapacityProfile.query.filter_by(vehicle_type="car").first()
    vehicle = Vehicle(
        driver_id=profile.id,
        capacity_profile_id=capacity.id,
        vehicle_type="car",
        registration_number=f"WB-{user.id}-car",
        make="Demo",
        model="Sedan",
        verification_status=domain.VERIFICATION_PENDING,
        is_active=True,
    )
    db.session.add(vehicle)
    db.session.commit()
    return user, profile, vehicle


def _order(consumer, *, area_name="Salt Lake"):
    now = domain.utcnow().replace(microsecond=0)
    start = now + timedelta(minutes=30)
    order = create_order(
        consumer,
        {
            "service_type": "parcel",
            "pickup": {
                "contact_name": "Riya Sen",
                "contact_phone": "9830000001",
                "address_line": "12 Lake Road",
                "area": area_name,
                "city": "Kolkata",
                "latitude": 22.60,
                "longitude": 88.41,
            },
            "delivery": {
                "contact_name": "Amit Das",
                "contact_phone": "9830000002",
                "address_line": "44 Park Street",
                "area": "Salt Lake",
                "city": "Kolkata",
                "latitude": 22.62,
                "longitude": 88.41,
            },
            "parcel": {
                "name": "Parcel",
                "category": "general",
                "quantity": 1,
                "weight_kg": 2.5,
                "length_cm": 30,
                "width_cm": 20,
                "height_cm": 10,
            },
            "pickup_window_start": start,
            "pickup_window_end": start + timedelta(hours=3),
            "delivery_deadline": start + timedelta(days=1),
        },
    )
    db.session.commit()
    return order


def _proof(order, driver_id):
    asset = MediaAsset(
        storage_backend="local",
        storage_key="2026/11/demo.jpg",
        original_filename="proof.jpg",
        content_type="image/jpeg",
        byte_size=10,
        checksum_sha256="0" * 64,
        visibility="private",
    )
    db.session.add(asset)
    db.session.flush()
    proof = ProofMedia(
        order_id=order.id,
        driver_id=driver_id,
        proof_type=domain.PROOF_DELIVERY,
        media_id=asset.id,
        captured_at=domain.utcnow(),
        received_at=domain.utcnow(),
        latitude=22.62,
        longitude=88.41,
        distance_from_stop_m=2,
        verification_status=domain.PROOF_PENDING,
    )
    db.session.add(proof)
    db.session.commit()
    return proof


def test_admin_endpoints_are_admin_only(client, db, reference_data):
    area = _area()
    _manager(area)
    consumer = make_user("consumer@example.com", role="consumer")
    _admin()

    manager = client.application.test_client()
    from tests.conftest import Session

    manager_session = Session(manager)
    manager_session.login("manager@example.com")
    assert manager_session.get("/api/v1/admin/summary").status_code == 403

    consumer_session = Session(client)
    consumer_session.login(consumer.email)
    assert consumer_session.get("/api/v1/admin/summary").status_code == 403

    admin_session = Session(client)
    admin_session.login("admin@example.com")
    response = admin_session.get("/api/v1/admin/summary")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["accounts"]["admins"] == 1
    assert "disclaimer" in data


def test_admin_summary_and_analytics_reflect_real_rows(client, db, reference_data):
    area = _area()
    consumer = make_user("consumer@example.com", role="consumer")
    order = _order(consumer)
    assert order.status == domain.ORDER_PENDING_REVIEW
    _admin()

    session = __import__("tests.conftest", fromlist=["Session"]).Session(client)
    session.login("admin@example.com")

    summary = session.get("/api/v1/admin/summary").get_json()["data"]
    assert summary["orders"]["total"] == 1
    assert summary["orders"]["by_status"][domain.ORDER_PENDING_REVIEW] == 1
    assert summary["service_areas"][0]["name"] == area.name

    analytics = session.get("/api/v1/admin/analytics")
    assert analytics.status_code == 200
    payload = analytics.get_json()["data"]
    assert payload["orders"]["total"] == 1
    assert "modelled estimates" in payload["disclaimer"]

    sustainability = session.get("/api/v1/admin/analytics/sustainability")
    assert sustainability.status_code == 200
    assert sustainability.get_json()["data"]["totals"]["batches_measured"] == 0


def test_admin_account_lists_and_service_area_crud(client, db, reference_data):
    area = _area()
    consumer = make_user("consumer@example.com", role="consumer")
    _order(consumer)
    _admin()
    session = __import__("tests.conftest", fromlist=["Session"]).Session(client)
    session.login("admin@example.com")

    consumers = session.get("/api/v1/admin/consumers?q=consumer").get_json()
    assert consumers["meta"]["total"] == 1
    assert consumers["data"][0]["email"] == "consumer@example.com"

    created = session.post(
        "/api/v1/admin/service-areas",
        {
            "name": "New Town",
            "city": "Kolkata",
            "center_latitude": 22.58,
            "center_longitude": 88.47,
            "radius_km": 7.5,
        },
    )
    assert created.status_code == 201, created.get_json()
    area_id = created.get_json()["data"]["id"]

    listed = session.get("/api/v1/admin/service-areas").get_json()["data"]
    assert any(row["name"] == "New Town" for row in listed)

    updated = session.patch(
        f"/api/v1/admin/service-areas/{area_id}", {"radius_km": 9, "is_active": False}
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["radius_km"] == 9.0
    assert updated.get_json()["data"]["is_active"] is False

    duplicate = session.post("/api/v1/admin/service-areas", {"name": "salt lake"})
    assert duplicate.status_code == 409

    audit = session.get("/api/v1/admin/audit?action=admin.service_area").get_json()
    assert audit["meta"]["total"] >= 2


def test_admin_matching_config_is_persisted_and_effective(client, db, reference_data):
    from app.services.route_planner import config

    _admin()
    session = __import__("tests.conftest", fromlist=["Session"]).Session(client)
    session.login("admin@example.com")

    before = session.get("/api/v1/admin/matching-config").get_json()["data"]
    assert before["overrides"] == {}

    response = session.patch(
        "/api/v1/admin/matching-config",
        {"overrides": {"max_detour_km": 4.5, "suggestion_ttl_minutes": 30}},
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["effective"]["max_detour_km"] == 4.5
    assert config()["suggestion_ttl_minutes"] == 30

    invalid = session.patch(
        "/api/v1/admin/matching-config", {"overrides": {"max_detour_km": 0.1}}
    )
    assert invalid.status_code == 422
    assert "max_detour_km" in invalid.get_json()["error"]["fields"]

    unknown = session.patch(
        "/api/v1/admin/matching-config", {"overrides": {"invented": 1}}
    )
    assert unknown.status_code == 422


def test_admin_proof_review_and_manager_scope(client, db, reference_data):
    area = _area()
    consumer = make_user("consumer@example.com", role="consumer")
    order = _order(consumer)
    driver_user, _, _ = _driver(area)
    proof = _proof(order, driver_user.id)
    _manager(area)
    _admin()

    manager_session = __import__("tests.conftest", fromlist=["Session"]).Session(
        client.application.test_client()
    )
    manager_session.login("manager@example.com")
    listed = manager_session.get("/api/v1/manager/proofs").get_json()
    assert listed["meta"]["total"] == 1

    admin_session = __import__("tests.conftest", fromlist=["Session"]).Session(
        client.application.test_client()
    )
    admin_session.login("admin@example.com")
    verified = admin_session.patch(
        f"/api/v1/admin/proofs/{proof.id}/verify",
        {"verification_status": domain.PROOF_REJECTED, "note": "Blurred image"},
    )
    assert verified.status_code == 200
    assert verified.get_json()["data"]["verification_status"] == domain.PROOF_REJECTED
    assert verified.get_json()["data"]["image_url"].startswith("/api/v1/media/")


def test_admin_vehicle_verification_is_audited(client, db, reference_data):
    area = _area()
    _driver(area)
    _admin()
    vehicle = Vehicle.query.first()
    session = __import__("tests.conftest", fromlist=["Session"]).Session(client)
    session.login("admin@example.com")

    response = session.patch(
        f"/api/v1/admin/vehicles/{vehicle.id}",
        {"verification_status": domain.VERIFICATION_VERIFIED, "reason": "Docs checked"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["verification_status"] == domain.VERIFICATION_VERIFIED

    audit = session.get("/api/v1/admin/audit?action=admin.vehicle_updated").get_json()
    assert audit["meta"]["total"] == 1
    assert audit["data"][0]["reason"] == "Docs checked"


def test_driver_profile_and_vehicle_update(client, db, reference_data):
    area = _area()
    _driver(area)
    session = __import__("tests.conftest", fromlist=["Session"]).Session(client)
    session.login("driver@example.com")

    profile = session.get("/api/v1/driver/profile")
    assert profile.status_code == 200
    data = profile.get_json()["data"]
    assert data["user"]["email"] == "driver@example.com"
    assert data["service_areas"][0]["name"] == area.name

    vehicle = Vehicle.query.first()
    updated = session.patch(
        "/api/v1/driver/vehicle",
        {"vehicle_id": vehicle.id, "make": "Updated", "color": "Blue", "year": 2024},
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["color"] == "Blue"

    # A driver cannot deactivate their only vehicle.
    refused = session.patch(
        "/api/v1/driver/vehicle", {"vehicle_id": vehicle.id, "is_active": False}
    )
    assert refused.status_code == 409
    assert refused.get_json()["error"]["code"] == "last_vehicle"


def test_issue_report_and_resolution_permissions(client, db, reference_data):
    area = _area()
    consumer = make_user("consumer@example.com", role="consumer")
    order = _order(consumer)
    _manager(area)

    consumer_session = __import__("tests.conftest", fromlist=["Session"]).Session(
        client.application.test_client()
    )
    consumer_session.login(consumer.email)
    created = consumer_session.post(
        "/api/v1/issues",
        {
            "category": "delivery",
            "severity": "high",
            "subject": "Parcel not collected",
            "description": "The pickup window passed without a driver arriving.",
            "order_id": order.id,
        },
    )
    assert created.status_code == 201, created.get_json()
    issue_id = created.get_json()["data"]["id"]
    assert created.get_json()["data"]["reporter"]["role"] == "consumer"

    manager_session = __import__("tests.conftest", fromlist=["Session"]).Session(
        client.application.test_client()
    )
    manager_session.login("manager@example.com")
    listed = manager_session.get("/api/v1/issues?status=open").get_json()
    assert listed["meta"]["total"] == 1
    resolved = manager_session.patch(
        f"/api/v1/issues/{issue_id}",
        {"status": "resolved", "resolution_note": "Driver reassigned and pickup completed."},
    )
    assert resolved.status_code == 200
    assert resolved.get_json()["data"]["status"] == "resolved"

    second = consumer_session.post(
        "/api/v1/issues",
        {
            "category": "account",
            "subject": "Cannot update address",
            "description": "Saving a new address fails on my account page.",
        },
    )
    assert second.status_code == 201
    forbidden = consumer_session.patch(
        f"/api/v1/issues/{second.get_json()['data']['id']}",
        {"status": "resolved", "resolution_note": "Not allowed"},
    )
    assert forbidden.status_code == 403


def test_admin_exception_resolution(client, db, reference_data):
    area = _area()
    consumer = make_user("consumer@example.com", role="consumer")
    order = _order(consumer)
    exception = DeliveryException(
        order_id=order.id,
        exception_type="address_not_found",
        description="Demo exception",
        status=domain.EXCEPTION_OPEN,
    )
    db.session.add(exception)
    db.session.commit()
    _admin()

    session = __import__("tests.conftest", fromlist=["Session"]).Session(client)
    session.login("admin@example.com")
    listed = session.get("/api/v1/admin/exceptions?status=open").get_json()
    assert listed["meta"]["total"] == 1

    resolved = session.patch(
        f"/api/v1/admin/exceptions/{exception.id}",
        {"status": domain.EXCEPTION_RESOLVED, "resolution_note": "Address confirmed by phone."},
    )
    assert resolved.status_code == 200
    assert resolved.get_json()["data"]["status"] == domain.EXCEPTION_RESOLVED


def test_admin_operations_live_labels_unavailable_tracking(client, db, reference_data):
    _driver(_area())
    _admin()
    session = __import__("tests.conftest", fromlist=["Session"]).Session(client)
    session.login("admin@example.com")
    data = session.get("/api/v1/admin/operations/live").get_json()["data"]
    # The helper driver has no duty session, so live operations must not invent one.
    assert data["drivers"] == []
    assert data["counts"]["drivers_on_duty"] == 0
    assert "stale" in data["note"] or "labelled" in data["note"]
