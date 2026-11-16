"""Deterministic route planning and on-route insertion estimates.

The planner is a greedy nearest-feasible heuristic with an explicit
pickup-before-delivery precedence rule. It is deterministic (ties break by
deadline, then stop kind, then order id) and explainable: every leg and planned
time is derived from a distance matrix that is either real OSRM road routing or
an explicitly labelled estimate. It is not presented as AI or machine learning.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from flask import current_app

from .. import domain
from .routing import build_matrix, haversine_km, route_geometry

EARTH_RADIUS_KM = 6371.0088


# --------------------------------------------------------------------------- #
# Configuration and conversions
# --------------------------------------------------------------------------- #
def config() -> dict:
    cfg = dict(current_app.config.get("MATCHING_DEFAULTS") or {})
    # Administrator overrides are stored in admin_settings and merged over the
    # environment defaults so tuning takes effect without a redeploy.
    try:
        from ..models import AdminSetting

        row = AdminSetting.query.filter_by(key="matching.defaults").first()
        if row is not None and isinstance(row.value, dict):
            for key, value in row.value.items():
                if key in cfg:
                    cfg[key] = value
    except Exception:  # pragma: no cover - settings are optional
        pass
    cfg["provider"] = str(current_app.config.get("ROUTING_PROVIDER", "auto")).lower()
    cfg["osrm_base_url"] = current_app.config.get("OSRM_BASE_URL", "")
    cfg["timeout_seconds"] = float(current_app.config.get("ROUTING_TIMEOUT_SECONDS", 3.0))
    return cfg


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=domain.UTC)
    return value.astimezone(domain.UTC)


def stops_for_order(order, *, cfg: dict | None = None) -> list[dict]:
    """Pickup + delivery snapshots for one order, with parcel load deltas."""
    cfg = cfg or config()
    parcel = order.parcel
    if parcel is None:
        return []
    weight = float(parcel.weight_kg or 0)
    volume = float(parcel.volume_m3 or 0)
    service = int(cfg.get("service_minutes", 6))
    rows: list[dict] = []
    for kind, address, extra in (
        (
            domain.STOP_PICKUP,
            order.pickup_address,
            {
                "window_start": order.pickup_window_start,
                "window_end": order.pickup_window_end,
            },
        ),
        (
            domain.STOP_DELIVERY,
            order.delivery_address,
            {"deadline": order.delivery_deadline},
        ),
    ):
        if address is None or address.latitude is None or address.longitude is None:
            continue
        row = {
            "order_id": order.id,
            "order_number": order.order_number,
            "kind": kind,
            "label": f"{kind.title()} {order.order_number}",
            "contact_name": address.contact_name,
            "contact_phone": address.contact_phone,
            "address_line": address.address_line,
            "area": address.area,
            "city": address.city,
            "postal_code": address.postal_code,
            "latitude": float(address.latitude),
            "longitude": float(address.longitude),
            "service_minutes": service,
            "parcel_weight_kg": weight,
            "parcel_volume_m3": volume,
            "parcel_count": 1,
            "is_fragile": bool(parcel.is_fragile),
            "handling_flags": parcel.handling_list,
            "deadline": None,
            "window_start": None,
            "window_end": None,
        }
        row.update(extra)
        rows.append(row)
    return rows


def stops_for_orders(orders, *, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or config()
    rows: list[dict] = []
    for order in orders:
        rows.extend(stops_for_order(order, cfg=cfg))
    return rows


def stop_from_route_stop(stop, *, cfg: dict | None = None) -> dict:
    """Convert a persisted RouteStop into a planner input row."""
    cfg = cfg or config()
    order = stop.order
    parcel = order.parcel if order is not None else None
    weight = float(parcel.weight_kg or 0) if parcel else 0.0
    volume = float(parcel.volume_m3 or 0) if parcel else 0.0
    return {
        "order_id": stop.order_id,
        "order_number": order.order_number if order else None,
        "kind": stop.kind,
        "label": stop.label,
        "contact_name": stop.contact_name,
        "contact_phone": stop.contact_phone,
        "address_line": stop.address_line,
        "area": stop.area,
        "city": stop.city,
        "postal_code": stop.postal_code,
        "latitude": float(stop.latitude),
        "longitude": float(stop.longitude),
        "service_minutes": stop.service_minutes or int(cfg.get("service_minutes", 6)),
        "parcel_weight_kg": weight,
        "parcel_volume_m3": volume,
        "parcel_count": 1,
        "is_fragile": bool(parcel.is_fragile) if parcel else False,
        "handling_flags": parcel.handling_list if parcel else [],
        "deadline": order.delivery_deadline if order and stop.kind == domain.STOP_DELIVERY else None,
        "window_start": order.pickup_window_start if order and stop.kind == domain.STOP_PICKUP else None,
        "window_end": order.pickup_window_end if order and stop.kind == domain.STOP_PICKUP else None,
    }


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _project(lat: float, lng: float, ref_lat: float) -> tuple[float, float]:
    """Local equirectangular projection in kilometres (small distances)."""
    x = (lng * 111.320) * abs(math.cos(math.radians(ref_lat)))
    y = lat * 110.574
    return x, y


def point_to_segment_km(
    lat: float, lng: float, a_lat: float, a_lng: float, b_lat: float, b_lng: float
) -> float:
    ref = (lat + a_lat + b_lat) / 3.0
    px, py = _project(lat, lng, ref)
    ax, ay = _project(a_lat, a_lng, ref)
    bx, by = _project(b_lat, b_lng, ref)
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return haversine_km(lat, lng, a_lat, a_lng)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return haversine_km(lat, lng, a_lat + t * (b_lat - a_lat), a_lng + t * (b_lng - a_lng))


def nearest_route_distance_km(
    lat: float,
    lng: float,
    start: tuple[float, float],
    existing_stops: list[dict],
) -> float:
    """Distance from a point to the current route corridor (start + pending stops)."""
    points = [start] + [
        (float(stop["latitude"]), float(stop["longitude"])) for stop in existing_stops
    ]
    if len(points) == 1:
        return haversine_km(lat, lng, points[0][0], points[0][1])
    best = float("inf")
    for index in range(len(points) - 1):
        a = points[index]
        b = points[index + 1]
        best = min(best, point_to_segment_km(lat, lng, a[0], a[1], b[0], b[1]))
    return round(best, 3)


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def plan(
    stops: list[dict],
    *,
    start_latitude: float,
    start_longitude: float,
    start_time: datetime,
    initial_weight_kg: float = 0.0,
    initial_volume_m3: float = 0.0,
    initial_parcels: int = 0,
    cfg: dict | None = None,
) -> dict:
    """Plan a deterministic sequence honouring pickup-before-delivery."""
    cfg = cfg or config()
    service_default = int(cfg.get("service_minutes", 6))
    start_time = as_utc(start_time) or domain.utcnow()
    if not stops:
        return {
            "stops": [],
            "distance_km": 0.0,
            "duration_minutes": 0.0,
            "distance_source": "estimated",
            "notes": [],
            "start": {"latitude": start_latitude, "longitude": start_longitude},
        }

    points = [(0, float(start_latitude), float(start_longitude))]
    points += [
        (index + 1, float(stop["latitude"]), float(stop["longitude"]))
        for index, stop in enumerate(stops)
    ]
    matrix = build_matrix(points, cfg)

    remaining = set(range(1, len(stops) + 1))
    picked_orders: set[int] = set()
    previous = 0
    clock = start_time
    load_weight = float(initial_weight_kg or 0)
    load_volume = float(initial_volume_m3 or 0)
    load_parcels = int(initial_parcels or 0)
    total_distance = 0.0
    total_duration = 0.0
    rows: list[dict] = []

    while remaining:
        feasible = [
            index
            for index in remaining
            if stops[index - 1]["kind"] == domain.STOP_PICKUP
            or stops[index - 1]["order_id"] in picked_orders
        ]
        if not feasible:  # pragma: no cover - every delivery has a pickup
            raise RuntimeError("route planning lost pickup-before-delivery precedence")

        def sort_key(index: int):
            stop = stops[index - 1]
            deadline = as_utc(stop.get("deadline"))
            return (
                matrix.distance(previous, index),
                deadline.timestamp() if deadline else float("inf"),
                0 if stop["kind"] == domain.STOP_PICKUP else 1,
                stop["order_id"],
                index,
            )

        chosen = min(feasible, key=sort_key)
        stop = dict(stops[chosen - 1])
        travel_km = matrix.distance(previous, chosen)
        travel_minutes = matrix.duration(previous, chosen)
        arrival = clock + timedelta(minutes=travel_minutes)
        wait_minutes = 0.0
        window_start = as_utc(stop.get("window_start"))
        if stop["kind"] == domain.STOP_PICKUP and window_start and arrival < window_start:
            wait_minutes = (window_start - arrival).total_seconds() / 60.0
            arrival = window_start
        service_minutes = int(stop.get("service_minutes") or service_default)
        departure = arrival + timedelta(minutes=service_minutes)

        if stop["kind"] == domain.STOP_PICKUP:
            load_weight += float(stop.get("parcel_weight_kg") or 0)
            load_volume += float(stop.get("parcel_volume_m3") or 0)
            load_parcels += int(stop.get("parcel_count") or 1)
            picked_orders.add(stop["order_id"])
        else:
            load_weight -= float(stop.get("parcel_weight_kg") or 0)
            load_volume -= float(stop.get("parcel_volume_m3") or 0)
            load_parcels -= int(stop.get("parcel_count") or 1)

        deadline = as_utc(stop.get("deadline"))
        window_end = as_utc(stop.get("window_end"))
        late_minutes = 0.0
        if stop["kind"] == domain.STOP_DELIVERY and deadline:
            late_minutes = max(0.0, (departure - deadline).total_seconds() / 60.0)
        elif window_end and arrival > window_end:
            late_minutes = max(0.0, (arrival - window_end).total_seconds() / 60.0)

        total_distance += travel_km
        total_duration += travel_minutes + service_minutes + wait_minutes
        rows.append(
            {
                **stop,
                "sequence": len(rows) + 1,
                "planned_arrival": arrival,
                "planned_departure": departure,
                "leg_distance_km": round(travel_km, 3),
                "leg_duration_minutes": round(travel_minutes, 2),
                "wait_minutes": round(wait_minutes, 2),
                "load_weight_kg": round(max(load_weight, 0.0), 3),
                "load_volume_m3": round(max(load_volume, 0.0), 5),
                "load_parcels": load_parcels,
                "late_minutes": round(late_minutes, 2),
                "late": late_minutes > float(cfg.get("deadline_buffer_minutes", 10)),
            }
        )
        previous = chosen
        remaining.discard(chosen)
        clock = departure

    return {
        "stops": rows,
        "distance_km": round(total_distance, 3),
        "duration_minutes": round(total_duration, 1),
        "distance_source": matrix.source,
        "notes": list(matrix.notes),
        "start": {"latitude": start_latitude, "longitude": start_longitude},
        "start_time": start_time,
        "end_time": clock,
        "precedence": "pickup-before-delivery",
        "algorithm": "greedy nearest-feasible with deadline tie-break",
    }


def geometry(rows: list[dict], cfg: dict | None = None) -> tuple[dict, str]:
    cfg = cfg or config()
    return route_geometry(rows, cfg)


def distance_along_sequence(
    stops: list[dict], *, start_latitude: float, start_longitude: float, cfg: dict | None = None
) -> tuple[float, float]:
    """Sum matrix distances/durations along an existing sequence without reordering."""
    cfg = cfg or config()
    if not stops:
        return 0.0, 0.0
    points = [(0, float(start_latitude), float(start_longitude))]
    points += [
        (index + 1, float(stop["latitude"]), float(stop["longitude"]))
        for index, stop in enumerate(stops)
    ]
    matrix = build_matrix(points, cfg)
    total_distance = 0.0
    total_duration = 0.0
    previous = 0
    for index in range(1, len(stops) + 1):
        total_distance += matrix.distance(previous, index)
        total_duration += matrix.duration(previous, index)
        previous = index
    return round(total_distance, 3), round(total_duration, 2)
