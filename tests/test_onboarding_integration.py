r"""Integration tests for onboarding flow."""

from __future__ import annotations

from pathlib import Path


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

    regs = client.get(f"/api/client-regulations?client_id={data['client_id']}&limit=500")
    assert regs.status_code == 200
    reg_items = regs.json()["items"]
    assert reg_items

    details = [
        client.get(f"/api/client-regulations/{item['id']}").json()
        for item in reg_items
    ]
    assert any(detail["kpis"] for detail in details)


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


def test_workspace_sidebar_uses_local_catalog_sections():
    """Workspace navigation keeps local catalogs under organization, without the old apps block."""
    root = Path(__file__).resolve().parents[1]
    registry = (root / "static" / "shared" / "sidebar-registry.js").read_text(encoding="utf-8")
    workspace = (root / "static" / "workspace" / "index.html").read_text(encoding="utf-8")

    assert "label: 'Приложения'" not in registry
    assert "Локальные подразделения" in registry
    assert "Локальные должности" in registry
    assert "Локальные регламенты" in registry
    assert "Локальные KPI" in registry
    assert "Локальные навыки" in registry
    assert "<h2>Локальные KPI</h2>" in workspace
    assert "<h2>Локальные навыки</h2>" in workspace


def test_clients_page_routes_creation_and_template_apply_through_onboarding():
    """Clients page should use onboarding for creation and template application."""
    root = Path(__file__).resolve().parents[1]
    clients_page = (root / "static" / "clients" / "index.html").read_text(encoding="utf-8")

    assert '<button type="button" class="btn btn-primary" id="btnCreate">Создать</button>' in clients_page
    assert '<a class="btn btn-secondary" href="/wizard"' not in clients_page
    assert 'id="createTemplateCode"' in clients_page
    assert 'id="applyTemplateCode"' in clients_page
    assert "window.location.href = '/wizard?' + params.toString()" in clients_page
    assert "btn-apply-template" in clients_page
    assert "apply_existing" in clients_page
    assert "/onboarding-runs" in clients_page


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


def test_onboarding_applies_template_to_existing_client(client):
    """Existing organization mode safely re-applies template without creating a client."""
    create_payload = {"template_code": "default", "client": {"code": "apply_existing_x", "name": "Apply Existing X"}, "admin": {"last_name": "A", "first_name": "B", "login": "apply_existing_admin", "password": "X", "email": None}}
    r1 = client.post("/api/onboarding-runs", json=create_payload)
    assert r1.status_code == 200
    client_id = r1.json()["client_id"]
    before = client.get(f"/api/org-units?client_id={client_id}").json()["total"]

    apply_payload = {
        "action": "apply_existing",
        "template_code": "default",
        "existing_client_id": client_id,
    }
    r2 = client.post("/api/onboarding-runs", json=apply_payload)
    assert r2.status_code == 200
    data = r2.json()
    assert data["client_id"] == client_id
    assert data["created_entities"]["action"] == "apply_existing"

    after = client.get(f"/api/org-units?client_id={client_id}").json()["total"]
    assert after == before
