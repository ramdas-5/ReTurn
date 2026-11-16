"""Phase 2: consumer registration, sessions, RBAC and staff provisioning."""
from __future__ import annotations

from app.extensions import db
from app.models import (
    BusinessProfile,
    DriverProfile,
    ManagerProfile,
    ServiceArea,
    User,
    Vehicle,
    VehicleCapacityProfile,
)
from tests.conftest import make_user

CONSUMER = {
    "full_name": "Riya Sen",
    "email": "riya@example.com",
    "phone": "9830000001",
    "password": "ReTurnStrong9",
    "confirm_password": "ReTurnStrong9",
    "account_type": "individual",
}


def _register(session, **overrides):
    payload = {**CONSUMER, **overrides}
    return session.post("/api/v1/auth/register", payload)


def _make_service_area(name="Salt Lake"):
    area = ServiceArea(
        name=name,
        city="Kolkata",
        postal_codes="700091",
        center_latitude=22.58,
        center_longitude=88.41,
        radius_km=10,
    )
    db.session.add(area)
    db.session.commit()
    return area


def test_consumer_registration_creates_consumer_session(session, db):
    response = _register(session)
    assert response.status_code == 201, response.get_json()
    user = response.get_json()["data"]["user"]
    assert user["role"] == "consumer"
    assert user["status"] == "active"
    assert user["consumer_profile"]["account_type"] == "individual"

    me = session.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.get_json()["data"]["user"]["email"] == "riya@example.com"


def test_business_registration_stores_business_profile(session, db):
    response = _register(
        session,
        account_type="business",
        email="shop@example.com",
        business={"business_name": "Sen Shoes", "category": "Footwear", "area": "Salt Lake"},
    )
    assert response.status_code == 201, response.get_json()
    profile = BusinessProfile.query.filter_by(business_name="Sen Shoes").one()
    assert profile.user.email == "shop@example.com"
    assert response.get_json()["data"]["user"]["business_profile"]["business_name"] == "Sen Shoes"


def test_registration_cannot_self_assign_staff_role(session, db):
    response = _register(session, email="sneaky@example.com", role="admin", is_admin=True)
    assert response.status_code == 201
    assert User.query.filter_by(email="sneaky@example.com").one().role == "consumer"


def test_duplicate_email_and_weak_password_rejected(session, db):
    _register(session)
    duplicate = _register(session, email="riya@example.com")
    assert duplicate.status_code == 409
    weak = _register(session, email="weak@example.com", password="short", confirm_password="short")
    assert weak.status_code == 422
    assert "password" in weak.get_json()["error"]["fields"]


def test_csrf_is_required(client, db):
    response = client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "whatever"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_failed"


def test_login_logout_and_suspension(session, db):
    _register(session)
    session.logout()

    bad = session.post("/api/v1/auth/login", {"email": "riya@example.com", "password": "WrongPass9"})
    assert bad.status_code == 401

    good = session.login("riya@example.com", "ReTurnStrong9")
    assert good.status_code == 200

    me = session.get("/api/v1/auth/me")
    assert me.status_code == 200

    session.logout()
    assert session.get("/api/v1/auth/me").status_code == 401

    user = User.query.filter_by(email="riya@example.com").one()
    user.status = "suspended"
    db.session.commit()
    blocked = session.post(
        "/api/v1/auth/login", {"email": "riya@example.com", "password": "ReTurnStrong9"}
    )
    assert blocked.status_code == 403
    assert blocked.get_json()["error"]["code"] == "account_suspended"


def test_admin_provisions_manager_then_manager_provisions_driver(
    session, db, reference_data
):
    area = _make_service_area()
    make_user("admin@example.com", role="admin")

    session.login("admin@example.com")

    created = session.post(
        "/api/v1/users/managers",
        {
            "full_name": "Maya Manager",
            "email": "maya@example.com",
            "phone": "9830000002",
            "service_area_ids": [area.id],
            "permission_codes": ["ops.view"],
        },
    )
    assert created.status_code == 201, created.get_json()
    body = created.get_json()["data"]
    assert body["temporary_password"]
    assert body["activation_token"]
    manager_id = body["user"]["id"]
    assert body["user"]["role"] == "manager"
    assert body["user"]["status"] == "pending_activation"

    # The manager cannot sign in before activation.
    pending = session.post(
        "/api/v1/auth/login",
        {"email": "maya@example.com", "password": body["temporary_password"]},
    )
    assert pending.status_code == 403
    assert pending.get_json()["error"]["code"] == "account_pending_activation"

    activated = session.post(
        "/api/v1/auth/activate",
        {
            "token": body["activation_token"],
            "new_password": "ManagerStrong9",
            "confirm_password": "ManagerStrong9",
        },
    )
    assert activated.status_code == 200, activated.get_json()
    session.logout()
    session.login("maya@example.com", "ManagerStrong9")

    # Managers cannot create managers or administrators.
    forbidden = session.post(
        "/api/v1/users/managers",
        {
            "full_name": "Shadow",
            "email": "shadow@example.com",
            "phone": "9830000003",
            "service_area_ids": [area.id],
        },
    )
    assert forbidden.status_code == 403

    capacity = VehicleCapacityProfile.query.filter_by(vehicle_type="bike").first()
    driver = session.post(
        "/api/v1/users/drivers",
        {
            "full_name": "Arjun Driver",
            "email": "arjun@example.com",
            "phone": "9830000004",
            "service_area_ids": [area.id],
            "vehicle": {
                "capacity_profile_id": capacity.id,
                "registration_number": "WB-01-AB-1234",
            },
        },
    )
    assert driver.status_code == 201, driver.get_json()
    driver_body = driver.get_json()["data"]
    assert driver_body["user"]["role"] == "driver"
    assert Vehicle.query.filter_by(registration_number="WB-01-AB-1234").count() == 1

    # Manager with a narrow scope cannot create a driver elsewhere.
    other = _make_service_area("Barasat")
    out_of_scope = session.post(
        "/api/v1/users/drivers",
        {
            "full_name": "Other Driver",
            "email": "other@example.com",
            "phone": "9830000005",
            "service_area_ids": [other.id],
            "vehicle": {
                "capacity_profile_id": capacity.id,
                "registration_number": "WB-01-CD-5678",
            },
        },
    )
    assert out_of_scope.status_code == 403

    # Owner listing is scoped to that manager's drivers only.
    listing = session.get("/api/v1/users?role=driver")
    assert listing.status_code == 200
    emails = [row["email"] for row in listing.get_json()["data"]]
    assert "arjun@example.com" in emails
    assert "other@example.com" not in emails


def test_driver_activation_and_temporary_password_flow(session, db, reference_data):
    area = _make_service_area()
    admin = make_user("admin2@example.com", role="admin")
    session.login("admin2@example.com")
    capacity = VehicleCapacityProfile.query.filter_by(vehicle_type="scooter").first()
    created = session.post(
        "/api/v1/users/drivers",
        {
            "full_name": "Scooter Driver",
            "email": "scooter@example.com",
            "phone": "9830000006",
            "service_area_ids": [area.id],
            "vehicle": {
                "capacity_profile_id": capacity.id,
                "registration_number": "WB-02-EF-9012",
            },
        },
    ).get_json()["data"]

    session.logout()
    # Temporary password signs in only after activation; activation resets it.
    activated = session.post(
        "/api/v1/auth/activate",
        {
            "token": created["activation_token"],
            "new_password": "DriverStrong9",
            "confirm_password": "DriverStrong9",
        },
    )
    assert activated.status_code == 200, activated.get_json()
    user = User.query.filter_by(email="scooter@example.com").one()
    assert user.status == "active"
    assert user.must_change_password is False
    assert user.driver_profile is not None

    # The activation token is single-use.
    replay = session.post(
        "/api/v1/auth/activate",
        {
            "token": created["activation_token"],
            "new_password": "AnotherStrong9",
            "confirm_password": "AnotherStrong9",
        },
    )
    assert replay.status_code == 400

    session.logout()
    session.login("scooter@example.com", "DriverStrong9")


def test_password_reset_flow(session, db):
    _register(session)
    session.logout()
    response = session.post("/api/v1/auth/forgot-password", {"email": "riya@example.com"})
    assert response.status_code == 202
    token = response.get_json()["data"].get("reset_token")
    assert token, response.get_json()

    reset = session.post(
        "/api/v1/auth/reset-password",
        {
            "token": token,
            "new_password": "BrandNewPass9",
            "confirm_password": "BrandNewPass9",
        },
    )
    assert reset.status_code == 200, reset.get_json()

    old = session.post(
        "/api/v1/auth/login", {"email": "riya@example.com", "password": "ReTurnStrong9"}
    )
    assert old.status_code == 401
    session.login("riya@example.com", "BrandNewPass9")


def test_consumer_cannot_use_staff_endpoints_or_see_others(session, db):
    _register(session)
    make_user("someone@example.com")

    assert session.get("/api/v1/users").status_code == 403
    assert session.get("/api/v1/users?role=driver").status_code == 403
    assert (
        session.post(
            "/api/v1/users/drivers",
            {"full_name": "Nope", "email": "nope@example.com", "phone": "9000000001"},
        ).status_code
        == 403
    )

    # Consumers only see their own addresses.
    mine = session.post(
        "/api/v1/users/me/addresses",
        {
            "label": "Home",
            "address_line": "12 Lake Road",
            "area": "Salt Lake",
            "latitude": 22.58,
            "longitude": 88.41,
            "is_default_pickup": True,
        },
    )
    assert mine.status_code == 201, mine.get_json()
    address_id = mine.get_json()["data"]["id"]
    other_user = User.query.filter_by(email="someone@example.com").one()
    from app.models import SavedAddress

    other_address = SavedAddress(
        user_id=other_user.id,
        label="Theirs",
        address_line="1 Elsewhere",
        area="Barasat",
        latitude=22.7,
        longitude=88.4,
    )
    db.session.add(other_address)
    db.session.commit()
    blocked = session.patch(f"/api/v1/users/me/addresses/{other_address.id}", {"label": "Hacked"})
    assert blocked.status_code == 404
