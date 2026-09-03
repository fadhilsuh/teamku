from datetime import datetime

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import JAKARTA, reset_demo_store, store

client = TestClient(app)
EMAILS = {
    "e-hr": "hr@movon.test",
    "e-manager": "manager@movon.test",
    "e-employee": "employee@movon.test",
    "e-008": "fajar@movon.test",
}


def headers(user: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": EMAILS[user], "password": "Demo123!"}
    )
    return {"X-Demo-User": response.json()["access_token"]}


def setup_function() -> None:
    reset_demo_store()


def test_leave_request_approval_updates_dashboard_and_balance() -> None:
    submitted = client.post(
        "/api/v1/leave-requests",
        headers=headers("e-employee"),
        json={"start": "2026-10-12", "end": "2026-10-13", "reason": "Acara keluarga"},
    )
    assert submitted.status_code == 200
    request_id = submitted.json()["id"]

    manager_dashboard = client.get("/api/v1/dashboard", headers=headers("e-manager"))
    assert manager_dashboard.json()["pending_approvals"] >= 1

    approved = client.post(
        f"/api/v1/approvals/{request_id}",
        headers=headers("e-manager"),
        json={"decision": "approved", "comment": "Disetujui, selamat beristirahat"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    requests = client.get("/api/v1/leave-requests", headers=headers("e-employee")).json()
    assert requests["items"][0]["status"] == "approved"
    assert requests["balance"]["remaining_days"] == 10


def test_hr_can_create_employee_and_dashboard_uses_the_new_record() -> None:
    before = client.get("/api/v1/dashboard", headers=headers("e-hr")).json()["headcount"]
    created = client.post(
        "/api/v1/employees",
        headers=headers("e-hr"),
        json={
            "name": "Dimas Wijaya",
            "email": "dimas.wijaya@movon.test",
            "department": "Product",
            "role": "employee",
            "salary": 9_500_000,
        },
    )
    assert created.status_code == 200

    after = client.get("/api/v1/dashboard", headers=headers("e-hr")).json()["headcount"]
    assert after == before + 1


def test_payroll_requires_valid_state_transitions_before_publish() -> None:
    created = client.post(
        "/api/v1/payroll/runs",
        headers=headers("e-hr"),
        json={"month": "2026-10"},
    )
    assert created.status_code == 200
    run_id = created.json()["id"]

    too_early = client.post(
        f"/api/v1/payroll/runs/{run_id}/publish", headers=headers("e-hr")
    )
    assert too_early.status_code == 409

    finalized = client.post(
        f"/api/v1/payroll/runs/{run_id}/finalize", headers=headers("e-hr")
    )
    assert finalized.json()["status"] == "finalized"

    published = client.post(
        f"/api/v1/payroll/runs/{run_id}/publish", headers=headers("e-hr")
    )
    assert published.json()["status"] == "published"

    employee_payslips = client.get(
        "/api/v1/payroll/payslips", headers=headers("e-employee")
    )
    assert employee_payslips.status_code == 200
    assert employee_payslips.json()["items"][0]["employee"] == "Sinta Lestari"


def test_employee_cannot_run_payroll_or_approve_requests() -> None:
    payroll = client.post(
        "/api/v1/payroll/runs",
        headers=headers("e-employee"),
        json={"month": "2026-10"},
    )
    assert payroll.status_code == 403

    approval = client.get("/api/v1/approvals", headers=headers("e-employee"))
    assert approval.status_code == 403


def test_forged_and_missing_session_tokens_are_rejected_and_logout_revokes() -> None:
    assert client.get("/api/v1/me").status_code == 401
    assert client.get("/api/v1/me", headers={"X-Demo-User": "e-hr"}).status_code == 401

    session_headers = headers("e-employee")
    assert client.get("/api/v1/me", headers=session_headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=session_headers).status_code == 200
    assert client.get("/api/v1/me", headers=session_headers).status_code == 401


def test_manager_cannot_approve_a_request_outside_their_department() -> None:
    submitted = client.post(
        "/api/v1/leave-requests",
        headers=headers("e-employee"),
        json={"start": "2026-11-02", "end": "2026-11-02", "reason": "Urusan keluarga"},
    )
    request_id = submitted.json()["id"]

    denied = client.post(
        f"/api/v1/approvals/{request_id}",
        headers=headers("e-008"),
        json={"decision": "approved", "comment": "Mencoba lintas departemen"},
    )

    assert denied.status_code == 403
    manager_items = client.get("/api/v1/approvals", headers=headers("e-manager")).json()
    request = next(item for item in manager_items["items"] if item["id"] == request_id)
    assert request["status"] == "pending"


def test_suspended_employee_is_removed_from_all_dashboard_counts() -> None:
    hr_headers = headers("e-hr")
    before = client.get("/api/v1/dashboard", headers=hr_headers).json()
    assert before["headcount"] == 18
    assert before["present"] == 7

    response = client.patch(
        "/api/v1/employees/e-manager",
        headers=hr_headers,
        json={"status": "suspended"},
    )
    assert response.status_code == 200

    after = client.get("/api/v1/dashboard", headers=hr_headers).json()
    assert after["headcount"] == 17
    assert after["present"] == 6


def test_seed_attendance_uses_the_current_jakarta_business_date() -> None:
    jakarta_dates = {
        attendance.checked_in_at.astimezone(JAKARTA).date()
        for attendance in store.attendance.values()
    }
    assert jakarta_dates == {datetime.now(JAKARTA).date()}
