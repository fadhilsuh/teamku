"""PostgreSQL persistence for the Teamku store.

The API keeps all working state in the in-memory ``DemoStore`` defined in
``movon_hr.modules.api``. This module mirrors that store to PostgreSQL so every
input survives process restarts:

* On startup the store is hydrated from the database (or seeded and saved when
  the database is still empty).
* After every mutating request the whole store is written back inside a single
  transaction.

Persistence is only active when ``MOVON_DATABASE_URL`` is configured. Without it
the API behaves exactly like the original ephemeral demo (used by the tests).
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
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from movon_hr.core.settings import settings
from movon_hr.modules.api import (
    Attendance,
    DemoStore,
    Employee,
    LeaveRequest,
    Notification,
    OfficeLocation,
    PayrollRun,
)

metadata = MetaData()

employees_table = Table(
    "employees",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("email", String, nullable=False),
    Column("role", String, nullable=False),
    Column("department", String, nullable=False),
    Column("title", String, nullable=False),
    Column("status", String, nullable=False),
    Column("salary", Integer, nullable=False),
)

attendance_table = Table(
    "attendance",
    metadata,
    Column("id", String, primary_key=True),
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
    Column("employee_id", String, nullable=False),
)

idempotency_table = Table(
    "idempotency",
    metadata,
    Column("key", String, primary_key=True),
    Column("attendance_id", String, nullable=False),
)

audit_table = Table(
    "audit_logs",
    metadata,
    Column("id", String, primary_key=True),
    Column("at", String, nullable=False),
    Column("action", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("target", String, nullable=False),
)

office_table = Table(
    "office_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
    Column("radius_meters", Float, nullable=False),
)

meta_table = Table(
    "store_meta",
    metadata,
    Column("key", String, primary_key=True),
    Column("value", String, nullable=False),
)

_engine: AsyncEngine | None = None


def is_enabled() -> bool:
    """Persistence is active only when a database URL is configured."""
    return bool(settings.database_url)


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, future=True)
    return _engine


async def init_db() -> None:
    """Create the schema if it does not exist yet."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def dispose() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def load_store(store: DemoStore) -> bool:
    """Hydrate ``store`` from the database.

    Returns ``True`` when existing data was loaded, ``False`` when the database
    is empty (so the caller can seed and persist the demo data instead).
    """
    engine = _get_engine()
    async with engine.connect() as conn:
        employees = (await conn.execute(select(employees_table))).mappings().all()
        if not employees:
            return False

        store.employees = {
            row["id"]: Employee(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                role=row["role"],
                department=row["department"],
                title=row["title"],
                status=row["status"],
                salary=row["salary"],
            )
            for row in employees
        }

        store.attendance = {
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
            for row in (await conn.execute(select(attendance_table))).mappings()
        }

        store.requests = {
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
            for row in (await conn.execute(select(leave_requests_table))).mappings()
        }

        store.payroll_runs = {
            row["id"]: PayrollRun(
                id=row["id"],
                period=row["period"],
                status=row["status"],
                items=row["items"],
                created_at=row["created_at"],
                finalized_at=row["finalized_at"],
                published_at=row["published_at"],
            )
            for row in (await conn.execute(select(payroll_runs_table))).mappings()
        }

        store.notifications = {
            row["id"]: Notification(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                detail=row["detail"],
                target=row["target"],
                created_at=row["created_at"],
                read=row["read"],
            )
            for row in (await conn.execute(select(notifications_table))).mappings()
        }

        store.sessions = {
            row["token"]: row["employee_id"]
            for row in (await conn.execute(select(sessions_table))).mappings()
        }
        store.idempotency = {
            row["key"]: row["attendance_id"]
            for row in (await conn.execute(select(idempotency_table))).mappings()
        }
        store.audit = [
            {
                "id": row["id"],
                "at": row["at"],
                "action": row["action"],
                "actor": row["actor"],
                "target": row["target"],
            }
            for row in (await conn.execute(select(audit_table))).mappings()
        ]

        office_row = (await conn.execute(select(office_table))).mappings().first()
        if office_row:
            store.office = OfficeLocation(
                name=office_row["name"],
                latitude=office_row["latitude"],
                longitude=office_row["longitude"],
                radius_meters=office_row["radius_meters"],
            )

        meta_row = (
            await conn.execute(
                select(meta_table).where(meta_table.c.key == "tenant_id")
            )
        ).mappings().first()
        if meta_row:
            store.tenant_id = meta_row["value"]

    return True


async def save_store(store: DemoStore) -> None:
    """Persist the entire store inside a single transaction (full replace)."""
    engine = _get_engine()
    async with engine.begin() as conn:
        for table in (
            attendance_table,
            leave_requests_table,
            payroll_runs_table,
            notifications_table,
            sessions_table,
            idempotency_table,
            audit_table,
            office_table,
            meta_table,
            employees_table,
        ):
            await conn.execute(delete(table))

        if store.employees:
            await conn.execute(
                employees_table.insert(),
                [asdict(item) for item in store.employees.values()],
            )
        if store.attendance:
            await conn.execute(
                attendance_table.insert(),
                [asdict(item) for item in store.attendance.values()],
            )
        if store.requests:
            await conn.execute(
                leave_requests_table.insert(),
                [asdict(item) for item in store.requests.values()],
            )
        if store.payroll_runs:
            await conn.execute(
                payroll_runs_table.insert(),
                [asdict(item) for item in store.payroll_runs.values()],
            )
        if store.notifications:
            await conn.execute(
                notifications_table.insert(),
                [asdict(item) for item in store.notifications.values()],
            )
        if store.sessions:
            await conn.execute(
                sessions_table.insert(),
                [
                    {"token": token, "employee_id": employee_id}
                    for token, employee_id in store.sessions.items()
                ],
            )
        if store.idempotency:
            await conn.execute(
                idempotency_table.insert(),
                [
                    {"key": key, "attendance_id": attendance_id}
                    for key, attendance_id in store.idempotency.items()
                ],
            )
        if store.audit:
            await conn.execute(audit_table.insert(), list(store.audit))

        await conn.execute(
            office_table.insert(), [{"id": 1, **asdict(store.office)}]
        )
        await conn.execute(
            meta_table.insert(),
            [{"key": "tenant_id", "value": store.tenant_id}],
        )


__all__ = [
    "dispose",
    "init_db",
    "is_enabled",
    "load_store",
    "save_store",
]
