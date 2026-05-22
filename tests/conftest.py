r"""Pytest fixtures for Typical infrastructure tests."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

# Use in-memory SQLite for tests
os.environ["SQLITE_PATH"] = ":memory:"

from app.main import app  # noqa: E402 — after env


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
