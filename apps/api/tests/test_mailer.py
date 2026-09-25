import asyncio
import logging
import threading

import pytest
import requests
import resend
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from movon_hr.core import mailer
from movon_hr.core.mailer import dispatch_email, outbox, send_email
from movon_hr.core.settings import Settings, settings
from movon_hr.main import app
from movon_hr.modules import api
from movon_hr.modules.api import reset_demo_store

client = TestClient(app)


def login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo123!"})
    return {"X-Demo-User": response.json()["access_token"]}


@pytest.fixture
def resend_on(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    monkeypatch.setattr(settings, "mail_provider", "resend")
    monkeypatch.setattr(settings, "resend_api_key", SecretStr("re_test"))
    monkeypatch.setattr(settings, "mail_from", "Teamku <noreply@movoncreative.dev>")
    sent: list[dict] = []
    monkeypatch.setattr(resend.Emails, "send", lambda params: sent.append(params) or {"id": "x"})
    return sent


def test_resend_provider_requires_key_and_from() -> None:
    with pytest.raises(ValidationError):
        Settings(mail_provider="resend", mail_from="a@b.dev")
    with pytest.raises(ValidationError):
        Settings(mail_provider="resend", resend_api_key="re_x")
    ok = Settings(mail_provider="resend", resend_api_key="re_x", mail_from="a@b.dev")
    assert "re_x" not in repr(ok)


def test_resend_sends_plain_text_and_skips_outbox(resend_on: list[dict]) -> None:
    before = len(outbox)
    assert send_email("sinta@gmail.com", "Halo", "isi", kind="invite") is True
    assert resend_on == [
        {
            "from": "Teamku <noreply@movoncreative.dev>",
            "to": ["sinta@gmail.com"],
            "subject": "Halo",
            "text": "isi",
            "tags": [{"name": "kind", "value": "invite"}],
        }
    ]
    assert len(outbox) == before


def test_resend_skips_reserved_domains(
    resend_on: list[dict], caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        assert send_email("maya@Movon.TEST", "Halo", "isi") is False
    assert "reserved_domain" in caplog.text
    assert resend_on == []


def test_resend_failure_never_raises_or_logs_body(
    resend_on: list[dict], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(params: dict) -> dict:
        raise resend.exceptions.ResendError(
            code=403, error_type="validation_error", message="domain", suggested_action=""
        )

    monkeypatch.setattr(resend.Emails, "send", boom)
    with caplog.at_level(logging.INFO):
        assert send_email("sinta@gmail.com", "Halo", "token=rahasia") is False
    assert "error=validation_error code=403" in caplog.text
    assert "rahasia" not in caplog.text


def test_resend_timeout_never_raises(
    resend_on: list[dict], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def slow(params: dict) -> dict:
        raise requests.Timeout()

    monkeypatch.setattr(resend.Emails, "send", slow)
    assert send_email("sinta@gmail.com", "Halo", "isi") is False
    assert "error=Timeout" in caplog.text


def test_console_hides_body_outside_development(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    with caplog.at_level(logging.INFO):
        assert send_email("a@movon.test", "Halo", "token=rahasia")
    assert "rahasia" not in caplog.text
    assert mailer.last_email_to("a@movon.test").body == "token=rahasia"


def test_dispatch_does_not_wait_for_resend(
    resend_on: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    monkeypatch.setattr(resend.Emails, "send", lambda params: release.wait(5) and {"id": "x"})

    async def run() -> None:
        dispatch_email("sinta@gmail.com", "Halo", "isi")  # would block 5s if awaited inline

    asyncio.run(asyncio.wait_for(run(), timeout=1))
    release.set()


def test_invite_reports_failed_email_but_keeps_invitation(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_demo_store()
    monkeypatch.setattr(api, "send_email", lambda *a, **k: False)
    response = client.post(
        "/api/v1/invites",
        headers=login("hr@movon.test"),
        json={
            "name": "Sinta",
            "email": "sinta@gmail.com",
            "department": "Product",
            "role": "employee",
            "title": "Designer",
            "salary": 9_000_000,
        },
    )
    assert response.status_code == 200
    assert response.json()["email_status"] == "failed"
    token = response.json()["invite_url"].split("token=")[1]
    assert client.get(f"/api/v1/invites/{token}").status_code == 200
    assert "invite.email_failed" in [item["action"] for item in api.store.audit]


def test_forgot_password_does_not_wait_on_send(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_demo_store()
    queued: list[str] = []
    monkeypatch.setattr(api, "dispatch_email", lambda to, *a, **k: queued.append(to))
    monkeypatch.setattr(
        api, "send_email", lambda *a, **k: pytest.fail("forgot-password waited on send")
    )
    response = client.post("/api/v1/auth/forgot-password", json={"email": "employee@movon.test"})
    assert response.status_code == 200
    assert queued == ["employee@movon.test"]
