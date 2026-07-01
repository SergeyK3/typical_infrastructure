"""Dev/local Global Admin bootstrap (login gladmin / Admin123!)."""

from __future__ import annotations

from sqlalchemy import select

from app.auth.context import build_current_account
from app.db import SessionLocal
from app.models import Account
from app.seed import seed_roles
from app.system_admin import DEV_SYSTEM_ADMIN_LOGIN, bootstrap_system_admin
from app.utils import verify_password
from tests.conftest import TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD, auth_login, onboarding_payload

DEV_GLOBAL_ADMIN_LOGIN = DEV_SYSTEM_ADMIN_LOGIN
DEV_GLOBAL_ADMIN_PASSWORD = "Admin123!"


def _logout(client) -> None:
    client.post("/api/auth/logout")


def _ensure_dev_global_admin() -> None:
    db = SessionLocal()
    try:
        seed_roles(db)
        bootstrap_system_admin(
            db,
            login=DEV_GLOBAL_ADMIN_LOGIN,
            password=DEV_GLOBAL_ADMIN_PASSWORD,
            sync_existing=True,
        )
    finally:
        db.close()


def test_dev_global_admin_account_is_platform_system_admin():
    _ensure_dev_global_admin()
    db = SessionLocal()
    try:
        acc = db.scalar(select(Account).where(Account.login == DEV_GLOBAL_ADMIN_LOGIN))
        assert acc is not None
        assert acc.employee_id is None
        assert acc.status == "active"
        assert verify_password(DEV_GLOBAL_ADMIN_PASSWORD, acc.password_hash)
        ctx = build_current_account(db, acc)
        assert ctx.is_global_admin is True
        assert "system_admin" in ctx.roles
    finally:
        db.close()


def test_dev_global_admin_login_and_users_page(client):
    _ensure_dev_global_admin()
    _logout(client)

    r = auth_login(client, DEV_GLOBAL_ADMIN_LOGIN, DEV_GLOBAL_ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_global_admin"] is True
    assert data["client_id"] is None
    assert data["redirect_url"] == "/clients"

    page = client.get("/users", follow_redirects=False)
    assert page.status_code == 200, page.text
    assert "Учётные записи" in page.text

    preset = client.get("/users?preset=org-admins", follow_redirects=False)
    assert preset.status_code == 200


def test_users_page_is_platform_html_not_workspace(client):
    _ensure_dev_global_admin()
    _logout(client)
    auth_login(client, DEV_GLOBAL_ADMIN_LOGIN, DEV_GLOBAL_ADMIN_PASSWORD)

    for path in ("/users", "/users?preset=org-admins", "/users/"):
        page = client.get(path, follow_redirects=False)
        assert page.status_code == 200, f"{path}: {page.text[:200]}"
        assert page.headers.get("x-platform-page") == "users", path
        html = page.text
        assert 'data-platform-page="users"' in html, path
        assert 'id="platformSidebar"' in html, path
        assert "Учётные записи" in html, path
        assert 'id="workspaceSidebar"' not in html, path
        assert 'id="clientSelector"' not in html, path
        assert 'id="panel-employees"' not in html, path
        assert "<h2>Сотрудники</h2>" not in html, path
        assert "platform-page-guard.js" in html, path


def test_org_admin_mmc_still_redirects_from_users(client):
    _logout(client)
    auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)
    payload = onboarding_payload(client_code="dev_mmc_block", admin_login="admin_mmc")
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200, r.text

    _logout(client)
    login = auth_login(client, "admin_mmc", "TempPass123!")
    assert login.status_code == 200, login.text
    assert login.json()["is_global_admin"] is False

    page = client.get("/users", follow_redirects=False)
    assert page.status_code == 302
    assert page.headers["location"].startswith("/client/")
