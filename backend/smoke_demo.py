"""Seeded four-role smoke check. Run after `python manage.py seed`."""

from wsgi import app

PASSWORD = "ReTurn#2026"

CHECKS = {
    "consumer": [
        ("priya@return.demo", "/api/v1/auth/me"),
        ("priya@return.demo", "/api/v1/consumer/summary"),
        ("priya@return.demo", "/api/v1/orders"),
    ],
    "driver": [
        ("arjun@return.demo", "/api/v1/driver/summary"),
        ("arjun@return.demo", "/api/v1/driver/assignments"),
        ("arjun@return.demo", "/api/v1/driver/profile"),
    ],
    "manager": [
        ("manager@return.demo", "/api/v1/manager/summary"),
        ("manager@return.demo", "/api/v1/manager/proofs"),
        ("manager@return.demo", "/api/v1/manager/batches"),
    ],
    "admin": [
        ("admin@return.demo", "/api/v1/admin/summary"),
        ("admin@return.demo", "/api/v1/admin/analytics"),
        ("admin@return.demo", "/api/v1/admin/proofs"),
    ],
}


def session_for(email: str):
    client = app.test_client()
    csrf = client.get("/api/v1/auth/csrf").get_json()["data"]["csrf_token"]
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, (email, response.status_code, response.get_json())
    token = response.get_json()["data"]["csrf_token"]
    return client, token, response.get_json()["data"]["user"]["role"]


def main() -> None:
    for expected_role, checks in CHECKS.items():
        client, token, role = session_for(checks[0][0])
        assert role == expected_role, (role, expected_role)
        for _email, path in checks:
            response = client.get(path, headers={"X-CSRF-Token": token})
            assert response.status_code == 200, (path, response.status_code, response.get_json())
            payload = response.get_json()["data"]
            if isinstance(payload, dict):
                summary = {k: len(v) for k, v in payload.items() if isinstance(v, list)}
                print(f"{role:8} {path:38} 200 {summary}")
            else:
                print(f"{role:8} {path:38} 200")

    # Verify a seeded batch and order are readable through scoped detail routes.
    manager, token, _ = session_for("manager@return.demo")
    batches = manager.get("/api/v1/manager/batches", headers={"X-CSRF-Token": token}).get_json()["data"]
    batch_list = batches["batches"] if isinstance(batches, dict) else batches
    assert batch_list, "seeded batch not visible to manager"
    batch_id = batch_list[0]["id"]
    detail = manager.get(f"/api/v1/manager/batches/{batch_id}", headers={"X-CSRF-Token": token})
    assert detail.status_code == 200, detail.get_json()
    print(f"manager  /manager/batches/{batch_id} detail 200")

    admin, token, _ = session_for("admin@return.demo")
    proofs = admin.get("/api/v1/admin/proofs", headers={"X-CSRF-Token": token}).get_json()["data"]
    proof_list = proofs["proofs"] if isinstance(proofs, dict) else proofs
    assert proof_list, "seeded proof not visible to admin"
    print(f"admin    seeded proofs visible: {len(proof_list)}")


if __name__ == "__main__":
    main()
