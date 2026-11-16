"""ReTurn relational model (PostgreSQL).

This is the redesigned operating schema for the four-role logistics platform:
consumers/businesses, delivery partners, managers and administrators.

Design rules enforced here:

* Every operational record is persisted; nothing important lives only in memory.
* Current state is projected onto the owning row, while transitions, offers,
  location reports, proofs and admin actions are append-only history tables.
* A parcel may have at most one active driver assignment (partial unique index).
* An order may belong to at most one active batch (partial unique index).
* Addresses, contacts and parcel snapshots are stored separately per order, so a
  consumer editing a saved address never rewrites historical orders.
* Money/weight/volume use Numeric; timestamps are timezone-aware UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Index, text

from .extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )


# --------------------------------------------------------------------------- #
# Identity and access
# --------------------------------------------------------------------------- #
class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_role_status", "role", "status"),
        db.CheckConstraint(
            "role IN ('consumer','driver','manager','admin')", name="ck_users_role"
        ),
        db.CheckConstraint(
            "status IN ('active','pending_activation','suspended','deactivated')",
            name="ck_users_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40))
    role = db.Column(db.String(20), nullable=False, index=True)
    status = db.Column(
        db.String(24), nullable=False, default="active", index=True
    )
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    mfa_secret = db.Column(db.String(128))
    timezone_name = db.Column(db.String(64), nullable=False, default="Asia/Kolkata")
    avatar_url = db.Column(db.String(500))
    notify_email = db.Column(db.Boolean, nullable=False, default=True)
    notify_in_app = db.Column(db.Boolean, nullable=False, default=True)
    last_login_at = db.Column(db.DateTime(timezone=True))
    password_changed_at = db.Column(db.DateTime(timezone=True))
    activated_at = db.Column(db.DateTime(timezone=True))
    disabled_at = db.Column(db.DateTime(timezone=True))
    disabled_reason = db.Column(db.String(500))

    consumer_profile = db.relationship(
        "ConsumerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="ConsumerProfile.user_id",
    )
    business_profile = db.relationship(
        "BusinessProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="BusinessProfile.user_id",
    )
    manager_profile = db.relationship(
        "ManagerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="ManagerProfile.user_id",
    )
    driver_profile = db.relationship(
        "DriverProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="DriverProfile.user_id",
    )
    extra_permissions = db.relationship(
        "UserPermission",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="UserPermission.user_id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User {self.email} {self.role}>"

    @property
    def display_role(self) -> str:
        return {
            "consumer": "Consumer",
            "driver": "Delivery partner",
            "manager": "Manager",
            "admin": "Administrator",
        }.get(self.role, self.role)


class Permission(TimestampMixin, db.Model):
    """Catalogue of granular permissions assignable to manager accounts."""

    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    label = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(500))
    is_system = db.Column(db.Boolean, nullable=False, default=True)


class UserPermission(db.Model):
    __tablename__ = "user_permissions"
    __table_args__ = (db.UniqueConstraint("user_id", "permission_code", name="uq_user_permission"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_code = db.Column(db.String(80), nullable=False)
    granted_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    user = db.relationship(
        "User", back_populates="extra_permissions", foreign_keys=[user_id]
    )
    granted_by = db.relationship("User", foreign_keys=[granted_by_id])


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    csrf_token = db.Column(db.String(64), nullable=False)
    user_agent = db.Column(db.String(255))
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    revoked_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", foreign_keys=[user_id])


class OneTimeToken(db.Model):
    """Activation / password-reset tokens. Only a hash is stored."""

    __tablename__ = "one_time_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    purpose = db.Column(db.String(24), nullable=False)  # activation | password_reset
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    used_at = db.Column(db.DateTime(timezone=True))
    requested_ip = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    user = db.relationship("User", foreign_keys=[user_id])


class ConsumerProfile(db.Model):
    __tablename__ = "consumer_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    account_type = db.Column(db.String(20), nullable=False, default="individual")
    company_role = db.Column(db.String(120))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    user = db.relationship("User", back_populates="consumer_profile", foreign_keys=[user_id])


class BusinessProfile(TimestampMixin, db.Model):
    __tablename__ = "business_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    business_name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(120))
    contact_phone = db.Column(db.String(40))
    contact_email = db.Column(db.String(255))
    address_line = db.Column(db.String(255))
    area = db.Column(db.String(120))
    city = db.Column(db.String(120), default="Kolkata")
    state = db.Column(db.String(120), default="West Bengal")
    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(9, 6))
    longitude = db.Column(db.Numeric(9, 6))
    logo_media_id = db.Column(db.Integer, db.ForeignKey("media_assets.id", ondelete="SET NULL"))
    tax_id = db.Column(db.String(80))
    registration_number = db.Column(db.String(80))
    verification_status = db.Column(db.String(24), nullable=False, default="not_required")
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    user = db.relationship("User", back_populates="business_profile", foreign_keys=[user_id])
    verified_by = db.relationship("User", foreign_keys=[verified_by_id])
    logo = db.relationship("MediaAsset", foreign_keys=[logo_media_id])


class ManagerProfile(TimestampMixin, db.Model):
    __tablename__ = "manager_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    employee_code = db.Column(db.String(40))
    contact_phone = db.Column(db.String(40))
    notes = db.Column(db.String(500))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    user = db.relationship("User", back_populates="manager_profile", foreign_keys=[user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    service_areas = db.relationship(
        "ManagerServiceArea", back_populates="manager", cascade="all, delete-orphan"
    )


class DriverProfile(TimestampMixin, db.Model):
    __tablename__ = "driver_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    license_number = db.Column(db.String(80))
    license_expiry = db.Column(db.Date)
    verification_status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    verification_note = db.Column(db.String(500))
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    rating = db.Column(db.Numeric(3, 2))
    completed_deliveries = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User", back_populates="driver_profile", foreign_keys=[user_id])
    verified_by = db.relationship("User", foreign_keys=[verified_by_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    vehicles = db.relationship(
        "Vehicle", back_populates="driver", cascade="all, delete-orphan", foreign_keys="Vehicle.driver_id"
    )
    service_areas = db.relationship(
        "DriverServiceArea", back_populates="driver", cascade="all, delete-orphan"
    )
    availability = db.relationship(
        "DriverAvailability", back_populates="driver", cascade="all, delete-orphan"
    )
    duty_sessions = db.relationship(
        "DriverDutySession",
        back_populates="driver",
        cascade="all, delete-orphan",
        foreign_keys="DriverDutySession.driver_id",
    )


# --------------------------------------------------------------------------- #
# Service areas, vehicles, availability and live operations
# --------------------------------------------------------------------------- #
class ServiceArea(TimestampMixin, db.Model):
    __tablename__ = "service_areas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False, default="Kolkata")
    state = db.Column(db.String(120), nullable=False, default="West Bengal")
    postal_codes = db.Column(db.String(500), nullable=False, default="")
    center_latitude = db.Column(db.Numeric(9, 6))
    center_longitude = db.Column(db.Numeric(9, 6))
    radius_km = db.Column(db.Numeric(6, 2), nullable=False, default=12)
    boundary = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    managers = db.relationship(
        "ManagerServiceArea", back_populates="service_area", cascade="all, delete-orphan"
    )
    drivers = db.relationship(
        "DriverServiceArea", back_populates="service_area", cascade="all, delete-orphan"
    )

    @property
    def postal_code_list(self) -> list[str]:
        return [code.strip() for code in (self.postal_codes or "").split(",") if code.strip()]


class ManagerServiceArea(db.Model):
    __tablename__ = "manager_service_areas"
    __table_args__ = (
        db.UniqueConstraint("manager_id", "service_area_id", name="uq_manager_service_area"),
    )

    id = db.Column(db.Integer, primary_key=True)
    manager_id = db.Column(
        db.Integer, db.ForeignKey("manager_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_area_id = db.Column(
        db.Integer, db.ForeignKey("service_areas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    manager = db.relationship("ManagerProfile", back_populates="service_areas")
    service_area = db.relationship("ServiceArea", back_populates="managers")


class DriverServiceArea(db.Model):
    __tablename__ = "driver_service_areas"
    __table_args__ = (
        db.UniqueConstraint("driver_id", "service_area_id", name="uq_driver_service_area"),
    )

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(
        db.Integer, db.ForeignKey("driver_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    service_area_id = db.Column(
        db.Integer, db.ForeignKey("service_areas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    driver = db.relationship("DriverProfile", back_populates="service_areas")
    service_area = db.relationship("ServiceArea", back_populates="drivers")


class DriverAvailability(db.Model):
    """Recurring weekly availability window for a driver."""

    __tablename__ = "driver_availability"
    __table_args__ = (
        db.UniqueConstraint(
            "driver_id", "weekday", "start_time", "end_time", name="uq_driver_availability_slot"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(
        db.Integer, db.ForeignKey("driver_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday = db.Column(db.Integer, nullable=False)  # 0 = Monday … 6 = Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    service_area_id = db.Column(db.Integer, db.ForeignKey("service_areas.id", ondelete="SET NULL"))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    driver = db.relationship("DriverProfile", back_populates="availability")
    service_area = db.relationship("ServiceArea")


class DriverDutySession(db.Model):
    """One on-duty period. Active session = ended_at IS NULL."""

    __tablename__ = "driver_duty_sessions"
    __table_args__ = (
        Index("ix_duty_driver_started", "driver_id", "started_at"),
        Index(
            "uq_duty_sessions_active_driver",
            "driver_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        db.CheckConstraint(
            "status IN ('available','on_duty','on_break','busy','unavailable')",
            name="ck_duty_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(
        db.Integer, db.ForeignKey("driver_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = db.Column(db.String(20), nullable=False, default="available", index=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    ended_at = db.Column(db.DateTime(timezone=True))
    ended_reason = db.Column(db.String(120))
    last_heartbeat_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    device_label = db.Column(db.String(120))
    start_latitude = db.Column(db.Numeric(9, 6))
    start_longitude = db.Column(db.Numeric(9, 6))
    end_latitude = db.Column(db.Numeric(9, 6))
    end_longitude = db.Column(db.Numeric(9, 6))

    driver = db.relationship("DriverProfile", back_populates="duty_sessions", foreign_keys=[driver_id])
    locations = db.relationship(
        "DriverLocationEvent", back_populates="duty_session", cascade="all, delete-orphan"
    )


class DriverLocationEvent(db.Model):
    __tablename__ = "driver_location_events"
    __table_args__ = (
        Index("ix_location_driver_recorded", "driver_id", "recorded_at"),
        Index("ix_location_duty_recorded", "duty_session_id", "recorded_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(
        db.Integer, db.ForeignKey("driver_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    duty_session_id = db.Column(
        db.Integer, db.ForeignKey("driver_duty_sessions.id", ondelete="CASCADE"), index=True
    )
    batch_id = db.Column(db.Integer, db.ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    accuracy_m = db.Column(db.Numeric(8, 2))
    heading_degrees = db.Column(db.Numeric(6, 2))
    speed_kmh = db.Column(db.Numeric(6, 2))
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    source = db.Column(db.String(40), nullable=False, default="browser_geolocation")

    driver = db.relationship("DriverProfile", foreign_keys=[driver_id])
    duty_session = db.relationship("DriverDutySession", back_populates="locations")
    batch = db.relationship("DeliveryBatch", foreign_keys=[batch_id])


class VehicleCapacityProfile(TimestampMixin, db.Model):
    __tablename__ = "vehicle_capacity_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(30), nullable=False)
    max_weight_kg = db.Column(db.Numeric(8, 2), nullable=False)
    max_volume_m3 = db.Column(db.Numeric(8, 3), nullable=False)
    max_length_cm = db.Column(db.Numeric(7, 2), nullable=False)
    max_width_cm = db.Column(db.Numeric(7, 2), nullable=False)
    max_height_cm = db.Column(db.Numeric(7, 2), nullable=False)
    max_parcels = db.Column(db.Integer, nullable=False, default=20)
    supports_fragile = db.Column(db.Boolean, nullable=False, default=True)
    supports_restricted = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.String(500))


class Vehicle(TimestampMixin, db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    driver_id = db.Column(
        db.Integer, db.ForeignKey("driver_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capacity_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicle_capacity_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_type = db.Column(db.String(30), nullable=False)
    registration_number = db.Column(db.String(40), unique=True, nullable=False)
    make = db.Column(db.String(80))
    model = db.Column(db.String(80))
    color = db.Column(db.String(40))
    year = db.Column(db.Integer)
    verification_status = db.Column(db.String(24), nullable=False, default="pending")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    driver = db.relationship("DriverProfile", back_populates="vehicles", foreign_keys=[driver_id])
    capacity_profile = db.relationship("VehicleCapacityProfile")


class SavedAddress(TimestampMixin, db.Model):
    __tablename__ = "saved_addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(160))
    contact_phone = db.Column(db.String(40))
    address_line = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    area = db.Column(db.String(120), nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False, default="Kolkata")
    state = db.Column(db.String(120), nullable=False, default="West Bengal")
    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    is_default_pickup = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", foreign_keys=[user_id])


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
class PickupAddress(db.Model):
    __tablename__ = "pickup_addresses"

    id = db.Column(db.Integer, primary_key=True)
    contact_name = db.Column(db.String(160), nullable=False)
    contact_phone = db.Column(db.String(40), nullable=False)
    address_line = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    area = db.Column(db.String(120), nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False, default="Kolkata")
    state = db.Column(db.String(120), nullable=False, default="West Bengal")
    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    instructions = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)


class DeliveryAddress(db.Model):
    __tablename__ = "delivery_addresses"

    id = db.Column(db.Integer, primary_key=True)
    contact_name = db.Column(db.String(160), nullable=False)
    contact_phone = db.Column(db.String(40), nullable=False)
    address_line = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    area = db.Column(db.String(120), nullable=False, index=True)
    city = db.Column(db.String(120), nullable=False, default="Kolkata")
    state = db.Column(db.String(120), nullable=False, default="West Bengal")
    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    instructions = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    phone = db.Column(db.String(40))
    email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)


class Order(TimestampMixin, db.Model):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_consumer_status", "consumer_id", "status"),
        Index("ix_orders_status_deadline", "status", "delivery_deadline"),
        Index("ix_orders_status_pickup", "status", "pickup_window_start"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    consumer_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    business_profile_id = db.Column(
        db.Integer, db.ForeignKey("business_profiles.id", ondelete="SET NULL")
    )
    service_type = db.Column(db.String(20), nullable=False, default="parcel")
    status = db.Column(db.String(32), nullable=False, default="submitted", index=True)
    pickup_address_id = db.Column(
        db.Integer, db.ForeignKey("pickup_addresses.id", ondelete="RESTRICT"), nullable=False
    )
    delivery_address_id = db.Column(
        db.Integer, db.ForeignKey("delivery_addresses.id", ondelete="RESTRICT"), nullable=False
    )
    sender_contact_id = db.Column(
        db.Integer, db.ForeignKey("contacts.id", ondelete="SET NULL")
    )
    recipient_contact_id = db.Column(
        db.Integer, db.ForeignKey("contacts.id", ondelete="SET NULL")
    )
    pickup_window_start = db.Column(db.DateTime(timezone=True), nullable=False)
    pickup_window_end = db.Column(db.DateTime(timezone=True), nullable=False)
    delivery_deadline = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    priority = db.Column(db.Integer, nullable=False, default=0)
    service_notes = db.Column(db.String(1000))
    special_requirements = db.Column(db.String(500))
    business_order_reference = db.Column(db.String(120))
    declared_value_inr = db.Column(db.Numeric(10, 2))
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    approved_at = db.Column(db.DateTime(timezone=True))
    rejection_reason = db.Column(db.String(500))
    cancelled_at = db.Column(db.DateTime(timezone=True))
    cancelled_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    cancellation_reason = db.Column(db.String(500))
    failure_reason = db.Column(db.String(500))
    delivered_at = db.Column(db.DateTime(timezone=True))
    is_demo = db.Column(db.Boolean, nullable=False, default=False)

    consumer = db.relationship("User", foreign_keys=[consumer_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    cancelled_by = db.relationship("User", foreign_keys=[cancelled_by_id])
    business_profile = db.relationship("BusinessProfile")
    pickup_address = db.relationship("PickupAddress", foreign_keys=[pickup_address_id])
    delivery_address = db.relationship("DeliveryAddress", foreign_keys=[delivery_address_id])
    sender_contact = db.relationship("Contact", foreign_keys=[sender_contact_id])
    recipient_contact = db.relationship("Contact", foreign_keys=[recipient_contact_id])
    parcel = db.relationship(
        "ParcelDetail", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    return_request = db.relationship(
        "ReturnRequest", back_populates="order", uselist=False, cascade="all, delete-orphan"
    )
    images = db.relationship(
        "ParcelImage", back_populates="order", cascade="all, delete-orphan"
    )
    status_history = db.relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.created_at",
    )
    batch_links = db.relationship(
        "BatchOrder", back_populates="order", cascade="all, delete-orphan"
    )
    assignments = db.relationship(
        "DriverAssignment", back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Order {self.order_number} {self.status}>"


class ParcelDetail(TimestampMixin, db.Model):
    __tablename__ = "parcel_details"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(1000))
    category = db.Column(db.String(80), nullable=False, default="general")
    quantity = db.Column(db.Integer, nullable=False, default=1)
    weight_kg = db.Column(db.Numeric(8, 3), nullable=False)
    length_cm = db.Column(db.Numeric(7, 2), nullable=False)
    width_cm = db.Column(db.Numeric(7, 2), nullable=False)
    height_cm = db.Column(db.Numeric(7, 2), nullable=False)
    volume_m3 = db.Column(db.Numeric(9, 5), nullable=False)
    is_fragile = db.Column(db.Boolean, nullable=False, default=False)
    handling_flags = db.Column(db.String(200), nullable=False, default="")
    declared_value_inr = db.Column(db.Numeric(10, 2))
    photo_exception_reason = db.Column(db.String(500))

    order = db.relationship("Order", back_populates="parcel")

    @property
    def handling_list(self) -> list[str]:
        return [flag for flag in (self.handling_flags or "").split(",") if flag]


class ReturnRequest(TimestampMixin, db.Model):
    __tablename__ = "return_requests"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    product_name = db.Column(db.String(200), nullable=False)
    original_order_reference = db.Column(db.String(120))
    reason = db.Column(db.String(1000), nullable=False)
    return_authorization_reference = db.Column(db.String(120))
    merchant_name = db.Column(db.String(200))
    merchant_business_profile_id = db.Column(
        db.Integer, db.ForeignKey("business_profiles.id", ondelete="SET NULL")
    )
    destination_type = db.Column(db.String(40), nullable=False, default="business")
    authorization_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    approval_status = db.Column(db.String(24), nullable=False, default="not_required", index=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    approved_at = db.Column(db.DateTime(timezone=True))
    received_at = db.Column(db.DateTime(timezone=True))
    condition_notes = db.Column(db.String(1000))
    refund_status = db.Column(db.String(40))

    order = db.relationship("Order", back_populates="return_request")
    merchant_business = db.relationship("BusinessProfile")
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])


class MediaAsset(db.Model):
    """Stored file. Private by default; access always goes through the API."""

    __tablename__ = "media_assets"

    id = db.Column(db.Integer, primary_key=True)
    storage_backend = db.Column(db.String(30), nullable=False, default="local")
    storage_key = db.Column(db.String(500), unique=True, nullable=False)
    original_filename = db.Column(db.String(255))
    content_type = db.Column(db.String(120), nullable=False)
    byte_size = db.Column(db.Integer, nullable=False)
    checksum_sha256 = db.Column(db.String(64))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    visibility = db.Column(db.String(20), nullable=False, default="private")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    deleted_at = db.Column(db.DateTime(timezone=True))

    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])


class ParcelImage(db.Model):
    __tablename__ = "parcel_images"
    __table_args__ = (
        Index(
            "uq_parcel_images_primary",
            "order_id",
            unique=True,
            postgresql_where=text("is_primary IS TRUE"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_id = db.Column(
        db.Integer, db.ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False
    )
    image_kind = db.Column(db.String(40), nullable=False, default="exterior")
    is_primary = db.Column(db.Boolean, nullable=False, default=False)
    captured_at = db.Column(db.DateTime(timezone=True))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    order = db.relationship("Order", back_populates="images")
    media = db.relationship("MediaAsset")
    uploaded_by = db.relationship("User", foreign_keys=[uploaded_by_id])


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"
    __table_args__ = (Index("ix_order_history_order_created", "order_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status = db.Column(db.String(32))
    to_status = db.Column(db.String(32), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    source = db.Column(db.String(24), nullable=False, default="system")
    reason = db.Column(db.String(500))
    event_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    order = db.relationship("Order", back_populates="status_history")
    actor = db.relationship("User", foreign_keys=[actor_id])


# --------------------------------------------------------------------------- #
# Dispatch: batches, routes, assignments
# --------------------------------------------------------------------------- #
class DeliveryBatch(TimestampMixin, db.Model):
    __tablename__ = "delivery_batches"
    __table_args__ = (Index("ix_batches_status_start", "status", "planned_start"),)

    id = db.Column(db.Integer, primary_key=True)
    batch_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default="draft", index=True)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), index=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id", ondelete="SET NULL"))
    service_area_id = db.Column(db.Integer, db.ForeignKey("service_areas.id", ondelete="SET NULL"))
    planned_start = db.Column(db.DateTime(timezone=True))
    planned_end = db.Column(db.DateTime(timezone=True))
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    cancelled_at = db.Column(db.DateTime(timezone=True))
    cancellation_reason = db.Column(db.String(500))
    distance_km = db.Column(db.Numeric(9, 2), nullable=False, default=0)
    duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    baseline_km = db.Column(db.Numeric(9, 2), nullable=False, default=0)
    distance_source = db.Column(db.String(20), nullable=False, default="estimated")
    geometry = db.Column(db.JSON)
    geometry_source = db.Column(db.String(20), nullable=False, default="estimated")
    algorithm = db.Column(db.String(160), nullable=False, default="insertion heuristic")
    explanation = db.Column(db.JSON, nullable=False, default=dict)
    notes = db.Column(db.String(1000))
    version = db.Column(db.Integer, nullable=False, default=1)

    manager = db.relationship("User", foreign_keys=[manager_id])
    driver = db.relationship("User", foreign_keys=[driver_id])
    vehicle = db.relationship("Vehicle")
    service_area = db.relationship("ServiceArea")
    order_links = db.relationship(
        "BatchOrder", back_populates="batch", cascade="all, delete-orphan"
    )
    route_plans = db.relationship(
        "RoutePlan",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="RoutePlan.version",
    )


class BatchOrder(db.Model):
    """Active reservation (removed_at IS NULL) plus retained membership history."""

    __tablename__ = "batch_orders"
    __table_args__ = (
        Index(
            "uq_batch_orders_active_order",
            "order_id",
            unique=True,
            postgresql_where=text("removed_at IS NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("delivery_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    added_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    removed_at = db.Column(db.DateTime(timezone=True))
    removed_reason = db.Column(db.String(500))

    batch = db.relationship("DeliveryBatch", back_populates="order_links")
    order = db.relationship("Order", back_populates="batch_links")
    added_by = db.relationship("User", foreign_keys=[added_by_id])


class RoutePlan(db.Model):
    __tablename__ = "route_plans"
    __table_args__ = (
        db.UniqueConstraint("batch_id", "version", name="uq_route_plan_version"),
        Index(
            "uq_route_plans_active_batch",
            "batch_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("delivery_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    algorithm = db.Column(db.String(160), nullable=False, default="insertion heuristic")
    distance_km = db.Column(db.Numeric(9, 2), nullable=False, default=0)
    duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    distance_source = db.Column(db.String(20), nullable=False, default="estimated")
    geometry = db.Column(db.JSON)
    geometry_source = db.Column(db.String(20), nullable=False, default="estimated")
    metrics = db.Column(db.JSON, nullable=False, default=dict)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    activated_at = db.Column(db.DateTime(timezone=True))
    superseded_at = db.Column(db.DateTime(timezone=True))

    batch = db.relationship("DeliveryBatch", back_populates="route_plans")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    stops = db.relationship(
        "RouteStop",
        back_populates="route_plan",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence",
    )
    legs = db.relationship(
        "RouteLeg",
        back_populates="route_plan",
        cascade="all, delete-orphan",
        order_by="RouteLeg.sequence",
    )


class RouteStop(db.Model):
    __tablename__ = "route_stops"
    __table_args__ = (
        db.UniqueConstraint("route_plan_id", "sequence", name="uq_route_stop_sequence"),
        db.UniqueConstraint("route_plan_id", "order_id", "kind", name="uq_route_stop_order_kind"),
    )

    id = db.Column(db.Integer, primary_key=True)
    route_plan_id = db.Column(
        db.Integer, db.ForeignKey("route_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind = db.Column(db.String(20), nullable=False)  # pickup | delivery
    sequence = db.Column(db.Integer, nullable=False)
    # Address snapshot: the route is reproducible even if the order is edited.
    label = db.Column(db.String(160), nullable=False)
    contact_name = db.Column(db.String(160), nullable=False)
    contact_phone = db.Column(db.String(40))
    address_line = db.Column(db.String(255), nullable=False)
    area = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    postal_code = db.Column(db.String(20))
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    planned_arrival = db.Column(db.DateTime(timezone=True), nullable=False)
    planned_departure = db.Column(db.DateTime(timezone=True), nullable=False)
    service_minutes = db.Column(db.Integer, nullable=False, default=6)
    leg_distance_km = db.Column(db.Numeric(9, 3), nullable=False, default=0)
    leg_duration_minutes = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    load_weight_kg = db.Column(db.Numeric(9, 3), nullable=False, default=0)
    load_volume_m3 = db.Column(db.Numeric(9, 5), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    arrived_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.String(500))

    route_plan = db.relationship("RoutePlan", back_populates="stops")
    order = db.relationship("Order")


class RouteLeg(db.Model):
    __tablename__ = "route_legs"
    __table_args__ = (db.UniqueConstraint("route_plan_id", "sequence", name="uq_route_leg_sequence"),)

    id = db.Column(db.Integer, primary_key=True)
    route_plan_id = db.Column(
        db.Integer, db.ForeignKey("route_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_stop_id = db.Column(db.Integer, db.ForeignKey("route_stops.id", ondelete="CASCADE"))
    to_stop_id = db.Column(db.Integer, db.ForeignKey("route_stops.id", ondelete="CASCADE"))
    sequence = db.Column(db.Integer, nullable=False)
    distance_km = db.Column(db.Numeric(9, 3), nullable=False, default=0)
    duration_minutes = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    distance_source = db.Column(db.String(20), nullable=False, default="estimated")
    geometry = db.Column(db.JSON)

    route_plan = db.relationship("RoutePlan", back_populates="legs")


class DriverAssignment(TimestampMixin, db.Model):
    __tablename__ = "driver_assignments"
    __table_args__ = (
        Index(
            "uq_driver_assignments_active_order",
            "order_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_assignments_driver_status", "driver_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id = db.Column(db.Integer, db.ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id", ondelete="SET NULL"))
    route_plan_id = db.Column(db.Integer, db.ForeignKey("route_plans.id", ondelete="SET NULL"))
    assigned_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    assigned_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    accepted_at = db.Column(db.DateTime(timezone=True))
    ended_at = db.Column(db.DateTime(timezone=True))
    end_reason = db.Column(db.String(500))

    order = db.relationship("Order", back_populates="assignments")
    driver = db.relationship("User", foreign_keys=[driver_id])
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_id])
    batch = db.relationship("DeliveryBatch", foreign_keys=[batch_id])
    vehicle = db.relationship("Vehicle")


class RouteAssignmentHistory(db.Model):
    __tablename__ = "route_assignment_history"
    __table_args__ = (Index("ix_assignment_history_order_created", "order_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id = db.Column(db.Integer, db.ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id", ondelete="SET NULL"))
    route_plan_id = db.Column(db.Integer, db.ForeignKey("route_plans.id", ondelete="SET NULL"))
    action = db.Column(db.String(30), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reason = db.Column(db.String(500))
    event_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    order = db.relationship("Order")
    driver = db.relationship("User", foreign_keys=[driver_id])
    actor = db.relationship("User", foreign_keys=[actor_id])


class MatchingSuggestion(db.Model):
    __tablename__ = "matching_suggestions"
    __table_args__ = (
        Index("ix_suggestions_status_created", "status", "created_at"),
        Index("ix_suggestions_order_status", "order_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id = db.Column(db.Integer, db.ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    route_plan_id = db.Column(db.Integer, db.ForeignKey("route_plans.id", ondelete="SET NULL"))
    status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    score = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    detour_km = db.Column(db.Numeric(9, 3), nullable=False, default=0)
    added_duration_minutes = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    distance_source = db.Column(db.String(20), nullable=False, default="estimated")
    capacity_snapshot = db.Column(db.JSON, nullable=False, default=dict)
    reasons = db.Column(db.JSON, nullable=False, default=list)
    blockers = db.Column(db.JSON, nullable=False, default=list)
    proposed_sequence = db.Column(db.JSON, nullable=False, default=list)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    decision_note = db.Column(db.String(500))
    rejection_code = db.Column(db.String(80))
    expires_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    order = db.relationship("Order")
    driver = db.relationship("User", foreign_keys=[driver_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])
    batch = db.relationship("DeliveryBatch", foreign_keys=[batch_id])


class MatchingRejectionReason(db.Model):
    """Catalogue of machine-readable rejection/blocker codes."""

    __tablename__ = "matching_rejection_reasons"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False, index=True)
    label = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(500))
    is_blocking = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


# --------------------------------------------------------------------------- #
# Proof, exceptions and audit
# --------------------------------------------------------------------------- #
class ProofMedia(db.Model):
    __tablename__ = "proof_media"
    __table_args__ = (Index("ix_proof_media_order_kind", "order_id", "proof_type"),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    duty_session_id = db.Column(
        db.Integer, db.ForeignKey("driver_duty_sessions.id", ondelete="SET NULL")
    )
    proof_type = db.Column(db.String(20), nullable=False)  # pickup | delivery
    media_id = db.Column(
        db.Integer, db.ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False
    )
    captured_at = db.Column(db.DateTime(timezone=True), nullable=False)
    received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    latitude = db.Column(db.Numeric(9, 6), nullable=False)
    longitude = db.Column(db.Numeric(9, 6), nullable=False)
    accuracy_m = db.Column(db.Numeric(8, 2))
    distance_from_stop_m = db.Column(db.Numeric(9, 2))
    verification_status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    verified_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.String(1000))

    order = db.relationship("Order")
    driver = db.relationship("User", foreign_keys=[driver_id])
    media = db.relationship("MediaAsset")
    verified_by = db.relationship("User", foreign_keys=[verified_by_id])


class PickupProof(db.Model):
    __tablename__ = "pickup_proofs"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    proof_media_id = db.Column(
        db.Integer, db.ForeignKey("proof_media.id", ondelete="RESTRICT"), nullable=False
    )
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    server_received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    status = db.Column(db.String(24), nullable=False, default="valid", index=True)
    notes = db.Column(db.String(500))

    order = db.relationship("Order")
    driver = db.relationship("User", foreign_keys=[driver_id])
    proof_media = db.relationship("ProofMedia", foreign_keys=[proof_media_id])


class DeliveryProof(db.Model):
    __tablename__ = "delivery_proofs"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    proof_media_id = db.Column(
        db.Integer, db.ForeignKey("proof_media.id", ondelete="RESTRICT"), nullable=False
    )
    captured_at = db.Column(db.DateTime(timezone=True), nullable=False)
    server_received_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    status = db.Column(db.String(24), nullable=False, default="valid", index=True)
    recipient_name = db.Column(db.String(160))
    notes = db.Column(db.String(500))

    order = db.relationship("Order")
    driver = db.relationship("User", foreign_keys=[driver_id])
    proof_media = db.relationship("ProofMedia", foreign_keys=[proof_media_id])


class DeliveryException(TimestampMixin, db.Model):
    __tablename__ = "delivery_exceptions"
    __table_args__ = (Index("ix_exceptions_status_created", "status", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    batch_id = db.Column(db.Integer, db.ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    exception_type = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(1500), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="open", index=True)
    resolution_note = db.Column(db.String(1500))
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = db.Column(db.DateTime(timezone=True))

    order = db.relationship("Order")
    driver = db.relationship("User", foreign_keys=[driver_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(600), nullable=False)
    link = db.Column(db.String(255))
    event_data = db.Column(db.JSON, nullable=False, default=dict)
    read_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now, index=True)

    user = db.relationship("User", foreign_keys=[user_id])


class IssueReport(TimestampMixin, db.Model):
    __tablename__ = "issue_reports"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="SET NULL"))
    batch_id = db.Column(db.Integer, db.ForeignKey("delivery_batches.id", ondelete="SET NULL"))
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    category = db.Column(db.String(40), nullable=False, default="other")
    severity = db.Column(db.String(20), nullable=False, default="medium", index=True)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(1500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    resolution_note = db.Column(db.String(1500))
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = db.Column(db.DateTime(timezone=True))

    order = db.relationship("Order")
    reporter = db.relationship("User", foreign_keys=[reporter_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_created", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    actor_role = db.Column(db.String(20))
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(40), nullable=False)
    entity_id = db.Column(db.Integer)
    summary = db.Column(db.String(600), nullable=False)
    reason = db.Column(db.String(500))
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    event_metadata = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)

    actor = db.relationship("User", foreign_keys=[actor_id])


class AdminSetting(TimestampMixin, db.Model):
    __tablename__ = "admin_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.JSON, nullable=False, default=dict)
    description = db.Column(db.String(500))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))

    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
