from movon_hr.core.settings import postgres_sync_url


def test_asyncpg_url_uses_psycopg_instead_of_default_psycopg2() -> None:
    assert (
        postgres_sync_url("postgresql+asyncpg://movon:movon@localhost:5432/movon")
        == "postgresql+psycopg://movon:movon@localhost:5432/movon"
    )


def test_bare_postgres_url_uses_psycopg() -> None:
    assert (
        postgres_sync_url("postgresql://movon:movon@localhost:5432/movon")
        == "postgresql+psycopg://movon:movon@localhost:5432/movon"
    )


def test_existing_psycopg_url_is_unchanged() -> None:
    url = "postgresql+psycopg://movon:movon@localhost:5432/movon"
    assert postgres_sync_url(url) == url
