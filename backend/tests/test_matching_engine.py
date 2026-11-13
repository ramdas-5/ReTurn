"""Matching engine feasibility, explainability and savings honesty."""
from __future__ import annotations

from datetime import timedelta

from app.domain import utcnow
from app.extensions import db
from app.models import DeliveryBatch, DeliveryRequest, User
from app.services import matching, routing


def _pending_codes(result: dict) -> set[str]:
    return {request["code"] for group in result["groups"] for request in group["requests"]}


def test_preview_groups_mixed_returns_and_parcel_with_different_destinations(db, admin):
    response = admin.post("/api/v1/matching/preview", {"params": {"max_group_size": 4}})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["groups"], data
    group = next(group for group in data["groups"] if len(group["request_ids"]) >= 2)
    types = {request["type"] for request in group["requests"]}
    assert {"return", "parcel"}.issubset(types)
    destinations = {request["destination"]["label"] for request in group["requests"]}
    assert len(destinations) == len(group["requests"])
    assert any("Authorized Returns Hub" in label for label in destinations)

    positions: dict[int, dict[str, int]] = {}
    for index, stop in enumerate(group["stops"]):
        positions.setdefault(stop["request_id"], {})[stop["kind"]] = index
    for request_id, pair in positions.items():
        assert pair["pickup"] < pair["dropoff"], "pickup must precede dropoff"

    assert group["savings_km"] > 0
    assert group["savings_percent"] > 0
    assert group["distance_source"] in {"osrm", "estimated"}
    assert group["distance_source_label"]
    assert any("estimate" in assumption.lower() for assumption in group["assumptions"])
    assert group["load_profile"]
    assert group["included_reasons"]


def test_preview_rejects_capacity_and_deadline_conflicts(db, admin):
    response = admin.post(
        "/api/v1/matching/preview",
        {"params": {"max_group_size": 4, "min_savings_pct": 5}},
    )
    data = response.get_json()["data"]
    reasons = {item["reason_code"] for item in data["near_misses"]}
    unmatched_reasons = {item["reason"] for item in data["unmatched"]}
    assert "deadline_missed" in reasons or "deadline_missed" in unmatched_reasons
    assert "capacity_exceeded" in reasons or "capacity_exceeded" in unmatched_reasons
    assert "restricted_exclusive" in reasons or "no_compatible_group" in unmatched_reasons
    for group in data["groups"]:
        for request in group["requests"]:
            assert "desk" not in (request["parcel"]["description"].lower())
            assert request["parcel"]["weight_kg"] <= 40


def test_preview_does_not_claim_trained_ai(db, admin):
    data = admin.post("/api/v1/matching/preview", {}).get_json()["data"]
    assert "rule-based" in " ".join(data["assumptions"]).lower()
    assert data["distance_source"] == "estimated"
    assert "not road navigation" in data["distance_source_label"].lower() or "estimated" in data["distance_source_label"].lower()


def test_estimated_matrix_is_labelled_and_symmetric():
    app_config = {
        "provider": "estimated",
        "road_factor": 1.32,
        "avg_speed_kmh": 24,
    }
    matrix = routing.build_matrix([(1, 22.7241, 88.4821), (2, 22.5726, 88.4282)], app_config)
    assert matrix.source == "estimated"
    assert "estimated" in matrix.source_label.lower()
    assert matrix.distance(1, 2) == matrix.distance(2, 1)
    assert matrix.distance(1, 1) == 0
    assert matrix.duration(1, 2) > 0


def test_capacity_is_checked_after_every_stop(db):
    pending = (
        DeliveryRequest.query.filter_by(status="pending_matching")
        .order_by(DeliveryRequest.pickup_window_start)
        .all()
    )
    by_code = {request.code: request for request in pending}
    heavy = by_code["RTN-REQ-1004"]  # 55 kg counterexample
    rahul = by_code["RTN-REQ-1001"]
    locations = []
    for request in (rahul, heavy):
        for location in (request.pickup_location, request.destination_location):
            locations.append((location.id, float(location.latitude), float(location.longitude)))
    matrix = routing.build_matrix(list({p[0]: p for p in locations}.values()), {
        "provider": "estimated", "road_factor": 1.32, "avg_speed_kmh": 24,
    })
    settings = matching.settings_from_params({"provider": "estimated"})
    settings["provider"] = "estimated"
    settings["max_detour_km"] = 100
    evaluation = matching.evaluate_order(
        [(rahul.id, "pickup"), (heavy.id, "pickup"), (rahul.id, "dropoff"), (heavy.id, "dropoff")],
        {rahul.id: rahul, heavy.id: heavy},
        matrix,
        settings,
        matching.vehicle_from_config(),
        utcnow(),
    )
    assert evaluation.feasible is False
    assert evaluation.reason == "capacity_exceeded"


def test_precedence_rule_rejects_delivery_before_pickup(db):
    request = DeliveryRequest.query.filter(
        DeliveryRequest.customer.has(User.email == "priya@return.demo")
    ).first()
    locations = []
    for location in (request.pickup_location, request.destination_location):
        locations.append((location.id, float(location.latitude), float(location.longitude)))
    matrix = routing.build_matrix(locations, {
        "provider": "estimated", "road_factor": 1.32, "avg_speed_kmh": 24,
    })
    settings = matching.settings_from_params()
    settings["provider"] = "estimated"
    evaluation = matching.evaluate_order(
        [(request.id, "dropoff"), (request.id, "pickup")],
        {request.id: request},
        matrix,
        settings,
        matching.vehicle_from_config(),
        utcnow(),
    )
    assert evaluation.feasible is False
    assert evaluation.reason == "route_infeasible"


def test_window_conflict_prevents_grouping(db):
    request = DeliveryRequest.query.filter(
        DeliveryRequest.customer.has(User.email == "rahul@return.demo")
    ).first()
    request.pickup_window_start = utcnow() + timedelta(hours=5)
    request.pickup_window_end = utcnow() + timedelta(hours=6)
    db.session.commit()
    result = matching.preview_matching(persist=False)
    for group in result["groups"]:
        assert request.id not in group["request_ids"]
    reasons = {item["reason_code"] for item in result["near_misses"]}
    assert "window_conflict" in reasons or any(
        item["request_id"] == request.id for item in result["unmatched"]
    )


def test_savings_never_negative_in_analytics(db, admin):
    batch = DeliveryBatch(
        status="completed",
        distance_km=12.0,
        baseline_km=10.0,  # deliberately worse than baseline
        savings_km=0,
        savings_percent=0,
        distance_source="estimated",
    )
    db.session.add(batch)
    db.session.commit()
    data = admin.get("/api/v1/analytics/sustainability").get_json()["data"]
    row = next(item for item in data["batches"] if item["batch_id"] == batch.id)
    assert row["saved_km"] == 0
    assert row["estimated_fuel_saved_l"] == 0
    assert row["estimated_co2e_avoided_kg"] == 0
