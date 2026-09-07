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


def hr_headers() -> dict[str, str]:
    return login("hr@movon.test")


def fresh_headers() -> dict[str, str]:
    return login("fresh@movon.test")


def check_in_payload(**overrides: object) -> dict:
    payload = {
        "latitude": OFFICE_LATITUDE,
        "longitude": OFFICE_LONGITUDE,
        "accuracy_meters": 10,
        "selfie_captured": True,
        "location_share_approved": True,
        "agenda": [{"title": "Kerja remote"}],
    }
    payload.update(overrides)
    return payload


def test_remote_employee_can_check_in_far_from_office() -> None:
    reset_demo_store()
    store.employees["e-fresh"].is_remote = True

    response = client.post(
        "/api/v1/attendance/check-in",
        headers=fresh_headers() | {"Idempotency-Key": "remote-far"},
        json=check_in_payload(latitude=-6.3, longitude=106.8166),
    )

    assert response.status_code == 200
    assert response.json()["id"]


def test_office_employee_far_from_office_is_still_rejected() -> None:
    reset_demo_store()

    response = client.post(
        "/api/v1/attendance/check-in",
        headers=fresh_headers() | {"Idempotency-Key": "office-far"},
        json=check_in_payload(latitude=-6.3, longitude=106.8166),
    )

    assert response.status_code == 403
    assert "ditolak" in response.json()["detail"].lower()


def test_create_and_invite_remote_employee_persists_flag() -> None:
    reset_demo_store()
    created = client.post(
        "/api/v1/employees",
        headers=hr_headers(),
        json={
            "name": "Remote Staff",
            "email": "remote.staff@movon.test",
            "department": "Engineering",
            "role": "employee",
            "salary": 8_000_000,
            "is_remote": True,
        },
    )
    assert created.status_code == 200
    assert created.json()["is_remote"] is True

    listed = client.get("/api/v1/employees", headers=hr_headers()).json()["items"]
    remote = next(item for item in listed if item["email"] == "remote.staff@movon.test")
    assert remote["is_remote"] is True

    invited = client.post(
        "/api/v1/invites",
        headers=hr_headers(),
        json={
            "name": "Remote Invite",
            "email": "remote.invite@movon.test",
            "department": "Engineering",
            "role": "employee",
            "salary": 8_000_000,
            "is_remote": True,
        },
    )
    assert invited.status_code == 200
    invitation = next(item for item in store.invitations.values() if item.email == "remote.invite@movon.test")
    assert invitation.is_remote is True
