"""Small vertical-slice application layer. Replace DemoStore with SQLAlchemy repositories in deployment."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()


@dataclass
class Employee:
    id: str
    name: str
    email: str
    role: str
    department: str
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
    status: str = "pending"
    approver_comment: str | None = None


@dataclass
class DemoStore:
    tenant_id: str = "pt-movon-solusi-kreatif"
    employees: dict[str, Employee] = field(default_factory=dict)
    attendance: dict[str, Attendance] = field(default_factory=dict)
    requests: dict[str, LeaveRequest] = field(default_factory=dict)
    idempotency: dict[str, str] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)


store = DemoStore()
store.employees = {
    "e-hr": Employee("e-hr", "Nadia Putri", "hr@movon.test", "hr_admin", "Human Resources", salary=12_000_000),
    "e-manager": Employee("e-manager", "Raka Pratama", "manager@movon.test", "manager", "Engineering", salary=15_000_000),
    "e-employee": Employee("e-employee", "Sinta Lestari", "employee@movon.test", "employee", "Engineering"),
}


def actor(user_id: str | None) -> Employee:
    employee = store.employees.get(user_id or "e-employee")
    if not employee:
        raise HTTPException(401, "Sesi tidak valid")
    return employee


def require(user: Employee, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Anda tidak memiliki izin untuk aksi ini")


def audit(action: str, user: Employee, target: str) -> None:
    store.audit.append({"id": str(uuid4()), "at": datetime.now(UTC).isoformat(), "action": action, "actor": user.id, "target": target})


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


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


@router.post("/auth/login")
async def login(payload: Login) -> dict:
    user = next((x for x in store.employees.values() if x.email == payload.email), None)
    if not user or payload.password != "Demo123!":
        raise HTTPException(401, "Email atau kata sandi salah")
    return {"user": asdict(user), "access_token": user.id, "notice": "Demo uses a short-lived API token; production uses HttpOnly rotating cookies."}


@router.get("/me")
async def me(x_demo_user: str | None = Header(default=None)) -> dict:
    return {"user": asdict(actor(x_demo_user))}


@router.get("/dashboard")
async def dashboard(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    employees = list(store.employees.values())
    scoped = employees if user.role == "hr_admin" else [e for e in employees if e.department == user.department]
    open_sessions = [a for a in store.attendance.values() if not a.checked_out_at]
    return {"headcount": len(scoped), "present": len(open_sessions), "pending_approvals": len([r for r in store.requests.values() if r.status == "pending"]), "attendance": [{"employee": store.employees[a.employee_id].name, "checked_in_at": a.checked_in_at, "anomaly": a.anomaly} for a in open_sessions]}


@router.get("/employees")
async def employees(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user); require(user, "hr_admin", "manager")
    visible = store.employees.values() if user.role == "hr_admin" else [e for e in store.employees.values() if e.department == user.department]
    return {"items": [asdict(e) | ({"salary": None} if user.role == "manager" else {}) for e in visible], "total": len(visible)}


@router.get("/attendance/today")
async def attendance_today(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    sessions = [item for item in store.attendance.values() if item.employee_id == user.id]
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
async def check_in(payload: CheckIn, idempotency_key: str = Header(...), x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user); require(user, "employee", "manager", "hr_admin")
    if idempotency_key in store.idempotency:
        return {"id": store.idempotency[idempotency_key], "idempotent": True}
    if any(a.employee_id == user.id and not a.checked_out_at for a in store.attendance.values()):
        raise HTTPException(409, "Anda masih memiliki sesi kehadiran yang terbuka")
    if not payload.selfie_captured:
        raise HTTPException(422, "Selfie kamera langsung wajib untuk kebijakan ini")
    distance = haversine_meters(payload.latitude, payload.longitude, -6.2000, 106.8166)
    anomaly = "outside_geofence" if distance > 300 + payload.accuracy_meters else ("low_accuracy" if payload.accuracy_meters > 100 else None)
    record = Attendance(str(uuid4()), user.id, datetime.now(UTC), payload.latitude, payload.longitude, payload.accuracy_meters, payload.agenda, anomaly)
    store.attendance[record.id] = record; store.idempotency[idempotency_key] = record.id; audit("attendance.check_in", user, record.id)
    return {"id": record.id, "checked_in_at": record.checked_in_at, "distance_meters": round(distance), "anomaly": anomaly, "agenda_count": len(payload.agenda)}


@router.post("/attendance/check-out")
async def check_out(payload: CheckOut, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    record = next((a for a in store.attendance.values() if a.employee_id == user.id and not a.checked_out_at), None)
    if not record: raise HTTPException(409, "Tidak ada sesi kehadiran terbuka")
    record.checked_out_at = datetime.now(UTC); record.summary = payload.summary; audit("attendance.check_out", user, record.id)
    return {"id": record.id, "checked_out_at": record.checked_out_at, "effective_hours": round((record.checked_out_at-record.checked_in_at).total_seconds()/3600, 2)}


@router.post("/leave-requests")
async def submit_leave(payload: LeaveInput, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    if payload.end < payload.start: raise HTTPException(422, "Tanggal selesai harus setelah tanggal mulai")
    if any(r.employee_id == user.id and r.status == "pending" and payload.start <= r.end and payload.end >= r.start for r in store.requests.values()): raise HTTPException(409, "Permohonan tumpang tindih")
    request = LeaveRequest(str(uuid4()), user.id, payload.start, payload.end, payload.reason); store.requests[request.id] = request; audit("leave.submitted", user, request.id)
    return asdict(request)


@router.get("/approvals")
async def approvals(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user); require(user, "manager", "hr_admin")
    items = list(store.requests.values()) if user.role == "hr_admin" else [r for r in store.requests.values() if store.employees[r.employee_id].department == user.department]
    return {"items": [asdict(r) | {"employee_name": store.employees[r.employee_id].name} for r in items]}


@router.post("/approvals/{request_id}")
async def decide(request_id: str, payload: ApprovalInput, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user); require(user, "manager", "hr_admin")
    request = store.requests.get(request_id)
    if not request: raise HTTPException(404, "Permohonan tidak ditemukan")
    if request.employee_id == user.id: raise HTTPException(403, "Persetujuan diri sendiri tidak diperbolehkan")
    if request.status != "pending": raise HTTPException(409, "Permohonan sudah diproses")
    request.status, request.approver_comment = payload.decision, payload.comment; audit("request." + payload.decision, user, request.id)
    return asdict(request)


@router.post("/payroll/runs")
async def payroll(payload: PayrollInput, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user); require(user, "hr_admin")
    rows=[]
    for employee in store.employees.values():
        gross=Decimal(employee.salary); deduction=(gross*Decimal("0.02")).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        rows.append({"employee": employee.name, "gross_rupiah": int(gross), "deductions_rupiah": int(deduction), "net_rupiah": int(gross-deduction)})
    audit("payroll.calculated", user, payload.month)
    return {"period": payload.month, "status": "draft", "calculation_version": "manual-components-v1", "items": rows, "disclaimer": "PPh 21 dan BPJS harus dikonfigurasi atau disesuaikan manual."}
