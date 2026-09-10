"""Functional Teamku vertical slices backed by a deterministic demo repository."""

from __future__ import annotations

import re
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt
from random import uniform
from secrets import token_urlsafe
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlencode, unquote, urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from movon_hr.core.mailer import reset_outbox, send_email
from movon_hr.core.policy_assistant import answer_question
from movon_hr.core.security import (
    generate_temporary_password,
    hash_password,
    needs_rehash,
    password_policy_error,
    verify_password,
)
from movon_hr.core.settings import settings
from movon_hr.core.tenancy import (
    DEMO_TENANT_ID,
    DEMO_TENANT_NAME,
    DEMO_TENANT_SLUG,
    bind_tenant,
    clear_registry,
    get_store,
    iter_stores,
    put_store,
    store,
)

router = APIRouter()
logger = logging.getLogger("movon_hr.calendar")
JAKARTA = ZoneInfo("Asia/Jakarta")

# Sessions expire after this idle-agnostic absolute lifetime.
SESSION_TTL = timedelta(hours=12)
# Login throttling: block an email after too many failures inside the window.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=15)
# Fields that must never be serialized to API clients.
SENSITIVE_EMPLOYEE_FIELDS = frozenset({"password_hash", "tenant_id"})


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
    password_hash: str = ""
    tenant_id: str = ""
    is_remote: bool = False
    work_location_id: str | None = "office-default"


@dataclass
class Session:
    token: str
    employee_id: str
    created_at: datetime
    expires_at: datetime
    tenant_id: str = ""


@dataclass
class Invitation:
    token: str
    tenant_id: str
    email: str
    name: str
    role: str
    department: str
    title: str
    salary: int
    invited_by: str
    expires_at: datetime
    accepted_at: datetime | None = None
    is_remote: bool = False
    work_location_id: str | None = None


@dataclass
class PasswordReset:
    token: str
    tenant_id: str
    employee_id: str
    expires_at: datetime
    used_at: datetime | None = None


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
    calendar_sync_status: str = "not_applicable"
    employee_calendar_event_id: str | None = None
    team_calendar_event_id: str | None = None


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
class LocationEvent:
    id: str
    employee_id: str
    attendance_id: str
    kind: str
    at: datetime
    lat: float | None = None
    lng: float | None = None
    accuracy: float | None = None
    distance_meters: float | None = None
    inside_geofence: bool | None = None
    anomaly: str | None = None
    due_at: datetime | None = None


@dataclass
class AlertReceipt:
    id: str
    employee_id: str
    kind: str
    local_date: date


@dataclass
class PolicySection:
    id: str
    heading: str
    body: str
    position: int


@dataclass
class PolicyDocument:
    id: str
    title: str
    category: str
    language: str
    effective_date: date
    expiry_date: date | None
    state: str = "draft"
    sections: list[PolicySection] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str = ""
    updated_by: str = ""


@dataclass
class PolicyAnswerAudit:
    id: str
    actor_id: str
    question: str
    cited_sections: list[dict]
    provider: str
    outcome: str
    suggested_action: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class OfficeLocation:
    id: str = "office-default"
    name: str = "Jakarta HQ"
    latitude: float = -6.2
    longitude: float = 106.8166
    radius_meters: float = 300
    reverify_enabled: bool = False
    reverify_count_per_day: int = 1
    reverify_window_start_minutes: int = 60
    reverify_window_end_minutes: int = 420
    alerts_enabled: bool = False
    clock_in_reminder_time: str = "09:15"
    clock_out_reminder_time: str = "18:15"
    max_open_hours: int = 10
    alert_managers: bool = False


@dataclass
class CalendarSettings:
    provider: str = ""
    connected: bool = False
    team_calendar_id: str = ""
    calendar_name: str = ""
    scope: str = "company"
    division: str = ""
    delivery_mode: str = "shared_and_email"
    refresh_token: str | None = None
    access_token: str | None = None
    token_expires_at: datetime | None = None


@dataclass
class DemoStore:
    tenant_id: str = DEMO_TENANT_ID
    tenant_name: str = DEMO_TENANT_NAME
    tenant_slug: str = DEMO_TENANT_SLUG
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    employees: dict[str, Employee] = field(default_factory=dict)
    attendance: dict[str, Attendance] = field(default_factory=dict)
    requests: dict[str, LeaveRequest] = field(default_factory=dict)
    payroll_runs: dict[str, PayrollRun] = field(default_factory=dict)
    notifications: dict[str, Notification] = field(default_factory=dict)
    sessions: dict[str, Session] = field(default_factory=dict)
    idempotency: dict[str, str] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)
    office: OfficeLocation = field(default_factory=OfficeLocation)
    office_locations: dict[str, OfficeLocation] = field(default_factory=dict)
    calendar: CalendarSettings = field(default_factory=CalendarSettings)
    invitations: dict[str, Invitation] = field(default_factory=dict)
    password_resets: dict[str, PasswordReset] = field(default_factory=dict)
    location_events: dict[str, LocationEvent] = field(default_factory=dict)
    alert_receipts: dict[str, AlertReceipt] = field(default_factory=dict)
    policies: dict[str, PolicyDocument] = field(default_factory=dict)
    policy_answer_audit: dict[str, PolicyAnswerAudit] = field(default_factory=dict)

# In-memory login throttle: email -> list of recent failed-attempt timestamps.
# Not persisted; a best-effort brute-force guard within a single process.
_login_attempts: dict[str, list[datetime]] = {}
_google_oauth_states: dict[str, tuple[str, str]] = {}

# Every demo account signs in with this password. Hashed once at import time so
# seeding stays fast even though tests reset the store frequently.
DEMO_PASSWORD = "Demo123!"
DEMO_PASSWORD_HASH = hash_password(DEMO_PASSWORD)


def reset_demo_store() -> None:
    """Restore the demo tenant and drop any other in-memory companies."""
    clear_registry()
    reset_outbox()
    demo = DemoStore(
        tenant_id=DEMO_TENANT_ID,
        tenant_name=DEMO_TENANT_NAME,
        tenant_slug=DEMO_TENANT_SLUG,
    )
    put_store(demo)
    bind_tenant(DEMO_TENANT_ID)
    people = [
        ("e-hr", "Nadia Putri", "hr@movon.test", "hr_admin", "Human Resources", "HR Lead", 12_000_000),
        ("e-manager", "Raka Pratama", "manager@movon.test", "manager", "Engineering", "Engineering Manager", 15_000_000),
        ("e-employee", "Sinta Lestari", "employee@movon.test", "employee", "Engineering", "Frontend Engineer", 8_000_000),
        ("e-fresh", "Rani Prasetyo", "fresh@movon.test", "employee", "Engineering", "QA Tester", 8_000_000),
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
        employee_id: Employee(
            employee_id, name, email, role, department, title, "active", salary,
            DEMO_PASSWORD_HASH,
            DEMO_TENANT_ID,
        )
        for employee_id, name, email, role, department, title, salary in people
    }
    jakarta_now = datetime.now(JAKARTA)
    store.attendance = {}
    store.location_events = {}
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
        event = LocationEvent(
            id=f"loc-seed-{index}",
            employee_id=employee_id,
            attendance_id=item.id,
            kind="check_in",
            at=checked_in,
            lat=-6.2,
            lng=106.8166,
            accuracy=18,
            distance_meters=0,
            inside_geofence=True,
            anomaly=item.anomaly,
        )
        store.location_events[event.id] = event
    store.employees["e-018"].is_remote = True
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
    store.office = OfficeLocation()
    store.office_locations = {store.office.id: store.office}
    store.invitations = {}
    store.password_resets = {}
    store.alert_receipts = {}
    store.policies = {}
    store.policy_answer_audit = {}
    _login_attempts.clear()


reset_demo_store()


def session_token_from(request: Request, header_token: str | None) -> str | None:
    return header_token or request.cookies.get(settings.session_cookie_name)


def actor(
    session_token: str | None,
    request: Request | None = None,
) -> Employee:
    token = session_token or (
        request.cookies.get(settings.session_cookie_name) if request is not None else None
    )
    if not token:
        raise HTTPException(401, "Sesi tidak valid")
    now = datetime.now(UTC)
    for tenant_store in iter_stores():
        session = tenant_store.sessions.get(token)
        if not session:
            continue
        if session.expires_at <= now:
            tenant_store.sessions.pop(session.token, None)
            raise HTTPException(401, "Sesi telah berakhir. Silakan masuk kembali.")
        employee = tenant_store.employees.get(session.employee_id)
        if not employee or employee.status != "active":
            raise HTTPException(401, "Sesi tidak valid")
        bind_tenant(tenant_store.tenant_id)
        if not employee.tenant_id:
            employee.tenant_id = tenant_store.tenant_id
        return employee
    raise HTTPException(401, "Sesi tidak valid")


def bind_from_token(token: str | None) -> None:
    """Bind the request to the tenant that owns ``token``, else the demo tenant."""
    if token:
        for tenant_store in iter_stores():
            if token in tenant_store.sessions:
                bind_tenant(tenant_store.tenant_id)
                return
    bind_tenant(DEMO_TENANT_ID)


def current_user(
    request: Request, x_demo_user: str | None = Header(default=None)
) -> Employee:
    return actor(session_token_from(request, x_demo_user))


def attach_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure or settings.environment == "production",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")


def tenant_payload(tenant_store: DemoStore | None = None, user: Employee | None = None) -> dict:
    if tenant_store is None and user and user.tenant_id:
        tenant_store = get_store(user.tenant_id)
    item = tenant_store or get_store()
    return {"id": item.tenant_id, "name": item.tenant_name, "slug": item.tenant_slug}


def find_employee_by_email(email: str) -> tuple[DemoStore, Employee] | None:
    needle = email.strip().lower()
    for tenant_store in iter_stores():
        for employee in tenant_store.employees.values():
            if employee.email.lower() == needle:
                return tenant_store, employee
    return None


def email_taken(email: str) -> bool:
    needle = email.strip().lower()
    if find_employee_by_email(needle):
        return True
    now = datetime.now(UTC)
    for tenant_store in iter_stores():
        for invitation in tenant_store.invitations.values():
            if (
                invitation.email.lower() == needle
                and invitation.accepted_at is None
                and invitation.expires_at > now
            ):
                return True
    return False


def slugify_company(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:40] or f"perusahaan-{uuid4().hex[:8]}"


def find_invitation(token: str) -> tuple[DemoStore, Invitation] | None:
    for tenant_store in iter_stores():
        invitation = tenant_store.invitations.get(token)
        if invitation:
            return tenant_store, invitation
    return None


def find_password_reset(token: str) -> tuple[DemoStore, PasswordReset] | None:
    for tenant_store in iter_stores():
        reset = tenant_store.password_resets.get(token)
        if reset:
            return tenant_store, reset
    return None


def app_url(path: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}{path}"


def auth_payload(user: Employee, token: str) -> dict:
    return {
        "user": public_employee(user),
        "access_token": token,
        "tenant": tenant_payload(user=user),
    }


def auth_response(user: Employee, token: str) -> JSONResponse:
    response = JSONResponse(auth_payload(user, token))
    attach_session_cookie(response, token)
    return response


def require(user: Employee, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Anda tidak memiliki izin untuk aksi ini")


def public_employee(employee: Employee, *, hide_salary: bool = False) -> dict:
    """Serialize an employee for API responses, never exposing secret fields."""
    data = {
        key: value
        for key, value in asdict(employee).items()
        if key not in SENSITIVE_EMPLOYEE_FIELDS
    }
    if hide_salary:
        data["salary"] = None
    location = current_office(employee) if not employee.is_remote else None
    data["work_mode"] = "field" if employee.is_remote else "office"
    data["work_location"] = office_payload(location) if location else None
    return data


def create_session(employee: Employee) -> Session:
    now = datetime.now(UTC)
    session = Session(
        token=token_urlsafe(32),
        employee_id=employee.id,
        created_at=now,
        expires_at=now + SESSION_TTL,
        tenant_id=get_store().tenant_id,
    )
    store.sessions[session.token] = session
    return session


def revoke_employee_sessions(employee_id: str, *, keep_token: str | None = None) -> None:
    """Invalidate every active session for an employee (optionally keep one)."""
    for token in [
        token
        for token, session in store.sessions.items()
        if session.employee_id == employee_id and token != keep_token
    ]:
        store.sessions.pop(token, None)


def register_failed_login(email: str) -> None:
    attempts = _login_attempts.setdefault(email, [])
    attempts.append(datetime.now(UTC))


def is_login_locked(email: str) -> bool:
    cutoff = datetime.now(UTC) - LOGIN_ATTEMPT_WINDOW
    attempts = [ts for ts in _login_attempts.get(email, []) if ts > cutoff]
    if attempts:
        _login_attempts[email] = attempts
    else:
        _login_attempts.pop(email, None)
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


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


def leave_recipients(request: LeaveRequest) -> list[Employee]:
    employee = store.employees[request.employee_id]
    recipients = [person for person in store.employees.values() if person.role == "manager" and person.department == employee.department]
    recipients.extend(person for person in store.employees.values() if person.role == "hr_admin" and person.status == "active")
    unique: dict[str, Employee] = {person.id: person for person in recipients}
    return list(unique.values())


def email_leave(recipients: list[Employee], subject: str, body: str) -> None:
    for recipient in recipients:
        if recipient.email:
            send_email(recipient.email, subject, body)


def sync_leave_calendar(request: LeaveRequest, employee: Employee) -> None:
    if store.calendar.provider != "google" or not store.calendar.connected or not store.calendar.team_calendar_id:
        request.calendar_sync_status = "skipped"
        return
    try:
        end_exclusive = request.end + timedelta(days=1)
        event = google_calendar_request(
            "POST",
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(store.calendar.team_calendar_id, safe='')}/events?sendUpdates=all",
            {
                "summary": f"Cuti · {employee.name}",
                "description": f"Permohonan cuti Teamku {request.id}.",
                "start": {"date": request.start.isoformat()},
                "end": {"date": end_exclusive.isoformat()},
                "attendees": [{"email": employee.email}],
                "transparency": "opaque",
            },
        )
        request.team_calendar_event_id = event.get("id")
        request.employee_calendar_event_id = None
        request.calendar_sync_status = "ok" if request.team_calendar_event_id else "failed"
    except Exception:
        logger.exception("Google Calendar event creation failed request_id=%s", request.id)
        request.calendar_sync_status = "failed"


def remove_leave_calendar(request: LeaveRequest) -> None:
    if request.team_calendar_event_id and store.calendar.provider == "google" and store.calendar.connected:
        try:
            google_calendar_request(
                "DELETE",
                f"https://www.googleapis.com/calendar/v3/calendars/{quote(store.calendar.team_calendar_id, safe='')}/events/{quote(request.team_calendar_event_id, safe='')}",
            )
            request.calendar_sync_status = "removed"
        except Exception:
            logger.exception("Google Calendar event deletion failed request_id=%s", request.id)
            request.calendar_sync_status = "failed"
        return
    request.calendar_sync_status = "removed"


GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"


def google_redirect_uri() -> str:
    return settings.google_redirect_uri or f"{settings.app_base_url.rstrip('/')}/api/v1/settings/calendar/google/callback"


def google_token_request(values: dict[str, str]) -> dict:
    request = UrlRequest(
        "https://oauth2.googleapis.com/token",
        data=urlencode(values).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        import json
        return json.loads(response.read())


def google_access_token() -> str:
    calendar = store.calendar
    if calendar.access_token and calendar.token_expires_at and datetime.now(UTC) < calendar.token_expires_at - timedelta(minutes=1):
        return calendar.access_token
    if not calendar.refresh_token or not settings.google_client_id or not settings.google_client_secret:
        raise ValueError("Google Calendar is not connected")
    tokens = google_token_request({
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": calendar.refresh_token,
        "grant_type": "refresh_token",
    })
    calendar.access_token = tokens["access_token"]
    calendar.token_expires_at = datetime.now(UTC) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    return calendar.access_token


def google_calendar_request(method: str, url: str, body: dict | None = None) -> dict:
    import json
    access_token = google_access_token()
    request = UrlRequest(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=15) as response:
        payload = response.read()
        return json.loads(payload) if payload else {}


DEFAULT_OFFICE_LATITUDE = -6.2
DEFAULT_OFFICE_LONGITUDE = 106.8166
DEFAULT_OFFICE_RADIUS_METERS = 300
# Keep aliases used by tests and seed data.
OFFICE_LATITUDE = DEFAULT_OFFICE_LATITUDE
OFFICE_LONGITUDE = DEFAULT_OFFICE_LONGITUDE
OFFICE_RADIUS_METERS = DEFAULT_OFFICE_RADIUS_METERS
# GPS uncertainty may expand the allowed radius slightly, but never enough to check in from home.
MAX_ACCURACY_CREDIT_METERS = 50
LOW_ACCURACY_METERS = 100


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    d_lat, d_lon = radians(lat2 - lat1), radians(lon2 - lon1)
    value = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * radius * asin(sqrt(value))


def current_office(employee: Employee | None = None) -> OfficeLocation:
    if employee and employee.work_location_id:
        return store.office_locations.get(employee.work_location_id, store.office)
    return store.office


def office_payload(office: OfficeLocation | None = None) -> dict:
    item = office or current_office()
    return {
        "id": item.id,
        "name": item.name,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "radius_meters": item.radius_meters,
        "reverify_enabled": item.reverify_enabled,
        "reverify_count_per_day": item.reverify_count_per_day,
        "reverify_window_start_minutes": item.reverify_window_start_minutes,
        "reverify_window_end_minutes": item.reverify_window_end_minutes,
        "alerts_enabled": item.alerts_enabled,
        "clock_in_reminder_time": item.clock_in_reminder_time,
        "clock_out_reminder_time": item.clock_out_reminder_time,
        "max_open_hours": item.max_open_hours,
        "alert_managers": item.alert_managers,
    }


def calendar_payload() -> dict:
    return {
        "provider": store.calendar.provider,
        "connected": store.calendar.connected,
        "team_calendar_id": store.calendar.team_calendar_id,
        "calendar_name": store.calendar.calendar_name,
        "scope": store.calendar.scope,
        "division": store.calendar.division,
        "delivery_mode": store.calendar.delivery_mode,
    }


def office_distance_meters(latitude: float, longitude: float, employee: Employee | None = None) -> float:
    office = current_office(employee)
    return haversine_meters(latitude, longitude, office.latitude, office.longitude)


def allowed_check_in_radius_meters(accuracy_meters: float, employee: Employee | None = None) -> float:
    return current_office(employee).radius_meters + min(max(accuracy_meters, 0), MAX_ACCURACY_CREDIT_METERS)


REVERIFY_GRACE_MINUTES = 15
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
ALERT_COPY = {
    "missed_clock_in": ("Belum clock-in", "Anda belum check-in hari ini."),
    "missed_clock_out": ("Sesi masih terbuka", "Sesi kehadiran Anda masih terbuka. Lakukan check-out."),
    "limit_reverify": (
        "Re-verifikasi terlewat",
        "Ada permintaan re-verifikasi lokasi yang belum diselesaikan.",
    ),
    "limit_geofence": (
        "Lokasi di luar area kantor",
        "Re-verifikasi lokasi tercatat di luar radius kantor.",
    ),
}


def validate_office_policy(data: dict) -> None:
    count = data["reverify_count_per_day"]
    if count not in {1, 2, 3}:
        raise HTTPException(422, "Jumlah re-verifikasi per hari harus 1, 2, atau 3")
    start = data["reverify_window_start_minutes"]
    end = data["reverify_window_end_minutes"]
    if not 0 <= start <= 1_440 or not 0 <= end <= 1_440:
        raise HTTPException(422, "Jendela re-verifikasi harus antara 0 dan 1440 menit")
    if end <= start:
        raise HTTPException(422, "Jendela akhir harus lebih besar dari jendela mulai")
    for key in ("clock_in_reminder_time", "clock_out_reminder_time"):
        if not TIME_PATTERN.fullmatch(str(data[key])):
            raise HTTPException(422, "Format jam pengingat harus HH:MM")
    hours = data["max_open_hours"]
    if hours < 1 or hours > 24:
        raise HTTPException(422, "Batas sesi terbuka harus antara 1 dan 24 jam")


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def jakarta_date(moment: datetime | None = None) -> date:
    value = moment or datetime.now(JAKARTA)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(JAKARTA).date()


def employee_sessions_on(employee_id: str, day: date) -> list[Attendance]:
    return [
        item
        for item in store.attendance.values()
        if item.employee_id == employee_id and jakarta_date(item.checked_in_at) == day
    ]


def has_approved_leave(employee_id: str, day: date) -> bool:
    return any(
        item.employee_id == employee_id
        and item.status == "approved"
        and item.start <= day <= item.end
        for item in store.requests.values()
    )


def location_events_for(attendance_id: str) -> list[LocationEvent]:
    return [item for item in store.location_events.values() if item.attendance_id == attendance_id]


def is_reverify_slot_open(event: LocationEvent) -> bool:
    return event.kind == "reverify" and event.lat is None and event.anomaly != "missed_reverify"


def record_location_event(**kwargs: object) -> LocationEvent:
    event = LocationEvent(id=str(uuid4()), **kwargs)  # type: ignore[arg-type]
    store.location_events[event.id] = event
    return event


def schedule_reverify_slots(record: Attendance, policy: OfficeLocation) -> None:
    count = policy.reverify_count_per_day
    start = policy.reverify_window_start_minutes
    span = max(policy.reverify_window_end_minutes - start, 1)
    for index in range(count):
        if index == 0:
            offset = start
        else:
            low = start + span * index / count
            high = start + span * (index + 1) / count
            offset = uniform(low, high)
        due_at = record.checked_in_at + timedelta(minutes=offset)
        record_location_event(
            employee_id=record.employee_id,
            attendance_id=record.id,
            kind="reverify",
            at=due_at,
            due_at=due_at,
        )


def expire_missed_reverify_slots(record: Attendance | None = None) -> None:
    now = datetime.now(UTC)
    items = location_events_for(record.id) if record else list(store.location_events.values())
    for event in items:
        if not is_reverify_slot_open(event) or event.due_at is None:
            continue
        if now >= event.due_at + timedelta(minutes=REVERIFY_GRACE_MINUTES):
            event.anomaly = "missed_reverify"
            event.at = now


def pending_reverify_for(record: Attendance) -> LocationEvent | None:
    expire_missed_reverify_slots(record)
    now = datetime.now(UTC)
    open_slots = [
        event
        for event in location_events_for(record.id)
        if is_reverify_slot_open(event) and event.due_at and event.due_at <= now
    ]
    if not open_slots:
        return None
    return min(open_slots, key=lambda item: item.due_at or item.at)


def pending_payload(event: LocationEvent | None) -> dict | None:
    if not event:
        return None
    return {"id": event.id, "due_at": event.due_at, "kind": event.kind}


def location_event_payload(event: LocationEvent) -> dict:
    maps_url = (
        f"https://www.google.com/maps?q={event.lat},{event.lng}"
        if event.lat is not None and event.lng is not None
        else None
    )
    return {
        "id": event.id,
        "employee_id": event.employee_id,
        "attendance_id": event.attendance_id,
        "kind": event.kind,
        "at": event.at,
        "lat": event.lat,
        "lng": event.lng,
        "accuracy": event.accuracy,
        "distance_meters": event.distance_meters,
        "inside_geofence": event.inside_geofence,
        "anomaly": event.anomaly,
        "due_at": event.due_at,
        "maps_url": maps_url,
    }


def visible_or_404(user: Employee, employee_id: str) -> Employee:
    employee = store.employees.get(employee_id)
    if not employee or employee.id not in {item.id for item in visible_employees(user)}:
        raise HTTPException(404, "Karyawan tidak ditemukan")
    return employee


def alert_receipt_key(kind: str, employee_id: str, day: date) -> str:
    return f"{kind}:{employee_id}:{day.isoformat()}"


def emit_attendance_alert(kind: str, employee: Employee, policy: OfficeLocation) -> None:
    today = jakarta_date()
    key = alert_receipt_key(kind, employee.id, today)
    if key in store.alert_receipts:
        return
    title, detail = ALERT_COPY[kind]
    store.alert_receipts[key] = AlertReceipt(key, employee.id, kind, today)
    notify(employee.id, title, detail, "/app/attendance/today")
    if kind in {"missed_clock_in", "missed_clock_out"}:
        send_email(
            employee.email,
            f"{title} — Teamku",
            (
                f"Halo {employee.name},\n\n{detail}\n"
                f"Buka presensi: {app_url('/app/attendance/today')}\n"
            ),
        )
    if not policy.alert_managers:
        return
    for recipient in store.employees.values():
        if recipient.id == employee.id or recipient.status != "active":
            continue
        same_manager = recipient.role == "manager" and recipient.department == employee.department
        if recipient.role == "hr_admin" or same_manager:
            notify(recipient.id, title, f"{employee.name}: {detail}", "/app/attendance/today")


def evaluate_attendance_alerts() -> None:
    policy = current_office()
    if not policy.alerts_enabled:
        return
    now = datetime.now(JAKARTA)
    today = now.date()
    reminder_in = datetime.combine(today, parse_hhmm(policy.clock_in_reminder_time), JAKARTA)
    reminder_out = datetime.combine(today, parse_hhmm(policy.clock_out_reminder_time), JAKARTA)

    for employee in store.employees.values():
        if employee.status != "active":
            continue
        sessions = employee_sessions_on(employee.id, today)
        open_session = next((item for item in sessions if not item.checked_out_at), None)
        if open_session:
            expire_missed_reverify_slots(open_session)

        if now >= reminder_in and not sessions and not has_approved_leave(employee.id, today):
            emit_attendance_alert("missed_clock_in", employee, policy)

        if open_session:
            hours_open = (datetime.now(UTC) - open_session.checked_in_at).total_seconds() / 3600
            if now >= reminder_out or hours_open >= policy.max_open_hours:
                emit_attendance_alert("missed_clock_out", employee, policy)

        if employee.is_remote:
            continue
        events = [
            item
            for item in store.location_events.values()
            if item.employee_id == employee.id and jakarta_date(item.at) == today
        ]
        if any(item.anomaly == "missed_reverify" for item in events):
            emit_attendance_alert("limit_reverify", employee, policy)
        if any(item.anomaly == "outside_geofence" for item in events):
            emit_attendance_alert("limit_geofence", employee, policy)


def _valid_coordinates(latitude: float, longitude: float) -> tuple[float, float] | None:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return round(latitude, 6), round(longitude, 6)


def parse_google_maps_location(text: str) -> tuple[float, float] | None:
    value = text.strip()
    if not value:
        return None

    raw = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", value)
    if raw:
        return _valid_coordinates(float(raw.group(1)), float(raw.group(2)))

    pin = re.search(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", value)
    if pin:
        return _valid_coordinates(float(pin.group(1)), float(pin.group(2)))

    at = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", value)
    if at:
        return _valid_coordinates(float(at.group(1)), float(at.group(2)))

    try:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        query = parse_qs(parsed.query)
        for key in ("q", "query", "ll", "center", "destination", "daddr"):
            if key not in query:
                continue
            match = re.search(
                r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)",
                unquote(query[key][0]),
            )
            if match:
                return _valid_coordinates(float(match.group(1)), float(match.group(2)))
    except ValueError:
        pass

    match = re.search(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", value)
    if match:
        return _valid_coordinates(float(match.group(1)), float(match.group(2)))
    return None


def resolve_maps_url(url: str) -> str:
    """Follow short Google Maps redirects so coordinates can be parsed from the final URL."""
    request = UrlRequest(
        url,
        headers={"User-Agent": "TeamkuOfficeSettings/1.0"},
        method="GET",
    )
    with urlopen(request, timeout=8) as response:
        return str(response.geturl())


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


def leave_balance(employee_id: str) -> dict:
    approved_days = sum(
        working_days(item.start, item.end)
        for item in store.requests.values()
        if item.employee_id == employee_id and item.status == "approved"
    )
    return {"annual_days": 12, "used_days": approved_days, "remaining_days": max(12 - approved_days, 0)}


def policy_payload(policy: PolicyDocument) -> dict:
    return {
        "id": policy.id, "title": policy.title, "category": policy.category, "language": policy.language,
        "effective_date": policy.effective_date, "expiry_date": policy.expiry_date, "state": policy.state,
        "sections": [asdict(item) for item in sorted(policy.sections, key=lambda item: item.position)],
        "created_at": policy.created_at, "updated_at": policy.updated_at,
        "created_by": policy.created_by, "updated_by": policy.updated_by,
    }


def validate_policy(title: str, sections: list[PolicySection]) -> None:
    if not title.strip() or not any(item.heading.strip() and item.body.strip() for item in sections):
        raise HTTPException(422, "Kebijakan memerlukan judul dan setidaknya satu bagian yang terisi")


class Login(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class Signup(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=3, max_length=40)
    admin_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=150)
    password: str = Field(min_length=8, max_length=128)


class InviteInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=150)
    department: str = Field(min_length=2, max_length=100)
    role: str = Field(pattern="^(employee|manager|hr_admin)$")
    title: str = Field(default="Staff", min_length=2, max_length=100)
    salary: int = Field(default=8_000_000, ge=0, le=10_000_000_000)
    is_remote: bool = False
    work_location_id: str | None = None


class AcceptInvite(BaseModel):
    token: str = Field(min_length=8, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, min_length=2, max_length=100)


class ForgotPassword(BaseModel):
    email: str = Field(min_length=5, max_length=150)


class ResetPassword(BaseModel):
    token: str = Field(min_length=8, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class CheckIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float = Field(ge=0, le=10_000)
    selfie_captured: bool
    location_share_approved: bool
    agenda: list[dict] = Field(min_length=1, max_length=5)


class CheckOut(BaseModel):
    summary: str = Field(min_length=4, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0, le=10_000)


class ReverifyInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float = Field(ge=0, le=10_000)
    selfie_captured: bool


class OfficeSettingsInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(ge=50, le=5_000)
    reverify_enabled: bool | None = None
    reverify_count_per_day: int | None = Field(default=None, ge=1, le=3)
    reverify_window_start_minutes: int | None = Field(default=None, ge=0, le=1_440)
    reverify_window_end_minutes: int | None = Field(default=None, ge=0, le=1_440)
    alerts_enabled: bool | None = None
    clock_in_reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    clock_out_reminder_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    max_open_hours: int | None = Field(default=None, ge=1, le=24)
    alert_managers: bool | None = None


class WorkLocationInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(default=300, ge=50, le=5_000)


class CalendarSettingsInput(BaseModel):
    provider: str = Field(pattern="^(google|microsoft)$")
    team_calendar_id: str = Field(min_length=2, max_length=300)
    connected: bool = False
    calendar_name: str = Field(default="Kalender perusahaan", max_length=120)
    scope: str = Field(default="company", pattern="^(company|division)$")
    division: str = Field(default="", max_length=100)
    delivery_mode: str = Field(default="shared_and_email", pattern="^(shared|shared_and_email)$")


class MapsUrlInput(BaseModel):
    url: str = Field(min_length=4, max_length=2_000)


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
    # Optional initial password; when omitted a temporary one is generated.
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_remote: bool = False
    work_location_id: str | None = None


class EmployeeUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(active|suspended|terminated)$")
    is_remote: bool | None = None
    work_location_id: str | None = None


class PolicySectionInput(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    heading: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=10_000)


class PolicyInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(default="general", min_length=2, max_length=80)
    language: str = Field(default="id", pattern="^(id|en)$")
    effective_date: date
    expiry_date: date | None = None
    sections: list[PolicySectionInput] = Field(min_length=1, max_length=50)


class PolicyQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=800)


@router.post("/auth/signup")
async def signup(payload: Signup) -> JSONResponse:
    email = payload.email.strip().lower()
    policy_error = password_policy_error(payload.password)
    if policy_error:
        raise HTTPException(422, policy_error)
    if email_taken(email):
        raise HTTPException(409, "Email kerja sudah digunakan")
    requested_slug = payload.slug.strip().lower() if payload.slug else slugify_company(payload.company_name)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", requested_slug):
        raise HTTPException(422, "Slug perusahaan hanya boleh huruf, angka, dan tanda hubung")
    if any(item.tenant_slug == requested_slug for item in iter_stores()):
        raise HTTPException(409, "Slug perusahaan sudah digunakan")
    tenant_id = f"t-{uuid4().hex[:12]}"
    company = DemoStore(
        tenant_id=tenant_id,
        tenant_name=payload.company_name.strip(),
        tenant_slug=requested_slug,
        office=OfficeLocation(name="Kantor Pusat"),
    )
    put_store(company)
    bind_tenant(tenant_id)
    admin = Employee(
        id=f"e-{uuid4().hex[:8]}",
        name=payload.admin_name.strip(),
        email=email,
        role="hr_admin",
        department="Human Resources",
        title="HR Admin",
        status="active",
        salary=0,
        password_hash=hash_password(payload.password),
        tenant_id=tenant_id,
    )
    store.employees[admin.id] = admin
    session = create_session(admin)
    audit("auth.signup", admin, company.tenant_id)
    return auth_response(admin, session.token)


@router.post("/auth/login")
async def login(payload: Login) -> JSONResponse:
    email = payload.email.strip().lower()
    if is_login_locked(email):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Terlalu banyak percobaan masuk. Coba lagi dalam beberapa menit.",
        )
    found = find_employee_by_email(email)
    user = found[1] if found else None
    if found:
        bind_tenant(found[0].tenant_id)
    # Always run verification against a real-looking hash to reduce timing/user
    # enumeration signals, then apply the same generic error to every failure.
    reference_hash = user.password_hash if user else DEMO_PASSWORD_HASH
    password_ok = verify_password(payload.password, reference_hash)
    if not user or not password_ok or user.status != "active":
        register_failed_login(email)
        raise HTTPException(401, "Email atau kata sandi salah")

    _login_attempts.pop(email, None)
    # Transparently upgrade legacy/weak hashes on successful login.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    session = create_session(user)
    audit("auth.login", user, user.id)
    return auth_response(user, session.token)


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    x_demo_user: str | None = Header(default=None),
) -> dict:
    token = session_token_from(request, x_demo_user)
    user = actor(token)
    store.sessions.pop(token or "", None)
    audit("auth.logout", user, user.id)
    clear_session_cookie(response)
    return {"ok": True}


@router.post("/invites")
async def create_invite(
    payload: InviteInput,
    request: Request,
    x_demo_user: str | None = Header(default=None),
) -> dict:
    user = current_user(request, x_demo_user)
    require(user, "hr_admin")
    bind_tenant(user.tenant_id or get_store().tenant_id)
    email = payload.email.strip().lower()
    if email_taken(email):
        raise HTTPException(409, "Email kerja sudah digunakan")
    invitation = Invitation(
        token=token_urlsafe(24),
        tenant_id=get_store().tenant_id,
        email=email,
        name=payload.name.strip(),
        role=payload.role,
        department=payload.department.strip(),
        title=payload.title.strip(),
        salary=payload.salary,
        invited_by=user.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        is_remote=payload.is_remote,
        work_location_id=payload.work_location_id,
    )
    store.invitations[invitation.token] = invitation
    invite_url = app_url(f"/invite?token={invitation.token}")
    send_email(
        email,
        f"Undangan Teamku — {get_store().tenant_name}",
        (
            f"Halo {invitation.name},\n\n"
            f"{user.name} mengundang Anda bergabung di {get_store().tenant_name}.\n"
            f"Aktifkan akun: {invite_url}\n"
            "Undangan berlaku 7 hari.\n"
        ),
    )
    audit("invite.created", user, invitation.email)
    return {
        "email": invitation.email,
        "expires_at": invitation.expires_at,
        "invite_url": invite_url,
    }


@router.get("/invites/{token}")
async def preview_invite(token: str) -> dict:
    found = find_invitation(token)
    if not found:
        raise HTTPException(404, "Undangan tidak ditemukan")
    tenant_store, invitation = found
    if invitation.accepted_at or invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(410, "Undangan sudah tidak berlaku")
    return {
        "email": invitation.email,
        "name": invitation.name,
        "company": tenant_store.tenant_name,
        "role": invitation.role,
        "department": invitation.department,
        "title": invitation.title,
    }


@router.post("/auth/accept-invite")
async def accept_invite(payload: AcceptInvite) -> JSONResponse:
    found = find_invitation(payload.token)
    if not found:
        raise HTTPException(404, "Undangan tidak ditemukan")
    tenant_store, invitation = found
    if invitation.accepted_at or invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(410, "Undangan sudah tidak berlaku")
    policy_error = password_policy_error(payload.password)
    if policy_error:
        raise HTTPException(422, policy_error)
    if find_employee_by_email(invitation.email):
        raise HTTPException(409, "Email kerja sudah digunakan")
    bind_tenant(tenant_store.tenant_id)
    employee = Employee(
        id=f"e-{uuid4().hex[:8]}",
        name=(payload.name or invitation.name).strip(),
        email=invitation.email,
        role=invitation.role,
        department=invitation.department,
        title=invitation.title,
        status="active",
        salary=invitation.salary,
        password_hash=hash_password(payload.password),
        tenant_id=tenant_store.tenant_id,
        is_remote=invitation.is_remote,
        work_location_id=invitation.work_location_id,
    )
    store.employees[employee.id] = employee
    invitation.accepted_at = datetime.now(UTC)
    session = create_session(employee)
    notify(employee.id, "Akun Anda aktif", "Undangan sudah diterima. Selamat datang.", "/app/overview")
    audit("invite.accepted", employee, invitation.email)
    return auth_response(employee, session.token)


@router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPassword) -> dict:
    email = payload.email.strip().lower()
    found = find_employee_by_email(email)
    if found and found[1].status == "active":
        tenant_store, user = found
        bind_tenant(tenant_store.tenant_id)
        reset = PasswordReset(
            token=token_urlsafe(24),
            tenant_id=tenant_store.tenant_id,
            employee_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        store.password_resets[reset.token] = reset
        reset_url = app_url(f"/reset-password?token={reset.token}")
        send_email(
            email,
            "Atur ulang kata sandi Teamku",
            (
                f"Halo {user.name},\n\n"
                f"Gunakan tautan ini untuk mengatur ulang kata sandi: {reset_url}\n"
                "Tautan berlaku 1 jam. Abaikan email ini jika Anda tidak memintanya.\n"
            ),
        )
        audit("auth.password_reset_requested", user, user.id)
    return {"ok": True}


@router.post("/auth/reset-password")
async def reset_password(payload: ResetPassword) -> JSONResponse:
    found = find_password_reset(payload.token)
    if not found:
        raise HTTPException(404, "Tautan atur ulang tidak valid")
    tenant_store, reset = found
    if reset.used_at or reset.expires_at <= datetime.now(UTC):
        raise HTTPException(410, "Tautan atur ulang sudah tidak berlaku")
    policy_error = password_policy_error(payload.password)
    if policy_error:
        raise HTTPException(422, policy_error)
    bind_tenant(tenant_store.tenant_id)
    user = store.employees.get(reset.employee_id)
    if not user or user.status != "active":
        raise HTTPException(404, "Tautan atur ulang tidak valid")
    user.password_hash = hash_password(payload.password)
    reset.used_at = datetime.now(UTC)
    revoke_employee_sessions(user.id)
    session = create_session(user)
    audit("auth.password_reset", user, user.id)
    return auth_response(user, session.token)


@router.post("/auth/change-password")
async def change_password(
    payload: ChangePassword,
    request: Request,
    x_demo_user: str | None = Header(default=None),
) -> dict:
    token = session_token_from(request, x_demo_user)
    user = actor(token)
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(401, "Kata sandi saat ini salah")
    if payload.new_password == payload.current_password:
        raise HTTPException(422, "Kata sandi baru harus berbeda dari kata sandi lama")
    policy_error = password_policy_error(payload.new_password)
    if policy_error:
        raise HTTPException(422, policy_error)
    user.password_hash = hash_password(payload.new_password)
    # Force re-login on other devices; keep the current session active.
    revoke_employee_sessions(user.id, keep_token=token)
    audit("auth.password_changed", user, user.id)
    return {"ok": True}


@router.get("/me")
async def me(request: Request, x_demo_user: str | None = Header(default=None)) -> dict:
    user = current_user(request, x_demo_user)
    return {"user": public_employee(user), "tenant": tenant_payload(user=user)}


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
    present_ids = {item.employee_id for item in sessions}
    leave_today_ids = {
        item.employee_id for item in store.requests.values()
        if item.status == "approved" and item.start <= today <= item.end and item.employee_id in employee_ids
    }
    absent_ids = employee_ids - present_ids - leave_today_ids
    late_ids = {
        item.employee_id for item in sessions
        if item.checked_in_at.astimezone(JAKARTA).time() >= time(9, 0)
    }
    return {
        "current_user": public_employee(user),
        "headcount": len(employees),
        "present": len(present_ids),
        "absent": len(absent_ids),
        "on_leave": len(leave_today_ids),
        "late": len(late_ids),
        "attendance_rate": round(len(present_ids) / len(employees) * 100) if employees else 0,
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
    hide_salary = user.role == "manager"
    items = [public_employee(employee, hide_salary=hide_salary) for employee in visible]
    return {"items": items, "total": len(items)}


@router.get("/employees/{employee_id}")
async def get_employee(
    employee_id: str, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    employee = visible_or_404(user, employee_id)
    hide_salary = user.role == "manager"
    return public_employee(employee, hide_salary=hide_salary)


@router.get("/employees/{employee_id}/location-history")
async def employee_location_history(
    employee_id: str, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "manager", "hr_admin")
    employee = visible_or_404(user, employee_id)
    events = [
        item for item in store.location_events.values() if item.employee_id == employee.id
    ]
    events.sort(key=lambda item: item.at)
    return {
        "employee_id": employee.id,
        "items": [location_event_payload(item) for item in events],
    }


@router.post("/employees")
async def create_employee(
    payload: EmployeeInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    if email_taken(payload.email):
        raise HTTPException(409, "Email kerja sudah digunakan")
    data = payload.model_dump()
    raw_password = data.pop("password", None)
    temporary_password: str | None = None
    if raw_password is None:
        raw_password = temporary_password = generate_temporary_password()
    else:
        policy_error = password_policy_error(raw_password)
        if policy_error:
            raise HTTPException(422, policy_error)
    employee = Employee(
        id=f"e-{uuid4().hex[:8]}",
        **data,
        password_hash=hash_password(raw_password),
        tenant_id=get_store().tenant_id,
    )
    store.employees[employee.id] = employee
    audit("employee.created", user, employee.id)
    notify(employee.id, "Akun Anda siap", "Profil dibuat oleh HR.", "/app/overview")
    response = public_employee(employee)
    # Returned once so HR can share it; never stored in plain text.
    if temporary_password is not None:
        response["temporary_password"] = temporary_password
    return response


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
    if payload.status is not None:
        if employee.id == user.id and payload.status != "active":
            raise HTTPException(409, "Anda tidak dapat menonaktifkan akun sendiri")
        employee.status = payload.status
        # Deactivated accounts must lose any active sessions immediately.
        if payload.status != "active":
            revoke_employee_sessions(employee.id)
        audit("employee.status_changed", user, employee.id)
    if payload.is_remote is not None:
        employee.is_remote = payload.is_remote
        audit("employee.remote_changed", user, employee.id)
    if payload.work_location_id is not None:
        if payload.work_location_id not in store.office_locations:
            raise HTTPException(422, "Lokasi kerja tidak ditemukan")
        employee.work_location_id = payload.work_location_id
        employee.is_remote = False
        audit("employee.location_changed", user, employee.id)
    return public_employee(employee)


@router.get("/settings/locations")
async def list_work_locations(x_demo_user: str | None = Header(default=None)) -> dict:
    actor(x_demo_user)
    if not store.office_locations:
        store.office_locations = {store.office.id: store.office}
    return {"items": [office_payload(item) for item in store.office_locations.values()]}


@router.post("/settings/locations")
async def create_work_location(payload: WorkLocationInput, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    location = OfficeLocation(id=f"location-{uuid4().hex[:8]}", **payload.model_dump())
    store.office_locations[location.id] = location
    audit("settings.location_created", user, location.id)
    return office_payload(location)


@router.get("/settings/office")
async def get_office_settings(x_demo_user: str | None = Header(default=None)) -> dict:
    actor(x_demo_user)
    return office_payload()


@router.put("/settings/office")
async def update_office_settings(
    payload: OfficeSettingsInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    current = asdict(store.office)
    current.update(payload.model_dump(exclude_unset=True))
    validate_office_policy(current)
    store.office = OfficeLocation(**current)
    audit("settings.office_updated", user, store.office.name)
    return office_payload()


@router.get("/settings/calendar")
async def get_calendar_settings(x_demo_user: str | None = Header(default=None)) -> dict:
    actor(x_demo_user)
    return calendar_payload()


@router.put("/settings/calendar")
async def update_calendar_settings(
    payload: CalendarSettingsInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    current = store.calendar
    store.calendar = CalendarSettings(
        provider=payload.provider,
        connected=payload.connected,
        team_calendar_id=payload.team_calendar_id.strip(),
        calendar_name=payload.calendar_name.strip() or "Kalender perusahaan",
        scope=payload.scope,
        division=payload.division.strip(),
        delivery_mode=payload.delivery_mode,
        refresh_token=current.refresh_token,
        access_token=current.access_token,
        token_expires_at=current.token_expires_at,
    )
    audit("settings.calendar_updated", user, store.calendar.team_calendar_id)
    return calendar_payload()


@router.get("/settings/calendar/google/start")
async def start_google_calendar(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    if not settings.google_client_id:
        raise HTTPException(503, "Google Calendar belum dikonfigurasi oleh administrator sistem")
    state = token_urlsafe(32)
    _google_oauth_states[state] = (store.tenant_id, user.id)
    query = urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": GOOGLE_CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    return {"authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}"}


@router.get("/settings/calendar/google/callback")
async def google_calendar_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> Response:
    if error or not code or not state:
        return Response("Google Calendar connection was cancelled.", status_code=400)
    context = _google_oauth_states.pop(state, None)
    if not context or not settings.google_client_id or not settings.google_client_secret:
        return Response("Google Calendar connection expired or is not configured.", status_code=400)
    tenant_id, _ = context
    try:
        tokens = google_token_request({
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        })
    except Exception:
        return Response("Google Calendar token exchange failed.", status_code=502)
    if not tokens.get("access_token"):
        return Response("Google Calendar did not return an access token.", status_code=502)
    tenant_store = get_store(tenant_id)
    tenant_store.calendar.provider = "google"
    tenant_store.calendar.connected = True
    tenant_store.calendar.access_token = tokens["access_token"]
    tenant_store.calendar.refresh_token = tokens.get("refresh_token") or tenant_store.calendar.refresh_token
    tenant_store.calendar.token_expires_at = datetime.now(UTC) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    return Response(status_code=302, headers={"Location": f"{settings.app_base_url.rstrip('/')}/app/settings?calendar=connected"})


@router.get("/settings/calendar/google/calendars")
async def google_calendars(x_demo_user: str | None = Header(default=None)) -> dict:
    actor_user = actor(x_demo_user)
    require(actor_user, "hr_admin")
    calendar = store.calendar
    if not calendar.access_token:
        raise HTTPException(409, "Hubungkan akun Google terlebih dahulu")
    try:
        data = google_calendar_request("GET", "https://www.googleapis.com/calendar/v3/users/me/calendarList?minAccessRole=writer")
    except Exception as error:
        raise HTTPException(502, "Daftar kalender Google tidak dapat diambil") from error
    return {"items": [{"id": item["id"], "name": item.get("summary") or item["id"], "primary": item.get("primary", False)} for item in data.get("items", [])]}


@router.post("/settings/office/from-maps-url")
async def office_from_maps_url(
    payload: MapsUrlInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    source = payload.url.strip()
    resolved = source
    host = urlparse(source if "://" in source else f"https://{source}").hostname or ""
    if host.endswith(("goo.gl", "app.goo.gl")):
        try:
            resolved = resolve_maps_url(source if "://" in source else f"https://{source}")
        except (URLError, TimeoutError, ValueError) as error:
            raise HTTPException(
                422,
                "Tautan singkat Google Maps tidak dapat dibuka. Salin URL lengkap dari bilah alamat setelah membuka tautan.",
            ) from error
    coords = parse_google_maps_location(resolved) or parse_google_maps_location(source)
    if not coords:
        raise HTTPException(
            422,
            "Koordinat tidak ditemukan. Tempel tautan Google Maps (Share) atau teks seperti -6.2, 106.8166.",
        )
    latitude, longitude = coords
    audit("settings.office_maps_parsed", user, f"{latitude},{longitude}")
    return {
        "latitude": latitude,
        "longitude": longitude,
        "resolved_url": resolved,
        "maps_url": f"https://www.google.com/maps?q={latitude},{longitude}",
    }


def _policy_sections(payload: PolicyInput) -> list[PolicySection]:
    return [
        PolicySection(item.id or f"section-{index + 1}", item.heading.strip(), item.body.strip(), index)
        for index, item in enumerate(payload.sections)
    ]


@router.get("/policies")
async def list_policies(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    return {"items": [policy_payload(item) for item in sorted(store.policies.values(), key=lambda p: p.updated_at, reverse=True)]}


@router.post("/policies")
async def create_policy(payload: PolicyInput, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    if payload.expiry_date and payload.expiry_date < payload.effective_date:
        raise HTTPException(422, "Tanggal berakhir harus setelah tanggal berlaku")
    sections = _policy_sections(payload)
    validate_policy(payload.title, sections)
    item = PolicyDocument(
        id=f"policy-{uuid4().hex[:12]}", title=payload.title.strip(), category=payload.category.strip(),
        language=payload.language, effective_date=payload.effective_date, expiry_date=payload.expiry_date,
        sections=sections, created_by=user.id, updated_by=user.id,
    )
    store.policies[item.id] = item
    audit("policy.created", user, item.id)
    return policy_payload(item)


@router.put("/policies/{policy_id}")
async def update_policy(policy_id: str, payload: PolicyInput, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    item = store.policies.get(policy_id)
    if not item:
        raise HTTPException(404, "Kebijakan tidak ditemukan")
    if payload.expiry_date and payload.expiry_date < payload.effective_date:
        raise HTTPException(422, "Tanggal berakhir harus setelah tanggal berlaku")
    sections = _policy_sections(payload)
    validate_policy(payload.title, sections)
    item.title, item.category, item.language = payload.title.strip(), payload.category.strip(), payload.language
    item.effective_date, item.expiry_date, item.sections = payload.effective_date, payload.expiry_date, sections
    item.updated_at, item.updated_by = datetime.now(UTC), user.id
    audit("policy.updated", user, item.id)
    return policy_payload(item)


@router.post("/policies/{policy_id}/publish")
async def publish_policy(policy_id: str, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    item = store.policies.get(policy_id)
    if not item:
        raise HTTPException(404, "Kebijakan tidak ditemukan")
    validate_policy(item.title, item.sections)
    item.state, item.updated_at, item.updated_by = "published", datetime.now(UTC), user.id
    audit("policy.published", user, item.id)
    return policy_payload(item)


@router.post("/policies/{policy_id}/archive")
async def archive_policy(policy_id: str, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    require(user, "hr_admin")
    item = store.policies.get(policy_id)
    if not item:
        raise HTTPException(404, "Kebijakan tidak ditemukan")
    item.state, item.updated_at, item.updated_by = "archived", datetime.now(UTC), user.id
    audit("policy.archived", user, item.id)
    return policy_payload(item)


@router.post("/policy-assistant/questions")
async def policy_question(payload: PolicyQuestion, x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    facts = [{"type": "leave_balance", "label": "Sisa cuti tahunan", "value": leave_balance(user.id)["remaining_days"]}]
    response, outcome = answer_question(
        policies=list(store.policies.values()), question=payload.question.strip(), today=jakarta_date(), facts=facts
    )
    receipt = PolicyAnswerAudit(
        id=str(uuid4()), actor_id=user.id, question=payload.question.strip()[:800],
        cited_sections=[{"policy_id": item["policy_id"], "section_id": item["section_id"]} for item in response["citations"]],
        provider="fake-policy-provider-v1", outcome=outcome, suggested_action=response["suggested_action"]["type"],
    )
    store.policy_answer_audit[receipt.id] = receipt
    audit("policy_assistant.answered", user, receipt.id)
    return response


@router.get("/attendance/today")
async def attendance_today(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    evaluate_attendance_alerts()
    today = jakarta_date()
    sessions = employee_sessions_on(user.id, today)
    if not sessions:
        return {
            "state": "not_checked_in",
            "session": None,
            "pending_reverification": None,
            "is_remote": user.is_remote,
        }
    latest = max(sessions, key=lambda item: item.checked_in_at)
    state = "completed" if latest.checked_out_at else "checked_in"
    pending = None if latest.checked_out_at else pending_reverify_for(latest)
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
        "pending_reverification": pending_payload(pending),
        "is_remote": user.is_remote,
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
    if not payload.location_share_approved:
        raise HTTPException(422, "Persetujuan berbagi lokasi diperlukan untuk check-in")
    distance = office_distance_meters(payload.latitude, payload.longitude, user)
    allowed_radius = allowed_check_in_radius_meters(payload.accuracy_meters, user)
    office = current_office(user)
    if not user.is_remote and distance > allowed_radius:
        raise HTTPException(
            403,
            (
                f"Check-in ditolak. Anda berada sekitar {round(distance)} m dari kantor. "
                f"Presensi hanya diizinkan dalam radius {round(office.radius_meters)} m dari {office.name}."
            ),
        )
    anomaly = "low_accuracy" if payload.accuracy_meters > LOW_ACCURACY_METERS else None
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
    record_location_event(
        employee_id=user.id,
        attendance_id=record.id,
        kind="check_in",
        at=record.checked_in_at,
        lat=payload.latitude,
        lng=payload.longitude,
        accuracy=payload.accuracy_meters,
        distance_meters=round(distance),
        inside_geofence=distance <= allowed_radius,
        anomaly=anomaly,
    )
    if office.reverify_enabled and not user.is_remote:
        schedule_reverify_slots(record, office)
    audit("attendance.check_in", user, record.id)
    return {
        "id": record.id,
        "checked_in_at": record.checked_in_at,
        "distance_meters": round(distance),
        "allowed_radius_meters": round(allowed_radius),
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
    expire_missed_reverify_slots(record)
    for event in location_events_for(record.id):
        if is_reverify_slot_open(event):
            event.anomaly = "missed_reverify"
            event.at = datetime.now(UTC)
    record.checked_out_at = datetime.now(UTC)
    record.summary = payload.summary
    checkout_distance = None
    checkout_inside = None
    if payload.latitude is not None and payload.longitude is not None:
        checkout_distance = office_distance_meters(payload.latitude, payload.longitude, user)
        checkout_inside = user.is_remote or checkout_distance <= allowed_check_in_radius_meters(payload.accuracy_meters or 0, user)
    record_location_event(
        employee_id=user.id,
        attendance_id=record.id,
        kind="check_out",
        at=record.checked_out_at,
        lat=payload.latitude,
        lng=payload.longitude,
        accuracy=payload.accuracy_meters,
        distance_meters=round(checkout_distance) if checkout_distance is not None else None,
        inside_geofence=checkout_inside,
    )
    audit("attendance.check_out", user, record.id)
    return {
        "id": record.id,
        "checked_out_at": record.checked_out_at,
        "effective_hours": round(
            (record.checked_out_at - record.checked_in_at).total_seconds() / 3600, 2
        ),
    }


@router.post("/attendance/reverify")
async def reverify(
    payload: ReverifyInput, x_demo_user: str | None = Header(default=None)
) -> dict:
    user = actor(x_demo_user)
    today = jakarta_date()
    record = next(
        (item for item in employee_sessions_on(user.id, today) if not item.checked_out_at),
        None,
    )
    if not record:
        raise HTTPException(409, "Tidak ada sesi kehadiran terbuka")
    pending = pending_reverify_for(record)
    distance = office_distance_meters(payload.latitude, payload.longitude, user)
    allowed_radius = allowed_check_in_radius_meters(payload.accuracy_meters, user)
    now = datetime.now(UTC)

    if user.is_remote:
        if pending:
            pending.lat = payload.latitude
            pending.lng = payload.longitude
            pending.accuracy = payload.accuracy_meters
            pending.at = now
            pending.distance_meters = round(distance)
            pending.inside_geofence = True
            pending.anomaly = None
            audit("attendance.reverify", user, pending.id)
            return location_event_payload(pending) | {"skipped": True}
        return {"skipped": True, "pending_reverification": None}

    if not payload.selfie_captured:
        raise HTTPException(422, "Selfie kamera langsung wajib untuk kebijakan ini")
    if not pending:
        raise HTTPException(409, "Tidak ada re-verifikasi yang menunggu")

    inside = distance <= allowed_radius
    pending.lat = payload.latitude
    pending.lng = payload.longitude
    pending.accuracy = payload.accuracy_meters
    pending.at = now
    pending.distance_meters = round(distance)
    pending.inside_geofence = inside
    pending.anomaly = None if inside else "outside_geofence"
    audit("attendance.reverify", user, pending.id)
    return location_event_payload(pending)


@router.get("/leave-requests")
async def list_leave_requests(x_demo_user: str | None = Header(default=None)) -> dict:
    user = actor(x_demo_user)
    items = [item for item in store.requests.values() if item.employee_id == user.id]
    return {
        "items": [
            asdict(item) | {"days": working_days(item.start, item.end)}
            for item in sorted(items, key=lambda entry: entry.created_at, reverse=True)
        ],
        "balance": leave_balance(user.id),
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
    email_leave(
        leave_recipients(request),
        "Permohonan cuti baru — Teamku",
        f"{user.name} mengajukan cuti {request.start} sampai {request.end} ({working_days(request.start, request.end)} hari kerja).\n\nBuka Teamku: /app/approvals",
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
    if request.status == "cancelled" and request.calendar_sync_status in {"ok", "failed"}:
        remove_leave_calendar(request)
    audit("leave.cancelled", user, request.id)
    cancel_recipients = leave_recipients(request)
    if request.employee_id not in {person.id for person in cancel_recipients}:
        cancel_recipients.append(user)
    email_leave(cancel_recipients, "Permohonan cuti dibatalkan — Teamku", f"{user.name} membatalkan permohonan cuti {request.start} sampai {request.end}.\n\nBuka Teamku: /app/time/time-off")
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
    email_leave(
        [employee],
        f"Permohonan cuti {payload.decision} — Teamku",
        f"Permohonan cuti Anda ({request.start} sampai {request.end}) telah {payload.decision}.\nCatatan: {payload.comment}\n\nBuka Teamku: /app/time/time-off",
    )
    if payload.decision == "approved":
        sync_leave_calendar(request, employee)
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
    evaluate_attendance_alerts()
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
