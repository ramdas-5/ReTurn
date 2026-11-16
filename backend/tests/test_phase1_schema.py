"""Phase 1 checks: schema, constraints, domain state machine, media storage."""
from __future__ import annotations

import io
import os
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app import domain
from app.extensions import db
from app.models import (
    DeliveryBatch,
    DriverAssignment,
    DriverProfile,
    MediaAsset,
    Order,
    OrderStatusHistory,
    ParcelDetail,
    User,
    Vehicle,
    VehicleCapacityProfile,
)
from app.security import hash_password
from app.services import storage


def _make_user(email, role="consumer", status="active"):
    user = User(
        email=email,
        full_name=email.split("@")[0],
        password_hash=hash_password("ReTurn#2026"),
        role=role,
        status=status,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _minimal_order(consumer):
    from datetime import datetime, timezone
    from app.services.orders import create_order

    now = datetime.now(timezone.utc)
    payload = {
        "service_type": "parcel",
        "pickup": {
            "contact_name": "Sender",
            "contact_phone": "9000000001",
            "address_line": "12 Lake Road",
            "area": "Salt Lake",
            "latitude": Decimal("22.580000"),
            "longitude": Decimal("88.410000"),
        },
        "delivery": {
            "contact_name": "Recipient",
            "contact_phone": "9000000002",
            "address_line": "8 Park Street",
            "area": "Park Street",
            "latitude": Decimal("22.550000"),
            "longitude": Decimal("88.350000"),
        },
        "parcel": {
            "name": "Books",
            "weight_kg": 2.5,
            "length_cm": 30,
            "width_cm": 20,
            "height_cm": 10,
        },
        "pickup_window_start": now + timedelta(hours=1),
        "pickup_window_end": now + timedelta(hours=3),
        "delivery_deadline": now + timedelta(hours=8),
    }
    order = create_order(consumer, payload)
    db.session.flush()
    return order


def test_all_expected_tables_exist(db):
    from sqlalchemy import text

    tables = {
        row[0]
        for row in db.session.execute(
            text("select tablename from pg_tables where schemaname='public'")
        )
    }
    for expected in (
        "users",
        "consumer_profiles",
        "business_profiles",
        "manager_profiles",
        "driver_profiles",
        "vehicles",
        "vehicle_capacity_profiles",
        "driver_duty_sessions",
        "driver_location_events",
        "service_areas",
        "orders",
        "parcel_details",
        "return_requests",
        "pickup_addresses",
        "delivery_addresses",
        "parcel_images",
        "order_status_history",
        "delivery_batches",
        "batch_orders",
        "route_plans",
        "route_stops",
        "route_legs",
        "driver_assignments",
        "matching_suggestions",
        "proof_media",
        "pickup_proofs",
        "delivery_proofs",
        "delivery_exceptions",
        "audit_logs",
        "admin_settings",
    ):
        assert expected in tables


def test_order_created_with_history_and_snapshot(db):
    consumer = _make_user("consumer@example.com")
    order = _minimal_order(consumer)
    assert order.order_number.startswith("RT-")
    assert order.status == domain.ORDER_PENDING_REVIEW
    assert order.parcel.weight_kg == Decimal("2.500")
    assert order.parcel.volume_m3 == Decimal("0.00600")
    history = OrderStatusHistory.query.filter_by(order_id=order.id).all()
    assert [row.to_status for row in history] == [
        domain.ORDER_SUBMITTED,
        domain.ORDER_PENDING_REVIEW,
    ]


def test_delivery_cannot_precede_pickup(db):
    from app.errors import ApiError
    from app.services.orders import record_status

    consumer = _make_user("consumer2@example.com")
    order = _minimal_order(consumer)
    with pytest.raises(ApiError) as exc:
        record_status(order, domain.ORDER_DELIVERED, source="system")
    assert exc.value.code == "invalid_status_transition"


def test_duplicate_active_assignment_rejected(db):
    consumer = _make_user("consumer3@example.com")
    driver = _make_user("driver@example.com", role="driver")
    profile = DriverProfile(user_id=driver.id, verification_status="verified")
    db.session.add(profile)
    db.session.flush()
    capacity = VehicleCapacityProfile(
        name="Bike",
        vehicle_type="bike",
        max_weight_kg=15,
        max_volume_m3=0.05,
        max_length_cm=60,
        max_width_cm=40,
        max_height_cm=40,
    )
    db.session.add(capacity)
    db.session.flush()
    vehicle = Vehicle(
        driver_id=profile.id,
        capacity_profile_id=capacity.id,
        vehicle_type="bike",
        registration_number="WB-01-AB-1234",
    )
    db.session.add(vehicle)
    db.session.flush()
    order = _minimal_order(consumer)
    db.session.add(
        DriverAssignment(
            order_id=order.id,
            driver_id=driver.id,
            vehicle_id=vehicle.id,
            status="active",
        )
    )
    db.session.flush()
    db.session.add(
        DriverAssignment(
            order_id=order.id,
            driver_id=driver.id,
            vehicle_id=vehicle.id,
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_media_storage_local_and_signature(app, db):
    app.config["MEDIA_LOCAL_DIR"] = os.path.join(
        os.path.dirname(__file__), "..", "var", "test-media"
    )
    with app.app_context():
        upload = type(
            "Upload",
            (),
            {
                "filename": "parcel.jpg",
                "mimetype": "image/jpeg",
                "read": lambda self: b"\xff\xd8\xff\xe0" + b"0" * 64,
                "__getattr__": lambda self, name: None,
            },
        )()
        asset = storage.save_image(upload)
        assert asset.content_type == "image/jpeg"
        assert asset.checksum_sha256
        signature = storage.sign_media_id(asset.id)
        expires = signature.split("expires=")[1].split("&")[0]
        sig = signature.split("signature=")[1]
        assert storage.verify_media_signature(asset.id, expires, sig)
        assert not storage.verify_media_signature(asset.id + 1, expires, sig)
        stream, content_type = storage.open_media(asset)
        assert content_type == "image/jpeg"
        assert stream.read().startswith(b"\xff\xd8")
        stream.close()


def test_bootstrap_admin_cli(runner, db):
    result = runner.invoke(args=["bootstrap-admin", "--email", "admin@example.com", "--password", "StrongPass123"])
    assert result.exit_code == 0, result.output
    admin = User.query.filter_by(email="admin@example.com").one()
    assert admin.role == "admin"
    assert admin.status == "active"
    # Idempotent: a second run does not create another admin.
    result2 = runner.invoke(args=["bootstrap-admin", "--email", "other@example.com", "--password", "StrongPass123"])
    assert result2.exit_code == 0
    assert User.query.filter_by(role="admin").count() == 1
