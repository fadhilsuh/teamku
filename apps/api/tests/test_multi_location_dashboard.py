from datetime import UTC, datetime

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import LeaveRequest, reset_demo_store, store

client = TestClient(app)


def login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo123!"})
    return {"X-Demo-User": response.json()["access_token"]}


def test_hr_can_add_location_and_assign_employee_to_its_geofence() -> None:
    reset_demo_store()
    hr = login("hr@movon.test")
    created = client.post("/api/v1/settings/locations", headers=hr, json={
        "name": "Bandung Site", "latitude": -6.9175, "longitude": 107.6191, "radius_meters": 250,
    })
    assert created.status_code == 200
    location_id = created.json()["id"]
    assigned = client.patch("/api/v1/employees/e-fresh", headers=hr, json={"work_location_id": location_id})
    assert assigned.status_code == 200
    assert assigned.json()["work_location"]["name"] == "Bandung Site"

    checked_in = client.post("/api/v1/attendance/check-in", headers=login("fresh@movon.test") | {"Idempotency-Key": "bandung"}, json={
        "latitude": -6.9175, "longitude": 107.6191, "accuracy_meters": 10,
        "selfie_captured": True, "location_share_approved": True, "agenda": [{"title": "Site visit"}],
    })
    assert checked_in.status_code == 200
    assert checked_in.json()["distance_meters"] == 0


def test_field_employee_checkout_records_location_and_dashboard_summarizes_today() -> None:
    reset_demo_store()
    store.employees["e-fresh"].is_remote = True
    employee = login("fresh@movon.test")
    client.post("/api/v1/attendance/check-in", headers=employee | {"Idempotency-Key": "field"}, json={
        "latitude": -6.9, "longitude": 107.6, "accuracy_meters": 12,
        "selfie_captured": True, "location_share_approved": True, "agenda": [{"title": "Visit customer"}],
    })
    checked_out = client.post("/api/v1/attendance/check-out", headers=employee, json={
        "summary": "Customer visit complete", "latitude": -6.91, "longitude": 107.61, "accuracy_meters": 15,
    })
    assert checked_out.status_code == 200
    events = [event for event in store.location_events.values() if event.employee_id == "e-fresh"]
    assert [event.kind for event in events] == ["check_in", "check_out"]
    assert events[-1].lat == -6.91

    today = datetime.now(UTC).astimezone().date()
    store.requests["leave-today"] = LeaveRequest("leave-today", "e-018", today, today, "Cuti", status="approved")
    dashboard = client.get("/api/v1/dashboard", headers=login("hr@movon.test")).json()
    assert {"headcount", "present", "absent", "on_leave", "late", "attendance_rate"} <= dashboard.keys()
    assert dashboard["on_leave"] == 1
