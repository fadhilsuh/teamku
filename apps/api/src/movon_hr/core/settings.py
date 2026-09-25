from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOVON_")
    environment: str = "development"
    # Backwards-compatible with the original .env.example key MOVON_ENV.
    env: str | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    # When set (e.g. postgresql+asyncpg://user:pass@host:5432/db) every input is
    # persisted to PostgreSQL and reloaded on startup. When unset the API falls
    # back to the ephemeral in-memory demo store.
    database_url: str | None = None
    app_base_url: str = "http://localhost:3000"
    session_cookie_name: str = "teamku_session"
    session_cookie_secure: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    mail_provider: Literal["console", "resend"] = "console"
    resend_api_key: SecretStr | None = None
    mail_from: str | None = None

    @model_validator(mode="after")
    def normalize_environment(self):
        if self.env and self.environment == "development":
            self.environment = self.env
        if self.mail_provider == "resend" and not (self.resend_api_key and self.mail_from):
            raise ValueError(
                "MOVON_MAIL_PROVIDER=resend needs MOVON_RESEND_API_KEY and MOVON_MAIL_FROM"
            )
        return self


settings = Settings()


def postgres_sync_url(url: str) -> str:
    """Convert an API database URL to the sync driver Alembic needs.

    The API uses asyncpg. Alembic's default online migrations are synchronous,
    and a bare postgresql:// URL would load psycopg2, which is not installed.
    """
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+asyncpg://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url
