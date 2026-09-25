import pytest

from movon_hr.core.settings import settings


@pytest.fixture(autouse=True)
def console_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    # A developer .env with MOVON_MAIL_PROVIDER=resend must never make tests send real email.
    monkeypatch.setattr(settings, "mail_provider", "console")
