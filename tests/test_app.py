from datetime import date
import hashlib

import pytest

from app import create_app
from security.crypto import hash_password, verify_legacy_password, verify_password
from security.session import token_digest


class FakeCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.current = None
        self.rowcount = 1

    def execute(self, _query, _params=None):
        self.current = next(self.rows, None)

    def fetchone(self):
        return self.current

    def fetchall(self):
        return self.current or []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


@pytest.fixture
def client():
    application = create_app()
    application.config.update(TESTING=True)
    return application.test_client()


def test_registration_assigns_default_user_role(client, monkeypatch):
    connection = FakeConnection([None, {"id": 7}, {"id": 2}, None])
    monkeypatch.setattr("routes.auth.get_connection", lambda: connection)

    response = client.post(
        "/api/register",
        json={"username": "demo_user", "password": "local-test-only"},
    )

    assert response.status_code == 201
    assert connection.committed


def test_login_and_invalid_login(client, monkeypatch):
    encoded = hash_password("correct-local-password")
    connections = iter(
        [
            FakeConnection([{"id": 3, "password_hash": encoded, "salt": None}]),
            FakeConnection([{"id": 3, "password_hash": encoded, "salt": None}]),
        ]
    )
    monkeypatch.setattr("routes.auth.get_connection", lambda: next(connections))
    monkeypatch.setattr("routes.auth.create_session", lambda *_args: "opaque-session")

    ok = client.post(
        "/api/login",
        json={"username": "demo_user", "password": "correct-local-password"},
    )
    rejected = client.post(
        "/api/login",
        json={"username": "demo_user", "password": "wrong-local-password"},
    )

    assert ok.status_code == 200
    assert "session_token=" in ok.headers["Set-Cookie"]
    assert rejected.status_code == 401


def test_password_and_session_values_are_one_way_digests():
    encoded = hash_password("local-test-only")
    assert encoded != "local-test-only"
    assert verify_password("local-test-only", encoded)
    assert not verify_password("different", encoded)
    assert token_digest("opaque-session") != "opaque-session"


def test_legacy_password_is_verified_and_rehashed_on_login(client, monkeypatch):
    salt = "legacy-test-salt"
    legacy_hash = hashlib.sha256((salt + "correct-local-password").encode("utf-8")).hexdigest()
    lookup = FakeConnection([{"id": 3, "password_hash": legacy_hash, "salt": salt}])
    migration = FakeConnection([None])
    connections = iter([lookup, migration])
    monkeypatch.setattr("routes.auth.get_connection", lambda: next(connections))
    monkeypatch.setattr("routes.auth.create_session", lambda *_args: "opaque-session")

    response = client.post(
        "/api/login",
        json={"username": "demo_user", "password": "correct-local-password"},
    )

    assert response.status_code == 200
    assert migration.committed
    assert verify_legacy_password("correct-local-password", salt, legacy_hash)


def test_role_access_is_denied_without_required_role(client, monkeypatch):
    monkeypatch.setattr(
        "security.auth_utils.get_current_user",
        lambda: {"id": 9, "username": "demo_user"},
    )
    monkeypatch.setattr("security.auth_utils.get_user_roles", lambda _user_id: {"USER"})

    response = client.get("/bookings")

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("conflict", "expected_status"),
    [(None, 201), ({"id": 44}, 409)],
)
def test_booking_creation_and_conflict(client, monkeypatch, conflict, expected_status):
    connection = FakeConnection(
        [
            {"id": 5, "status": "AVAILABLE"},
            conflict,
            {"id": 12} if conflict is None else None,
        ]
    )
    monkeypatch.setattr("routes.bookings.get_connection", lambda: connection)
    monkeypatch.setattr(
        "security.auth_utils.get_current_user",
        lambda: {"id": 9, "username": "demo_user"},
    )
    monkeypatch.setattr("security.auth_utils.get_user_roles", lambda _user_id: {"USER"})

    response = client.post(
        "/bookings",
        json={
            "car_id": 5,
            "start_date": date(2030, 1, 10).isoformat(),
            "end_date": date(2030, 1, 12).isoformat(),
        },
    )

    assert response.status_code == expected_status
    assert connection.committed is (conflict is None)
