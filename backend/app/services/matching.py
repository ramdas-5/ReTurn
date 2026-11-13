"""Explainable constrained matching and routing engine.

This is rule-based optimisation, not a trained model. For each candidate group we
check hard feasibility (windows, deadlines, precedence, capacity at every stop,
handling, partner eligibility, pickups radius, detour, savings) and only then
produce a proposal. Every rejection carries a machine code and a human reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import mean

from flask import current_app

from ..domain import (
    ACTIVE_BATCH_STATUSES,
    HANDLING_FLAGS,
    MATCHING_REASONS,
    PARTNER_VERIFIED,
    REQUEST_PENDING,
    batch_code,
    iso,
    parcel_code,
    request_code,
    utcnow,
)
from ..extensions import db
from ..models import BatchRequest, DeliveryRequest, MatchingRun, PartnerProfile
from ..serializers import serialize_location
from . import routing

REASON_PRIORITY = [
    "handling_incompatible",
    "restricted_exclusive",
    "capacity_exceeded",
    "deadline_missed",
    "window_conflict",
    "pickup_radius",
    "destination_missing",
    "service_area",
    "insufficient_savings",
    "group_size",
    "route_infeasible",
    "no_eligible_partner",
]


class InfeasibleGroup(Exception):
    def __init__(self, reason: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details or {}


@dataclass
class PlanStop:
    request_id: int
    kind: str
    location_id: int
    latitude: float
    longitude: float
    arrival: datetime
    departure: datetime
    leg_km: float
    leg_minutes: float
    load_weight: float
    load_volume: float


@dataclass
class Evaluation:
    feasible: bool
    reason: str | None = None
    detail: str | None = None
    stops: list[PlanStop] = field(default_factory=list)
    distance_km: float = 0.0
    duration_minutes: float = 0.0
    baseline_km: float = 0.0
    max_weight_kg: float = 0.0
    max_volume_m3: float = 0.0
    detour_km: dict[int, float] = field(default_factory=dict)


def settings_from_params(params: dict | None = None, *, provider: str | None = None) -> dict:
    defaults = dict(current_app.config["MATCHING_DEFAULTS"])
    merged = {**defaults, **(params or {})}
    merged["max_group_size"] = max(2, min(int(merged.get("max_group_size", 3)), 4))
    merged["max_pickup_radius_km"] = float(merged.get("max_pickup_radius_km", 6))
    merged["max_detour_km"] = float(merged.get("max_detour_km", 12))
    merged["min_savings_pct"] = max(0.0, float(merged.get("min_savings_pct", 12)))
    merged["service_minutes"] = max(0, int(merged.get("service_minutes", 6)))
    merged["avg_speed_kmh"] = max(1.0, float(merged.get("avg_speed_kmh", 24)))
    merged["road_factor"] = max(1.0, float(merged.get("road_factor", 1.32)))
    merged["provider"] = (provider or current_app.config["ROUTING_PROVIDER"]).lower()
    merged["osrm_base_url"] = current_app.config["OSRM_BASE_URL"]
    merged["timeout_seconds"] = current_app.config["ROUTING_TIMEOUT_SECONDS"]
    return merged


def vehicle_from_config(overrides: dict | None = None) -> dict:
    base = dict(current_app.config["UNASSIGNED_VEHICLE_PROFILE"])
    base.update(overrides or {})
    return base


def vehicle_from_partner(profile: PartnerProfile) -> dict:
    return {
        "label": f"{profile.company_name} ({profile.vehicle_type})",
        "vehicle_type": profile.vehicle_type,
        "max_weight_kg": float(profile.max_weight_kg),
        "max_volume_m3": float(profile.max_volume_m3),
        "accepts_fragile": profile.accepts_fragile,
        "accepts_restricted": profile.accepts_restricted,
        "service_areas": profile.service_area_list,
        "partner_id": profile.user_id,
    }


def _handling_flags(req: DeliveryRequest) -> list[str]:
    if req.parcel is None or not req.parcel.handling_flags:
        return []
    return [flag for flag in req.parcel.handling_flags.split(",") if flag in HANDLING_FLAGS]


def _parcel_dims(req: DeliveryRequest) -> tuple[float, float]:
    if req.parcel is None:
        return 0.0, 0.0
    return float(req.parcel.weight_kg), float(req.parcel.volume_m3)


def _areas(req: DeliveryRequest) -> list[str]:
    areas = []
    for location in (req.pickup_location, req.destination_location):
        if location and location.area and location.area not in areas:
            areas.append(location.area)
    return areas


def worst_reason(reasons: list[str]) -> str:
    for candidate in REASON_PRIORITY:
        if candidate in reasons:
            return candidate
    return reasons[0] if reasons else "route_infeasible"


def _infeasible(reason: str, detail: str, **kwargs) -> Evaluation:
    return Evaluation(feasible=False, reason=reason, detail=detail, **kwargs)


def evaluate_order(
    order: list[tuple[int, str]],
    requests: dict[int, DeliveryRequest],
    matrix: routing.MatrixResult,
    settings: dict,
    vehicle: dict,
    plan_start: datetime,
) -> Evaluation:
    """Simulate the itinerary in the given order and validate every hard rule."""
    request_ids = list({rid for rid, _ in order})
    flags: list[str] = []
    for rid in request_ids:
        for flag in _handling_flags(requests[rid]):
            if flag not in flags:
                flags.append(flag)

    restricted = "restricted" in flags
    if restricted and len(request_ids) > 1:
        return _infeasible(
            "restricted_exclusive",
            "A restricted parcel needs a dedicated vehicle, so it cannot share this batch.",
        )
    if "fragile" in flags and not vehicle.get("accepts_fragile", True):
        return _infeasible(
            "handling_incompatible", "The selected vehicle does not accept fragile parcels."
        )
    if restricted and not vehicle.get("accepts_restricted", False):
        return _infeasible(
            "handling_incompatible", "The selected vehicle is not authorised for restricted items."
        )

    # Precedence: a parcel can never be dropped off before it is collected.
    picked: set[int] = set()
    for rid, kind in order:
        if kind == "pickup":
            picked.add(rid)
        elif rid not in picked:
            return _infeasible(
                "route_infeasible",
                "Pickup must be scheduled before the matching delivery stop.",
            )

    service_minutes = int(settings["service_minutes"])
    prev_loc = None
    prev_departure = plan_start
    load_w = 0.0
    load_v = 0.0
    stops: list[PlanStop] = []
    total_km = 0.0
    total_minutes = 0.0
    max_w = 0.0
    max_v = 0.0

    for rid, kind in order:
        req = requests[rid]
        if req.pickup_location is None or req.destination_location is None:
            return _infeasible("destination_missing", "A request has an unresolved location.")
        location = req.pickup_location if kind == "pickup" else req.destination_location
        weight, volume = _parcel_dims(req)

        leg_km = 0.0
        leg_minutes = 0.0
        if prev_loc is not None:
            leg_km = matrix.distance(prev_loc.id, location.id)
            leg_minutes = matrix.duration(prev_loc.id, location.id)
        arrival = prev_departure + timedelta(minutes=leg_minutes)

        if kind == "pickup":
            window_start = req.pickup_window_start
            window_end = req.pickup_window_end
            if window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=plan_start.tzinfo)
            if window_end.tzinfo is None:
                window_end = window_end.replace(tzinfo=plan_start.tzinfo)
            if arrival < window_start:
                arrival = window_start  # wait for the customer's window
            if arrival > window_end:
                return _infeasible(
                    "window_conflict",
                    f"{request_code(req.id)} cannot be collected inside its pickup window.",
                )
            load_w += weight
            load_v += volume
            max_w = max(max_w, load_w)
            max_v = max(max_v, load_v)
            if load_w > float(vehicle["max_weight_kg"]) + 1e-6:
                return _infeasible(
                    "capacity_exceeded",
                    f"Load would reach {load_w:.2f} kg, above the {float(vehicle['max_weight_kg']):g} kg vehicle limit.",
                )
            if load_v > float(vehicle["max_volume_m3"]) + 1e-6:
                return _infeasible(
                    "capacity_exceeded",
                    f"Load would reach {load_v:.3f} m³, above the {float(vehicle['max_volume_m3']):g} m³ vehicle limit.",
                )
        else:
            delivered = req.delivery_deadline
            if delivered.tzinfo is None:
                delivered = delivered.replace(tzinfo=plan_start.tzinfo)
            if arrival > delivered:
                return _infeasible(
                    "deadline_missed",
                    f"Arrival at {request_code(req.id)}'s destination would miss its delivery deadline.",
                )
            load_w = max(0.0, load_w - weight)
            load_v = max(0.0, load_v - volume)

        departure = arrival + timedelta(minutes=service_minutes)
        total_km += leg_km
        total_minutes += leg_minutes + service_minutes
        stops.append(
            PlanStop(
                request_id=rid,
                kind=kind,
                location_id=location.id,
                latitude=float(location.latitude),
                longitude=float(location.longitude),
                arrival=arrival,
                departure=departure,
                leg_km=round(leg_km, 3),
                leg_minutes=round(leg_minutes, 2),
                load_weight=round(load_w, 3),
                load_volume=round(load_v, 4),
            )
        )
        prev_loc = location
        prev_departure = departure

    baseline = 0.0
    for rid in request_ids:
        req = requests[rid]
        baseline += matrix.distance(req.pickup_location_id, req.destination_location_id)

    detour: dict[int, float] = {}
    for rid in request_ids:
        pickup_index = next(
            (index for index, stop in enumerate(stops) if stop.request_id == rid and stop.kind == "pickup"),
            None,
        )
        dropoff_index = next(
            (index for index, stop in enumerate(stops) if stop.request_id == rid and stop.kind == "dropoff"),
            None,
        )
        if pickup_index is None or dropoff_index is None or dropoff_index <= pickup_index:
            return _infeasible("route_infeasible", "Pickup must be scheduled before delivery.")
        journey = sum(stops[index].leg_km for index in range(pickup_index + 1, dropoff_index + 1))
        direct = matrix.distance(
            requests[rid].pickup_location_id, requests[rid].destination_location_id
        )
        detour[rid] = round(max(0.0, journey - direct), 3)
        if detour[rid] > settings["max_detour_km"]:
            return _infeasible(
                "deadline_missed" if detour[rid] > settings["max_detour_km"] * 2 else "route_infeasible",
                f"{request_code(rid)} would travel {detour[rid]:.1f} km further than its direct trip, "
                f"above the {settings['max_detour_km']:g} km detour limit.",
            )

    return Evaluation(
        feasible=True,
        stops=stops,
        distance_km=round(total_km, 2),
        duration_minutes=round(total_minutes, 1),
        baseline_km=round(baseline, 2),
        max_weight_kg=round(max_w, 2),
        max_volume_m3=round(max_v, 3),
        detour_km=detour,
    )


def _best_insertion(
    order: list[tuple[int, str]],
    candidate: DeliveryRequest,
    requests: dict[int, DeliveryRequest],
    matrix: routing.MatrixResult,
    settings: dict,
    vehicle: dict,
    plan_start: datetime,
) -> tuple[list[tuple[int, str]] | None, Evaluation, list[str]]:
    best_order = None
    best_eval = None
    reasons: list[str] = []
    best_distance = float("inf")
    for pickup_index in range(len(order) + 1):
        with_pickup = order[:pickup_index] + [(candidate.id, "pickup")] + order[pickup_index:]
        for dropoff_index in range(pickup_index + 1, len(order) + 2):
            trial = (
                with_pickup[:dropoff_index]
                + [(candidate.id, "dropoff")]
                + with_pickup[dropoff_index:]
            )
            evaluation = evaluate_order(trial, requests, matrix, settings, vehicle, plan_start)
            if evaluation.feasible:
                if evaluation.distance_km < best_distance:
                    best_distance = evaluation.distance_km
                    best_order = trial
                    best_eval = evaluation
            else:
                reasons.append(evaluation.reason or "route_infeasible")
    return best_order, best_eval, reasons


def _eligible_partners(profile_query, requests: list[DeliveryRequest], vehicle: dict, load_w: float, load_v: float, areas: set[str]) -> list[dict]:
    options = []
    flags = {flag for req in requests for flag in _handling_flags(req)}
    for profile in profile_query:
        reasons = []
        if float(profile.max_weight_kg) < load_w:
            continue
        if float(profile.max_volume_m3) < load_v:
            continue
        if "fragile" in flags and not profile.accepts_fragile:
            continue
        if "restricted" in flags and not profile.accepts_restricted:
            continue
        if profile.service_area_list and not areas.issubset(set(profile.service_area_list)):
            continue
        reasons.append(f"Capacity fits the {load_w:.1f} kg / {load_v:.3f} m³ peak load.")
        if flags:
            reasons.append(f"Handling accepted: {', '.join(sorted(flags))}.")
        reasons.append(f"Service areas include {', '.join(sorted(areas))}.")
        options.append(
            {
                "partner_id": profile.user_id,
                "profile_id": profile.id,
                "name": profile.user.name if profile.user else profile.company_name,
                "vehicle_type": profile.vehicle_type,
                "max_weight_kg": float(profile.max_weight_kg),
                "max_volume_m3": float(profile.max_volume_m3),
                "availability": profile.availability,
                "reasons": reasons,
            }
        )
    options.sort(key=lambda option: (-option["max_weight_kg"], option["name"] or ""))
    return options


def _summary(req: DeliveryRequest) -> dict:
    return {
        "id": req.id,
        "code": request_code(req.id),
        "type": req.type,
        "status": req.status,
        "customer_name": req.customer.name if req.customer else None,
        "parcel": (
            {
                "id": req.parcel.id,
                "code": parcel_code(req.parcel.id),
                "description": req.parcel.description,
                "weight_kg": float(req.parcel.weight_kg),
                "volume_m3": float(req.parcel.volume_m3),
                "handling": req.parcel.handling_list,
            }
            if req.parcel
            else None
        ),
        "pickup": serialize_location(req.pickup_location),
        "destination": serialize_location(req.destination_location),
        "authorized_hub": req.return_detail.authorized_hub_name if req.return_detail else None,
        "recipient_name": req.recipient_detail.recipient_name if req.recipient_detail else None,
        "pickup_window_start": iso(req.pickup_window_start),
        "pickup_window_end": iso(req.pickup_window_end),
        "delivery_deadline": iso(req.delivery_deadline),
    }


def _stop_payload(stop: PlanStop, requests: dict[int, DeliveryRequest]) -> dict:
    req = requests[stop.request_id]
    location = req.pickup_location if stop.kind == "pickup" else req.destination_location
    return {
        "request_id": stop.request_id,
        "request_code": request_code(stop.request_id),
        "kind": stop.kind,
        "location_id": stop.location_id,
        "location": serialize_location(location),
        "arrival": iso(stop.arrival),
        "departure": iso(stop.departure),
        "leg_distance_km": stop.leg_km,
        "leg_duration_minutes": stop.leg_minutes,
        "load_weight_kg": stop.load_weight,
        "load_volume_m3": stop.load_volume,
    }


def build_group(
    requests: list[DeliveryRequest],
    settings: dict,
    vehicle: dict,
    partner_query=None,
    *,
    enforce_savings: bool = True,
) -> dict:
    """Build a feasible ordered itinerary for exactly these requests."""
    if len(requests) < 1:
        raise InfeasibleGroup("route_infeasible", "Select at least one request.")
    if len(requests) > settings["max_group_size"]:
        raise InfeasibleGroup(
            "group_size",
            f"A batch may contain at most {settings['max_group_size']} requests with the current settings.",
        )
    requests_by_id = {req.id: req for req in requests}
    flagged = [req for req in requests if "restricted" in _handling_flags(req)]
    if flagged and len(requests) > 1:
        raise InfeasibleGroup("restricted_exclusive", MATCHING_REASONS["restricted_exclusive"])

    points = []
    for req in requests:
        for location in (req.pickup_location, req.destination_location):
            if location is None:
                raise InfeasibleGroup("destination_missing", MATCHING_REASONS["destination_missing"])
            points.append((location.id, float(location.latitude), float(location.longitude)))
    # Deduplicate by id so the matrix can be indexed by location id.
    unique_points = list({point[0]: point for point in points}.values())
    matrix = routing.build_matrix(unique_points, settings)

    plan_start = utcnow()
    ordered = sorted(requests, key=lambda item: (item.pickup_window_start, -item.priority, item.id))
    order: list[tuple[int, str]] = [
        (ordered[0].id, "pickup"),
        (ordered[0].id, "dropoff"),
    ]
    evaluation = evaluate_order(order, requests_by_id, matrix, settings, vehicle, plan_start)
    if not evaluation.feasible:
        raise InfeasibleGroup(
            evaluation.reason or "route_infeasible",
            evaluation.detail or MATCHING_REASONS.get(evaluation.reason or "", "No feasible route."),
        )
    for req in ordered[1:]:
        anchor = requests_by_id[ordered[0].id].pickup_location
        distance = matrix.distance(anchor.id, req.pickup_location_id)
        if distance > settings["max_pickup_radius_km"]:
            raise InfeasibleGroup(
                "pickup_radius",
                f"{request_code(req.id)} pickup is {distance:.1f} km from the group anchor, "
                f"above the {settings['max_pickup_radius_km']:g} km radius.",
            )
        new_order, new_eval, _ = _best_insertion(
            order, req, requests_by_id, matrix, settings, vehicle, plan_start
        )
        if new_order is None or new_eval is None:
            reason = worst_reason(_candidate_reasons(req, order, requests_by_id, matrix, settings, vehicle, plan_start))
            raise InfeasibleGroup(
                reason,
                f"{request_code(req.id)} cannot be inserted without breaking a hard constraint ({MATCHING_REASONS.get(reason, reason)}).",
            )
        order = new_order
        evaluation = new_eval

    savings = evaluation.baseline_km - evaluation.distance_km
    savings_pct = (savings / evaluation.baseline_km * 100) if evaluation.baseline_km > 0 else 0.0
    if enforce_savings:
        if savings <= 0:
            raise InfeasibleGroup(
                "insufficient_savings",
                f"The shared route ({evaluation.distance_km:.1f} km) is not shorter than separate trips "
                f"({evaluation.baseline_km:.1f} km).",
            )
        if savings_pct < settings["min_savings_pct"]:
            raise InfeasibleGroup(
                "insufficient_savings",
                f"Estimated saving of {savings_pct:.1f}% is below the configured "
                f"{settings['min_savings_pct']:g}% minimum.",
            )

    areas = {area for req in requests for area in _areas(req)}
    if partner_query is not None:
        partner_options = _eligible_partners(
            partner_query,
            requests,
            vehicle,
            evaluation.max_weight_kg,
            evaluation.max_volume_m3,
            areas,
        )
    else:
        partner_options = []

    fuel_factor = current_app.config["SUSTAINABILITY_FUEL_L_PER_KM"]
    co2_factor = current_app.config["SUSTAINABILITY_KG_CO2E_PER_LITRE"]
    saved = max(0.0, savings)
    fuel_saved = round(saved * fuel_factor, 3)
    co2_saved = round(fuel_saved * co2_factor, 3)

    assumptions = [
        "Pickup windows are hard constraints; the schedule never plans a late pickup.",
        "Each request's baseline is one direct pickup → authorised destination trip measured on the same distance basis as the shared route.",
        f"Service time of {settings['service_minutes']} minutes is included at every stop.",
        "Vehicle capacity is checked after every pickup and drop-off, including load released at drop-offs.",
        "Distance, fuel and CO₂e values are modelled estimates, not measured facts.",
        "Partner repositioning to the first pickup is excluded from both the shared route and the baseline.",
    ]
    if matrix.source == "estimated":
        assumptions.append(
            "Road routing was unavailable; distances use haversine × "
            f"{settings['road_factor']:g} road factor at {settings['avg_speed_kmh']:g} km/h."
        )
    if not partner_options:
        assumptions.append(
            f"No verified, available partner currently matches this group; the feasibility check used the "
            f"configured reference vehicle ({vehicle['max_weight_kg']:g} kg / {vehicle['max_volume_m3']:g} m³)."
        )

    included_reasons = [
        f"Pickup windows can be served in one ordered itinerary starting {iso(plan_start)}.",
        "Every pickup is scheduled before its own delivery stop.",
        f"Peak vehicle load {evaluation.max_weight_kg:.2f} kg / {evaluation.max_volume_m3:.3f} m³ is within "
        f"{float(vehicle['max_weight_kg']):g} kg / {float(vehicle['max_volume_m3']):g} m³.",
        f"Estimated shared distance {evaluation.distance_km:.1f} km vs {evaluation.baseline_km:.1f} km "
        f"for separate trips ({savings_pct:.1f}% estimated saving).",
        "Destinations are preserved exactly: authorised return hubs and recipient addresses are unchanged.",
    ]
    if any(_handling_flags(req) for req in requests):
        included_reasons.append(
            "Handling requirements ("
            + ", ".join(sorted({flag for req in requests for flag in _handling_flags(req)}))
            + ") are compatible with the selected vehicle profile."
        )

    return {
        "request_ids": [req.id for req in requests],
        "requests": [_summary(req) for req in requests],
        "stops": [_stop_payload(stop, requests_by_id) for stop in evaluation.stops],
        "distance_km": evaluation.distance_km,
        "baseline_km": evaluation.baseline_km,
        "savings_km": round(savings, 2),
        "savings_percent": round(savings_pct, 1),
        "duration_minutes": int(round(evaluation.duration_minutes)),
        "load_profile": [
            {
                "sequence": index + 1,
                "kind": stop.kind,
                "request_code": request_code(stop.request_id),
                "weight_kg": stop.load_weight,
                "volume_m3": stop.load_volume,
            }
            for index, stop in enumerate(evaluation.stops)
        ],
        "max_load_weight_kg": evaluation.max_weight_kg,
        "max_load_volume_m3": evaluation.max_volume_m3,
        "detour_km": {request_code(rid): value for rid, value in evaluation.detour_km.items()},
        "vehicle": vehicle,
        "distance_source": matrix.source,
        "distance_source_label": matrix.source_label,
        "routing_notes": matrix.notes
        + ([matrix.fallback_reason] if matrix.fallback_reason else []),
        "partner_options": partner_options,
        "included_reasons": included_reasons,
        "assumptions": assumptions,
        "estimated_fuel_saved_l": fuel_saved,
        "estimated_co2e_avoided_kg": co2_saved,
        "minimum_savings_pct": settings["min_savings_pct"],
        "service_minutes": settings["service_minutes"],
        "feasible": True,
    }


def _candidate_reasons(
    candidate: DeliveryRequest,
    order: list[tuple[int, str]],
    requests: dict[int, DeliveryRequest],
    matrix,
    settings,
    vehicle,
    plan_start,
) -> list[str]:
    reasons: list[str] = []
    for pickup_index in range(len(order) + 1):
        with_pickup = order[:pickup_index] + [(candidate.id, "pickup")] + order[pickup_index:]
        for dropoff_index in range(pickup_index + 1, len(order) + 2):
            trial = (
                with_pickup[:dropoff_index]
                + [(candidate.id, "dropoff")]
                + with_pickup[dropoff_index:]
            )
            evaluation = evaluate_order(trial, requests, matrix, settings, vehicle, plan_start)
            if not evaluation.feasible and evaluation.reason:
                reasons.append(evaluation.reason)
    return reasons


def eligible_pending_requests(request_ids: list[int] | None = None) -> list[DeliveryRequest]:
    query = DeliveryRequest.query.filter(DeliveryRequest.status == REQUEST_PENDING)
    if request_ids:
        query = query.filter(DeliveryRequest.id.in_(request_ids))
    requests = query.order_by(
        DeliveryRequest.pickup_window_start.asc(), DeliveryRequest.priority.desc(), DeliveryRequest.id.asc()
    ).all()
    # Defensive: a request with an active reservation is never eligible.
    active_ids = {
        link.request_id
        for link in BatchRequest.query.filter(BatchRequest.released_at.is_(None)).all()
    }
    return [req for req in requests if req.id not in active_ids]


def preview_matching(
    *,
    request_ids: list[int] | None = None,
    params: dict | None = None,
    actor_id: int | None = None,
    persist: bool = True,
) -> dict:
    settings = settings_from_params(params)
    vehicle = vehicle_from_config((params or {}).get("vehicle"))
    plan_start = utcnow()

    pending = eligible_pending_requests(request_ids)
    found_ids = {req.id for req in pending}
    excluded = []
    if request_ids:
        for rid in request_ids:
            if rid not in found_ids:
                excluded.append(
                    {
                        "request_id": rid,
                        "code": request_code(rid),
                        "reason": "not_pending",
                        "message": "Request is not awaiting matching or is reserved in another batch.",
                    }
                )

    partner_query = (
        PartnerProfile.query.join(PartnerProfile.user)
        .filter(PartnerProfile.verification_status == PARTNER_VERIFIED)
        .filter(PartnerProfile.availability == "available")
        .order_by(PartnerProfile.max_weight_kg.desc())
        .all()
    )

    points = []
    for req in pending:
        for location in (req.pickup_location, req.destination_location):
            if location is not None:
                points.append((location.id, float(location.latitude), float(location.longitude)))
    matrix = routing.build_matrix(list({p[0]: p for p in points}.values()), settings)

    groups: list[dict] = []
    near_misses: list[dict] = []
    unmatched: list[dict] = []
    used: set[int] = set()
    attempted: set[int] = set()
    seen_near_miss: set[tuple[int, ...]] = set()

    for seed in pending:
        if seed.id in used or seed.id in attempted:
            continue
        group = [seed]
        group_ids = {seed.id}
        anchor = seed.pickup_location
        group_eval = evaluate_order(
            [(seed.id, "pickup"), (seed.id, "dropoff")],
            {seed.id: seed},
            matrix,
            settings,
            vehicle,
            plan_start,
        )
        if not group_eval.feasible:
            unmatched.append(
                {
                    "request_id": seed.id,
                    "code": request_code(seed.id),
                    "reason": group_eval.reason,
                    "message": group_eval.detail
                    or MATCHING_REASONS.get(group_eval.reason or "", "Not feasible."),
                }
            )
            attempted.add(seed.id)
            continue

        order: list[tuple[int, str]] = [(seed.id, "pickup"), (seed.id, "dropoff")]
        for candidate in pending:
            if candidate.id in group_ids or candidate.id in used:
                continue
            if len(group) >= settings["max_group_size"]:
                break
            if anchor and candidate.pickup_location:
                radius = matrix.distance(anchor.id, candidate.pickup_location_id)
                if radius > settings["max_pickup_radius_km"]:
                    key = tuple(sorted((seed.id, candidate.id)))
                    if key not in seen_near_miss:
                        seen_near_miss.add(key)
                        near_misses.append(
                            {
                                "request_ids": list(key),
                                "reason_code": "pickup_radius",
                                "message": f"{request_code(candidate.id)} pickup is {radius:.1f} km from the group anchor, outside the {settings['max_pickup_radius_km']:g} km prefilter.",
                            }
                        )
                    continue

            trial_requests = {req.id: req for req in group + [candidate]}
            new_order, new_eval, reasons = _best_insertion(
                order, candidate, trial_requests, matrix, settings, vehicle, plan_start
            )
            if new_order is None or new_eval is None:
                reason = worst_reason(reasons)
                key = tuple(sorted([req.id for req in group] + [candidate.id]))
                if key not in seen_near_miss:
                    seen_near_miss.add(key)
                    near_misses.append(
                        {
                            "request_ids": list(key),
                            "reason_code": reason,
                            "message": f"{request_code(candidate.id)} was not added: {MATCHING_REASONS.get(reason, reason)}",
                        }
                    )
                continue

            group.append(candidate)
            group_ids.add(candidate.id)
            order = new_order
            group_eval = new_eval

        if len(group) >= 2:
            savings = group_eval.baseline_km - group_eval.distance_km
            savings_pct = (savings / group_eval.baseline_km * 100) if group_eval.baseline_km > 0 else 0.0
            if savings > 0 and savings_pct >= settings["min_savings_pct"]:
                requests_for_group = sorted(group, key=lambda item: group_eval.detour_km.get(item.id, 0))
                try:
                    group_payload = build_group(
                        requests_for_group,
                        settings,
                        vehicle,
                        partner_query,
                        enforce_savings=True,
                    )
                except InfeasibleGroup as exc:
                    near_misses.append(
                        {
                            "request_ids": sorted(group_ids),
                            "reason_code": exc.reason,
                            "message": exc.message,
                        }
                    )
                else:
                    group_payload["group_key"] = ",".join(
                        str(rid) for rid in group_payload["request_ids"]
                    )
                    groups.append(group_payload)
                    used.update(group_ids)
                    continue
            key = tuple(sorted(group_ids))
            if key not in seen_near_miss:
                seen_near_miss.add(key)
                near_misses.append(
                    {
                        "request_ids": list(key),
                        "reason_code": "insufficient_savings",
                        "message": f"Estimated saving {savings_pct:.1f}% is below the configured {settings['min_savings_pct']:g}% minimum.",
                    }
                )

        attempted.add(seed.id)
        unmatched.append(
            {
                "request_id": seed.id,
                "code": request_code(seed.id),
                "reason": "no_compatible_group",
                "message": "No compatible request with a positive shared-route benefit was found yet. Nearby does not always mean compatible.",
            }
        )

    # A failed seed may still have joined a later feasible group; report only truly unmatched requests.
    unmatched = [item for item in unmatched if item["request_id"] not in used]

    result = {
        "run_id": None,
        "generated_at": iso(plan_start),
        "settings": settings,
        "vehicle": vehicle,
        "distance_source": matrix.source,
        "distance_source_label": matrix.source_label,
        "routing_notes": matrix.notes
        + ([matrix.fallback_reason] if matrix.fallback_reason else []),
        "pending_count": len(pending),
        "groups": groups,
        "near_misses": near_misses,
        "unmatched": unmatched,
        "excluded": excluded,
        "assumptions": [
            "Matching is rule-based and explainable; there is no trained model.",
            "Nearby pickups alone never justify a batch: windows, deadlines, capacity, handling, detour and estimated savings are all checked.",
            "Estimated savings compare the shared route with one direct pickup→destination trip per request on the same distance basis.",
            "All distance, fuel and CO₂e values are estimates for planning and are not measured.",
        ],
    }

    if persist:
        run = MatchingRun(
            actor_id=actor_id,
            params=_json_safe(params or {}),
            result=_json_safe(result),
        )
        db.session.add(run)
        db.session.flush()
        result["run_id"] = run.id
        run.result = _json_safe(result)
        db.session.commit()
    return result


def quote_selected_requests(
    request_ids: list[int],
    *,
    partner_profile: PartnerProfile | None = None,
    params: dict | None = None,
) -> tuple[dict, routing.MatrixResult]:
    """Fresh feasibility quote used by commit; never trusts a stored preview."""
    if not request_ids:
        raise InfeasibleGroup("route_infeasible", "Select at least one request.")
    if len(set(request_ids)) != len(request_ids):
        raise InfeasibleGroup("route_infeasible", "Duplicate request ids are not allowed.")
    requests = DeliveryRequest.query.filter(DeliveryRequest.id.in_(request_ids)).all()
    if len(requests) != len(request_ids):
        raise InfeasibleGroup("not_pending", "One or more requests no longer exist.")
    for req in requests:
        if req.status != REQUEST_PENDING:
            raise InfeasibleGroup(
                "not_pending",
                f"{request_code(req.id)} is not awaiting matching (status: {req.status.replace('_', ' ')}).",
            )
        if BatchRequest.query.filter(
            BatchRequest.request_id == req.id, BatchRequest.released_at.is_(None)
        ).first():
            raise InfeasibleGroup(
                "already_reserved", f"{request_code(req.id)} is already reserved in an active batch."
            )

    settings = settings_from_params(params)
    vehicle = vehicle_from_partner(partner_profile) if partner_profile else vehicle_from_config(
        (params or {}).get("vehicle")
    )
    group = build_group(
        requests,
        settings,
        vehicle,
        PartnerProfile.query.filter(PartnerProfile.verification_status == PARTNER_VERIFIED).all(),
        enforce_savings=True,
    )
    points = []
    for req in requests:
        for location in (req.pickup_location, req.destination_location):
            points.append((location.id, float(location.latitude), float(location.longitude)))
    matrix = routing.build_matrix(list({p[0]: p for p in points}.values()), settings)
    return group, matrix


def partner_eligible_for_batch(batch, profile: PartnerProfile) -> tuple[bool, str | None]:
    if profile is None:
        return False, "No partner profile."
    if profile.verification_status != PARTNER_VERIFIED:
        return False, "Partner is not verified."
    if profile.availability != "available":
        return False, "Partner is not currently available."
    load_w = max((float(stop.load_weight_kg) for stop in batch.stops), default=0)
    load_v = max((float(stop.load_volume_m3) for stop in batch.stops), default=0)
    if float(profile.max_weight_kg) < load_w:
        return False, f"Vehicle limit {float(profile.max_weight_kg):g} kg is below the {load_w:.1f} kg load."
    if float(profile.max_volume_m3) < load_v:
        return False, f"Vehicle volume {float(profile.max_volume_m3):g} m³ is below the {load_v:.3f} m³ load."
    flags = {
        flag
        for link in batch.request_links
        if link.released_at is None and link.request.parcel
        for flag in link.request.parcel.handling_list
    }
    if "fragile" in flags and not profile.accepts_fragile:
        return False, "Partner vehicle does not accept fragile parcels."
    if "restricted" in flags and not profile.accepts_restricted:
        return False, "Partner is not authorised for restricted items."
    areas = set()
    for link in batch.request_links:
        if link.released_at is not None or link.request is None:
            continue
        areas.update(_areas(link.request))
    if profile.service_area_list and not areas.issubset(set(profile.service_area_list)):
        missing = sorted(areas - set(profile.service_area_list))
        return False, f"Partner does not cover: {', '.join(missing)}."
    if batch.status in ACTIVE_BATCH_STATUSES and batch.status in {"accepted", "in_progress"}:
        return True, None
    return True, None


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return iso(value)
    return value


def summarize_savings(groups: list[dict]) -> dict:
    if not groups:
        return {"baseline_km": 0, "shared_km": 0, "saved_km": 0, "percent": 0}
    baseline = sum(group["baseline_km"] for group in groups)
    shared = sum(group["distance_km"] for group in groups)
    saved = max(0.0, baseline - shared)
    return {
        "baseline_km": round(baseline, 2),
        "shared_km": round(shared, 2),
        "saved_km": round(saved, 2),
        "percent": round((saved / baseline * 100) if baseline else 0, 1),
    }
