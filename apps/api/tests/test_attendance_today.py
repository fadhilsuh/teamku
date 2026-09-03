from datetime import UTC, datetime

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import Attendance, store

client = TestClient(app)


def test_today_returns_active_session_instead_of_offering_second_check_in() -> None:
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

    response = client.get("/api/v1/attendance/today", headers={"X-Demo-User": "e-employee"})

    assert response.status_code == 200
    assert response.json()["state"] == "checked_in"
    assert response.json()["session"]["id"] == record.id
    store.attendance.pop(record.id, None)
