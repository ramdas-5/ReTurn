"""Deterministic, entirely fictional demo data for local demonstrations.

This module is only invoked by the explicit `seed` / `seed-if-empty` commands.
It never runs automatically in production. `reset=True` truncates the schema; the
CLI prints the target database and the standard deploy path only seeds an empty
database. All names, phone numbers and coordinates are fictional demo values.
"""
from __future__ import annotations

from datetime import timedelta
from io import BytesIO

from sqlalchemy import text
from werkzeug.datastructures import FileStorage

from .. import domain
from ..extensions import db
from ..models import (
    BusinessProfile,
    ConsumerProfile,
    DeliveryBatch,
    DeliveryException,
    DeliveryProof,
    DriverAssignment,
    DriverDutySession,
    DriverLocationEvent,
    DriverProfile,
    DriverServiceArea,
    ManagerProfile,
    ManagerServiceArea,
    MatchingSuggestion,
    Order,
    ParcelImage,
    PickupAddress,
    ProofMedia,
    SavedAddress,
    ServiceArea,
    User,
    Vehicle,
    VehicleCapacityProfile,
)
from ..security import hash_password
from . import dispatch, matching
from .notifications import notify_user
from .orders import create_order, record_status
from .reference import ensure_reference_data
from .storage import save_image

DEMO_PASSWORD = "ReTurn#2026"
AREA_COORDINATES = {
    "Barasat": (22.7240, 88.4780),
    "Madhyamgram": (22.7000, 88.4450),
    "Airport": (22.6540, 88.4460),
    "Salt Lake": (22.5800, 88.4100),
    "New Town": (22.5800, 88.4700),
}


def _truncate() -> None:
    from sqlalchemy import inspect

    existing = set(inspect(db.engine).get_table_names())
    tables = [table for table in db.metadata.tables.keys() if table in existing]
    if not tables:
        return
    names = ", ".join(f'"{table}"' for table in tables)
    db.session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    db.session.commit()


def _area(name: str, radius: float = 8.0) -> ServiceArea:
    latitude, longitude = AREA_COORDINATES[name]
    area = ServiceArea(
        name=name,
        city="Kolkata",
        state="West Bengal",
        postal_codes="",
        center_latitude=latitude,
        center_longitude=longitude,
        radius_km=radius,
        is_active=True,
    )
    db.session.add(area)
    db.session.flush()
    return area


def _user(email: str, name: str, role: str, phone: str, *, status: str = "active") -> User:
    user = User(
        email=email,
        full_name=name,
        phone=phone,
        role=role,
        status=status,
        password_hash=hash_password(DEMO_PASSWORD),
        activated_at=domain.utcnow() if status == "active" else None,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _driver(
    email: str,
    name: str,
    phone: str,
    areas: list[ServiceArea],
    vehicle_type: str,
    registration: str,
    *,
    latitude: float,
    longitude: float,
) -> tuple[User, DriverProfile, Vehicle]:
    user = _user(email, name, "driver", phone)
    profile = DriverProfile(
        user_id=user.id,
        verification_status=domain.VERIFICATION_VERIFIED,
        verified_at=domain.utcnow(),
        license_number=f"WB-DEMO-{user.id:04d}",
        completed_deliveries=0,
    )
    db.session.add(profile)
    db.session.flush()
    for area in areas:
        db.session.add(DriverServiceArea(driver_id=profile.id, service_area_id=area.id))
    capacity = VehicleCapacityProfile.query.filter_by(vehicle_type=vehicle_type).first()
    vehicle = Vehicle(
        driver_id=profile.id,
        capacity_profile_id=capacity.id,
        vehicle_type=vehicle_type,
        registration_number=registration,
        make="Demo",
        model="Fictional",
        color="Green",
        verification_status=domain.VERIFICATION_VERIFIED,
        is_active=True,
    )
    db.session.add(vehicle)
    now = domain.utcnow()
    session = DriverDutySession(
        driver_id=profile.id,
        status=domain.DUTY_AVAILABLE,
        started_at=now - timedelta(minutes=30),
        last_heartbeat_at=now,
        device_label="Demo phone",
        start_latitude=latitude,
        start_longitude=longitude,
    )
    db.session.add(session)
    db.session.flush()
    db.session.add(
        DriverLocationEvent(
            driver_id=profile.id,
            duty_session_id=session.id,
            latitude=latitude,
            longitude=longitude,
            accuracy_m=12,
            recorded_at=now,
            received_at=now,
            source="demo_fixture",
        )
    )
    return user, profile, vehicle


def _order_payload(
    *,
    service_type: str,
    pickup: dict,
    delivery: dict,
    parcel: dict,
    start_minutes: int = 60,
    return_details: dict | None = None,
    notes: str | None = None,
) -> dict:
    now = domain.utcnow().replace(microsecond=0)
    start = now + timedelta(minutes=start_minutes)
    return {
        "service_type": service_type,
        "pickup": {
            "contact_name": pickup["contact_name"],
            "contact_phone": pickup["contact_phone"],
            "address_line": pickup["address_line"],
            "area": pickup["area"],
            "city": "Kolkata",
            "state": "West Bengal",
            "latitude": pickup["latitude"],
            "longitude": pickup["longitude"],
            "instructions": pickup.get("instructions"),
        },
        "delivery": {
            "contact_name": delivery["contact_name"],
            "contact_phone": delivery["contact_phone"],
            "address_line": delivery["address_line"],
            "area": delivery["area"],
            "city": "Kolkata",
            "state": "West Bengal",
            "latitude": delivery["latitude"],
            "longitude": delivery["longitude"],
            "instructions": delivery.get("instructions"),
        },
        "parcel": parcel,
        "pickup_window_start": start,
        "pickup_window_end": start + timedelta(hours=2),
        "delivery_deadline": start + timedelta(hours=6),
        "service_notes": notes,
        "return_details": return_details,
        "is_demo": True,
    }


def _photo_upload() -> FileStorage:
    jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\x00" * 128
    )
    return FileStorage(
        stream=BytesIO(jpeg), filename="demo-proof.jpg", content_type="image/jpeg"
    )


def _delivered_with_proof(order: Order, driver_user: User, profile: DriverProfile) -> None:
    for status in (
        domain.ORDER_ASSIGNED,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_PICKED_UP,
        domain.ORDER_IN_TRANSIT,
        domain.ORDER_OUT_FOR_DELIVERY,
        domain.ORDER_DELIVERED,
    ):
        record_status(order, status, actor=driver_user, source="seed", reason="Demo history")
    db.session.flush()
    assignment = DriverAssignment.query.filter_by(order_id=order.id, status="active").one()
    assignment.status = "completed"
    assignment.ended_at = domain.utcnow()
    asset = save_image(_photo_upload(), uploaded_by=driver_user, error_prefix="demo_proof")
    address = order.delivery_address
    media = ProofMedia(
        order_id=order.id,
        driver_id=driver_user.id,
        proof_type=domain.PROOF_DELIVERY,
        media_id=asset.id,
        captured_at=domain.utcnow(),
        received_at=domain.utcnow(),
        latitude=address.latitude,
        longitude=address.longitude,
        accuracy_m=8,
        distance_from_stop_m=3,
        verification_status=domain.PROOF_VALID,
        verified_by_id=driver_user.id,
        verified_at=domain.utcnow(),
        notes="Demo proof fixture",
    )
    db.session.add(media)
    db.session.flush()
    db.session.add(
        DeliveryProof(
            order_id=order.id,
            driver_id=driver_user.id,
            proof_media_id=media.id,
            captured_at=domain.utcnow(),
            server_received_at=domain.utcnow(),
            status=domain.PROOF_VALID,
            recipient_name=address.contact_name,
            notes="Demo proof fixture",
        )
    )
    profile.completed_deliveries = (profile.completed_deliveries or 0) + 1


def seed_demo_data(*, reset: bool = False) -> dict:
    """Create the fictional demo scenario. Returns row-count style evidence."""
    if not reset and User.query.first() is not None:
        return {"skipped": 1, "reason": "database already has users"}

    if reset:
        _truncate()
    ensure_reference_data()
    db.session.flush()

    areas = {name: _area(name) for name in AREA_COORDINATES}
    all_areas = list(areas.values())

    admin = _user("admin@return.demo", "ReTurn Administrator", "admin", "9000000000")
    manager = _user("manager@return.demo", "Ananya Ghosh", "manager", "9000000001")
    manager_profile = ManagerProfile(
        user_id=manager.id, employee_code="MGR-001", created_by_id=admin.id
    )
    db.session.add(manager_profile)
    db.session.flush()
    for area in all_areas:
        db.session.add(
            ManagerServiceArea(manager_id=manager_profile.id, service_area_id=area.id)
        )

    arjun, arjun_profile, arjun_vehicle = _driver(
        "arjun@return.demo",
        "Arjun Das",
        "9000000010",
        all_areas,
        "bike",
        "WB-04-DEMO-01",
        latitude=AREA_COORDINATES["Barasat"][0],
        longitude=AREA_COORDINATES["Barasat"][1],
    )
    vikram, vikram_profile, vikram_vehicle = _driver(
        "vikram@return.demo",
        "Vikram Nair",
        "9000000011",
        all_areas,
        "van",
        "WB-04-DEMO-02",
        latitude=AREA_COORDINATES["Salt Lake"][0],
        longitude=AREA_COORDINATES["Salt Lake"][1],
    )

    priya = _user("priya@return.demo", "Priya Sen", "consumer", "9000000020")
    db.session.add(ConsumerProfile(user_id=priya.id, account_type="business"))
    db.session.add(
        BusinessProfile(
            user_id=priya.id,
            business_name="Sen Apparel (demo)",
            category="Clothing",
            contact_phone="9000000020",
            contact_email="priya@return.demo",
            address_line="7 Demo Lane",
            area="Barasat",
            city="Kolkata",
            latitude=AREA_COORDINATES["Barasat"][0],
            longitude=AREA_COORDINATES["Barasat"][1],
            verification_status=domain.VERIFICATION_NOT_REQUIRED,
        )
    )
    rahul = _user("rahul@return.demo", "Rahul Basu", "consumer", "9000000021")
    db.session.add(ConsumerProfile(user_id=rahul.id, account_type="individual"))
    amit = _user("amit@return.demo", "Amit Roy", "consumer", "9000000022")
    db.session.add(ConsumerProfile(user_id=amit.id, account_type="individual"))
    db.session.flush()

    def parcel(name: str, weight: float, length: float, width: float, height: float, **extra):
        data = {
            "name": name,
            "category": extra.pop("category", "general"),
            "quantity": 1,
            "weight_kg": weight,
            "length_cm": length,
            "width_cm": width,
            "height_cm": height,
            "is_fragile": extra.pop("is_fragile", False),
        }
        data.update(extra)
        return data

    def point(area_name: str, line: str, contact: str, phone: str) -> dict:
        latitude, longitude = AREA_COORDINATES[area_name]
        return {
            "contact_name": contact,
            "contact_phone": phone,
            "address_line": line,
            "area": area_name,
            "latitude": latitude,
            "longitude": longitude,
        }

    # 1. Pending returns / parcels in the manager review queue.
    shoes = create_order(
        rahul,
        _order_payload(
            service_type="return",
            pickup=point("Barasat", "12 Demo Street", "Rahul Basu", "9000000021"),
            delivery=point("Salt Lake", "Authorised Returns Hub, Sector V", "Returns Desk", "9000000030"),
            parcel=parcel("Running shoes", 1.2, 35, 25, 15, is_fragile=True),
            return_details={
                "product_name": "Running shoes",
                "reason": "Size did not fit",
                "merchant_name": "Sen Apparel (demo)",
                "destination_type": "warehouse",
                "authorization_confirmed": True,
                "merchant_approval_required": False,
            },
        ),
    )
    apparel = create_order(
        priya,
        _order_payload(
            service_type="parcel",
            pickup=point("Barasat", "7 Demo Lane", "Priya Sen", "9000000020"),
            delivery=point("New Town", "88 Demo Avenue", "Meera Kapoor", "9000000023"),
            parcel=parcel("Two shirts", 1.8, 30, 22, 8),
            notes="Business order S-1042",
        ),
    )
    heavy = create_order(
        amit,
        _order_payload(
            service_type="parcel",
            pickup=point("Madhyamgram", "5 Heavy Road", "Amit Roy", "9000000022"),
            delivery=point("Airport", "Cargo demo desk", "Airport desk", "9000000031"),
            parcel=parcel("Flat-pack desk", 40.0, 120, 60, 20),
        ),
    )
    for order in (shoes, apparel):
        record_status(
            order,
            domain.ORDER_AWAITING_ASSIGNMENT,
            actor=manager,
            source="seed",
            reason="Approved for scheduling (demo)",
        )
        order.approved_by_id = manager.id
        order.approved_at = domain.utcnow()
    db.session.flush()

    # 2. An active shared route for Arjun.
    batch = dispatch.create_batch(
        [shoes, apparel],
        arjun,
        actor=manager,
        planned_start=domain.utcnow(),
        notes="Demo shared route: Barasat → Salt Lake / New Town",
    )
    batch.status = domain.BATCH_ACTIVE
    batch.started_at = domain.utcnow()
    db.session.flush()
    record_status(
        shoes, domain.ORDER_PICKUP_SCHEDULED, actor=arjun, source="seed", reason="Demo route progress"
    )
    record_status(
        apparel,
        domain.ORDER_PICKUP_SCHEDULED,
        actor=arjun,
        source="seed",
        reason="Demo route progress",
    )
    record_status(
        shoes, domain.ORDER_PICKUP_ARRIVED, actor=arjun, source="seed", reason="Demo route progress"
    )

    # 3. A newly approved order that fits the active route — persisted suggestion.
    on_route = create_order(
        priya,
        _order_payload(
            service_type="parcel",
            pickup=point("Airport", "9 Gate Road", "Priya Sen", "9000000020"),
            delivery=point("Salt Lake", "21 Sector II", "Rohan Gupta", "9000000024"),
            parcel=parcel("Documents", 0.4, 25, 18, 4),
        ),
    )
    record_status(
        on_route,
        domain.ORDER_AWAITING_ASSIGNMENT,
        actor=manager,
        source="seed",
        reason="Approved for scheduling (demo)",
    )
    on_route.approved_by_id = manager.id
    on_route.approved_at = domain.utcnow()
    db.session.flush()
    db.session.expire_all()
    matching.scan_order(on_route, manager)

    # 4. A delivered order with valid proof (therefore legitimate history).
    delivered = create_order(
        priya,
        _order_payload(
            service_type="parcel",
            pickup=point("Barasat", "7 Demo Lane", "Priya Sen", "9000000020"),
            delivery=point("Salt Lake", "14 Demo Park", "Sneha Mitra", "9000000025"),
            parcel=parcel("Gift box", 1.1, 28, 20, 12),
            start_minutes=-180,
        ),
    )
    record_status(
        delivered,
        domain.ORDER_AWAITING_ASSIGNMENT,
        actor=manager,
        source="seed",
        reason="Approved for scheduling (demo)",
    )
    db.session.flush()
    db.session.add(
        DriverAssignment(
            order_id=delivered.id,
            driver_id=vikram.id,
            vehicle_id=vikram_vehicle.id,
            assigned_by_id=manager.id,
            status="active",
        )
    )
    db.session.flush()
    _delivered_with_proof(delivered, vikram, vikram_profile)

    # 5. One exception that needs a manager decision.
    failed = create_order(
        amit,
        _order_payload(
            service_type="parcel",
            pickup=point("Madhyamgram", "5 Heavy Road", "Amit Roy", "9000000022"),
            delivery=point("New Town", "3 Demo Circle", "Dev Sharma", "9000000026"),
            parcel=parcel("Fragile ceramics", 3.0, 40, 30, 25, is_fragile=True),
        ),
    )
    record_status(failed, domain.ORDER_AWAITING_ASSIGNMENT, actor=manager, source="seed", reason="Approved")
    db.session.add(
        DriverAssignment(
            order_id=failed.id,
            driver_id=vikram.id,
            vehicle_id=vikram_vehicle.id,
            assigned_by_id=manager.id,
            status="active",
        )
    )
    db.session.flush()
    for status in (
        domain.ORDER_ASSIGNED,
        domain.ORDER_PICKUP_SCHEDULED,
        domain.ORDER_PICKUP_ARRIVED,
        domain.ORDER_FAILED,
    ):
        record_status(failed, status, actor=vikram, source="seed", reason="Demo failed pickup")
    db.session.add(
        DeliveryException(
            order_id=failed.id,
            driver_id=vikram.id,
            exception_type="parcel_damaged",
            description="Demo fixture: packaging was damaged before collection.",
            status=domain.EXCEPTION_OPEN,
        )
    )

    # 6. A saved address and a notification so empty states are not misleading.
    db.session.add(
        SavedAddress(
            user_id=rahul.id,
            label="Home (demo)",
            contact_name="Rahul Basu",
            contact_phone="9000000021",
            address_line="12 Demo Street",
            area="Barasat",
            city="Kolkata",
            state="West Bengal",
            latitude=AREA_COORDINATES["Barasat"][0],
            longitude=AREA_COORDINATES["Barasat"][1],
            is_default_pickup=True,
        )
    )
    notify_user(
        priya,
        "order_status",
        f"Order {apparel.order_number} assigned",
        "Your parcel is on Arjun's shared route.",
        link=f"/consumer/orders/{apparel.id}",
        event_data={"order_id": apparel.id, "demo": True},
    )

    db.session.commit()
    return {
        "users": User.query.count(),
        "consumers": User.query.filter_by(role="consumer").count(),
        "drivers": User.query.filter_by(role="driver").count(),
        "managers": User.query.filter_by(role="manager").count(),
        "service_areas": ServiceArea.query.count(),
        "orders": Order.query.count(),
        "batches": DeliveryBatch.query.count(),
        "suggestions": MatchingSuggestion.query.count(),
        "open_exceptions": DeliveryException.query.filter_by(status="open").count(),
        "capacity_profiles": VehicleCapacityProfile.query.count(),
        "demo_password": DEMO_PASSWORD,
    }
