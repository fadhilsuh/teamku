from datetime import UTC, datetime, timedelta

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


def enable_immediate_reverify(*, count: int = 1) -> None:
    store.office.reverify_enabled = True
    store.office.reverify_count_per_day = count
    store.office.reverify_window_start_minutes = 0
    store.office.reverify_window_end_minutes = 1


def check_in(email: str, key: str, **overrides: object):
    payload = {
        "latitude": OFFICE_LATITUDE,
        "longitude": OFFICE_LONGITUDE,
        "accuracy_meters": 10,
        "selfie_captured": True,
        "location_share_approved": True,
        "agenda": [{"title": "Reverify flow"}],
    }
    payload.update(overrides)
    return client.post(
        "/api/v1/attendance/check-in",
        headers=login(email) | {"Idempotency-Key": key},
        json=payload,
    )


def test_office_worker_gets_scheduled_reverify_when_enabled() -> None:
    reset_demo_store()
    enable_immediate_reverify(count=2)

    response = check_in("fresh@movon.test", "reverify-on")
    assert response.status_code == 200

    today = client.get("/api/v1/attendance/today", headers=login("fresh@movon.test")).json()
    assert today["pending_reverification"] is not None
    slots = [
        item
        for item in store.location_events.values()
        if item.employee_id == "e-fresh" and item.kind == "reverify"
    ]
    assert len(slots) == 2


def test_remote_worker_never_gets_pending_reverify() -> None:
    reset_demo_store()
    enable_immediate_reverify()
    store.employees["e-fresh"].is_remote = True

    response = check_in("fresh@movon.test", "remote-skip", latitude=-6.3)
    assert response.status_code == 200

    today = client.get("/api/v1/attendance/today", headers=login("fresh@movon.test")).json()
    assert today["pending_reverification"] is None
    assert today["is_remote"] is True


def test_outside_geofence_reverify_is_recorded_with_anomaly() -> None:
    reset_demo_store()
    enable_immediate_reverify()
    assert check_in("fresh@movon.test", "outside-reverify").status_code == 200

    submitted = client.post(
        "/api/v1/attendance/reverify",
        headers=login("fresh@movon.test"),
        json={
            "latitude": -6.3,
            "longitude": 106.8166,
            "accuracy_meters": 12,
            "selfie_captured": True,
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["anomaly"] == "outside_geofence"
    assert submitted.json()["inside_geofence"] is False

    today = client.get("/api/v1/attendance/today", headers=login("fresh@movon.test")).json()
    assert today["pending_reverification"] is None


def test_successful_reverify_clears_pending_and_writes_event() -> None:
    reset_demo_store()
    enable_immediate_reverify()
    assert check_in("fresh@movon.test", "ok-reverify").status_code == 200

    submitted = client.post(
        "/api/v1/attendance/reverify",
        headers=login("fresh@movon.test"),
        json={
            "latitude": OFFICE_LATITUDE,
            "longitude": OFFICE_LONGITUDE,
            "accuracy_meters": 10,
            "selfie_captured": True,
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["anomaly"] is None
    assert submitted.json()["kind"] == "reverify"

    today = client.get("/api/v1/attendance/today", headers=login("fresh@movon.test")).json()
    assert today["pending_reverification"] is None


def test_missed_deadline_creates_missed_reverify_anomaly() -> None:
    reset_demo_store()
    enable_immediate_reverify()
    assert check_in("fresh@movon.test", "missed-reverify").status_code == 200
    slot = next(
        item
        for item in store.location_events.values()
        if item.employee_id == "e-fresh" and item.kind == "reverify"
    )
    slot.due_at = datetime.now(UTC) - timedelta(minutes=20)
    slot.at = slot.due_at

    today = client.get("/api/v1/attendance/today", headers=login("fresh@movon.test")).json()
    assert today["pending_reverification"] is None
    refreshed = store.location_events[slot.id]
    assert refreshed.anomaly == "missed_reverify"
