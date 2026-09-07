from sqlalchemy import Column, Float, Integer, MetaData, String, Table, create_engine, inspect

from movon_hr.core.persistence import _add_missing_columns


def _legacy_schema() -> MetaData:
    legacy = MetaData()
    Table(
        "employees",
        legacy,
        Column("id", String, primary_key=True),
        Column("tenant_id", String, nullable=False),
        Column("name", String, nullable=False),
        Column("email", String, nullable=False),
        Column("role", String, nullable=False),
        Column("department", String, nullable=False),
        Column("title", String, nullable=False),
        Column("status", String, nullable=False),
        Column("salary", Integer, nullable=False),
        Column("password_hash", String, nullable=False, server_default=""),
    )
    Table(
        "invitations",
        legacy,
        Column("token", String, primary_key=True),
        Column("tenant_id", String, nullable=False),
        Column("email", String, nullable=False),
        Column("name", String, nullable=False),
        Column("role", String, nullable=False),
        Column("department", String, nullable=False),
        Column("title", String, nullable=False),
        Column("salary", Integer, nullable=False),
        Column("invited_by", String, nullable=False),
        Column("expires_at", String, nullable=False),
        Column("accepted_at", String, nullable=True),
    )
    Table(
        "office_settings",
        legacy,
        Column("tenant_id", String, primary_key=True),
        Column("name", String, nullable=False),
        Column("latitude", Float, nullable=False),
        Column("longitude", Float, nullable=False),
        Column("radius_meters", Float, nullable=False),
    )
    return legacy


def test_add_missing_columns_upgrades_legacy_remote_schema() -> None:
    engine = create_engine("sqlite://")
    _legacy_schema().create_all(engine)

    with engine.begin() as connection:
        _add_missing_columns(connection)

    inspector = inspect(engine)
    employees = {column["name"] for column in inspector.get_columns("employees")}
    invitations = {column["name"] for column in inspector.get_columns("invitations")}
    office = {column["name"] for column in inspector.get_columns("office_settings")}

    assert "is_remote" in employees
    assert "is_remote" in invitations
    assert "reverify_enabled" in office
    assert "alerts_enabled" in office


def test_add_missing_columns_is_idempotent() -> None:
    engine = create_engine("sqlite://")
    _legacy_schema().create_all(engine)

    with engine.begin() as connection:
        _add_missing_columns(connection)
    with engine.begin() as connection:
        _add_missing_columns(connection)

    inspector = inspect(engine)
    employees = [column["name"] for column in inspector.get_columns("employees")]
    assert employees.count("is_remote") == 1
