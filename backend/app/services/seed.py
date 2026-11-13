"""Deterministic fictional demo data for ReTurn (development only).

All names, addresses and contact details are fictional. Coordinates are
approximate area centroids for a Barasat / Kolkata demonstration, not real
customer addresses.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text

from ..domain import (
    BATCH_COMPLETED,
    PARCEL_DELIVERED,
    PARCEL_PICKUP_ARRIVED,
    PARCEL_PICKED_UP,
    PARCEL_IN_TRANSIT,
    PARCEL_PARTNER_ACCEPTED,
    PARTNER_VERIFIED,
    REQUEST_COMPLETED,
    REQUEST_PENDING,
    iso,
    utcnow,
)
from ..extensions import db
from ..models import (
    BatchAssignment,
    BatchRequest,
    BatchStop,
    DeliveryBatch,
    DeliveryRequest,
    Location,
    PartnerProfile,
    Parcel,
    RecipientDetail,
    ReturnDetail,
    AuditEvent,
    IssueReport,
    Notification,
    TrackingEvent,
    User,
)
from ..security import hash_password

DEMO_PASSWORD = "ReTurn#2026"
_SEED_HASH: str | None = None

LOCATIONS = [
    # label, address, area, lat, lng, is_hub
    ("Barasat — Champadali More", "Champadali More, Barasat", "Barasat", 22.7241, 88.4821, False),
    ("Barasat — Nabapally", "Nabapally, Barasat", "Barasat", 22.7195, 88.4870, False),
    ("Barasat — Colony More", "Colony More, Barasat", "Barasat", 22.7230, 88.4790, False),
    ("Barasat — Jessore Road", "Jessore Road, Barasat", "Barasat", 22.7305, 88.4900, False),
    ("Madhyamgram — Station Road", "Station Road, Madhyamgram", "Madhyamgram", 22.7005, 88.4460, False),
    ("Madhyamgram — Badu", "Badu, Madhyamgram", "Madhyamgram", 22.7040, 88.4530, False),
    ("Birati — Nimta Road", "Nimta Road, Birati", "Birati", 22.6660, 88.4180, False),
    ("Dum Dum — Cantonment", "Cantonment Road, Dum Dum", "Dum Dum", 22.6420, 88.4280, False),
    ("Salt Lake — Sector V", "Sector V, Bidhannagar", "Salt Lake", 22.5726, 88.4282, False),
    ("Salt Lake — Sector II", "Sector II, Bidhannagar", "Salt Lake", 22.5860, 88.4150, False),
    ("New Town — Action Area II", "Action Area II, New Town", "New Town", 22.5920, 88.4650, False),
    ("Bidhannagar — Karunamoyee", "Karunamoyee, Bidhannagar", "Salt Lake", 22.5790, 88.4080, False),
    (
        "ReTurn Authorized Returns Hub — Barasat",
        "Authorized returns facility, Barasat",
        "Barasat",
        22.7155,
        88.4650,
        True,
    ),
    (
        "ReTurn Authorized Returns Hub — New Town",
        "Authorized returns facility, New Town",
        "New Town",
        22.5980,
        88.4700,
        True,
    ),
    (
        "ReTurn Authorized Returns Hub — Salt Lake",
        "Authorized returns facility, Salt Lake",
        "Salt Lake",
        22.5800,
        88.4320,
        True,
    ),
]


def _truncate():
    db.session.execute(
        text(
            "TRUNCATE TABLE audit_events, issue_reports, notifications, tracking_events, "
            "batch_assignments, batch_stops, batch_requests, delivery_batches, matching_runs, "
            "return_details, recipient_details, parcels, delivery_requests, partner_profiles, "
            "user_sessions, users, locations RESTART IDENTITY CASCADE"
        )
    )
    db.session.commit()


def _loc_by_label(label: str) -> Location:
    location = Location.query.filter_by(label=label).first()
    if location is None:
        raise RuntimeError(f"Seed location missing: {label}")
    return location


def _user(name: str, email: str, role: str, phone: str | None = None, disabled: bool = False) -> User:
    global _SEED_HASH
    if _SEED_HASH is None:
        _SEED_HASH = hash_password(DEMO_PASSWORD)
    user = User(
        name=name,
        email=email,
        role=role,
        phone=phone,
        password_hash=_SEED_HASH,
        disabled_at=utcnow() if disabled else None,
        notify_email=True,
        notify_in_app=True,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _request(
    customer: User,
    service_type: str,
    pickup: Location,
    destination: Location,
    *,
    window_start_delta: int,
    window_end_delta: int,
    deadline_delta: int,
    description: str,
    weight_kg: float,
    volume_m3: float,
    size_class: str,
    handling: list[str] | None = None,
    notes: str | None = None,
    status: str = REQUEST_PENDING,
    base=None,
    authorized_hub: str | None = None,
    return_reference: str | None = None,
    retailer: str | None = None,
    recipient_name: str | None = None,
    recipient_phone: str | None = None,
    instructions: str | None = None,
    tracking_number: str,
    parcel_status: str = "pending",
) -> tuple[DeliveryRequest, Parcel]:
    base = base or utcnow()
    request = DeliveryRequest(
        customer_id=customer.id,
        type=service_type,
        pickup_location_id=pickup.id,
        destination_location_id=destination.id,
        pickup_window_start=base + timedelta(minutes=window_start_delta),
        pickup_window_end=base + timedelta(minutes=window_end_delta),
        delivery_deadline=base + timedelta(minutes=deadline_delta),
        status=status,
        notes=notes,
        created_at=base,
    )
    db.session.add(request)
    db.session.flush()
    parcel = Parcel(
        request_id=request.id,
        description=description,
        category="apparel" if service_type == "return" else "general",
        weight_kg=weight_kg,
        volume_m3=volume_m3,
        size_class=size_class,
        handling_flags=",".join(handling or []),
        tracking_number=tracking_number,
        status=parcel_status,
    )
    db.session.add(parcel)
    if service_type == "return":
        db.session.add(
            ReturnDetail(
                request_id=request.id,
                authorized_hub_name=authorized_hub or destination.label,
                return_reference=return_reference,
                retailer=retailer,
            )
        )
    else:
        db.session.add(
            RecipientDetail(
                request_id=request.id,
                recipient_name=recipient_name or "Recipient",
                recipient_phone=recipient_phone,
                delivery_instructions=instructions,
            )
        )
    db.session.flush()
    return request, parcel


def seed_demo_data(reset: bool = True) -> dict:
    if reset:
        _truncate()

    for index, (label, address, area, lat, lng, is_hub) in enumerate(LOCATIONS):
        db.session.add(
            Location(
                label=label,
                address_line=address,
                area=area,
                city="Kolkata",
                latitude=lat,
                longitude=lng,
                source="sample",
                is_sample=True,
            )
        )
    db.session.flush()

    admin = _user("Ananya Bose", "admin@return.demo", "admin", "+91 90000 10001")
    partner = _user("Sourav Ghosh", "partner@return.demo", "partner", "+91 90000 20001")
    pending_partner = _user("Ritika Das", "partner2@return.demo", "partner", "+91 90000 20002")
    rahul = _user("Rahul Basu", "rahul@return.demo", "customer", "+91 90000 30001")
    priya = _user("Priya Sen", "priya@return.demo", "customer", "+91 90000 30002")
    amit = _user("Amit Roy", "amit@return.demo", "customer", "+91 90000 30003")
    sneha = _user("Sneha Mitra", "sneha@return.demo", "customer", "+91 90000 30004")
    vikram = _user("Vikram Nair", "vikram@return.demo", "customer", "+91 90000 30005")
    farhan = _user("Farhan Ali", "farhan@return.demo", "customer", "+91 90000 30006")
    neha = _user("Neha Chatterjee", "neha@return.demo", "customer", "+91 90000 30007")
    arjun = _user("Arjun Dutta", "arjun@return.demo", "customer", "+91 90000 30008")

    partner_profile = PartnerProfile(
        user_id=partner.id,
        company_name="Barasat Neighbourhood Couriers",
        vehicle_type="van",
        max_weight_kg=40,
        max_volume_m3=0.25,
        accepts_fragile=True,
        accepts_restricted=True,
        service_areas="Barasat, Madhyamgram, Salt Lake, New Town, Dum Dum, Birati",
        availability="available",
        verification_status=PARTNER_VERIFIED,
        verification_note="Verified against demo vehicle and service-area documents.",
        verified_at=utcnow() - timedelta(days=6),
        verified_by_id=admin.id,
    )
    db.session.add(partner_profile)
    db.session.add(
        PartnerProfile(
            user_id=pending_partner.id,
            company_name="Ritika Two-Wheeler Deliveries",
            vehicle_type="bike",
            max_weight_kg=12,
            max_volume_m3=0.06,
            accepts_fragile=True,
            accepts_restricted=False,
            service_areas="Barasat, Salt Lake",
            availability="available",
            verification_status="pending",
        )
    )

    hub_barasat = _loc_by_label("ReTurn Authorized Returns Hub — Barasat")
    hub_new_town = _loc_by_label("ReTurn Authorized Returns Hub — New Town")
    hub_salt_lake = _loc_by_label("ReTurn Authorized Returns Hub — Salt Lake")
    barasat_pickup = _loc_by_label("Barasat — Champadali More")
    barasat_nabapally = _loc_by_label("Barasat — Nabapally")
    barasat_colony = _loc_by_label("Barasat — Colony More")
    barasat_jessore = _loc_by_label("Barasat — Jessore Road")
    dum_dum = _loc_by_label("Dum Dum — Cantonment")
    salt_lake = _loc_by_label("Salt Lake — Sector V")
    new_town = _loc_by_label("New Town — Action Area II")
    birati = _loc_by_label("Birati — Nimta Road")

    # ------------------------------------------------------------- pending demo
    rahul_req, rahul_parcel = _request(
        rahul,
        "return",
        barasat_pickup,
        hub_new_town,
        window_start_delta=75,
        window_end_delta=170,
        deadline_delta=300,
        description="Running shoes in the original box",
        weight_kg=1.2,
        volume_m3=0.014,
        size_class="small",
        notes="Ring the bell at the side gate. Box is taped for return.",
        authorized_hub="ReTurn Authorized Returns Hub — New Town",
        return_reference="RET-SHOE-88421",
        retailer="Stride & Co.",
        tracking_number="RTN-TRK-884210",
    )
    priya_req, priya_parcel = _request(
        priya,
        "parcel",
        barasat_nabapally,
        salt_lake,
        window_start_delta=60,
        window_end_delta=160,
        deadline_delta=360,
        description="Hardcover book, gift-wrapped",
        weight_kg=0.8,
        volume_m3=0.006,
        size_class="small",
        notes="Please keep upright.",
        recipient_name="Ananya Ghosh",
        recipient_phone="+91 90000 40001",
        instructions="Hand to the recipient; call on arrival.",
        tracking_number="RTN-TRK-884211",
    )
    amit_req, amit_parcel = _request(
        amit,
        "return",
        barasat_jessore,
        hub_salt_lake,
        window_start_delta=70,
        window_end_delta=175,
        deadline_delta=330,
        description="Wireless headphones with charging case",
        weight_kg=0.6,
        volume_m3=0.008,
        size_class="small",
        handling=["fragile"],
        notes="Fragile electronics. Please handle with care.",
        authorized_hub="ReTurn Authorized Returns Hub — Salt Lake",
        return_reference="RET-AUDIO-55102",
        retailer="Sonic Labs",
        tracking_number="RTN-TRK-884212",
    )
    sneha_req, sneha_parcel = _request(
        sneha,
        "return",
        barasat_colony,
        hub_barasat,
        window_start_delta=85,
        window_end_delta=180,
        deadline_delta=320,
        description="Oversized study desk (flat-pack)",
        weight_kg=55,
        volume_m3=0.32,
        size_class="large",
        handling=[],
        notes="Counterexample: exceeds the demo van's capacity.",
        authorized_hub="ReTurn Authorized Returns Hub — Barasat",
        return_reference="RET-DESK-11009",
        retailer="HomeWorks",
        tracking_number="RTN-TRK-884213",
    )
    vikram_req, vikram_parcel = _request(
        vikram,
        "parcel",
        barasat_jessore,
        dum_dum,
        window_start_delta=95,
        window_end_delta=140,
        deadline_delta=100,
        description="Sealed document envelope",
        weight_kg=0.3,
        volume_m3=0.002,
        size_class="small",
        handling=[],
        notes="Counterexample: deadline is earlier than any feasible pickup + travel.",
        recipient_name="Meera Nair",
        recipient_phone="+91 90000 40002",
        instructions="Deliver to the security desk.",
        tracking_number="RTN-TRK-884214",
    )
    farhan_req, farhan_parcel = _request(
        farhan,
        "parcel",
        barasat_jessore,
        salt_lake,
        window_start_delta=90,
        window_end_delta=170,
        deadline_delta=340,
        description="Used power bank with lithium cells",
        weight_kg=2.0,
        volume_m3=0.004,
        size_class="small",
        handling=["restricted"],
        notes="Restricted item: requires a dedicated vehicle, cannot share a batch.",
        recipient_name="Sana Ali",
        recipient_phone="+91 90000 40003",
        instructions="Recipient must sign for the restricted item.",
        tracking_number="RTN-TRK-884215",
    )

    # ------------------------------------------------------- completed history
    history_base = utcnow() - timedelta(days=1)
    neha_req, neha_parcel = _request(
        neha,
        "return",
        new_town,
        hub_new_town,
        window_start_delta=0,
        window_end_delta=60,
        deadline_delta=150,
        description="Foldable keyboard return",
        weight_kg=0.9,
        volume_m3=0.01,
        size_class="small",
        authorized_hub="ReTurn Authorized Returns Hub — New Town",
        return_reference="RET-KEY-67010",
        retailer="TypeWorks",
        tracking_number="RTN-TRK-884216",
        status=REQUEST_COMPLETED,
        base=history_base,
        parcel_status=PARCEL_DELIVERED,
    )
    arjun_req, arjun_parcel = _request(
        arjun,
        "parcel",
        _loc_by_label("Salt Lake — Sector II"),
        birati,
        window_start_delta=5,
        window_end_delta=70,
        deadline_delta=180,
        description="Board game in a gift box",
        weight_kg=1.8,
        volume_m3=0.02,
        size_class="medium",
        handling=["fragile"],
        recipient_name="Rohit Dutta",
        recipient_phone="+91 90000 40004",
        instructions="Leave with the building concierge if unavailable.",
        tracking_number="RTN-TRK-884217",
        status=REQUEST_COMPLETED,
        base=history_base,
        parcel_status=PARCEL_DELIVERED,
    )

    completed_batch = DeliveryBatch(
        status=BATCH_COMPLETED,
        partner_id=partner.id,
        created_by_id=admin.id,
        distance_km=14.2,
        duration_minutes=71,
        baseline_km=18.6,
        savings_km=4.4,
        savings_percent=23.7,
        distance_source="estimated",
        geometry_source="estimated",
        route_method="Pickup-and-delivery insertion heuristic (rule-based)",
        explanation={
            "included_reasons": [
                "Pickup windows overlap in the 09:00–10:10 window.",
                "Pickup order handles New Town before Salt Lake Sector II.",
                "Two different destinations preserved: authorised hub and recipient address.",
            ],
            "distance_source_label": "Estimated demo record (seed data)",
            "note": "Seeded completed batch for history and analytics demonstration.",
        },
        assumptions=[
            "Seeded historical batch; distances are modelled estimates.",
            "Baseline is one direct pickup→destination trip per request.",
        ],
        load_profile=[
            {"sequence": 1, "kind": "pickup", "request_code": f"RTN-REQ-{1000 + neha_req.id}", "weight_kg": 0.9, "volume_m3": 0.01},
            {"sequence": 2, "kind": "pickup", "request_code": f"RTN-REQ-{1000 + arjun_req.id}", "weight_kg": 2.7, "volume_m3": 0.03},
            {"sequence": 3, "kind": "dropoff", "request_code": f"RTN-REQ-{1000 + neha_req.id}", "weight_kg": 1.8, "volume_m3": 0.02},
            {"sequence": 4, "kind": "dropoff", "request_code": f"RTN-REQ-{1000 + arjun_req.id}", "weight_kg": 0.0, "volume_m3": 0.0},
        ],
        offered_at=history_base - timedelta(hours=2),
        accepted_at=history_base - timedelta(hours=1, minutes=50),
        started_at=history_base,
        completed_at=history_base + timedelta(hours=2),
        created_at=history_base - timedelta(hours=3),
        geometry={
            "type": "LineString",
            "coordinates": [
                [88.4650, 22.5920],
                [88.4150, 22.5860],
                [88.4700, 22.5980],
                [88.4180, 22.6660],
            ],
        },
    )
    db.session.add(completed_batch)
    db.session.flush()
    for req in (neha_req, arjun_req):
        db.session.add(BatchRequest(batch_id=completed_batch.id, request_id=req.id))
    history_stops = [
        (neha_req, "pickup", new_town, history_base, history_base + timedelta(minutes=6), 0.0, 0.9, 0.01),
        (arjun_req, "pickup", _loc_by_label("Salt Lake — Sector II"), history_base + timedelta(minutes=20), history_base + timedelta(minutes=26), 7.1, 2.7, 0.03),
        (neha_req, "dropoff", hub_new_town, history_base + timedelta(minutes=52), history_base + timedelta(minutes=58), 6.2, 1.8, 0.02),
        (arjun_req, "dropoff", birati, history_base + timedelta(minutes=135), history_base + timedelta(minutes=141), 5.1, 0.0, 0.0),
    ]
    for sequence, (req, kind, location, arrival, departure, leg_km, load_w, load_v) in enumerate(
        history_stops, start=1
    ):
        db.session.add(
            BatchStop(
                batch_id=completed_batch.id,
                request_id=req.id,
                kind=kind,
                sequence=sequence,
                location_id=location.id,
                planned_arrival=arrival,
                planned_departure=departure,
                service_minutes=6,
                leg_distance_km=leg_km,
                leg_duration_minutes=int(leg_km / 24 * 60),
                load_weight_kg=load_w,
                load_volume_m3=load_v,
                status="done",
                completed_at=departure,
            )
        )
    db.session.add(
        BatchAssignment(
            batch_id=completed_batch.id,
            partner_id=partner.id,
            actor_id=admin.id,
            action="accepted",
            reason="Seeded completed assignment.",
            created_at=history_base - timedelta(hours=1, minutes=50),
        )
    )
    for req, parcel in ((neha_req, neha_parcel), (arjun_req, arjun_parcel)):
        for offset, event_type, note in (
            (0, PARCEL_PARTNER_ACCEPTED, "Partner accepted the batch."),
            (20, PARCEL_PICKUP_ARRIVED, "Partner arrived at the pickup location."),
            (26, PARCEL_PICKED_UP, "Parcel collected from the customer."),
            (60, PARCEL_IN_TRANSIT, "Parcel loaded and moving along the shared route."),
            (140, PARCEL_DELIVERED, "Delivered and handover recorded."),
        ):
            db.session.add(
                TrackingEvent(
                    parcel_id=parcel.id,
                    request_id=req.id,
                    event_type=event_type,
                    actor_id=partner.id,
                    notes=note,
                    created_at=history_base + timedelta(minutes=offset),
                )
            )

    # --------------------------------------------------------------- issues etc
    db.session.add(
        IssueReport(
            request_id=arjun_req.id,
            batch_id=completed_batch.id,
            reporter_id=arjun.id,
            category="damaged_parcel",
            severity="medium",
            description="Recipient reported the outer gift box was dented on arrival.",
            status="open",
            created_at=history_base + timedelta(hours=3),
        )
    )
    db.session.add(
        IssueReport(
            request_id=neha_req.id,
            batch_id=completed_batch.id,
            reporter_id=partner.id,
            category="address_problem",
            severity="low",
            description="Gate code was missing from the pickup notes; resolved by calling the customer.",
            status="resolved",
            resolution_note="Confirmed gate code with the customer and updated the delivery note.",
            resolved_by_id=admin.id,
            resolved_at=history_base + timedelta(hours=4),
            created_at=history_base + timedelta(hours=1),
        )
    )
    db.session.add(
        Notification(
            user_id=rahul.id,
            type="request_created",
            title="Return request received",
            body="Your shoes return is waiting for compatible requests. Grouping is not guaranteed.",
            link=f"/customer/requests/{rahul_req.id}",
            created_at=utcnow() - timedelta(minutes=12),
        )
    )
    db.session.add(
        AuditEvent(
            actor_id=admin.id,
            action="partner.verified",
            entity_type="partner",
            entity_id=partner.id,
            summary="Verified Barasat Neighbourhood Couriers for van operations.",
            created_at=utcnow() - timedelta(days=6),
        )
    )
    db.session.add(
        AuditEvent(
            actor_id=admin.id,
            action="batch.completed",
            entity_type="batch",
            entity_id=completed_batch.id,
            summary="Seeded completed batch for demonstration history.",
            created_at=history_base + timedelta(hours=2),
        )
    )
    db.session.commit()

    return {
        "users": {
            "admin": "admin@return.demo",
            "verified_partner": "partner@return.demo",
            "pending_partner": "partner2@return.demo",
            "customers": ["rahul@return.demo", "priya@return.demo", "amit@return.demo"],
        },
        "password": DEMO_PASSWORD,
        "requests": {
            "rahul_return": f"RTN-REQ-{1000 + rahul_req.id}",
            "priya_parcel": f"RTN-REQ-{1000 + priya_req.id}",
            "amit_return": f"RTN-REQ-{1000 + amit_req.id}",
            "capacity_counterexample": f"RTN-REQ-{1000 + sneha_req.id}",
            "deadline_counterexample": f"RTN-REQ-{1000 + vikram_req.id}",
            "restricted_counterexample": f"RTN-REQ-{1000 + farhan_req.id}",
            "completed_history": [f"RTN-REQ-{1000 + neha_req.id}", f"RTN-REQ-{1000 + arjun_req.id}"],
        },
        "completed_batch": f"RTN-BAT-{200 + completed_batch.id}",
        "seeded_at": iso(utcnow()),
    }
