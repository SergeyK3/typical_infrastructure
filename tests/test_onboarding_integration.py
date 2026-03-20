r"""Integration tests for onboarding flow."""

from __future__ import annotations

import pytest


def test_onboarding_full_run(client):
    """Full onboarding creates client, org, positions, employee, account."""
    payload = {"template_code": "default", "client": {"code": "full_run_x", "name": "Full Run X"}, "admin": {"last_name": "A", "first_name": "B", "login": "full_run_admin", "password": "X", "email": None}}
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert data["client_id"] is not None

    run_id = data["id"]
    r2 = client.get(f"/api/onboarding-runs/{run_id}")
    assert r2.status_code == 200
    run_detail = r2.json()
    assert run_detail["run"]["client_id"] == data["client_id"]
    assert len(run_detail["steps"]) >= 5

    # Traceability: created_entities present
    run_obj = run_detail["run"]
    if run_obj.get("created_entities"):
        ce = run_obj["created_entities"]
        assert "client_id" in ce
        assert "account_id" in ce
        assert "employee_id" in ce


def test_onboarding_creates_client(client):
    """Onboarding creates a client that can be fetched."""
    payload = {"template_code": "default", "client": {"code": "creates_client_x", "name": "Creates Client X"}, "admin": {"last_name": "A", "first_name": "B", "login": "creates_client_admin", "password": "X", "email": None}}
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200
    client_id = r.json()["client_id"]
    assert client_id

    r2 = client.get(f"/api/clients/{client_id}")
    assert r2.status_code == 200
    assert r2.json()["code"] == "creates_client_x"


def test_onboarding_creates_org_units(client):
    """Onboarding creates org units for the client."""
    payload = {"template_code": "default", "client": {"code": "creates_ou_x", "name": "Creates OU X"}, "admin": {"last_name": "A", "first_name": "B", "login": "creates_ou_admin", "password": "X", "email": None}}
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200
    client_id = r.json()["client_id"]

    r2 = client.get(f"/api/org-units?client_id={client_id}")
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert len(items) >= 1


def test_onboarding_creates_account(client):
    """Onboarding creates admin account."""
    payload = {"template_code": "default", "client": {"code": "creates_acc_x", "name": "Creates Acc X"}, "admin": {"last_name": "A", "first_name": "B", "login": "creates_acc_admin", "password": "X", "email": None}}
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200
    client_id = r.json()["client_id"]

    r2 = client.get(f"/api/accounts?client_id={client_id}")
    assert r2.status_code == 200
    items = r2.json()["items"]
    assert len(items) >= 1
    assert any(a["login"] == "creates_acc_admin" for a in items)
