"""Pytest fixtures for the ReTurn API test suite (PostgreSQL only)."""
from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy import text

# Minimal JPEG: the storage layer validates the magic bytes and MIME type.
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://return:return_dev_pw@127.0.0.1:5433/return_test",
)

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db as _db  # noqa: E402


@pytest.fixture(scope="session")
def app():
    application = create_app(TestConfig)
    with application.app_context():
        # The test database is disposable: start from an empty schema so stale
        # tables from earlier revisions cannot interfere.
        with _db.engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        _db.create_all()
    yield application
    with application.app_context():
        _db.session.remove()


@pytest.fixture()
def db(app):
    with app.app_context():
        tables = ", ".join(
            f'"{table}"' for table in _db.metadata.tables.keys()
        )
        _db.session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        _db.session.commit()
        yield _db
        _db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


def _refreshed_csrf(payload) -> str | None:
    """Some endpoints return a list; only object payloads carry a rotated token."""
    data = (payload or {}).get("data")
    return data.get("csrf_token") if isinstance(data, dict) else None


class Session:
    """Cookie + CSRF-aware client wrapper."""

    def __init__(self, client):
        self.client = client
        self.token = None

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-CSRF-Token"] = self.token
        return headers

    def refresh_csrf(self):
        response = self.client.get("/api/v1/auth/csrf")
        if response.status_code == 200:
            self.token = response.get_json()["data"]["csrf_token"]
        return self.token

    def get(self, path):
        return self.client.get(path)

    def post(self, path, json=None):
        if not self.token:
            self.refresh_csrf()
        response = self.client.post(path, json=json or {}, headers=self._headers())
        payload = response.get_json(silent=True) or {}
        if (
            response.status_code == 403
            and (payload.get("error") or {}).get("code") == "csrf_failed"
        ):
            # Cookie/session rotation (e.g. after logout) invalidates the old token.
            self.refresh_csrf()
            response = self.client.post(path, json=json or {}, headers=self._headers())
            payload = response.get_json(silent=True) or {}
        refreshed = _refreshed_csrf(payload)
        if refreshed:
            self.token = refreshed
        return response

    def patch(self, path, json=None):
        if not self.token:
            self.refresh_csrf()
        return self.client.patch(path, json=json or {}, headers=self._headers())

    def delete(self, path):
        if not self.token:
            self.refresh_csrf()
        return self.client.delete(path, headers=self._headers())

    def post_file(
        self,
        path,
        *,
        field="photo",
        content=JPEG_BYTES,
        filename="parcel.jpg",
        form=None,
        include_payload=None,
    ):
        if not self.token:
            self.refresh_csrf()
        import json as _json

        data = {}
        if include_payload is not None:
            data["payload"] = _json.dumps(include_payload)
        if form:
            data.update(form)
        data[field] = (BytesIO(content), filename)
        response = self.client.post(
            path,
            data=data,
            headers={"X-CSRF-Token": self.token},
            content_type="multipart/form-data",
        )
        refreshed = _refreshed_csrf(response.get_json(silent=True))
        if refreshed:
            self.token = refreshed
        return response

    def post_multipart(self, path, payload):
        if not self.token:
            self.refresh_csrf()
        import json as _json

        data = {
            "payload": _json.dumps(payload),
            "photo": (BytesIO(JPEG_BYTES), "parcel.jpg"),
        }
        response = self.client.post(
            path,
            data=data,
            headers={"X-CSRF-Token": self.token},
            content_type="multipart/form-data",
        )
        refreshed = _refreshed_csrf(response.get_json(silent=True))
        if refreshed:
            self.token = refreshed
        return response

    def post_multipart_without_photo(self, path, payload):
        if not self.token:
            self.refresh_csrf()
        import json as _json

        response = self.client.post(
            path,
            data={"payload": _json.dumps(payload)},
            headers={"X-CSRF-Token": self.token},
            content_type="multipart/form-data",
        )
        refreshed = _refreshed_csrf(response.get_json(silent=True))
        if refreshed:
            self.token = refreshed
        return response

    def login(self, email: str, password: str = "ReTurn#2026"):
        response = self.post("/api/v1/auth/login", {"email": email, "password": password})
        assert response.status_code == 200, response.get_json()
        self.refresh_csrf()
        return response

    def logout(self):
        response = self.post("/api/v1/auth/logout")
        self.token = None
        return response


@pytest.fixture()
def session(client):
    return Session(client)


@pytest.fixture()
def reference_data(app):
    """Insert permissions, rejection codes and vehicle capacity profiles."""
    with app.app_context():
        from app.services.reference import ensure_reference_data

        created = ensure_reference_data()
        _db.session.commit()
        return created


def make_user(
    email,
    *,
    role="consumer",
    status="active",
    password="ReTurn#2026",
    full_name=None,
    phone="9000000000",
):
    from app.models import User
    from app.security import hash_password

    user = User(
        email=email,
        full_name=full_name or email.split("@")[0].replace(".", " ").title(),
        phone=phone,
        password_hash=hash_password(password),
        role=role,
        status=status,
    )
    _db.session.add(user)
    _db.session.commit()
    return user
