from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import (
    OFFICE_LATITUDE,
    OFFICE_LONGITUDE,
    OFFICE_RADIUS_METERS,
    Attendance,
    reset_demo_store,
    store,
)

client = TestClient(app)


def employee_headers() -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@movon.test", "password": "Demo123!"},
    )
    return {"X-Demo-User": response.json()["access_token"]}


def fresh_employee_headers() -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "fresh@movon.test", "password": "Demo123!"},
    )
    return {"X-Demo-User": response.json()["access_token"]}


def check_in_payload(**overrides: object) -> dict:
    payload = {
        "latitude": OFFICE_LATITUDE,
        "longitude": OFFICE_LONGITUDE,
        "accuracy_meters": 10,
        "selfie_captured": True,
        "location_share_approved": True,
        "agenda": [{"title": "Kerja di kantor"}],
    }
    payload.update(overrides)
    return payload


def test_fresh_demo_account_starts_without_a_check_in() -> None:
    reset_demo_store()

    response = client.get("/api/v1/attendance/today", headers=fresh_employee_headers())

    assert response.status_code == 200
    assert response.json() == {
        "state": "not_checked_in",
        "session": None,
        "pending_reverification": None,
        "is_remote": False,
    }


def test_check_in_requires_location_sharing_approval() -> None:
    reset_demo_store()

    response = client.post(
        "/api/v1/attendance/check-in",
        headers=fresh_employee_headers() | {"Idempotency-Key": "location-consent-test"},
        json=check_in_payload(location_share_approved=False, agenda=[{"title": "Konfirmasi lokasi"}]),
    )

    assert response.status_code == 422
    assert "persetujuan" in response.json()["detail"].lower()


def test_check_in_succeeds_inside_office_geofence() -> None:
    reset_demo_store()

    response = client.post(
        "/api/v1/attendance/check-in",
        headers=fresh_employee_headers() | {"Idempotency-Key": "inside-geofence"},
        json=check_in_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["anomaly"] is None
    assert body["distance_meters"] == 0
    assert body["allowed_radius_meters"] == OFFICE_RADIUS_METERS + 10


def test_check_in_rejects_location_far_from_office() -> None:
    reset_demo_store()
    # Roughly ~11 km south of Jakarta HQ — typical "check-in from home" attempt.
    response = client.post(
        "/api/v1/attendance/check-in",
        headers=fresh_employee_headers() | {"Idempotency-Key": "outside-geofence"},
        json=check_in_payload(latitude=-6.3, longitude=106.8166),
    )

    assert response.status_code == 403
    detail = response.json()["detail"].lower()
    assert "ditolak" in detail
    assert "radius" in detail
    assert str(OFFICE_RADIUS_METERS) in detail


def test_check_in_rejects_inflated_accuracy_used_to_bypass_geofence() -> None:
    reset_demo_store()
    # ~550 m away: would pass if accuracy_meters were added uncapped (300 + 500).
    response = client.post(
        "/api/v1/attendance/check-in",
        headers=fresh_employee_headers() | {"Idempotency-Key": "accuracy-bypass"},
        json=check_in_payload(latitude=-6.205, longitude=106.8166, accuracy_meters=500),
    )

    assert response.status_code == 403
    assert "ditolak" in response.json()["detail"].lower()


def test_today_returns_active_session_instead_of_offering_second_check_in() -> None:
    reset_demo_store()
    record = Attendance(
        id="attendance-active-test",
        employee_id="e-employee",
        checked_in_at=datetime.now(UTC),
        latitude=OFFICE_LATITUDE,
        longitude=OFFICE_LONGITUDE,
        accuracy_meters=12,
        agenda=[{"title": "Test agenda"}],
    )
    store.attendance[record.id] = record

    response = client.get("/api/v1/attendance/today", headers=employee_headers())

    assert response.status_code == 200
    assert response.json()["state"] == "checked_in"
    assert response.json()["session"]["id"] == record.id
    store.attendance.pop(record.id, None)


def test_check_in_rejects_an_open_session_from_a_prior_day() -> None:
    reset_demo_store()
    record = Attendance(
        id="attendance-prior-day-open",
        employee_id="e-employee",
        checked_in_at=datetime.now(UTC) - timedelta(days=1),
        latitude=OFFICE_LATITUDE,
        longitude=OFFICE_LONGITUDE,
        accuracy_meters=12,
        agenda=[{"title": "Agenda kemarin"}],
    )
    store.attendance[record.id] = record

    response = client.post(
        "/api/v1/attendance/check-in",
        headers=employee_headers() | {"Idempotency-Key": "prior-day-test"},
        json=check_in_payload(agenda=[{"title": "Agenda baru"}]),
    )

    assert response.status_code == 409
    assert "sesi kehadiran" in response.json()["detail"]
