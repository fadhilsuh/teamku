"""Functional Movon HR vertical slices backed by a deterministic demo repository."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt
from secrets import token_urlsafe
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()
JAKARTA = ZoneInfo("Asia/Jakarta")


@dataclass
class Employee:
    id: str
    name: str
    email: str
    role: str
    department: str
    title: str = "Staff"
    status: str = "active"
    salary: int = 8_000_000


@dataclass
class Attendance:
    id: str
    employee_id: str
    checked_in_at: datetime
    latitude: float
    longitude: float
    accuracy_meters: float
    agenda: list[dict]
    anomaly: str | None = None
    checked_out_at: datetime | None = None
    summary: str | None = None


@dataclass
class LeaveRequest:
    id: str
    employee_id: str
    start: date
    end: date
    reason: str
    request_type: str = "time_off"
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approver_comment: str | None = None


@dataclass
class PayrollRun:
    id: str
    period: str
    status: str
    items: list[dict]
    created_at: datetime
    finalized_at: datetime | None = None
    published_at: datetime | None = None


@dataclass
class Notification:
    id: str
    user_id: str
    title: str
    detail: str
    target: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    read: bool = False


@dataclass
class DemoStore:
    tenant_id: str = "pt-movon-solusi-kreatif"
    employees: dict[str, Employee] = field(default_factory=dict)
    attendance: dict[str, Attendance] = field(default_factory=dict)
    requests: dict[str, LeaveRequest] = field(default_factory=dict)
    payroll_runs: dict[str, PayrollRun] = field(default_factory=dict)
    notifications: dict[str, Notification] = field(default_factory=dict)
    sessions: dict[str, str] = field(default_factory=dict)
    idempotency: dict[str, str] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)


store = DemoStore()


def reset_demo_store() -> None:
    """Restore demo records without replacing the imported store object."""
    people = [
        ("e-hr", "Nadia Putri", "hr@movon.test", "hr_admin", "Human Resources", "HR Lead", 12_000_000),
        ("e-manager", "Raka Pratama", "manager@movon.test", "manager", "Engineering", "Engineering Manager", 15_000_000),
        ("e-employee", "Sinta Lestari", "employee@movon.test", "employee", "Engineering", "Frontend Engineer", 8_000_000),
        ("e-004", "Andi Gunawan", "andi@movon.test", "employee", "Product", "Product Designer", 9_000_000),
        ("e-005", "Rizky Pranata", "rizky@movon.test", "employee", "Sales", "Sales Lead", 11_000_000),
        ("e-006", "Budi Santoso", "budi@movon.test", "employee", "Operations", "Logistics Staff", 7_000_000),
        ("e-007", "Dewi Lestari", "dewi@movon.test", "employee", "Creative", "Marketing Executive", 8_500_000),
        ("e-008", "Fajar Nugroho", "fajar@movon.test", "manager", "Product", "Product Manager", 14_000_000),
        ("e-009", "Ayu Maharani", "ayu@movon.test", "employee", "Engineering", "QA Engineer", 8_500_000),
        ("e-010", "Gilang Ramadhan", "gilang@movon.test", "employee", "Engineering", "Backend Engineer", 10_000_000),
        ("e-011", "Maya Sari", "maya@movon.test", "employee", "Human Resources", "People Ops", 8_500_000),
        ("e-012", "Kevin Wijaya", "kevin@movon.test", "employee", "Creative", "Copywriter", 7_500_000),
        ("e-013", "Lina Hartati", "lina@movon.test", "employee", "Finance", "Finance Staff", 9_000_000),
        ("e-014", "Yoga Saputra", "yoga@movon.test", "employee", "Operations", "Project Officer", 8_000_000),
        ("e-015", "Nabila Azzahra", "nabila@movon.test", "employee", "Sales", "Account Executive", 8_000_000),
        ("e-016", "Reza Maulana", "reza@movon.test", "employee", "Product", "Product Analyst", 8_500_000),
        ("e-017", "Citra Amelia", "citra@movon.test", "employee", "Management", "Executive Assistant", 9_000_000),
        ("e-018", "Dian Permata", "dian@movon.test", "employee", "Engineering", "Engineering Intern", 4_500_000),
    ]
    store.employees = {
        employee_id: Employee(employee_id, name, email, role, department, title, "active", salary)
        for employee_id, name, email, role, department, title, salary in people
    }
    jakarta_now = datetime.now(JAKARTA)
    store.attendance = {}
    for index, employee_id in enumerate(
        ["e-manager", "e-004", "e-005", "e-006", "e-007", "e-009", "e-010"]
    ):
        checked_in = (
            jakarta_now.replace(hour=8, minute=50, second=0, microsecond=0)
            + timedelta(minutes=index * 4)
        ).astimezone(UTC)
        item = Attendance(
            f"attendance-seed-{index}",
            employee_id,
            checked_in,
            -6.2,
            106.8166,
            18,
            [{"title": "Prioritas utama", "status": "done" if index < 4 else "planned"}],
            "low_accuracy" if index == 5 else None,
        )
        store.attendance[item.id] = item
    demo_today = datetime.now(JAKARTA).date()
    request = LeaveRequest(
        "request-seed-1",
        "e-009",
        demo_today + timedelta(days=7),
        demo_today + timedelta(days=8),
        "Acara keluarga",
    )
    store.requests = {request.id: request}
    store.payroll_runs = {}
    store.notifications = {
        "notification-manager": Notification(
            "notification-manager",
            "e-manager",
            "Permohonan cuti baru",
            "Ayu Maharani menunggu persetujuan Anda.",
            "/app/approvals",
        ),
        "notification-hr": Notification(
            "notification-hr",
            "e-hr",
            "Data demo siap",
            "Dashboard operasional sudah diperbarui.",
            "/app/overview",
        ),
    }
    store.idempotency = {}
    store.sessions = {}
    store.audit = []


reset_demo_store()


def actor(session_token: str | None) -> Employee:
    employee_id = store.sessions.get(session_token or "")
    employee = store.employees.get(employee_id or "")
    if not employee or employee.status != "active":
        raise HTTPException(401, "Sesi tidak valid")
    return employee


def require(user: Employee, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Anda tidak memiliki izin untuk aksi ini")


def audit(action: str, user: Employee, target: str) -> None:
    store.audit.append(
        {
            "id": str(uuid4()),
            "at": datetime.now(UTC).isoformat(),
            "action": action,
            "actor": user.id,
            "target": target,
        }
    )


def notify(user_id: str, title: str, detail: str, target: str) -> None:
    item = Notification(str(uuid4()), user_id, title, detail, target)
    store.notifications[item.id] = item


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    value = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * radius * asin(sqrt(value))


def working_days(start: date, end: date) -> int:
    return sum(
        1
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    )


def visible_employees(user: Employee) -> list[Employee]:
    if user.role == "hr_admin":
        return list(store.employees.values())
    if user.role == "manager":
        return [item for item in store.employees.values() if item.department == user.department]
    return [user]


def calculate_payroll_items() -> list[dict]:
    rows = []
    for employee in store.employees.values():
        if employee.status != "active":
            continue
        gross = Decimal(employee.salary)
        deduction = (gross * Decimal("0.02")).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        rows.append(
            {
                "employee_id": employee.id,
                "employee": employee.name,
                "gross_rupiah": int(gross),
                "deductions_rupiah": int(deduction),
                "net_rupiah": int(gross - deduction),
            }
        )
    return rows


def payroll_payload(run: PayrollRun) -> dict:
    return asdict(run) | {
        "total_gross_rupiah": sum(item["gross_rupiah"] for item in run.items),
        "total_deductions_rupiah": sum(item["deductions_rupiah"] for item in run.items),
        "total_net_rupiah": sum(item["net_rupiah"] for item in run.items),
        "calculation_version": "manual-components-v1",
        "disclaimer": "PPh 21 dan BPJS harus dikonfigurasi atau disesuaikan manual.",
    }


class Login(BaseModel):
    email: str
    password: str = Field(min_length=8)


class CheckIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float = Field(ge=0, le=10_000)
    selfie_captured: bool
    agenda: list[dict] = Field(min_length=1, max_length=5)


class CheckOut(BaseModel):
    summary: str = Field(min_length=4, max_length=1000)


class LeaveInput(BaseModel):
    start: date
    end: date
    reason: str = Field(min_length=4, max_length=500)


class ApprovalInput(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|revision_requested)$")
    comment: str = Field(min_length=3, max_length=500)


class PayrollInput(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


class EmployeeInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=150)
    department: str = Field(min_length=2, max_length=100)
    role: str = Field(pattern="^(employee|manager|hr_admin)$")
    title: str = Field(default="Staff", min_length=2, max_length=100)
    salary: int = Field(ge=0, le=10_000_000_000)


class EmployeeUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended|terminated)$")


@router.post("/auth/login")
async def login(payload: Login) -> dict:
    user = next((item for item in store.employees.values() if item.email == payload.email), None)
    if not user or payload.password != "Demo123!" or user.status != "active":
        raise HTTPException(401, "Email atau kata sandi salah")
    session_token = token_urlsafe(32)
    store.sessions[session_token] = user.id
    audit("auth.login", user, user.id)
    return {"user": asdict(user), "access_token": session_token}


@router.post("/auth/logout")
async def logout(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    store.sessions.pop(x_demo_user or "", None)
    audit("auth.logout", user, user.id)
    return {"ok": True}


@router.get("/me")
async def me(x_demo_user: str | None = Header(default=None)) -> dict:
    return {"user": asdict(actor(x_demo_user))}


@router.get("/dashboard")
async def dashboard(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    employees = [item for item in visible_employees(user) if item.status == "active"]
    employee_ids = {employee.id for employee in employees}
    today = datetime.now(JAKARTA).date()
    sessions = [
        item
        for item in store.attendance.values()
        if item.employee_id in employee_ids
        and item.checked_in_at.astimezone(JAKARTA).date() == today
    ]
    agenda_items = [agenda for session in sessions for agenda in session.agenda]
    pending = [
        item
        for item in store.requests.values()
        if item.status == "pending" and item.employee_id in employee_ids
    ]
    return {
        "current_user": asdict(user),
        "headcount": len(employees),
        "present": len({item.employee_id for item in sessions}),
        "late": sum(
            1 for item in sessions if item.checked_in_at.astimezone(JAKARTA).time().hour >= 9
        ),
        "pending_approvals": len(pending) if user.role in {"manager", "hr_admin"} else 0,
        "agenda_total": len(agenda_items),
        "agenda_completed": sum(1 for item in agenda_items if item.get("status") == "done"),
        "attendance": [
            {
                "employee": store.employees[item.employee_id].name,
                "department": store.employees[item.employee_id].department,
                "checked_in_at": item.checked_in_at,
                "checked_out_at": item.checked_out_at,
                "anomaly": item.anomaly,
            }
            for item in sorted(sessions, key=lambda entry: entry.checked_in_at, reverse=True)
        ],
    }


@router.get("/employees")
async def employees(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin", "manager")
    visible = visible_employees(user)
    items = [
        asdict(employee) | ({"salary": None} if user.role == "manager" else {})
        for employee in visible
    ]
    return {"items": items, "total": len(items)}


@router.post("/employees")
async def create_employee(
    payload: EmployeeInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    if any(item.email.lower() == payload.email.lower() for item in store.employees.values()):
        raise HTTPException(409, "Email kerja sudah digunakan")
    employee = Employee(id=f"e-{uuid4().hex[:8]}", **payload.model_dump())
    store.employees[employee.id] = employee
    audit("employee.created", user, employee.id)
    notify(employee.id, "Akun Anda siap", "Profil dibuat oleh HR.", "/app/overview")
    return asdict(employee)


@router.patch("/employees/{employee_id}")
async def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    x_demo_user: str | None = Header(default=None),
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    employee = store.employees.get(employee_id)
    if not employee:
        raise HTTPException(404, "Karyawan tidak ditemukan")
    if employee.id == user.id and payload.status != "active":
        raise HTTPException(409, "Anda tidak dapat menonaktifkan akun sendiri")
    employee.status = payload.status
    audit("employee.status_changed", user, employee.id)
    return asdict(employee)


@router.get("/attendance/today")
async def attendance_today(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    today = datetime.now(JAKARTA).date()
    sessions = [
        item
        for item in store.attendance.values()
        if item.employee_id == user.id
        and item.checked_in_at.astimezone(JAKARTA).date() == today
    ]
    if not sessions:
        return {"state": "not_checked_in", "session": None}
    latest = max(sessions, key=lambda item: item.checked_in_at)
    state = "completed" if latest.checked_out_at else "checked_in"
    return {
        "state": state,
        "session": {
            "id": latest.id,
            "checked_in_at": latest.checked_in_at,
            "checked_out_at": latest.checked_out_at,
            "anomaly": latest.anomaly,
            "agenda_count": len(latest.agenda),
            "summary": latest.summary,
        },
    }


@router.post("/attendance/check-in")
async def check_in(
    payload: CheckIn,
    idempotency_key: str = Header(...),
    x_demo_user: str | None = Header(default=None),
) -> dict:
    user = actor(x_demo_user)
    if idempotency_key in store.idempotency:
        return {"id": store.idempotency[idempotency_key], "idempotent": True}
    if any(
        item.employee_id == user.id
        and not item.checked_out_at
        for item in store.attendance.values()
    ):
        raise HTTPException(409, "Anda masih memiliki sesi kehadiran yang terbuka")
    if not payload.selfie_captured:
        raise HTTPException(422, "Selfie kamera langsung wajib untuk kebijakan ini")
    distance = haversine_meters(payload.latitude, payload.longitude, -6.2, 106.8166)
    anomaly = (
        "outside_geofence"
        if distance > 300 + payload.accuracy_meters
        else ("low_accuracy" if payload.accuracy_meters > 100 else None)
    )
    record = Attendance(
        str(uuid4()),
        user.id,
        datetime.now(UTC),
        payload.latitude,
        payload.longitude,
        payload.accuracy_meters,
        payload.agenda,
        anomaly,
    )
    store.attendance[record.id] = record
    store.idempotency[idempotency_key] = record.id
    audit("attendance.check_in", user, record.id)
    return {
        "id": record.id,
        "checked_in_at": record.checked_in_at,
        "distance_meters": round(distance),
        "anomaly": anomaly,
        "agenda_count": len(payload.agenda),
    }


@router.post("/attendance/check-out")
async def check_out(
    payload: CheckOut, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    record = next(
        (
            item
            for item in store.attendance.values()
            if item.employee_id == user.id and not item.checked_out_at
        ),
        None,
    )
    if not record:
        raise HTTPException(409, "Tidak ada sesi kehadiran terbuka")
    record.checked_out_at = datetime.now(UTC)
    record.summary = payload.summary
    audit("attendance.check_out", user, record.id)
    return {
        "id": record.id,
        "checked_out_at": record.checked_out_at,
        "effective_hours": round(
            (record.checked_out_at - record.checked_in_at).total_seconds() / 3600, 2
        ),
    }


@router.get("/leave-requests")
async def list_leave_requests(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    items = [item for item in store.requests.values() if item.employee_id == user.id]
    approved_days = sum(
        working_days(item.start, item.end) for item in items if item.status == "approved"
    )
    return {
        "items": [
            asdict(item) | {"days": working_days(item.start, item.end)}
            for item in sorted(items, key=lambda entry: entry.created_at, reverse=True)
        ],
        "balance": {
            "annual_days": 12,
            "used_days": approved_days,
            "remaining_days": max(12 - approved_days, 0),
        },
    }


@router.post("/leave-requests")
async def submit_leave(
    payload: LeaveInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    if payload.end < payload.start:
        raise HTTPException(422, "Tanggal selesai harus setelah tanggal mulai")
    if working_days(payload.start, payload.end) == 0:
        raise HTTPException(422, "Rentang cuti tidak memiliki hari kerja")
    if any(
        item.employee_id == user.id
        and item.status in {"pending", "approved"}
        and payload.start <= item.end
        and payload.end >= item.start
        for item in store.requests.values()
    ):
        raise HTTPException(409, "Permohonan tumpang tindih")
    request = LeaveRequest(str(uuid4()), user.id, payload.start, payload.end, payload.reason)
    store.requests[request.id] = request
    audit("leave.submitted", user, request.id)
    for manager in store.employees.values():
        if manager.role == "manager" and manager.department == user.department:
            notify(
                manager.id,
                "Permohonan cuti baru",
                f"{user.name} menunggu persetujuan Anda.",
                "/app/approvals",
            )
    return asdict(request) | {"days": working_days(request.start, request.end)}


@router.post("/leave-requests/{request_id}/cancel")
async def cancel_leave(
    request_id: str, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    request = store.requests.get(request_id)
    if not request or request.employee_id != user.id:
        raise HTTPException(404, "Permohonan tidak ditemukan")
    if request.status not in {"pending", "approved"}:
        raise HTTPException(409, "Permohonan ini tidak dapat dibatalkan")
    request.status = "cancelled"
    audit("leave.cancelled", user, request.id)
    return asdict(request)


@router.get("/approvals")
async def approvals(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "manager", "hr_admin")
    items = list(store.requests.values())
    if user.role == "manager":
        items = [
            item
            for item in items
            if store.employees[item.employee_id].department == user.department
        ]
    return {
        "items": [
            asdict(item)
            | {
                "employee_name": store.employees[item.employee_id].name,
                "department": store.employees[item.employee_id].department,
                "days": working_days(item.start, item.end),
            }
            for item in sorted(items, key=lambda entry: entry.created_at, reverse=True)
        ],
        "pending": sum(1 for item in items if item.status == "pending"),
    }


@router.post("/approvals/{request_id}")
async def decide(
    request_id: str,
    payload: ApprovalInput,
    x_demo_user: str | None = Header(default=None),
) -> dict:
    user = actor(x_demo_user)
    require(user, "manager", "hr_admin")
    request = store.requests.get(request_id)
    if not request:
        raise HTTPException(404, "Permohonan tidak ditemukan")
    employee = store.employees[request.employee_id]
    if user.role == "manager" and employee.department != user.department:
        raise HTTPException(403, "Permohonan berada di luar cakupan tim Anda")
    if request.employee_id == user.id:
        raise HTTPException(403, "Persetujuan diri sendiri tidak diperbolehkan")
    if request.status != "pending":
        raise HTTPException(409, "Permohonan sudah diproses")
    request.status = payload.decision
    request.approver_comment = payload.comment
    audit("request." + payload.decision, user, request.id)
    notify(
        request.employee_id,
        "Status permohonan diperbarui",
        f"Permohonan Anda {payload.decision}.",
        "/app/time/time-off",
    )
    return asdict(request)


@router.get("/payroll/runs")
async def list_payroll(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    items = [
        payroll_payload(item)
        for item in sorted(
            store.payroll_runs.values(), key=lambda entry: entry.created_at, reverse=True
        )
    ]
    return {"items": items}


@router.post("/payroll/runs")
async def payroll(
    payload: PayrollInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    existing = next(
        (item for item in store.payroll_runs.values() if item.period == payload.month), None
    )
    if existing:
        return payroll_payload(existing)
    run = PayrollRun(
        str(uuid4()), payload.month, "draft", calculate_payroll_items(), datetime.now(UTC)
    )
    store.payroll_runs[run.id] = run
    audit("payroll.calculated", user, run.id)
    return payroll_payload(run)


@router.post("/payroll/runs/{run_id}/finalize")
async def finalize_payroll(
    run_id: str, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    run = store.payroll_runs.get(run_id)
    if not run:
        raise HTTPException(404, "Payroll run tidak ditemukan")
    if run.status != "draft":
        raise HTTPException(409, "Hanya draft payroll yang dapat difinalisasi")
    run.status = "finalized"
    run.finalized_at = datetime.now(UTC)
    audit("payroll.finalized", user, run.id)
    return payroll_payload(run)


@router.post("/payroll/runs/{run_id}/publish")
async def publish_payroll(
    run_id: str, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    run = store.payroll_runs.get(run_id)
    if not run:
        raise HTTPException(404, "Payroll run tidak ditemukan")
    if run.status != "finalized":
        raise HTTPException(409, "Finalisasi payroll sebelum dipublikasikan")
    run.status = "published"
    run.published_at = datetime.now(UTC)
    audit("payroll.published", user, run.id)
    for employee in store.employees.values():
        notify(
            employee.id,
            "Slip gaji tersedia",
            f"Payroll periode {run.period} telah dipublikasikan.",
            "/app/payroll/payslips",
        )
    return payroll_payload(run)


@router.get("/payroll/payslips")
async def payslips(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    items = []
    for run in store.payroll_runs.values():
        if run.status != "published":
            continue
        employee_row = next(
            (row for row in run.items if row["employee_id"] == user.id),
            None,
        )
        if employee_row:
            items.append(
                {
                    "id": run.id,
                    "period": run.period,
                    "published_at": run.published_at,
                    **employee_row,
                }
            )
    items.sort(key=lambda item: item["period"], reverse=True)
    return {"items": items}


@router.get("/notifications")
async def notifications(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    items = [item for item in store.notifications.values() if item.user_id == user.id]
    items.sort(key=lambda entry: entry.created_at, reverse=True)
    return {
        "items": [asdict(item) for item in items],
        "unread": sum(1 for item in items if not item.read),
    }


@router.post("/notifications/read-all")
async def read_notifications(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    for item in store.notifications.values():
        if item.user_id == user.id:
            item.read = True
    return {"ok": True}


@router.get("/audit-logs")
async def audit_logs(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    return {"items": list(reversed(store.audit))}
