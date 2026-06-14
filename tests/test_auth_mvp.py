"""Auth MVP: system_admin vs client admin, login redirects, tenant scoping."""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, AccountRole, Role
from app.utils import hash_password, new_id32
from tests.conftest import TEST_SYSTEM_PASSWORD, TEST_SYSTEM_LOGIN, auth_login, onboarding_payload


def _logout(client) -> None:
    client.post("/api/auth/logout")


def _employee_id_for_login(login: str) -> str | None:
    db = SessionLocal()
    try:
        acc = db.scalar(select(Account).where(Account.login == login))
        assert acc is not None, f"account not found: {login}"
        return acc.employee_id
    finally:
        db.close()


def _onboard_client(client, *, code: str, admin_login: str) -> str:
    payload = onboarding_payload(client_code=code, admin_login=admin_login)
    r = client.post("/api/onboarding-runs", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "completed"
    return data["client_id"]


def test_system_admin_login(client):
    _logout(client)
    r = auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)
    assert r.status_code == 200
    data = r.json()
    assert data["is_system"] is True
    assert data["client_id"] is None
    assert data["redirect_url"] == "/clients"
    assert "account_id" in data
    assert "roles" in data
    assert "allowed_clients" in data
    assert "system_admin" in data["roles"]

    assert _employee_id_for_login(TEST_SYSTEM_LOGIN) is None

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    me_data = me.json()
    assert me_data["login"] == TEST_SYSTEM_LOGIN
    assert me_data["is_system"] is True


def test_client_admin_login(client):
    _logout(client)
    client_id = _onboard_client(client, code="auth_client_a", admin_login="auth_client_a_admin")
    r = auth_login(client, "auth_client_a_admin", "TempPass123!")
    assert r.status_code == 200
    data = r.json()
    assert data["is_system"] is False
    assert data["client_id"] == client_id
    assert data["redirect_url"] == f"/client/{client_id}"
    assert client_id in data["allowed_clients"]
    assert "admin" in data["roles"]

    assert _employee_id_for_login("auth_client_a_admin") is not None


def test_misconfigured_account_without_employee_denied(client):
    _logout(client)
    login = "auth_orphan_no_employee"
    password = "OrphanPass123!"
    db = SessionLocal()
    try:
        employee_role = db.scalar(select(Role).where(Role.code == "employee", Role.is_active == True))
        assert employee_role is not None
        acc = Account(
            id=new_id32(),
            employee_id=None,
            login=login,
            password_hash=hash_password(password),
            status="active",
        )
        db.add(acc)
        db.flush()
        db.add(AccountRole(id=new_id32(), account_id=acc.id, role_id=employee_role.id))
        db.commit()
    finally:
        db.close()

    r = auth_login(client, login, password)
    assert r.status_code == 403
    body = r.json()
    assert body.get("error", {}).get("code") == "account_misconfigured" or body.get("detail") == "account_misconfigured"


def test_client_admin_cannot_access_another_client(client):
    _logout(client)
    client_a = _onboard_client(client, code="auth_tenant_a", admin_login="auth_tenant_a_admin")
    client_b = _onboard_client(client, code="auth_tenant_b", admin_login="auth_tenant_b_admin")
    auth_login(client, "auth_tenant_a_admin", "TempPass123!")

    api = client.get(f"/api/clients/{client_b}")
    assert api.status_code == 403

    page = client.get(f"/client/{client_b}", follow_redirects=False)
    assert page.status_code == 403

    own = client.get(f"/api/clients/{client_a}")
    assert own.status_code == 200


def test_unauthenticated_workspace_redirects_to_login(client):
    _logout(client)
    r = client.get("/client/some-client-id", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].startswith("/login")
    assert "next=%2Fclient%2Fsome-client-id" in r.headers["location"] or "/client/some-client-id" in r.headers["location"]


def test_system_admin_redirect_to_clients(client):
    _logout(client)
    r = auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)
    assert r.json()["redirect_url"] == "/clients"

    page = client.get("/clients", follow_redirects=False)
    assert page.status_code == 200


def test_client_admin_redirect_to_client_workspace(client):
    _logout(client)
    client_id = _onboard_client(client, code="auth_redirect_client", admin_login="auth_redirect_admin")
    r = auth_login(client, "auth_redirect_admin", "TempPass123!")
    assert r.json()["redirect_url"] == f"/client/{client_id}"

    page = client.get(f"/client/{client_id}", follow_redirects=False)
    assert page.status_code == 200


def test_encode_password_requires_system_admin(client):
    _logout(client)
    _onboard_client(client, code="auth_enc_client", admin_login="auth_enc_admin")
    auth_login(client, "auth_enc_admin", "TempPass123!")
    r = client.post("/api/accounts/encode-password", json={"password": "Secret123!"})
    assert r.status_code == 403

    _logout(client)
    auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)
    r2 = client.post("/api/accounts/encode-password", json={"password": "Secret123!"})
    assert r2.status_code == 200
    assert r2.json()["password_hash"]


def test_unauthenticated_clients_api_returns_401(client):
    _logout(client)
    r = client.get("/api/clients")
    assert r.status_code == 401
