"""Relational model for ReTurn (PostgreSQL).

Every operational record is persisted. Offer/decision history, parcel tracking
and admin actions are append-only; current state is projected onto the owning
row for efficient queries.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Index, text

from .extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    timezone_name = db.Column(db.String(64), nullable=False, default="Asia/Kolkata")
    notify_email = db.Column(db.Boolean, nullable=False, default=True)
    notify_in_app = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    last_login_at = db.Column(db.DateTime(timezone=True))
    disabled_at = db.Column(db.DateTime(timezone=True))

    partner_profile = db.relationship(
        "PartnerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="PartnerProfile.user_id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User {self.email} {self.role}>"


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    csrf_token = db.Column(db.String(64), nullable=False)
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User")


class PartnerProfile(db.Model):
    __tablename__ = "partner_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    company_name = db.Column(db.String(160), nullable=False, default="Independent partner")
    vehicle_type = db.Column(db.String(20), nullable=False, default="van")
    max_weight_kg = db.Column(db.Numeric(7, 2), nullable=False, default=25)
    max_volume_m3 = db.Column(db.Numeric(7, 3), nullable=False, default=0.15)
    accepts_fragile = db.Column(db.Boolean, nullable=False, default=True)
    accepts_restricted = db.Column(db.Boolean, nullable=False, default=False)
    service_areas = db.Column(db.String(500), nullable=False, default="")
    availability = db.Column(db.String(20), nullable=False, default="available", index=True)
    verification_status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    verification_note = db.Column(db.String(500))
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    operating_start_hour = db.Column(db.Integer, nullable=False, default=8)
    operating_end_hour = db.Column(db.Integer, nullable=False, default=21)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    user = db.relationship("User", back_populates="partner_profile", foreign_keys=[user_id])

    @property
    def service_area_list(self) -> list[str]:
        return [area.strip() for area in (self.service_areas or "").split(",") if area.strip()]


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(160), nullable=False)
    address_line = db.Column(db.String(255), nullable=False)
    area = db.Column(db.String(120), nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False, default="Kolkata")
    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    source = db.Column(db.String(30), nullable=False, default="customer_pin")
    is_sample = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)


class DeliveryRequest(db.Model):
    __tablename__ = "delivery_requests"
    __table_args__ = (
        Index("ix_requests_status_window", "status", "pickup_window_start"),
        Index("ix_requests_customer_status", "customer_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    pickup_location_id = db.Column(
        db.Integer, db.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    destination_location_id = db.Column(
        db.Integer, db.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    pickup_window_start = db.Column(db.DateTime(timezone=True), nullable=False)
    pickup_window_end = db.Column(db.DateTime(timezone=True), nullable=False)
    delivery_deadline = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending_matching", index=True)
    notes = db.Column(db.String(1000))
    priority = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)
    cancelled_at = db.Column(db.DateTime(timezone=True))
    cancellation_reason = db.Column(db.String(500))
    failure_reason = db.Column(db.String(500))

    customer = db.relationship("User", foreign_keys=[customer_id])
    pickup_location = db.relationship("Location", foreign_keys=[pickup_location_id])
    destination_location = db.relationship("Location", foreign_keys=[destination_location_id])
    parcel = db.relationship("Parcel", back_populates="request", uselist=False)
    return_detail = db.relationship(
        "ReturnDetail", back_populates="request", uselist=False, cascade="all, delete-orphan"
    )
    recipient_detail = db.relationship(
        "RecipientDetail", back_populates="request", uselist=False, cascade="all, delete-orphan"
    )
    batch_links = db.relationship(
        "BatchRequest", back_populates="request", cascade="all, delete-orphan"
    )

    @property
    def code(self) -> str:
        from .domain import request_code

        return request_code(self.id)


class Parcel(db.Model):
    __tablename__ = "parcels"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("delivery_requests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="general")
    weight_kg = db.Column(db.Numeric(7, 2), nullable=False)
    volume_m3 = db.Column(db.Numeric(7, 3), nullable=False)
    size_class = db.Column(db.String(20), nullable=False, default="small")
    handling_flags = db.Column(db.String(120), nullable=False, default="")
    declared_value_inr = db.Column(db.Numeric(10, 2))
    tracking_number = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    request = db.relationship("DeliveryRequest", back_populates="parcel")

    @property
    def code(self) -> str:
        from .domain import parcel_code

        return parcel_code(self.id)

    @property
    def handling_list(self) -> list[str]:
        return [flag for flag in (self.handling_flags or "").split(",") if flag]


class ReturnDetail(db.Model):
    __tablename__ = "return_details"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("delivery_requests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    authorized_hub_name = db.Column(db.String(160), nullable=False)
    return_reference = db.Column(db.String(120))
    retailer = db.Column(db.String(160))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    request = db.relationship("DeliveryRequest", back_populates="return_detail")


class RecipientDetail(db.Model):
    __tablename__ = "recipient_details"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("delivery_requests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    recipient_name = db.Column(db.String(160), nullable=False)
    recipient_phone = db.Column(db.String(40))
    delivery_instructions = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    request = db.relationship("DeliveryRequest", back_populates="recipient_detail")


class MatchingRun(db.Model):
    __tablename__ = "matching_runs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    params = db.Column(db.JSON, nullable=False, default=dict)
    result = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, index=True)

    actor = db.relationship("User")


class DeliveryBatch(db.Model):
    __tablename__ = "delivery_batches"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), nullable=False, default="proposed", index=True)
    partner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    matching_run_id = db.Column(db.Integer, db.ForeignKey("matching_runs.id", ondelete="SET NULL"))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    distance_km = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    baseline_km = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    savings_km = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    savings_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    distance_source = db.Column(db.String(20), nullable=False, default="estimated")
    geometry = db.Column(db.JSON)
    geometry_source = db.Column(db.String(20), nullable=False, default="estimated")
    route_method = db.Column(db.String(160), nullable=False, default="insertion heuristic")
    explanation = db.Column(db.JSON, nullable=False, default=dict)
    assumptions = db.Column(db.JSON, nullable=False, default=list)
    load_profile = db.Column(db.JSON, nullable=False, default=list)

    version = db.Column(db.Integer, nullable=False, default=1)
    offered_at = db.Column(db.DateTime(timezone=True))
    accepted_at = db.Column(db.DateTime(timezone=True))
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    declined_reason = db.Column(db.String(500))
    cancelled_reason = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    partner = db.relationship("User", foreign_keys=[partner_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    stops = db.relationship(
        "BatchStop",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="BatchStop.sequence",
    )
    request_links = db.relationship(
        "BatchRequest", back_populates="batch", cascade="all, delete-orphan"
    )
    assignments = db.relationship(
        "BatchAssignment",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="BatchAssignment.created_at",
    )

    @property
    def code(self) -> str:
        from .domain import batch_code

        return batch_code(self.id)


class BatchRequest(db.Model):
    """Active reservation (released_at IS NULL) plus retained membership history."""

    __tablename__ = "batch_requests"
    __table_args__ = (
        Index(
            "uq_batch_requests_active_request",
            "request_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("delivery_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_id = db.Column(
        db.Integer, db.ForeignKey("delivery_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    released_at = db.Column(db.DateTime(timezone=True))

    batch = db.relationship("DeliveryBatch", back_populates="request_links")
    request = db.relationship("DeliveryRequest", back_populates="batch_links")


class BatchStop(db.Model):
    __tablename__ = "batch_stops"
    __table_args__ = (Index("ix_batch_stops_batch_sequence", "batch_id", "sequence", unique=True),)

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("delivery_batches.id", ondelete="CASCADE"), nullable=False
    )
    request_id = db.Column(
        db.Integer, db.ForeignKey("delivery_requests.id", ondelete="CASCADE"), nullable=False
    )
    kind = db.Column(db.String(20), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    location_id = db.Column(
        db.Integer, db.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False
    )
    planned_arrival = db.Column(db.DateTime(timezone=True), nullable=False)
    planned_departure = db.Column(db.DateTime(timezone=True), nullable=False)
    service_minutes = db.Column(db.Integer, nullable=False, default=6)
    leg_distance_km = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    leg_duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    load_weight_kg = db.Column(db.Numeric(7, 2), nullable=False, default=0)
    load_volume_m3 = db.Column(db.Numeric(7, 3), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="pending")
    completed_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.String(500))

    batch = db.relationship("DeliveryBatch", back_populates="stops")
    request = db.relationship("DeliveryRequest")
    location = db.relationship("Location")


class BatchAssignment(db.Model):
    __tablename__ = "batch_assignments"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("delivery_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    partner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(30), nullable=False)
    reason = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    batch = db.relationship("DeliveryBatch", back_populates="assignments")
    partner = db.relationship("User", foreign_keys=[partner_id])
    actor = db.relationship("User", foreign_keys=[actor_id])


class TrackingEvent(db.Model):
    __tablename__ = "tracking_events"
    __table_args__ = (Index("ix_tracking_parcel_created", "parcel_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    parcel_id = db.Column(
        db.Integer, db.ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False
    )
    request_id = db.Column(
        db.Integer, db.ForeignKey("delivery_requests.id", ondelete="CASCADE"), nullable=False
    )
    event_type = db.Column(db.String(40), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    notes = db.Column(db.String(500))
    event_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    parcel = db.relationship("Parcel")
    actor = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(600), nullable=False)
    link = db.Column(db.String(255))
    read_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)


class IssueReport(db.Model):
    __tablename__ = "issue_reports"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("delivery_requests.id", ondelete="CASCADE"))
    batch_id = db.Column(db.Integer, db.ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    category = db.Column(db.String(40), nullable=False, default="other")
    severity = db.Column(db.String(20), nullable=False, default="medium", index=True)
    description = db.Column(db.String(1500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    resolution_note = db.Column(db.String(1000))
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    request = db.relationship("DeliveryRequest")
    batch = db.relationship("DeliveryBatch")
    reporter = db.relationship("User", foreign_keys=[reporter_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])


class AuditEvent(db.Model):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(60), nullable=False)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer)
    summary = db.Column(db.String(600), nullable=False)
    reason = db.Column(db.String(500))
    event_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    actor = db.relationship("User")
