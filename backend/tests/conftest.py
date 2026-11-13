"""Pytest fixtures for the ReTurn API test suite (PostgreSQL only)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://return:return_dev_pw@127.0.0.1:5433/return_test",
)

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db as _db  # noqa: E402
from app.services.seed import seed_demo_data  # noqa: E402


@pytest.fixture(scope="session")
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.drop_all()
        _db.create_all()
    yield application
    with application.app_context():
        _db.session.remove()


@pytest.fixture()
def db(app):
    with app.app_context():
        seed_demo_data(reset=True)
        yield _db
        _db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


class Session:
    """Small helper that keeps cookies and the CSRF token in sync."""

    def __init__(self, client):
        self.client = client
        response = client.get("/api/v1/auth/csrf")
        self.token = response.get_json()["data"]["csrf_token"]

    def _headers(self):
        return {"X-CSRF-Token": self.token, "Content-Type": "application/json"}

    def get(self, path):
        return self.client.get(path)

    def post(self, path, json=None):
        response = self.client.post(path, json=json or {}, headers=self._headers())
        if "data" in (response.get_json(silent=True) or {}) and response.status_code < 400:
            new_token = (response.get_json() or {}).get("data", {}).get("csrf_token")
            if new_token:
                self.token = new_token
        return response

    def patch(self, path, json=None):
        return self.client.patch(path, json=json or {}, headers=self._headers())

    def login(self, email: str, password: str = "ReTurn#2026"):
        response = self.post("/api/v1/auth/login", {"email": email, "password": password})
        assert response.status_code == 200, response.get_json()
        # Login rotates the server-side session and its CSRF token.
        refresh = self.client.get("/api/v1/auth/csrf")
        self.token = refresh.get_json()["data"]["csrf_token"]
        return response


@pytest.fixture()
def session(client):
    return Session(client)


@pytest.fixture()
def admin(app):
    helper = Session(app.test_client())
    helper.login("admin@return.demo")
    return helper


@pytest.fixture()
def partner(app):
    helper = Session(app.test_client())
    helper.login("partner@return.demo")
    return helper


@pytest.fixture()
def rahul(app):
    helper = Session(app.test_client())
    helper.login("rahul@return.demo")
    return helper


@pytest.fixture()
def customer_auth(app):
    return Session(app.test_client())


def ids_by_email(app):
    from app.models import User

    return {user.email: user.id for user in User.query.all()}


def request_id_for_code(app, code: str) -> int:
    return int(code.split("-")[-1]) - 1000
