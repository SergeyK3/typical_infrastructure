r"""Pytest fixtures for Typical infrastructure tests."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Use in-memory SQLite for tests
os.environ["SQLITE_PATH"] = ":memory:"
os.environ["AUTH_SECRET_KEY"] = "test-auth-secret-key-for-pytest-only!!"

from app.main import app  # noqa: E402 — after env

TEST_SYSTEM_LOGIN = "test_system_admin"
TEST_SYSTEM_PASSWORD = "TestSysAdmin123!"


def bootstrap_test_system_admin() -> None:
    from app.db import SessionLocal
    from app.seed import seed_roles
    from app.system_admin import bootstrap_system_admin

    db = SessionLocal()
    try:
        seed_roles(db)
        bootstrap_system_admin(db, login=TEST_SYSTEM_LOGIN, password=TEST_SYSTEM_PASSWORD)
    finally:
        db.close()


def auth_login(client: TestClient, login: str, password: str):
    return client.post("/api/auth/login", json={"login": login, "password": password})


@pytest.fixture(autouse=True)
def _auto_system_admin_login(client: TestClient) -> None:
    """Most API tests expect an authenticated system_admin session."""
    bootstrap_test_system_admin()
    auth_login(client, TEST_SYSTEM_LOGIN, TEST_SYSTEM_PASSWORD)


@pytest.fixture(autouse=True)
def psych_rbac_off_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests opt into RBAC via monkeypatch; local .env may have pilot flags on."""
    monkeypatch.setenv("PSYCH_TESTING_RBAC_ASSIGN", "0")
    monkeypatch.setenv("PSYCH_TESTING_RBAC_VIEW", "0")
    monkeypatch.setenv("PSYCH_TESTING_RBAC_EXPORT", "0")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


def onboarding_payload(
    client_code: str = "test_client",
    client_name: str = "Test Client",
    template_code: str = "default",
    admin_login: str = "admin_test",
    idempotency_key: str | None = None,
) -> dict:
    return {
        "template_code": template_code,
        "client": {"code": client_code, "name": client_name},
        "admin": {
            "last_name": "Admin",
            "first_name": "Test",
            "login": admin_login,
            "password": "TempPass123!",
            "email": "admin@test.example",
        },
        **({"idempotency_key": idempotency_key} if idempotency_key else {}),
    }


@pytest.fixture
def valid_payload() -> dict:
    return onboarding_payload()


@pytest.fixture
def idempotency_key() -> str:
    return "test-idem-key-001"


def ensure_employee_consent_schema() -> None:
    """Создать таблицу единого согласия ПДн в in-memory SQLite (без полного app startup)."""
    import app.models  # noqa: F401
    from app.db import Base, engine
    from app.migrate import migrate_employee_consent_records

    Base.metadata.create_all(bind=engine)
    migrate_employee_consent_records()
