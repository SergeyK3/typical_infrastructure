"""Two-level admin model: Global Admin vs Organization Admin."""

from __future__ import annotations

from tests.conftest import TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD, auth_login, onboarding_payload


def _logout(client) -> None:
    client.post("/api/auth/logout")


def _onboard(client, *, code: str, admin_login: str) -> str:
    auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)
    payload = onboarding_payload(client_code=code, admin_login=admin_login)
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["client_id"]


def _login_org_admin(client, admin_login: str) -> None:
    _logout(client)
    r = auth_login(client, admin_login, "TempPass123!")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_org_admin"] is True
    assert data["is_global_admin"] is False


def test_org_admin_cannot_read_global_directories(client):
    client_id = _onboard(client, code="adm_global_read", admin_login="adm_global_read_admin")
    _login_org_admin(client, "adm_global_read_admin")

    for path in (
        "/api/enterprise-templates",
        "/api/template-org-units?template_code=default",
        "/api/position-catalog?template_code=default",
        "/api/kpi-templates?template_code=default",
        "/api/regulations?template_code=default",
    ):
        r = client.get(path)
        assert r.status_code == 403, path


def test_org_admin_cannot_write_global_tables(client):
    client_id = _onboard(client, code="adm_global_write", admin_login="adm_global_write_admin")
    _login_org_admin(client, "adm_global_write_admin")

    create_tpl = client.post(
        "/api/enterprise-templates",
        json={"code": "hack_tpl", "name": "Hack", "version": "1", "description": "x"},
    )
    assert create_tpl.status_code == 403

    copy_global = client.post(
        "/api/catalog-copy/kpi",
        json={
            "mode": "local_to_global",
            "client_id": client_id,
            "target_template_code": "default",
            "source_client_standalone_kpi_id": "missing",
        },
    )
    assert copy_global.status_code == 403


def test_org_admin_cannot_access_other_organization(client):
    client_a = _onboard(client, code="adm_tenant_a", admin_login="adm_tenant_a_admin")
    client_b = _onboard(client, code="adm_tenant_b", admin_login="adm_tenant_b_admin")
    _login_org_admin(client, "adm_tenant_a_admin")

    assert client.get(f"/api/clients/{client_b}").status_code == 403
    assert client.get(f"/api/employees?client_id={client_b}").status_code == 403
    assert client.get(f"/api/org-admins?client_id={client_b}").status_code == 403
    assert client.get(f"/client/{client_b}", follow_redirects=False).status_code == 403

    assert client.get(f"/api/clients/{client_a}").status_code == 200
    assert client.get(f"/api/org-admins?client_id={client_a}").status_code == 200


def test_global_admin_manages_organizations_and_org_admins(client):
    _logout(client)
    auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["is_global_admin"] is True

    client_id = _onboard(client, code="adm_ga_org", admin_login="adm_ga_org_admin")

    org_admins = client.get(f"/api/org-admins?client_id={client_id}")
    assert org_admins.status_code == 200
    items = org_admins.json()["items"]
    assert any(row["login"] == "adm_ga_org_admin" for row in items)

    clients = client.get("/api/clients")
    assert clients.status_code == 200
    assert any(row["id"] == client_id for row in clients.json()["items"])

    templates = client.get("/api/enterprise-templates")
    assert templates.status_code == 200


def test_org_admin_global_html_pages_redirect(client):
    _onboard(client, code="adm_html_block", admin_login="adm_html_block_admin")
    _login_org_admin(client, "adm_html_block_admin")

    for path in ("/global", "/users", "/wizard", "/org-admins", "/regulations"):
        page = client.get(path, follow_redirects=False)
        assert page.status_code == 302, path
        assert page.headers["location"].startswith("/client/")


def test_org_admin_roles_list_excludes_platform_roles(client):
    _onboard(client, code="adm_roles_filter", admin_login="adm_roles_filter_admin")
    _login_org_admin(client, "adm_roles_filter_admin")

    roles = client.get("/api/roles").json()
    codes = {row["code"] for row in roles}
    assert "admin" in codes
    assert "system_admin" not in codes
    assert "developer" not in codes


def test_org_admin_cannot_assign_platform_role(client):
    client_id = _onboard(client, code="adm_role_assign", admin_login="adm_role_assign_admin")
    _login_org_admin(client, "adm_role_assign_admin")

    employees = client.get(f"/api/employees?client_id={client_id}&limit=5").json()["items"]
    emp_id = employees[0]["id"]
    r = client.post(
        "/api/accounts",
        json={
            "employee_id": emp_id,
            "login": "should_not_get_sys_role",
            "password": "TempPass123!",
            "status": "active",
            "role_codes": ["system_admin"],
        },
    )
    assert r.status_code == 403


def test_non_admin_employee_cannot_manage_accounts(client):
    client_id = _onboard(client, code="adm_emp_block", admin_login="adm_emp_block_admin")
    auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)

    org_units = client.get(f"/api/org-units?client_id={client_id}&limit=5").json()["items"]
    positions = client.get(f"/api/positions?client_id={client_id}&limit=5").json()["items"]
    assert org_units and positions
    emp_create = client.post(
        "/api/employees",
        json={
            "client_id": client_id,
            "org_unit_id": org_units[0]["id"],
            "position_id": positions[0]["id"],
            "last_name": "Worker",
            "first_name": "Test",
            "email": "worker@test.example",
            "employment_status": "active",
        },
    )
    assert emp_create.status_code == 200, emp_create.text
    worker_id = emp_create.json()["id"]

    client.post(
        "/api/accounts",
        json={
            "employee_id": worker_id,
            "login": "plain_employee_user",
            "password": "TempPass123!",
            "status": "active",
            "role_codes": ["employee"],
        },
    )

    _logout(client)
    auth_login(client, "plain_employee_user", "TempPass123!")
    r = client.post(
        "/api/accounts",
        json={
            "employee_id": worker_id,
            "login": "another_user",
            "password": "TempPass123!",
            "status": "active",
            "role_codes": ["employee"],
        },
    )
    assert r.status_code == 403
