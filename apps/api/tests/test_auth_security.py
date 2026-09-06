from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import (
    DEMO_PASSWORD,
    LOGIN_MAX_ATTEMPTS,
    reset_demo_store,
    store,
)

client = TestClient(app)


def setup_function() -> None:
    reset_demo_store()


def login(email: str, password: str = DEMO_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def token_for(email: str) -> str:
    return login(email).json()["access_token"]


def test_password_is_verified_against_hash_and_never_leaked() -> None:
    wrong = login("hr@movon.test", "totally-wrong-1")
    assert wrong.status_code == 401

    ok = login("hr@movon.test")
    assert ok.status_code == 200
    assert "password_hash" not in ok.json()["user"]

    token = ok.json()["access_token"]
    headers = {"X-Demo-User": token}
    assert "password_hash" not in client.get("/api/v1/me", headers=headers).json()["user"]

    listed = client.get("/api/v1/employees", headers=headers).json()["items"]
    assert all("password_hash" not in item for item in listed)


def test_login_is_rate_limited_after_repeated_failures() -> None:
    for _ in range(LOGIN_MAX_ATTEMPTS):
        assert login("hr@movon.test", "wrong-pass-9").status_code == 401
    # Threshold reached: even a valid password is temporarily blocked.
    locked = login("hr@movon.test")
    assert locked.status_code == 429


def test_expired_session_is_rejected() -> None:
    token = token_for("employee@movon.test")
    assert client.get("/api/v1/me", headers={"X-Demo-User": token}).status_code == 200

    store.sessions[token].expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert client.get("/api/v1/me", headers={"X-Demo-User": token}).status_code == 401
    # Expired token is cleaned up on rejection.
    assert token not in store.sessions


def test_change_password_revokes_other_sessions_and_rotates_credentials() -> None:
    keep = token_for("employee@movon.test")
    other = token_for("employee@movon.test")

    changed = client.post(
        "/api/v1/auth/change-password",
        headers={"X-Demo-User": keep},
        json={"current_password": DEMO_PASSWORD, "new_password": "BrandNew123"},
    )
    assert changed.status_code == 200

    # Current session survives; other sessions are revoked.
    assert client.get("/api/v1/me", headers={"X-Demo-User": keep}).status_code == 200
    assert client.get("/api/v1/me", headers={"X-Demo-User": other}).status_code == 401

    # Old credentials no longer work; new ones do.
    assert login("employee@movon.test", DEMO_PASSWORD).status_code == 401
    assert login("employee@movon.test", "BrandNew123").status_code == 200


def test_change_password_enforces_policy_and_current_password() -> None:
    token = token_for("employee@movon.test")

    wrong_current = client.post(
        "/api/v1/auth/change-password",
        headers={"X-Demo-User": token},
        json={"current_password": "not-the-one", "new_password": "BrandNew123"},
    )
    assert wrong_current.status_code == 401

    weak = client.post(
        "/api/v1/auth/change-password",
        headers={"X-Demo-User": token},
        json={"current_password": DEMO_PASSWORD, "new_password": "alllowercase"},
    )
    assert weak.status_code == 422


def test_created_employee_gets_temporary_password_and_can_sign_in() -> None:
    hr = {"X-Demo-User": token_for("hr@movon.test")}
    created = client.post(
        "/api/v1/employees",
        headers=hr,
        json={
            "name": "Bimo Aji",
            "email": "bimo.aji@movon.test",
            "department": "Product",
            "role": "employee",
            "salary": 9_000_000,
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert "password_hash" not in body
    temporary_password = body["temporary_password"]

    assert login("bimo.aji@movon.test", temporary_password).status_code == 200


def test_creating_employee_with_weak_password_is_rejected() -> None:
    hr = {"X-Demo-User": token_for("hr@movon.test")}
    response = client.post(
        "/api/v1/employees",
        headers=hr,
        json={
            "name": "Weak Pass",
            "email": "weak.pass@movon.test",
            "department": "Product",
            "role": "employee",
            "salary": 9_000_000,
            "password": "nodigitshere",
        },
    )
    assert response.status_code == 422
