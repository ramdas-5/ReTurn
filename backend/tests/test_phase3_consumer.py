"""Phase 3: consumer parcel booking, returns, tracking and private media."""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app import domain
from app.extensions import db
from app.models import (
    DriverAvailability,
    DriverDutySession,
    DriverProfile,
    DriverServiceArea,
    ManagerProfile,
    ManagerServiceArea,
    Order,
    ServiceArea,
)
from app.services.orders import record_status
from tests.conftest import make_user

CONSUMER = {
    "full_name": "Riya Sen",
    "email": "riya@example.com",
    "phone": "9830000001",
    "password": "ReTurnStrong9",
    "confirm_password": "ReTurnStrong9",
    "account_type": "individual",
}


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


def _manager(email="maya@example.com", areas=()):
    user = make_user(email, role="manager")
    profile = ManagerProfile(user_id=user.id)
    db.session.add(profile)
    db.session.flush()
    for area in areas:
        db.session.add(ManagerServiceArea(manager_id=profile.id, service_area_id=area.id))
    db.session.commit()
    return user


def _on_duty_driver(email="arjun@example.com", area=None, *, heartbeat_age_minutes=0):
    user = make_user(email, role="driver")
    profile = DriverProfile(
        user_id=user.id, verification_status=domain.VERIFICATION_VERIFIED
    )
    db.session.add(profile)
    db.session.flush()
    if area is not None:
        db.session.add(
            DriverServiceArea(driver_id=profile.id, service_area_id=area.id)
        )
    now = domain.utcnow()
    db.session.add(
        DriverDutySession(
            driver_id=profile.id,
            status=domain.DUTY_AVAILABLE,
            started_at=now - timedelta(hours=1),
            last_heartbeat_at=now - timedelta(minutes=heartbeat_age_minutes),
        )
    )
    db.session.commit()
    return profile


def _payload(**overrides):
    now = domain.utcnow()
    start = (now + timedelta(hours=2)).replace(microsecond=0)
    payload = {
        "service_type": "parcel",
        "pickup": {
            "contact_name": "Riya Sen",
            "contact_phone": "9830000001",
            "address_line": "12 Lake Road",
            "area": "Salt Lake",
            "city": "Kolkata",
            "latitude": 22.58,
            "longitude": 88.41,
            "instructions": "Call on arrival",
        },
        "delivery": {
            "contact_name": "Amit Das",
            "contact_phone": "9830000002",
            "address_line": "44 Park Street",
            "area": "Salt Lake",
            "city": "Kolkata",
            "latitude": 22.59,
            "longitude": 88.42,
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
    payload.update(overrides)
    return payload


def _register(session, **overrides):
    response = session.post("/api/v1/auth/register", {**CONSUMER, **overrides})
    assert response.status_code == 201, response.get_json()
    return response


def _create_order(session, payload=None, *, photo=True):
    payload = payload or _payload()
    if photo:
        return session.post_multipart("/api/v1/orders", payload)
    return session.post("/api/v1/orders", payload)


def _create_return(session, payload=None, *, photo=True):
    payload = payload or _payload()
    if photo:
        return session.post_multipart("/api/v1/returns", payload)
    return session.post("/api/v1/returns", payload)


# --------------------------------------------------------------------------- #
# Intake and availability
# --------------------------------------------------------------------------- #
def test_order_creation_records_snapshots_and_notifies(session, db, reference_data):
    area = _service_area()
    manager = _manager(areas=[area])
    _on_duty_driver(area=area)
    _register(session)

    availability = session.get(
        "/api/v1/availability?pickup_area=Salt%20Lake&pickup_latitude=22.58"
        "&pickup_longitude=88.41&delivery_area=Salt%20Lake"
    )
    assert availability.status_code == 200, availability.get_json()
    info = availability.get_json()["data"]
    assert info["serviceable"] is True
    assert info["available"] is True
    assert info["drivers_on_duty"] == 1
    assert info["availability_label"] == "Limited availability"

    response = _create_order(session)
    assert response.status_code == 201, response.get_json()
    order = response.get_json()["data"]
    assert order["order_number"].startswith("RT-")
    assert order["status"] == "pending_review"
    assert order["has_photo"] is True
    assert len(order["images"]) == 1
    assert order["images"][0]["is_primary"] is True
    assert order["images"][0]["url"].startswith("/api/v1/media/")
    assert order["parcel"]["weight_kg"] == 2.5
    assert [row["to_status"] for row in order["status_history"]] == [
        "submitted",
        "pending_review",
    ]
    assert "assigned_driver" not in order or order["assigned_driver"] is None

    listing = session.get("/api/v1/orders")
    assert listing.status_code == 200
    assert listing.get_json()["meta"]["total"] == 1
    assert listing.get_json()["data"][0]["has_photo"] is True

    tracking = session.get(f"/api/v1/orders/{order['id']}/tracking")
    assert tracking.status_code == 200
    timeline = tracking.get_json()["data"]["timeline"]
    assert [row["to_status"] for row in timeline] == ["submitted", "pending_review"]
    assert tracking.get_json()["data"]["assigned_driver"] is None

    # The manager receives a real queue item and a notification.
    session.logout()
    session.login(manager.email)
    manager_orders = session.get("/api/v1/orders?status=pending_review")
    assert manager_orders.status_code == 200
    assert manager_orders.get_json()["meta"]["total"] == 1
    feed = session.get("/api/v1/notifications")
    assert feed.get_json()["meta"]["total"] >= 1
    assert any(
        order["order_number"] in row["title"]
        for row in feed.get_json()["data"]
        if row["title"]
    )


def test_parcel_photo_is_required_with_documented_exception(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)

    missing = _create_order(session, photo=False)
    assert missing.status_code == 422
    error = missing.get_json()["error"]
    assert error["code"] == "parcel_photo_required"
    assert "photo" in error["fields"]

    short_reason = _payload()
    short_reason["parcel"] = {**short_reason["parcel"], "photo_exception_reason": "no cam"}
    rejected = _create_order(session, short_reason, photo=False)
    assert rejected.status_code == 422
    assert rejected.get_json()["error"]["code"] == "parcel_photo_exception_too_short"

    exception = _payload()
    exception["parcel"] = {
        **exception["parcel"],
        "photo_exception_reason": "Camera unavailable; parcel sealed and inspected at pickup.",
    }
    accepted = _create_order(session, exception, photo=False)
    assert accepted.status_code == 201, accepted.get_json()
    detail = accepted.get_json()["data"]
    assert detail["has_photo"] is False
    assert detail["parcel"]["photo_exception_reason"].startswith("Camera unavailable")


def test_order_outside_service_area_is_rejected(session, db):
    _register(session)
    payload = _payload()
    payload["pickup"] = {**payload["pickup"], "area": "Atlantis"}
    payload["delivery"] = {**payload["delivery"], "area": "Atlantis"}
    response = _create_order(session, payload)
    assert response.status_code == 422
    error = response.get_json()["error"]
    assert error["code"] == "area_not_serviceable"
    assert "pickup.area" in error["fields"]
    assert "delivery.area" in error["fields"]


def test_availability_counts_only_live_verified_drivers(session, db):
    area = _service_area()
    _register(session)

    none = session.get("/api/v1/availability?pickup_area=Salt%20Lake")
    assert none.get_json()["data"]["available"] is False
    assert none.get_json()["data"]["drivers_on_duty"] == 0
    assert "no_driver_available" in none.get_json()["data"]["reasons"]

    _on_duty_driver(email="stale@example.com", area=area, heartbeat_age_minutes=120)
    stale = session.get("/api/v1/availability?pickup_area=Salt%20Lake")
    assert stale.get_json()["data"]["drivers_on_duty"] == 0

    _on_duty_driver(email="fresh@example.com", area=area)
    fresh = session.get("/api/v1/availability?pickup_area=Salt%20Lake")
    assert fresh.get_json()["data"]["drivers_on_duty"] == 1


def test_scheduled_availability_uses_declared_windows(session, db):
    area = _service_area()
    _register(session)
    driver = make_user("scheduled@example.com", role="driver")
    profile = DriverProfile(
        user_id=driver.id, verification_status=domain.VERIFICATION_VERIFIED
    )
    db.session.add(profile)
    db.session.flush()
    db.session.add(DriverServiceArea(driver_id=profile.id, service_area_id=area.id))
    start = domain.utcnow() + timedelta(hours=3)
    local = start.astimezone(ZoneInfo("Asia/Kolkata"))
    db.session.add(
        DriverAvailability(
            driver_id=profile.id,
            weekday=local.weekday(),
            start_time=local.replace(hour=0, minute=0, second=0, microsecond=0).time(),
            end_time=local.replace(hour=23, minute=59, second=0, microsecond=0).time(),
            service_area_id=area.id,
        )
    )
    db.session.commit()

    response = session.get(
        "/api/v1/availability?"
        + urlencode(
            {
                "pickup_area": "Salt Lake",
                "delivery_area": "Salt Lake",
                "window_start": start.isoformat(),
                "window_end": (start + timedelta(hours=2)).isoformat(),
            }
        )
    )
    info = response.get_json()["data"]
    assert info["drivers_on_duty"] == 0
    assert info["drivers_scheduled"] == 1
    assert info["available"] is True
    assert info["availability_label"] == "Scheduled availability for this slot"


# --------------------------------------------------------------------------- #
# Returns
# --------------------------------------------------------------------------- #
def test_return_request_requires_details_and_can_be_cancelled(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)

    missing = _payload()
    del missing["service_type"]
    response = _create_return(session, missing)
    assert response.status_code == 422
    assert "return_details" in response.get_json()["error"]["fields"]

    return_payload = _payload(service_type="return")
    return_payload["delivery"] = {
        **return_payload["delivery"],
        "contact_name": "Sen Shoes Returns Desk",
        "address_line": "9 Mall Road",
    }
    return_payload["return_details"] = {
        "product_name": "Running shoes",
        "original_order_reference": "SHOP-4821",
        "reason": "Wrong size delivered",
        "merchant_name": "Sen Shoes",
        "destination_type": "business",
        "authorization_confirmed": True,
        "merchant_approval_required": True,
    }
    created = _create_return(session, return_payload)
    assert created.status_code == 201, created.get_json()
    detail = created.get_json()["data"]
    assert detail["service_type"] == "return"
    assert detail["return_request"]["approval_status"] == "pending"
    assert detail["return_request"]["merchant_name"] == "Sen Shoes"
    assert detail["return_request"]["authorization_confirmed"] is True

    listing = session.get("/api/v1/returns")
    assert listing.status_code == 200
    assert [row["id"] for row in listing.get_json()["data"]] == [detail["id"]]

    single = session.get(f"/api/v1/returns/{detail['id']}")
    assert single.status_code == 200
    assert single.get_json()["data"]["return_request"]["reason"] == "Wrong size delivered"

    cancelled = session.post(
        f"/api/v1/returns/{detail['id']}/cancel", {"reason": "Return no longer needed"}
    )
    assert cancelled.status_code == 200, cancelled.get_json()
    assert cancelled.get_json()["data"]["status"] == "cancelled"

    again = session.post(
        f"/api/v1/returns/{detail['id']}/cancel", {"reason": "Duplicate cancellation"}
    )
    assert again.status_code == 409


def test_return_detail_hides_other_consumers_orders(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    return_payload = _payload(service_type="return")
    return_payload["return_details"] = {
        "reason": "Not as described",
        "destination_type": "warehouse",
    }
    detail = _create_return(session, return_payload).get_json()["data"]

    session.logout()
    _register(
        session,
        email="other@example.com",
        phone="9830000009",
        full_name="Other Person",
    )
    assert session.get(f"/api/v1/returns/{detail['id']}").status_code == 404
    assert session.get("/api/v1/returns").get_json()["data"] == []


# --------------------------------------------------------------------------- #
# Ownership, cancellation and tracking
# --------------------------------------------------------------------------- #
def test_consumer_cannot_see_or_cancel_another_consumers_order(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    order = _create_order(session).get_json()["data"]

    session.logout()
    _register(session, email="neighbour@example.com", phone="9830000010", full_name="Neighbour")
    assert session.get(f"/api/v1/orders/{order['id']}").status_code == 403
    assert (
        session.post(
            f"/api/v1/orders/{order['id']}/cancel", {"reason": "Not mine"}
        ).status_code
        == 403
    )
    assert session.get("/api/v1/orders").get_json()["data"] == []


def test_consumer_can_cancel_only_before_custody(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    first = _create_order(session).get_json()["data"]

    cancelled = session.post(
        f"/api/v1/orders/{first['id']}/cancel", {"reason": "Plans changed"}
    )
    assert cancelled.status_code == 200, cancelled.get_json()
    assert cancelled.get_json()["data"]["status"] == "cancelled"
    assert cancelled.get_json()["data"]["cancellation_reason"] == "Plans changed"

    second = _create_order(session).get_json()["data"]
    order = db.session.get(Order, second["id"])
    for status in (
        domain.ORDER_AWAITING_ASSIGNMENT,
        domain.ORDER_ASSIGNED,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
    ):
        record_status(order, status, source="system", reason="test progression")
    db.session.commit()

    blocked = session.post(
        f"/api/v1/orders/{second['id']}/cancel", {"reason": "Changed my mind"}
    )
    assert blocked.status_code == 409
    assert blocked.get_json()["error"]["code"] == "order_in_custody"

    tracking = session.get(f"/api/v1/orders/{second['id']}/tracking")
    assert tracking.status_code == 200
    body = tracking.get_json()["data"]
    assert body["status"] == "picked_up"
    assert body["is_closed"] is False
    assert len(body["timeline"]) == 7


def test_adding_images_respects_order_limits(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    order = _create_order(session).get_json()["data"]

    added = session.post_file(f"/api/v1/orders/{order['id']}/images")
    assert added.status_code == 201, added.get_json()
    assert len(added.get_json()["data"]["images"]) == 2
    primary = [row for row in added.get_json()["data"]["images"] if row["is_primary"]]
    assert len(primary) == 1

    # Once collected, no more parcel photographs.
    stored = db.session.get(Order, order["id"])
    for status in (
        domain.ORDER_AWAITING_ASSIGNMENT,
        domain.ORDER_ASSIGNED,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
    ):
        record_status(stored, status, source="system")
    db.session.commit()
    blocked = session.post_file(f"/api/v1/orders/{order['id']}/images")
    assert blocked.status_code == 409


# --------------------------------------------------------------------------- #
# Media privacy
# --------------------------------------------------------------------------- #
def test_media_is_served_by_signature_or_order_access(session, db, reference_data, app):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    detail = _create_order(session).get_json()["data"]
    signed_url = detail["images"][0]["url"]
    asset_id = signed_url.split("/api/v1/media/")[1].split("?")[0]

    # A signed URL works without a session.
    anonymous = app.test_client()
    signed = anonymous.get(signed_url)
    assert signed.status_code == 200
    assert signed.mimetype == "image/jpeg"
    assert signed.data.startswith(b"\xff\xd8\xff")
    assert signed.headers["Cache-Control"].startswith("private")

    tampered = anonymous.get(f"/api/v1/media/{asset_id}?expires=9999999999&signature=deadbeef")
    assert tampered.status_code == 403

    # The owner can read without a signature; another consumer cannot.
    assert session.get(f"/api/v1/media/{asset_id}").status_code == 200
    session.logout()
    _register(session, email="curious@example.com", phone="9830000011", full_name="Curious")
    assert session.get(f"/api/v1/media/{asset_id}").status_code == 403

    # The manager responsible for the pickup area can verify the photograph.
    manager = _manager(email="verifier@example.com", areas=[area])
    session.logout()
    session.login(manager.email)
    assert session.get(f"/api/v1/media/{asset_id}").status_code == 200


# --------------------------------------------------------------------------- #
# Notifications and consumer summary
# --------------------------------------------------------------------------- #
def test_notifications_can_be_read_and_counted(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    _create_order(session)

    feed = session.get("/api/v1/notifications")
    assert feed.status_code == 200
    assert feed.get_json()["meta"]["total"] == 1
    notification = feed.get_json()["data"][0]
    assert notification["read_at"] is None

    count = session.get("/api/v1/notifications/unread-count")
    assert count.get_json()["data"]["unread"] == 1

    read = session.post(f"/api/v1/notifications/{notification['id']}/read")
    assert read.status_code == 200
    assert read.get_json()["data"]["read_at"] is not None
    assert session.get("/api/v1/notifications/unread-count").get_json()["data"]["unread"] == 0

    _create_order(session)
    assert session.get("/api/v1/notifications/unread-count").get_json()["data"]["unread"] == 1
    marked = session.post("/api/v1/notifications/read-all")
    assert marked.get_json()["data"]["marked_read"] == 1


def test_consumer_summary_uses_stored_counts(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    _create_order(session)
    cancelled = _create_order(session).get_json()["data"]
    session.post(
        f"/api/v1/orders/{cancelled['id']}/cancel", {"reason": "Testing summary"}
    )

    summary = session.get("/api/v1/consumer/summary")
    assert summary.status_code == 200, summary.get_json()
    data = summary.get_json()["data"]
    assert data["counts"]["total"] == 2
    assert data["counts"]["awaiting_review"] == 1
    assert data["counts"]["cancelled"] == 1
    assert data["counts"]["delivered"] == 0
    assert data["counts"]["returns"] == 0
    assert len(data["active_orders"]) == 1
    assert data["profile"]["account_type"] == "individual"
    assert data["notifications"]["unread"] >= 1


def test_saved_address_can_be_used_for_pickup(session, db, reference_data):
    area = _service_area()
    _on_duty_driver(area=area)
    _register(session)
    saved = session.post(
        "/api/v1/users/me/addresses",
        {
            "label": "Home",
            "address_line": "12 Lake Road",
            "area": "Salt Lake",
            "latitude": 22.58,
            "longitude": 88.41,
            "contact_name": "Riya Sen",
            "contact_phone": "9830000001",
            "is_default_pickup": True,
        },
    )
    assert saved.status_code == 201, saved.get_json()
    address_id = saved.get_json()["data"]["id"]

    payload = _payload()
    payload["pickup"] = {"address_id": address_id}
    response = _create_order(session, payload)
    assert response.status_code == 201, response.get_json()
    body = response.get_json()["data"]
    assert body["pickup_address"]["address_line"] == "12 Lake Road"
    assert body["pickup_address"]["contact_phone"] == "9830000001"

    # A different consumer cannot borrow that address id.
    session.logout()
    _register(session, email="borrow@example.com", phone="9830000012", full_name="Borrow")
    payload = _payload()
    payload["pickup"] = {"address_id": address_id}
    blocked = _create_order(session, payload)
    assert blocked.status_code == 422
    assert "pickup.address_id" in blocked.get_json()["error"]["fields"]
