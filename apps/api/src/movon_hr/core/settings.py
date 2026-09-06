from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MOVON_")
    environment: str = "development"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )
    # When set (e.g. postgresql+asyncpg://user:pass@host:5432/db) every input is
    # persisted to PostgreSQL and reloaded on startup. When unset the API falls
    # back to the ephemeral in-memory demo store.
    database_url: str | None = None


settings = Settings()
