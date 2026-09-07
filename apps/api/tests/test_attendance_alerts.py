from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from movon_hr.core.mailer import last_email_to
from movon_hr.main import app
from movon_hr.modules.api import (
    JAKARTA,
    OFFICE_LATITUDE,
    OFFICE_LONGITUDE,
    Attendance,
    LeaveRequest,
    LocationEvent,
    reset_demo_store,
    store,
)

client = TestClient(app)


def login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "Demo123!"})
    return {"X-Demo-User": response.json()["access_token"]}


def enable_alerts(**overrides: object) -> None:
    store.office.alerts_enabled = True
    store.office.clock_in_reminder_time = "00:00"
    store.office.clock_out_reminder_time = "23:59"
    store.office.max_open_hours = 10
    store.office.alert_managers = False
    for key, value in overrides.items():
        setattr(store.office, key, value)


def attendance_alerts_for(user_id: str) -> list:
    return [
        item
        for item in store.notifications.values()
        if item.user_id == user_id
        and item.title in {"Belum clock-in", "Sesi masih terbuka", "Re-verifikasi terlewat", "Lokasi di luar area kantor"}
    ]


def test_disabled_policy_creates_no_attendance_alerts() -> None:
    reset_demo_store()
    store.office.alerts_enabled = False
    before = len(store.notifications)

    client.get("/api/v1/notifications", headers=login("fresh@movon.test"))

    assert len(store.notifications) == before
    assert attendance_alerts_for("e-fresh") == []


def test_missed_clock_in_notifies_employee_once_per_day() -> None:
    reset_demo_store()
    enable_alerts()

    first = client.get("/api/v1/notifications", headers=login("fresh@movon.test"))
    second = client.get("/api/v1/notifications", headers=login("fresh@movon.test"))

    titles = [item["title"] for item in first.json()["items"]]
    assert titles.count("Belum clock-in") == 1
    assert [item["title"] for item in second.json()["items"]].count("Belum clock-in") == 1
    assert last_email_to("fresh@movon.test") is not None


def test_approved_leave_skips_missed_clock_in() -> None:
    reset_demo_store()
    enable_alerts()
    today = datetime.now(JAKARTA).date()
    request = LeaveRequest("leave-today", "e-fresh", today, today, "Cuti hari ini", status="approved")
    store.requests[request.id] = request

    client.get("/api/v1/notifications", headers=login("fresh@movon.test"))

    assert attendance_alerts_for("e-fresh") == []


def test_open_session_past_max_hours_notifies_employee() -> None:
    reset_demo_store()
    enable_alerts(max_open_hours=1)
    store.attendance["open-long"] = Attendance(
        id="open-long",
        employee_id="e-fresh",
        checked_in_at=datetime.now(UTC) - timedelta(hours=3),
        latitude=OFFICE_LATITUDE,
        longitude=OFFICE_LONGITUDE,
        accuracy_meters=10,
        agenda=[{"title": "Sesi panjang"}],
    )

    client.get("/api/v1/attendance/today", headers=login("fresh@movon.test"))

    titles = [item.title for item in attendance_alerts_for("e-fresh")]
    assert "Sesi masih terbuka" in titles


def test_alert_managers_notifies_department_manager_and_hr() -> None:
    reset_demo_store()
    enable_alerts(alert_managers=True)

    client.get("/api/v1/notifications", headers=login("fresh@movon.test"))

    assert any(item.title == "Belum clock-in" for item in attendance_alerts_for("e-fresh"))
    assert any(
        item.title == "Belum clock-in" and "Rani" in item.detail
        for item in store.notifications.values()
        if item.user_id == "e-manager"
    )
    assert any(
        item.title == "Belum clock-in" and "Rani" in item.detail
        for item in store.notifications.values()
        if item.user_id == "e-hr"
    )


def test_remote_employee_gets_clock_in_reminder_but_not_geofence_alert() -> None:
    reset_demo_store()
    enable_alerts()
    store.employees["e-fresh"].is_remote = True
    store.location_events["geo-remote"] = LocationEvent(
        id="geo-remote",
        employee_id="e-fresh",
        attendance_id="none",
        kind="reverify",
        at=datetime.now(UTC),
        lat=-6.3,
        lng=106.8166,
        anomaly="outside_geofence",
    )

    client.get("/api/v1/notifications", headers=login("fresh@movon.test"))

    titles = [item.title for item in attendance_alerts_for("e-fresh")]
    assert "Belum clock-in" in titles
    assert "Lokasi di luar area kantor" not in titles


def test_outside_geofence_creates_accountability_alert_for_office_worker() -> None:
    reset_demo_store()
    enable_alerts()
    store.attendance["today-office"] = Attendance(
        id="today-office",
        employee_id="e-fresh",
        checked_in_at=datetime.now(UTC),
        latitude=OFFICE_LATITUDE,
        longitude=OFFICE_LONGITUDE,
        accuracy_meters=10,
        agenda=[{"title": "Di kantor"}],
    )
    store.location_events["geo-office"] = LocationEvent(
        id="geo-office",
        employee_id="e-fresh",
        attendance_id="today-office",
        kind="reverify",
        at=datetime.now(UTC),
        lat=-6.3,
        lng=106.8166,
        anomaly="outside_geofence",
    )

    client.get("/api/v1/notifications", headers=login("fresh@movon.test"))

    titles = [item.title for item in attendance_alerts_for("e-fresh")]
    assert "Lokasi di luar area kantor" in titles
    assert "Belum clock-in" not in titles


def test_repeated_notifications_poll_does_not_duplicate_kind_day() -> None:
    reset_demo_store()
    enable_alerts()

    client.get("/api/v1/notifications", headers=login("fresh@movon.test"))
    client.get("/api/v1/notifications", headers=login("fresh@movon.test"))
    client.get("/api/v1/attendance/today", headers=login("fresh@movon.test"))

    assert len(attendance_alerts_for("e-fresh")) == 1
