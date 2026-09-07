from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import (
    OFFICE_LATITUDE,
    OFFICE_LONGITUDE,
    OFFICE_RADIUS_METERS,
    reset_demo_store,
    store,
)

client = TestClient(app)


def hr_headers() -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "hr@movon.test", "password": "Demo123!"},
    )
    return {"X-Demo-User": response.json()["access_token"]}


def employee_headers() -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "fresh@movon.test", "password": "Demo123!"},
    )
    return {"X-Demo-User": response.json()["access_token"]}


def test_any_user_can_read_office_settings() -> None:
    reset_demo_store()

    response = client.get("/api/v1/settings/office", headers=employee_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Jakarta HQ"
    assert body["latitude"] == OFFICE_LATITUDE
    assert body["longitude"] == OFFICE_LONGITUDE
    assert body["radius_meters"] == OFFICE_RADIUS_METERS
    assert body["reverify_enabled"] is False
    assert body["alerts_enabled"] is False


def test_employee_cannot_update_office_settings() -> None:
    reset_demo_store()

    response = client.put(
        "/api/v1/settings/office",
        headers=employee_headers(),
        json={
            "name": "Rumah",
            "latitude": -6.3,
            "longitude": 106.8,
            "radius_meters": 1000,
        },
    )

    assert response.status_code == 403
    assert store.office.name == "Jakarta HQ"


def test_hr_admin_can_update_office_settings() -> None:
    reset_demo_store()

    response = client.put(
        "/api/v1/settings/office",
        headers=hr_headers(),
        json={
            "name": "Bandung Hub",
            "latitude": -6.9175,
            "longitude": 107.6191,
            "radius_meters": 200,
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Bandung Hub"
    assert store.office.latitude == -6.9175
    assert store.office.radius_meters == 200


def test_check_in_uses_configured_office_location() -> None:
    reset_demo_store()
    store.office.name = "Bandung Hub"
    store.office.latitude = -6.9175
    store.office.longitude = 107.6191
    store.office.radius_meters = 200

    rejected = client.post(
        "/api/v1/attendance/check-in",
        headers=employee_headers() | {"Idempotency-Key": "old-hq"},
        json={
            "latitude": OFFICE_LATITUDE,
            "longitude": OFFICE_LONGITUDE,
            "accuracy_meters": 10,
            "selfie_captured": True,
            "location_share_approved": True,
            "agenda": [{"title": "Masih di Jakarta"}],
        },
    )
    assert rejected.status_code == 403
    assert "bandung hub" in rejected.json()["detail"].lower()

    accepted = client.post(
        "/api/v1/attendance/check-in",
        headers=employee_headers() | {"Idempotency-Key": "new-hub"},
        json={
            "latitude": -6.9175,
            "longitude": 107.6191,
            "accuracy_meters": 10,
            "selfie_captured": True,
            "location_share_approved": True,
            "agenda": [{"title": "Kerja di Bandung"}],
        },
    )
    assert accepted.status_code == 200
    assert accepted.json()["distance_meters"] == 0


def test_hr_admin_can_parse_google_maps_share_link() -> None:
    reset_demo_store()

    response = client.post(
        "/api/v1/settings/office/from-maps-url",
        headers=hr_headers(),
        json={"url": "https://www.google.com/maps/place/Monas/@-6.175392,106.827153,17z"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["latitude"] == -6.175392
    assert body["longitude"] == 106.827153
    assert "google.com/maps" in body["maps_url"]


def test_hr_admin_can_parse_raw_coordinates() -> None:
    reset_demo_store()

    response = client.post(
        "/api/v1/settings/office/from-maps-url",
        headers=hr_headers(),
        json={"url": "-6.200000, 106.816600"},
    )

    assert response.status_code == 200
    assert response.json()["latitude"] == -6.2
    assert response.json()["longitude"] == 106.8166


def test_employee_cannot_parse_maps_url() -> None:
    reset_demo_store()

    response = client.post(
        "/api/v1/settings/office/from-maps-url",
        headers=employee_headers(),
        json={"url": "https://www.google.com/maps?q=-6.2,106.8166"},
    )

    assert response.status_code == 403
