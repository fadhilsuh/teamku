from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import (
    OFFICE_LATITUDE,
    OFFICE_LONGITUDE,
    reset_demo_store,
    store,
)

client = TestClient(app)


def login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo123!"})
    return {"X-Demo-User": response.json()["access_token"]}


def office_payload(**overrides: object) -> dict:
    payload = {
        "name": "Jakarta HQ",
        "latitude": OFFICE_LATITUDE,
        "longitude": OFFICE_LONGITUDE,
        "radius_meters": 300,
        "reverify_enabled": True,
        "reverify_count_per_day": 2,
        "reverify_window_start_minutes": 0,
        "reverify_window_end_minutes": 120,
    }
    payload.update(overrides)
    return payload


def test_hr_can_enable_reverify_policy_from_settings() -> None:
    reset_demo_store()

    response = client.put(
        "/api/v1/settings/office",
        headers=login("hr@movon.test"),
        json=office_payload(),
    )

    assert response.status_code == 200
    assert response.json()["reverify_enabled"] is True
    assert response.json()["reverify_count_per_day"] == 2
    fetched = client.get("/api/v1/settings/office", headers=login("hr@movon.test"))
    assert fetched.json()["reverify_count_per_day"] == 2


def test_invalid_reverify_count_is_rejected() -> None:
    reset_demo_store()

    response = client.put(
        "/api/v1/settings/office",
        headers=login("hr@movon.test"),
        json=office_payload(reverify_count_per_day=4),
    )

    assert response.status_code == 422
    assert store.office.reverify_enabled is False


def test_manager_cannot_update_attendance_policy() -> None:
    reset_demo_store()

    response = client.put(
        "/api/v1/settings/office",
        headers=login("manager@movon.test"),
        json=office_payload(),
    )

    assert response.status_code == 403
    assert store.office.reverify_enabled is False


def test_disabled_policy_does_not_schedule_pending_reverify() -> None:
    reset_demo_store()
    store.office.reverify_enabled = False

    checked_in = client.post(
        "/api/v1/attendance/check-in",
        headers=login("fresh@movon.test") | {"Idempotency-Key": "policy-off"},
        json={
            "latitude": OFFICE_LATITUDE,
            "longitude": OFFICE_LONGITUDE,
            "accuracy_meters": 10,
            "selfie_captured": True,
            "location_share_approved": True,
            "agenda": [{"title": "Tanpa reverify"}],
        },
    )
    assert checked_in.status_code == 200

    today = client.get("/api/v1/attendance/today", headers=login("fresh@movon.test"))
    assert today.status_code == 200
    assert today.json()["pending_reverification"] is None
