from datetime import date, timedelta

from fastapi.testclient import TestClient

from movon_hr.main import app
from movon_hr.modules.api import DEMO_PASSWORD, reset_demo_store, store

client = TestClient(app)


def setup_function() -> None:
    reset_demo_store()


def login(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    return {"X-Demo-User": response.json()["access_token"]}


def create_policy(headers: dict[str, str], *, state: str = "published") -> dict:
    response = client.post(
        "/api/v1/policies", headers=headers, json={
            "title": "Sick Leave Policy", "category": "leave", "language": "en",
            "effective_date": str(date.today() - timedelta(days=1)),
            "sections": [{"id": "medical-certificate", "heading": "Medical certificate", "body": "A doctor letter is required after two sick days."}],
        },
    )
    assert response.status_code == 200
    policy = response.json()
    if state == "published":
        assert client.post(f"/api/v1/policies/{policy['id']}/publish", headers=headers).status_code == 200
    return policy


def test_hr_publishes_policy_and_employee_gets_grounded_citation() -> None:
    hr = login("hr@movon.test")
    policy = create_policy(hr)
    response = client.post("/api/v1/policy-assistant/questions", headers=login("employee@movon.test"), json={"question": "Do I need a doctor letter for sick leave?"})
    assert response.status_code == 200
    body = response.json()
    assert body["confidence"] == "supported"
    assert body["citations"] == [{**body["citations"][0]}]
    assert body["citations"][0]["policy_id"] == policy["id"]
    assert body["citations"][0]["section_id"] == "medical-certificate"
    assert store.policy_answer_audit


def test_draft_and_cross_tenant_policy_never_answer_question() -> None:
    hr = login("hr@movon.test")
    create_policy(hr, state="draft")
    response = client.post("/api/v1/policy-assistant/questions", headers=login("employee@movon.test"), json={"question": "Do I need a doctor letter for sick leave?"})
    assert response.json()["confidence"] == "insufficient_evidence"

    other = client.post("/api/v1/auth/signup", json={"company_name": "Tenant Two", "admin_name": "Admin Dua", "email": "hr@two.test", "password": "Company123"})
    create_policy({"X-Demo-User": other.json()["access_token"]})
    assert client.post("/api/v1/policy-assistant/questions", headers=login("employee@movon.test"), json={"question": "doctor letter"}).json()["confidence"] == "insufficient_evidence"


def test_non_hr_cannot_manage_policies_and_empty_evidence_is_safe() -> None:
    employee = login("employee@movon.test")
    assert client.get("/api/v1/policies", headers=employee).status_code == 403
    assert client.post("/api/v1/policies", headers=employee, json={}).status_code in {403, 422}
    response = client.post("/api/v1/policy-assistant/questions", headers=employee, json={"question": "What is my salary?"})
    assert response.status_code == 200
    assert response.json()["confidence"] == "insufficient_evidence"
    assert response.json()["citations"] == []
