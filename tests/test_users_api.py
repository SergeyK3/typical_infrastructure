"""Global Admin users list API and /users page (PROJ-ACCESS-ADMIN Stage 2A)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.conftest import TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD, auth_login, onboarding_payload

ROOT = Path(__file__).resolve().parents[1]
PRESET_HELPER = ROOT / "tests/helpers/users_preset_url.mjs"


def _logout(client) -> None:
    client.post("/api/auth/logout")


def _login_global_admin(client) -> None:
    _logout(client)
    r = auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)
    assert r.status_code == 200, r.text


def _onboard(client, *, code: str, admin_login: str) -> str:
    _login_global_admin(client)
    payload = onboarding_payload(client_code=code, admin_login=admin_login)
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["client_id"]


def _create_hr_account(client, client_id: str, *, login: str) -> None:
    org_units = client.get(f"/api/org-units?client_id={client_id}&limit=5").json()["items"]
    positions = client.get(f"/api/positions?client_id={client_id}&limit=5").json()["items"]
    emp_create = client.post(
        "/api/employees",
        json={
            "client_id": client_id,
            "org_unit_id": org_units[0]["id"],
            "position_id": positions[0]["id"],
            "last_name": "Hr",
            "first_name": login.replace("_", " ").title()[:20],
            "email": f"{login}@test.example",
            "employment_status": "active",
        },
    )
    assert emp_create.status_code == 200, emp_create.text
    emp_id = emp_create.json()["id"]
    acc = client.post(
        "/api/accounts",
        json={
            "employee_id": emp_id,
            "login": login,
            "password": "TempPass123!",
            "status": "active",
            "role_codes": ["hr"],
        },
    )
    assert acc.status_code == 200, acc.text


def test_users_api_returns_role_codes_and_employee_id(client):
    client_id = _onboard(client, code="usr_api_roles", admin_login="usr_api_roles_admin")
    _create_hr_account(client, client_id, login="usr_api_roles_hr")

    r = client.get("/api/users")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, "expected at least one user row"

    admin_row = next(row for row in items if row["login"] == "usr_api_roles_admin")
    hr_row = next(row for row in items if row["login"] == "usr_api_roles_hr")

    assert admin_row["employee_id"]
    assert "admin" in admin_row["role_codes"]
    assert hr_row["employee_id"]
    assert "hr" in hr_row["role_codes"]
    assert admin_row["client_id"] == client_id


def test_users_api_filter_role_code_admin(client):
    client_id = _onboard(client, code="usr_api_f_admin", admin_login="usr_api_f_admin_admin")
    _create_hr_account(client, client_id, login="usr_api_f_admin_hr")

    r = client.get("/api/users", params={"role_code": "admin"})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items
    assert all("admin" in row["role_codes"] for row in items)
    assert any(row["login"] == "usr_api_f_admin_admin" for row in items)
    assert not any(row["login"] == "usr_api_f_admin_hr" for row in items)


def test_users_api_filter_client_id(client):
    client_a = _onboard(client, code="usr_api_f_ca", admin_login="usr_api_f_ca_admin")
    _onboard(client, code="usr_api_f_cb", admin_login="usr_api_f_cb_admin")

    r = client.get("/api/users", params={"client_id": client_a})
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items
    assert all(row["client_id"] == client_a for row in items)
    assert any(row["login"] == "usr_api_f_ca_admin" for row in items)
    assert not any(row["login"] == "usr_api_f_cb_admin" for row in items)


def test_users_api_filter_status(client):
    client_id = _onboard(client, code="usr_api_f_status", admin_login="usr_api_f_status_admin")
    accounts = client.get(f"/api/accounts?client_id={client_id}").json()["items"]
    admin_acc = next(a for a in accounts if a["login"] == "usr_api_f_status_admin")
    patch = client.patch(
        f"/api/accounts/{admin_acc['id']}",
        json={"status": "blocked"},
    )
    assert patch.status_code == 200, patch.text

    active = client.get("/api/users", params={"status": "active"})
    assert active.status_code == 200
    active_logins = {row["login"] for row in active.json()["items"]}
    assert "usr_api_f_status_admin" not in active_logins

    blocked = client.get("/api/users", params={"status": "blocked", "client_id": client_id})
    assert blocked.status_code == 200
    blocked_items = blocked.json()["items"]
    assert len(blocked_items) == 1
    assert blocked_items[0]["login"] == "usr_api_f_status_admin"
    assert blocked_items[0]["status"] == "blocked"


def test_users_page_has_accounts_title_and_roles_column(client):
    _login_global_admin(client)
    page = client.get("/users")
    assert page.status_code == 200, page.text
    assert "Учётные записи" in page.text

    html = (ROOT / "static/users/index.html").read_text(encoding="utf-8")
    assert "<h1>Учётные записи</h1>" in html
    assert "Платформенные и организационные учётные записи" in html
    assert "<th>Роли</th>" in html


def test_users_page_has_platform_and_org_account_sections(client):
    html = (ROOT / "static/users/index.html").read_text(encoding="utf-8")
    assert 'id="platformAccountsSection"' in html
    assert 'id="orgAccountsSection"' in html
    assert "<h2" in html and "Платформенные аккаунты" in html
    assert "<h2" in html and "Учётные записи организаций" in html
    assert "администрирования платформы" in html
    assert "передачи полномочий преемнику" in html
    assert "делегирования административного доступа" in html
    assert "delegирования" not in html
    assert "Раздел находится в разработке" in html
    assert "Управление платформенными аккаунтами станет доступно" in html
    assert 'id="btnCreatePlatformAccount"' in html
    assert "Создать платформенный аккаунт" in html
    assert 'id="btnCreatePlatformAccount" disabled' not in html.replace("\n", " ")
    assert "Platform Account Lifecycle" in html
    assert "API, audit, lifecycle, policy" in html
    assert "Функция будет доступна после реализации Platform Account Lifecycle" in html
    assert "административном контуре соответствующей организации" in html
    assert 'id="modalPlatformAccount"' in html
    assert 'id="userAccClient"' not in html
    assert "POST', '/accounts'" not in html and 'POST", "/accounts"' not in html
    assert "btnCreatePlatformAccount').onclick" in html

    _login_global_admin(client)
    page = client.get("/users")
    assert page.status_code == 200
    assert "Платформенные аккаунты" in page.text
    assert "Учётные записи организаций" in page.text
    assert "Создать платформенный аккаунт" in page.text


def test_users_page_platform_account_create_is_placeholder_only(client):
    html = (ROOT / "static/users/index.html").read_text(encoding="utf-8")
    assert 'id="btnPlatformAccountSave"' not in html
    assert 'id="platformAccLogin"' not in html


def test_users_page_preset_org_admins_in_html(client):
    html = (ROOT / "static/users/index.html").read_text(encoding="utf-8")
    assert "org-admins" in html
    assert "normalizePresetUrl" in html
    assert "ROLE_UI_LABELS" in html
    assert "Администратор организации" in html
    assert "urlPreset !== 'org-admins'" in html or "urlPreset != 'org-admins'" in html

    _login_global_admin(client)
    page = client.get("/users?preset=org-admins")
    assert page.status_code == 200
    assert "Учётные записи" in page.text


def test_users_preset_url_logic():
    result = subprocess.run(
        ["node", str(PRESET_HELPER)],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip() == "ok"


def test_users_api_admin_role_code_for_preset_filter(client):
    client_id = _onboard(client, code="usr_preset_admin", admin_login="usr_preset_admin_admin")
    _create_hr_account(client, client_id, login="usr_preset_admin_hr")

    r = client.get("/api/users", params={"role_code": "admin"})
    assert r.status_code == 200, r.text
    admin_row = next(row for row in r.json()["items"] if row["login"] == "usr_preset_admin_admin")
    assert "admin" in admin_row["role_codes"]
    assert "Administrator" not in admin_row["role_codes"]


def test_global_admin_me_enables_sidebar_render_context(client):
    _login_global_admin(client)
    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    payload = me.json()
    assert payload["is_global_admin"] is True

    from tests.test_platform_sidebar import render_platform_sidebar_html, users_nav_label, users_nav_match

    html = render_platform_sidebar_html(current_path="/users", is_global_admin=payload["is_global_admin"])
    match = users_nav_match(html)
    assert match is not None, html
    assert match.group(1) == users_nav_label()
