"""PostgreSQL persistence with tenant-scoped rows.

Each company is a row in ``tenants``. Child tables always include ``tenant_id``.
Mutations persist only the active tenant so one company cannot overwrite another.
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.schema import CreateColumn

from movon_hr.core.settings import settings
from movon_hr.core.tenancy import DEMO_TENANT_ID, bind_tenant, clear_registry, put_store
from movon_hr.modules.api import (
    AlertReceipt,
    Attendance,
    DemoStore,
    Employee,
    Invitation,
    LeaveRequest,
    LocationEvent,
    Notification,
    OfficeLocation,
    PasswordReset,
    PayrollRun,
    Session,
)

metadata = MetaData()

tenants_table = Table(
    "tenants",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("slug", String, nullable=False, unique=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

employees_table = Table(
    "employees",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("role", String, nullable=False),
    Column("department", String, nullable=False),
    Column("title", String, nullable=False),
    Column("status", String, nullable=False),
    Column("salary", Integer, nullable=False),
    Column("password_hash", String, nullable=False, server_default=""),
    Column("is_remote", Boolean, nullable=False, server_default="false"),
)

attendance_table = Table(
    "attendance",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("employee_id", String, nullable=False),
    Column("checked_in_at", DateTime(timezone=True), nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("accuracy_meters", Float, nullable=False),
    Column("agenda", JSONB, nullable=False),
    Column("anomaly", String, nullable=True),
    Column("checked_out_at", DateTime(timezone=True), nullable=True),
    Column("summary", Text, nullable=True),
)

leave_requests_table = Table(
    "leave_requests",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("employee_id", String, nullable=False),
    Column("start", Date, nullable=False),
    Column("end", Date, nullable=False),
    Column("reason", Text, nullable=False),
    Column("request_type", String, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("approver_comment", Text, nullable=True),
)

payroll_runs_table = Table(
    "payroll_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("period", String, nullable=False),
    Column("status", String, nullable=False),
    Column("items", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("finalized_at", DateTime(timezone=True), nullable=True),
    Column("published_at", DateTime(timezone=True), nullable=True),
)

notifications_table = Table(
    "notifications",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("user_id", String, nullable=False),
    Column("title", String, nullable=False),
    Column("detail", Text, nullable=False),
    Column("target", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("read", Boolean, nullable=False),
)

sessions_table = Table(
    "sessions",
    metadata,
    Column("token", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("employee_id", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)

idempotency_table = Table(
    "idempotency",
    metadata,
    Column("key", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("attendance_id", String, nullable=False),
)

audit_table = Table(
    "audit_logs",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("at", String, nullable=False),
    Column("action", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("target", String, nullable=False),
)

office_table = Table(
    "office_settings",
    metadata,
    Column("tenant_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("radius_meters", Float, nullable=False),
    Column("reverify_enabled", Boolean, nullable=False, server_default="false"),
    Column("reverify_count_per_day", Integer, nullable=False, server_default="1"),
    Column("reverify_window_start_minutes", Integer, nullable=False, server_default="60"),
    Column("reverify_window_end_minutes", Integer, nullable=False, server_default="420"),
    Column("alerts_enabled", Boolean, nullable=False, server_default="false"),
    Column("clock_in_reminder_time", String, nullable=False, server_default="09:15"),
    Column("clock_out_reminder_time", String, nullable=False, server_default="18:15"),
    Column("max_open_hours", Integer, nullable=False, server_default="10"),
    Column("alert_managers", Boolean, nullable=False, server_default="false"),
)

invitations_table = Table(
    "invitations",
    metadata,
    Column("token", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("email", String, nullable=False),
    Column("name", String, nullable=False),
    Column("role", String, nullable=False),
    Column("department", String, nullable=False),
    Column("title", String, nullable=False),
    Column("salary", Integer, nullable=False),
    Column("invited_by", String, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("accepted_at", DateTime(timezone=True), nullable=True),
    Column("is_remote", Boolean, nullable=False, server_default="false"),
)

password_resets_table = Table(
    "password_resets",
    metadata,
    Column("token", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("employee_id", String, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True), nullable=True),
)

location_events_table = Table(
    "location_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("employee_id", String, nullable=False),
    Column("attendance_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
    Column("lat", Float, nullable=True),
    Column("lng", Float, nullable=True),
    Column("accuracy", Float, nullable=True),
    Column("distance_meters", Float, nullable=True),
    Column("inside_geofence", Boolean, nullable=True),
    Column("anomaly", String, nullable=True),
    Column("due_at", DateTime(timezone=True), nullable=True),
)

alert_receipts_table = Table(
    "alert_receipts",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", String, nullable=False, index=True),
    Column("employee_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("local_date", Date, nullable=False),
)

_engine: AsyncEngine | None = None


def is_enabled() -> bool:
    return bool(settings.database_url)


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


def _add_column(connection, table: Table, column: Column) -> None:
    preparer = connection.dialect.identifier_preparer
    column_spec = str(CreateColumn(column).compile(dialect=connection.dialect))
    connection.execute(text(f"ALTER TABLE {preparer.format_table(table)} ADD COLUMN {column_spec}"))


def _add_missing_columns(connection) -> None:
    """Add model columns that create_all will not attach to existing tables."""
    inspector = inspect(connection)
    for table in metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            _add_column(connection, table, column)


def _ensure_schema(connection) -> None:
    metadata.create_all(connection)
    _add_missing_columns(connection)


async def init_db() -> None:
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(_ensure_schema)


async def dispose() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def _with_tenant(payload: dict, tenant_id: str) -> dict:
    return {**payload, "tenant_id": tenant_id}


async def load_store(store: DemoStore | None = None) -> bool:
    """Hydrate every tenant into the registry. Returns True when data existed."""
    engine = _get_engine()
    clear_registry()
    async with engine.connect() as conn:
        tenants = (await conn.execute(select(tenants_table))).mappings().all()
        if not tenants:
            return False

        for tenant in tenants:
            item = DemoStore(
                tenant_id=tenant["id"],
                tenant_name=tenant["name"],
                tenant_slug=tenant["slug"],
                created_at=tenant["created_at"],
            )
            tid = item.tenant_id

            item.employees = {
                row["id"]: Employee(
                    id=row["id"],
                    name=row["name"],
                    email=row["email"],
                    role=row["role"],
                    department=row["department"],
                    title=row["title"],
                    status=row["status"],
                    salary=row["salary"],
                    password_hash=row["password_hash"],
                    tenant_id=row["tenant_id"],
                    is_remote=bool(row.get("is_remote") or False),
                )
                for row in (
                    await conn.execute(
                        select(employees_table).where(employees_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.attendance = {
                row["id"]: Attendance(
                    id=row["id"],
                    employee_id=row["employee_id"],
                    checked_in_at=row["checked_in_at"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    accuracy_meters=row["accuracy_meters"],
                    agenda=row["agenda"],
                    anomaly=row["anomaly"],
                    checked_out_at=row["checked_out_at"],
                    summary=row["summary"],
                )
                for row in (
                    await conn.execute(
                        select(attendance_table).where(attendance_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.requests = {
                row["id"]: LeaveRequest(
                    id=row["id"],
                    employee_id=row["employee_id"],
                    start=row["start"],
                    end=row["end"],
                    reason=row["reason"],
                    request_type=row["request_type"],
                    status=row["status"],
                    created_at=row["created_at"],
                    approver_comment=row["approver_comment"],
                )
                for row in (
                    await conn.execute(
                        select(leave_requests_table).where(leave_requests_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.payroll_runs = {
                row["id"]: PayrollRun(
                    id=row["id"],
                    period=row["period"],
                    status=row["status"],
                    items=row["items"],
                    created_at=row["created_at"],
                    finalized_at=row["finalized_at"],
                    published_at=row["published_at"],
                )
                for row in (
                    await conn.execute(
                        select(payroll_runs_table).where(payroll_runs_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.notifications = {
                row["id"]: Notification(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    detail=row["detail"],
                    target=row["target"],
                    created_at=row["created_at"],
                    read=row["read"],
                )
                for row in (
                    await conn.execute(
                        select(notifications_table).where(notifications_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.sessions = {
                row["token"]: Session(
                    token=row["token"],
                    employee_id=row["employee_id"],
                    created_at=row["created_at"],
                    expires_at=row["expires_at"],
                    tenant_id=row["tenant_id"],
                )
                for row in (
                    await conn.execute(
                        select(sessions_table).where(sessions_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.idempotency = {
                row["key"]: row["attendance_id"]
                for row in (
                    await conn.execute(
                        select(idempotency_table).where(idempotency_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.audit = [
                {
                    "id": row["id"],
                    "at": row["at"],
                    "action": row["action"],
                    "actor": row["actor"],
                    "target": row["target"],
                }
                for row in (
                    await conn.execute(select(audit_table).where(audit_table.c.tenant_id == tid))
                ).mappings()
            ]
            office_row = (
                await conn.execute(select(office_table).where(office_table.c.tenant_id == tid))
            ).mappings().first()
            if office_row:
                item.office = OfficeLocation(
                    name=office_row["name"],
                    latitude=office_row["latitude"],
                    longitude=office_row["longitude"],
                    radius_meters=office_row["radius_meters"],
                    reverify_enabled=bool(office_row.get("reverify_enabled") or False),
                    reverify_count_per_day=int(office_row.get("reverify_count_per_day") or 1),
                    reverify_window_start_minutes=int(
                        office_row.get("reverify_window_start_minutes") or 60
                    ),
                    reverify_window_end_minutes=int(
                        office_row.get("reverify_window_end_minutes") or 420
                    ),
                    alerts_enabled=bool(office_row.get("alerts_enabled") or False),
                    clock_in_reminder_time=office_row.get("clock_in_reminder_time") or "09:15",
                    clock_out_reminder_time=office_row.get("clock_out_reminder_time") or "18:15",
                    max_open_hours=int(office_row.get("max_open_hours") or 10),
                    alert_managers=bool(office_row.get("alert_managers") or False),
                )
            item.invitations = {
                row["token"]: Invitation(
                    token=row["token"],
                    tenant_id=row["tenant_id"],
                    email=row["email"],
                    name=row["name"],
                    role=row["role"],
                    department=row["department"],
                    title=row["title"],
                    salary=row["salary"],
                    invited_by=row["invited_by"],
                    expires_at=row["expires_at"],
                    accepted_at=row["accepted_at"],
                    is_remote=bool(row.get("is_remote") or False),
                )
                for row in (
                    await conn.execute(
                        select(invitations_table).where(invitations_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.password_resets = {
                row["token"]: PasswordReset(
                    token=row["token"],
                    tenant_id=row["tenant_id"],
                    employee_id=row["employee_id"],
                    expires_at=row["expires_at"],
                    used_at=row["used_at"],
                )
                for row in (
                    await conn.execute(
                        select(password_resets_table).where(password_resets_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.location_events = {
                row["id"]: LocationEvent(
                    id=row["id"],
                    employee_id=row["employee_id"],
                    attendance_id=row["attendance_id"],
                    kind=row["kind"],
                    at=row["at"],
                    lat=row["lat"],
                    lng=row["lng"],
                    accuracy=row["accuracy"],
                    distance_meters=row["distance_meters"],
                    inside_geofence=row["inside_geofence"],
                    anomaly=row["anomaly"],
                    due_at=row["due_at"],
                )
                for row in (
                    await conn.execute(
                        select(location_events_table).where(location_events_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            item.alert_receipts = {
                row["id"]: AlertReceipt(
                    id=row["id"],
                    employee_id=row["employee_id"],
                    kind=row["kind"],
                    local_date=row["local_date"],
                )
                for row in (
                    await conn.execute(
                        select(alert_receipts_table).where(alert_receipts_table.c.tenant_id == tid)
                    )
                ).mappings()
            }
            put_store(item)

    ids = {row["id"] for row in tenants}
    bind_tenant(DEMO_TENANT_ID if DEMO_TENANT_ID in ids else tenants[0]["id"])
    return True


async def save_store(store: DemoStore) -> None:
    """Replace one tenant's rows inside a single transaction."""
    engine = _get_engine()
    tid = store.tenant_id
    async with engine.begin() as conn:
        await conn.execute(delete(employees_table).where(employees_table.c.tenant_id == tid))
        await conn.execute(delete(attendance_table).where(attendance_table.c.tenant_id == tid))
        await conn.execute(delete(leave_requests_table).where(leave_requests_table.c.tenant_id == tid))
        await conn.execute(delete(payroll_runs_table).where(payroll_runs_table.c.tenant_id == tid))
        await conn.execute(delete(notifications_table).where(notifications_table.c.tenant_id == tid))
        await conn.execute(delete(sessions_table).where(sessions_table.c.tenant_id == tid))
        await conn.execute(delete(idempotency_table).where(idempotency_table.c.tenant_id == tid))
        await conn.execute(delete(audit_table).where(audit_table.c.tenant_id == tid))
        await conn.execute(delete(office_table).where(office_table.c.tenant_id == tid))
        await conn.execute(delete(invitations_table).where(invitations_table.c.tenant_id == tid))
        await conn.execute(delete(password_resets_table).where(password_resets_table.c.tenant_id == tid))
        await conn.execute(delete(location_events_table).where(location_events_table.c.tenant_id == tid))
        await conn.execute(delete(alert_receipts_table).where(alert_receipts_table.c.tenant_id == tid))
        await conn.execute(delete(tenants_table).where(tenants_table.c.id == tid))

        await conn.execute(
            tenants_table.insert(),
            [
                {
                    "id": store.tenant_id,
                    "name": store.tenant_name,
                    "slug": store.tenant_slug,
                    "created_at": store.created_at,
                }
            ],
        )
        if store.employees:
            await conn.execute(
                employees_table.insert(),
                [_with_tenant(asdict(item), tid) for item in store.employees.values()],
            )
        if store.attendance:
            await conn.execute(
                attendance_table.insert(),
                [_with_tenant(asdict(item), tid) for item in store.attendance.values()],
            )
        if store.requests:
            await conn.execute(
                leave_requests_table.insert(),
                [_with_tenant(asdict(item), tid) for item in store.requests.values()],
            )
        if store.payroll_runs:
            await conn.execute(
                payroll_runs_table.insert(),
                [_with_tenant(asdict(item), tid) for item in store.payroll_runs.values()],
            )
        if store.notifications:
            await conn.execute(
                notifications_table.insert(),
                [_with_tenant(asdict(item), tid) for item in store.notifications.values()],
            )
        if store.sessions:
            await conn.execute(
                sessions_table.insert(),
                [
                    {**asdict(session), "tenant_id": session.tenant_id or tid}
                    for session in store.sessions.values()
                ],
            )
        if store.idempotency:
            await conn.execute(
                idempotency_table.insert(),
                [
                    {"key": key, "attendance_id": attendance_id, "tenant_id": tid}
                    for key, attendance_id in store.idempotency.items()
                ],
            )
        if store.audit:
            await conn.execute(
                audit_table.insert(),
                [_with_tenant(row, tid) for row in store.audit],
            )
        await conn.execute(
            office_table.insert(),
            [{"tenant_id": tid, **asdict(store.office)}],
        )
        if store.invitations:
            await conn.execute(
                invitations_table.insert(),
                [asdict(item) for item in store.invitations.values()],
            )
        if store.password_resets:
            await conn.execute(
                password_resets_table.insert(),
                [asdict(item) for item in store.password_resets.values()],
            )
        if store.location_events:
            await conn.execute(
                location_events_table.insert(),
                [_with_tenant(asdict(item), tid) for item in store.location_events.values()],
            )
        if store.alert_receipts:
            await conn.execute(
                alert_receipts_table.insert(),
                [_with_tenant(asdict(item), tid) for item in store.alert_receipts.values()],
            )


__all__ = [
    "dispose",
    "init_db",
    "is_enabled",
    "load_store",
    "metadata",
    "save_store",
]
