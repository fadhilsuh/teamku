from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import (
    OFFICE_LATITUDE,
    OFFICE_LONGITUDE,
    LocationEvent,
    reset_demo_store,
    store,
)

client = TestClient(app)


def login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo123!"})
    return {"X-Demo-User": response.json()["access_token"]}


def test_manager_cannot_read_other_department_history() -> None:
    reset_demo_store()

    response = client.get(
        "/api/v1/employees/e-005/location-history",
        headers=login("manager@movon.test"),
    )

    assert response.status_code == 404


def test_hr_can_list_location_events_for_any_tenant_employee() -> None:
    reset_demo_store()

    response = client.get(
        "/api/v1/employees/e-employee/location-history",
        headers=login("hr@movon.test"),
    )

    assert response.status_code == 200
    assert response.json()["employee_id"] == "e-employee"


def test_employee_cannot_fetch_another_employee_location_history() -> None:
    reset_demo_store()

    response = client.get(
        "/api/v1/employees/e-004/location-history",
        headers=login("employee@movon.test"),
    )

    assert response.status_code == 403


def test_detail_history_is_chronological_check_in_and_reverify() -> None:
    reset_demo_store()
    earlier = datetime.now(UTC).replace(microsecond=0)
    store.location_events["loc-a"] = LocationEvent(
        id="loc-a",
        employee_id="e-employee",
        attendance_id="attendance-a",
        kind="reverify",
        at=earlier,
        lat=OFFICE_LATITUDE,
        lng=OFFICE_LONGITUDE,
        accuracy=10,
        distance_meters=0,
        inside_geofence=True,
    )
    store.location_events["loc-b"] = LocationEvent(
        id="loc-b",
        employee_id="e-employee",
        attendance_id="attendance-a",
        kind="check_in",
        at=earlier - timedelta(hours=1),
        lat=OFFICE_LATITUDE,
        lng=OFFICE_LONGITUDE,
        accuracy=12,
        distance_meters=0,
        inside_geofence=True,
    )

    response = client.get(
        "/api/v1/employees/e-employee/location-history",
        headers=login("manager@movon.test"),
    )

    assert response.status_code == 200
    kinds = [item["kind"] for item in response.json()["items"]]
    assert kinds == ["check_in", "reverify"]
    assert response.json()["items"][0]["at"] <= response.json()["items"][-1]["at"]

    profile = client.get("/api/v1/employees/e-employee", headers=login("manager@movon.test"))
    assert profile.status_code == 200
    assert profile.json()["id"] == "e-employee"
