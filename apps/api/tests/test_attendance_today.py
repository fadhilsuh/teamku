from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import Attendance, reset_demo_store, store

client = TestClient(app)


def employee_headers() -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee@movon.test", "password": "Demo123!"},
    )
    return {"X-Demo-User": response.json()["access_token"]}


def test_today_returns_active_session_instead_of_offering_second_check_in() -> None:
    reset_demo_store()
    record = Attendance(
        id="attendance-active-test",
        employee_id="e-employee",
        checked_in_at=datetime.now(UTC),
        latitude=-6.2,
        longitude=106.8166,
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
        latitude=-6.2,
        longitude=106.8166,
        accuracy_meters=12,
        agenda=[{"title": "Agenda kemarin"}],
    )
    store.attendance[record.id] = record

    response = client.post(
        "/api/v1/attendance/check-in",
        headers=employee_headers() | {"Idempotency-Key": "prior-day-test"},
        json={
            "latitude": -6.2,
            "longitude": 106.8166,
            "accuracy_meters": 10,
            "selfie_captured": True,
            "agenda": [{"title": "Agenda baru"}],
        },
    )

    assert response.status_code == 409
    assert "sesi kehadiran" in response.json()["detail"]
