"""Read-only enrichment полей учётной записи в GET /api/employees."""

from __future__ import annotations

from tests.conftest import auth_login, onboarding_payload


def _onboard(client, *, suffix: str) -> str:
    r = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code=f"emp_acc_{suffix}",
            client_name=f"EmpAcc {suffix}",
            admin_login=f"emp_acc_admin_{suffix}",
        ),
    )
    assert r.status_code == 200
    return r.json()["client_id"]


def _create_employee(client, *, client_id: str, last_name: str) -> str:
    r = client.post(
        "/api/employees",
        json={
            "client_id": client_id,
            "last_name": last_name,
            "first_name": "Test",
            "employment_status": "active",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_employee_list_without_account_has_empty_enrichment(client):
    client_id = _onboard(client, suffix="noacc")
    auth_login(client, "emp_acc_admin_noacc", "TempPass123!")
    emp_id = _create_employee(client, client_id=client_id, last_name="NoAccount")

    items = client.get("/api/employees", params={"client_id": client_id, "limit": 50}).json()["items"]
    sample = next(e for e in items if e["id"] == emp_id)
    assert sample.get("account_id") is None
    assert sample.get("account_status") is None
    assert sample.get("system_role_labels") == []


def test_employee_list_with_account_returns_enrichment(client):
    client_id = _onboard(client, suffix="withacc")
    auth_login(client, "emp_acc_admin_withacc", "TempPass123!")
    emp_id = _create_employee(client, client_id=client_id, last_name="WithAccount")

    create = client.post(
        "/api/accounts",
        json={
            "employee_id": emp_id,
            "login": "emp_acc_user_withacc",
            "password": "NewUserPass123!",
            "status": "active",
            "role_codes": ["employee", "manager"],
        },
    )
    assert create.status_code == 200, create.text

    refreshed = client.get("/api/employees", params={"client_id": client_id, "limit": 50}).json()["items"]
    enriched = next(e for e in refreshed if e["id"] == emp_id)
    assert enriched["account_id"]
    assert enriched["account_login"] == "emp_acc_user_withacc"
    assert enriched["account_status"] == "active"
    assert "Employee" in enriched["system_role_labels"]
    assert "Manager" in enriched["system_role_labels"]
