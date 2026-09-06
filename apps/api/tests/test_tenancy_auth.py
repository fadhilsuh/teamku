from fastapi.testclient import TestClient

from movon_hr.core.mailer import last_email_to, outbox
from movon_hr.core.settings import settings
from movon_hr.core.tenancy import iter_stores
from movon_hr.main import app
from movon_hr.modules.api import DEMO_PASSWORD, reset_demo_store

client = TestClient(app)


def setup_function() -> None:
    reset_demo_store()


def signup(company: str, email: str, slug: str | None = None):
    payload = {
        "company_name": company,
        "admin_name": "Admin Satu",
        "email": email,
        "password": "Company123",
    }
    if slug:
        payload["slug"] = slug
    return client.post("/api/v1/auth/signup", json=payload)


def bearer(response) -> dict[str, str]:
    return {"X-Demo-User": response.json()["access_token"]}


def test_signup_creates_isolated_tenant_and_sets_cookie() -> None:
    response = signup("PT Merdeka Digital", "admin@merdeka.test", "merdeka")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "admin@merdeka.test"
    assert body["user"]["role"] == "hr_admin"
    assert body["tenant"]["slug"] == "merdeka"
    assert settings.session_cookie_name in response.cookies
    me = client.get("/api/v1/me", headers=bearer(response))
    assert me.json()["tenant"]["slug"] == "merdeka"
    assert len(iter_stores()) == 2  # demo + new company


def test_tenants_cannot_see_each_others_employees() -> None:
    first = signup("PT Satu", "hr@satu.test", "satu")
    assert first.status_code == 200
    created = client.post(
        "/api/v1/employees",
        headers=bearer(first),
        json={
            "name": "Karyawan Satu",
            "email": "orang@satu.test",
            "department": "Engineering",
            "role": "employee",
            "salary": 8_000_000,
        },
    )
    assert created.status_code == 200
    satu_emails = {
        item["email"]
        for item in client.get("/api/v1/employees", headers=bearer(first)).json()["items"]
    }
    assert "orang@satu.test" in satu_emails
    assert "hr@movon.test" not in satu_emails

    second = signup("PT Dua", "hr@dua.test", "dua")
    assert second.status_code == 200
    dua_emails = {
        item["email"]
        for item in client.get("/api/v1/employees", headers=bearer(second)).json()["items"]
    }
    assert dua_emails == {"hr@dua.test"}


def test_cookie_login_works_without_demo_header() -> None:
    fresh = TestClient(app)
    login = fresh.post(
        "/api/v1/auth/login",
        json={"email": "employee@movon.test", "password": DEMO_PASSWORD},
    )
    assert login.status_code == 200
    assert settings.session_cookie_name in login.cookies
    me = fresh.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "employee@movon.test"
    assert me.json()["tenant"]["id"] == "pt-movon-solusi-kreatif"


def test_invite_and_accept_creates_employee_in_same_tenant() -> None:
    created = signup("PT Undang", "hr@undang.test", "undang")
    assert created.status_code == 200
    invited = client.post(
        "/api/v1/invites",
        headers=bearer(created),
        json={
            "name": "Sinta Baru",
            "email": "sinta@undang.test",
            "department": "Product",
            "role": "employee",
            "title": "Designer",
            "salary": 9_000_000,
        },
    )
    assert invited.status_code == 200
    assert last_email_to("sinta@undang.test") is not None
    token = invited.json()["invite_url"].split("token=")[1]

    preview = client.get(f"/api/v1/invites/{token}")
    assert preview.status_code == 200
    assert preview.json()["company"] == "PT Undang"

    accepted = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token, "password": "Sinta1234"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["user"]["email"] == "sinta@undang.test"
    assert accepted.json()["tenant"]["slug"] == "undang"


def test_password_reset_rotates_credentials() -> None:
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "employee@movon.test"})
    assert forgot.status_code == 200
    message = last_email_to("employee@movon.test")
    assert message is not None
    token = next(part for part in message.body.split() if "token=" in part).split("token=")[1]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "BaruSekali1"},
    )
    assert reset.status_code == 200
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "employee@movon.test", "password": DEMO_PASSWORD},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "employee@movon.test", "password": "BaruSekali1"},
    ).status_code == 200


def test_forgot_password_does_not_reveal_unknown_email() -> None:
    before = len(outbox)
    response = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@unknown.test"})
    assert response.status_code == 200
    assert len(outbox) == before
