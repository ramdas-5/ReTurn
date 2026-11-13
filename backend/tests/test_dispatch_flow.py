"""End-to-end dispatch, acceptance, execution and tracking."""
from __future__ import annotations

from app.models import (
    BatchRequest,
    DeliveryBatch,
    DeliveryRequest,
    Notification,
    Parcel,
    TrackingEvent,
    User,
)


def _preview_group(admin, size: int = 2) -> dict:
    data = admin.post(
        "/api/v1/matching/preview", {"params": {"max_group_size": 4}}
    ).get_json()["data"]
    group = max(data["groups"], key=lambda item: len(item["request_ids"]))
    assert len(group["request_ids"]) >= size
    return group


def test_commit_offer_accept_execute_and_track(db, admin, partner):
    group = _preview_group(admin)
    response = admin.post(
        "/api/v1/matching/commit",
        {"request_ids": group["request_ids"], "note": "Integration test batch."},
    )
    assert response.status_code == 201, response.get_json()
    batch_id = response.get_json()["data"]["id"]
    batch = DeliveryBatch.query.get(batch_id)
    assert batch.status == "proposed"
    assert batch.distance_source in {"osrm", "estimated"}
    assert len(batch.stops) == 2 * len(group["request_ids"])
    assert all(request.status == "batched" for request in _batch_requests(batch))

    partner_user = User.query.filter_by(email="partner@return.demo").first()
    offer = admin.post(f"/api/v1/batches/{batch_id}/offer", {"partner_id": partner_user.id})
    assert offer.status_code == 200, offer.get_json()
    assert offer.get_json()["data"]["status"] == "offered"

    accept = partner.post(f"/api/v1/batches/{batch_id}/decision", {"decision": "accept"})
    assert accept.status_code == 200, accept.get_json()
    assert accept.get_json()["data"]["status"] == "accepted"
    for request in _batch_requests(batch):
        assert request.status == "assigned"
        assert request.parcel.status == "partner_accepted"

    start = partner.post(f"/api/v1/batches/{batch_id}/start", {})
    assert start.status_code == 200
    assert start.get_json()["data"]["status"] == "in_progress"

    parcels = [request.parcel for request in _batch_requests(batch)]
    # Deliver one parcel fully; the other must remain independently traceable.
    first = parcels[0]
    for event in ("pickup_arrived", "picked_up", "in_transit", "delivered"):
        response = partner.post(
            f"/api/v1/parcels/{first.id}/events",
            {"event_type": event, "notes": f"test {event}"},
        )
        assert response.status_code == 200, response.get_json()
    assert first.status == "delivered"
    assert parcels[1].status == "partner_accepted"
    assert DeliveryBatch.query.get(batch_id).status == "in_progress"
    tracking = partner.get(f"/api/v1/parcels/{parcels[1].id}/tracking").get_json()["data"]
    assert tracking["allowed_next"] == ["pickup_arrived", "failed"]

    for parcel in parcels:
        if parcel.status == "delivered":
            continue
        for event in ("pickup_arrived", "picked_up", "in_transit", "delivered"):
            response = partner.post(
                f"/api/v1/parcels/{parcel.id}/events", {"event_type": event}
            )
            assert response.status_code == 200, response.get_json()

    completed_batch = DeliveryBatch.query.get(batch_id)
    assert completed_batch.status == "completed"
    assert completed_batch.completed_at is not None
    for request in _batch_requests(completed_batch):
        assert request.status == "completed"
    assert TrackingEvent.query.filter_by(parcel_id=first.id).count() >= 4
    assert Notification.query.filter_by(user_id=first.request.customer_id).count() >= 1

    # The customer sees their own parcel timeline but not the other customer's rows.
    customer_request = _batch_requests(completed_batch)[0]
    customer_id = customer_request.customer_id
    from tests.conftest import Session

    customer = Session(admin.client.application.test_client())
    customer.login(
        User.query.get(customer_id).email
    )
    detail = customer.get(f"/api/v1/requests/{customer_request.id}").get_json()["data"]
    assert detail["tracking"]
    assert detail["parcel"]["status"] == "delivered"


def _batch_requests(batch: DeliveryBatch) -> list[DeliveryRequest]:
    return [link.request for link in batch.request_links if link.released_at is None]


def test_duplicate_active_reservation_is_rejected(db, admin):
    group = _preview_group(admin, size=2)
    first = admin.post("/api/v1/matching/commit", {"request_ids": group["request_ids"]})
    assert first.status_code == 201
    second = admin.post("/api/v1/matching/commit", {"request_ids": group["request_ids"]})
    assert second.status_code == 409
    active = BatchRequest.query.filter(
        BatchRequest.request_id.in_(group["request_ids"]), BatchRequest.released_at.is_(None)
    ).count()
    assert active == len(group["request_ids"])


def test_illegal_status_transitions_are_refused(db, admin, partner):
    group = _preview_group(admin)
    batch_id = admin.post(
        "/api/v1/matching/commit", {"request_ids": group["request_ids"]}
    ).get_json()["data"]["id"]
    partner_user = User.query.filter_by(email="partner@return.demo").first()
    admin.post(f"/api/v1/batches/{batch_id}/offer", {"partner_id": partner_user.id})
    partner.post(f"/api/v1/batches/{batch_id}/decision", {"decision": "accept"})
    partner.post(f"/api/v1/batches/{batch_id}/start", {})
    batch = DeliveryBatch.query.get(batch_id)
    parcel = _batch_requests(batch)[0].parcel

    # Delivered before pickup is never legal.
    response = partner.post(
        f"/api/v1/parcels/{parcel.id}/events", {"event_type": "delivered"}
    )
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "invalid_transition"

    # Failure requires a reason.
    response = partner.post(
        f"/api/v1/parcels/{parcel.id}/events", {"event_type": "failed"}
    )
    assert response.status_code == 422

    # Status must not change without a valid transition.
    assert Parcel.query.get(parcel.id).status == "partner_accepted"


def test_partner_cannot_update_an_unassigned_batch(db, admin, partner):
    group = _preview_group(admin)
    batch_id = admin.post(
        "/api/v1/matching/commit", {"request_ids": group["request_ids"]}
    ).get_json()["data"]["id"]
    batch = DeliveryBatch.query.get(batch_id)
    parcel = _batch_requests(batch)[0].parcel
    response = partner.post(
        f"/api/v1/parcels/{parcel.id}/events", {"event_type": "pickup_arrived"}
    )
    assert response.status_code == 403


def test_decline_releases_offer_for_reassignment(db, admin, partner):
    group = _preview_group(admin)
    batch_id = admin.post(
        "/api/v1/matching/commit", {"request_ids": group["request_ids"]}
    ).get_json()["data"]["id"]
    partner_user = User.query.filter_by(email="partner@return.demo").first()
    admin.post(f"/api/v1/batches/{batch_id}/offer", {"partner_id": partner_user.id})
    decline = partner.post(
        f"/api/v1/batches/{batch_id}/decision",
        {"decision": "decline", "reason": "Vehicle in service."},
    )
    assert decline.status_code == 200
    batch = DeliveryBatch.query.get(batch_id)
    assert batch.status == "declined"
    assert batch.partner_id is None
    assert all(request.status == "batched" for request in _batch_requests(batch))

    reassigned = admin.post(
        f"/api/v1/batches/{batch_id}/reassign",
        {"partner_id": partner_user.id, "reason": "Partner confirmed availability again."},
    )
    assert reassigned.status_code == 200
    assert reassigned.get_json()["data"]["status"] == "offered"


def test_admin_cancel_releases_requests(db, admin):
    group = _preview_group(admin)
    batch_id = admin.post(
        "/api/v1/matching/commit", {"request_ids": group["request_ids"]}
    ).get_json()["data"]["id"]
    response = admin.post(
        f"/api/v1/batches/{batch_id}/cancel", {"reason": "Operational consolidation."}
    )
    assert response.status_code == 200
    batch = DeliveryBatch.query.get(batch_id)
    assert batch.status == "cancelled"
    for link in batch.request_links:
        assert link.released_at is not None
        assert link.request.status == "pending_matching"
    assert (
        BatchRequest.query.filter(
            BatchRequest.request_id.in_(group["request_ids"]),
            BatchRequest.released_at.is_(None),
        ).count()
        == 0
    )


def test_customer_cancellation_dissolves_proposed_batch(db, admin, rahul):
    group = _preview_group(admin)
    batch_id = admin.post(
        "/api/v1/matching/commit", {"request_ids": group["request_ids"]}
    ).get_json()["data"]["id"]
    batch = DeliveryBatch.query.get(batch_id)
    rahul_request = next(
        request for request in _batch_requests(batch) if request.customer.email == "rahul@return.demo"
    )
    response = rahul.post(
        f"/api/v1/requests/{rahul_request.id}/cancel", {"reason": "No longer needed."}
    )
    assert response.status_code == 200
    assert DeliveryBatch.query.get(batch_id).status == "cancelled"
    for request in _batch_requests(DeliveryBatch.query.get(batch_id)):
        if request.id != rahul_request.id:
            assert request.status == "pending_matching"
