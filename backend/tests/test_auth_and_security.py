"""Auth, CSRF, role and ownership protection."""
from __future__ import annotations

from app.models import BatchRequest, DeliveryBatch, DeliveryRequest, User

from .conftest import Session


def test_csrf_required_for_mutations(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "rahul@return.demo", "password": "ReTurn#2026"},
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "csrf_failed"


def test_register_customer_and_session(client):
    session = Session(client)
    response = session.post(
        "/api/v1/auth/register",
        {
            "name": "Test Customer",
            "email": "new.customer@example.test",
            "password": "Password123",
            "role": "customer",
        },
    )
    assert response.status_code == 201
    assert response.get_json()["data"]["user"]["role"] == "customer"
    me = session.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.get_json()["data"]["user"]["email"] == "new.customer@example.test"


def test_register_partner_requires_verification(db, client):
    session = Session(client)
    response = session.post(
        "/api/v1/auth/register",
        {
            "name": "Test Partner",
            "email": "new.partner@example.test",
            "password": "Password123",
            "role": "partner",
            "vehicle_type": "bike",
        },
    )
    assert response.status_code == 201
    profile = response.get_json()["data"]["partner_profile"]
    assert profile["verification_status"] == "pending"


def test_wrong_password_rejected(client):
    session = Session(client)
    response = session.post(
        "/api/v1/auth/login",
        {"email": "rahul@return.demo", "password": "not-the-password"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_credentials"


def test_unauthenticated_cannot_list_requests(client):
    response = client.get("/api/v1/requests")
    assert response.status_code == 401


def test_customer_cannot_read_other_customer_request(db, session):
    other = DeliveryRequest.query.filter(
        DeliveryRequest.customer.has(User.email == "priya@return.demo")
    ).first()
    session.login("rahul@return.demo")
    response = session.get(f"/api/v1/requests/{other.id}")
    assert response.status_code == 403


def test_customer_cannot_use_admin_endpoints(rahul):
    assert rahul.get("/api/v1/customers").status_code == 403
    assert rahul.post("/api/v1/matching/preview", {}).status_code == 403
    assert rahul.get("/api/v1/analytics/summary").status_code == 403


def test_disabled_customer_session_removed(app, db, session):
    session.login("rahul@return.demo")
    rahul = User.query.filter_by(email="rahul@return.demo").first()
    admin_session = Session(app.test_client())
    admin_session.login("admin@return.demo")
    response = admin_session.patch(f"/api/v1/customers/{rahul.id}", {"disabled": True})
    assert response.status_code == 200
    assert rahul.disabled_at is not None
    # The previously issued session must stop resolving to a user.
    assert session.get("/api/v1/auth/me").status_code == 401


def test_partner_cannot_view_unrelated_request(db, session):
    rahul_request = DeliveryRequest.query.filter(
        DeliveryRequest.customer.has(User.email == "rahul@return.demo")
    ).first()
    session.login("partner@return.demo")
    response = session.get(f"/api/v1/requests/{rahul_request.id}")
    assert response.status_code == 403


def test_admin_can_verify_partner(db, session):
    from app.models import PartnerProfile

    profile = PartnerProfile.query.filter_by(verification_status="pending").first()
    session.login("admin@return.demo")
    response = session.patch(
        f"/api/v1/partners/{profile.user_id}/verify",
        {"decision": "verified", "note": "Documents checked."},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["profile"]["verification_status"] == "verified"


def test_rejection_requires_note(db, admin):
    from app.models import PartnerProfile

    profile = PartnerProfile.query.filter_by(verification_status="pending").first()
    response = admin.patch(
        f"/api/v1/partners/{profile.user_id}/verify", {"decision": "rejected"}
    )
    assert response.status_code == 422


def test_customer_cancellation_and_forbidden_second_cancel(db, rahul):
    request = DeliveryRequest.query.filter(
        DeliveryRequest.customer.has(User.email == "rahul@return.demo")
    ).first()
    response = rahul.post(f"/api/v1/requests/{request.id}/cancel", {"reason": "Changed my mind."})
    assert response.status_code == 200
    assert response.get_json()["data"]["status"] == "cancelled"
    again = rahul.post(f"/api/v1/requests/{request.id}/cancel", {"reason": "again"})
    assert again.status_code == 409
