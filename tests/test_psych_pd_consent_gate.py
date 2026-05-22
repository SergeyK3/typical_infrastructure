"""Psych entry points call unified require_pd_consent_or_prompt (no duplicate logic)."""

from __future__ import annotations

import os

import pytest

from psychological_testing.adapters.telegram_outbound import (
    FakeTelegramOutbound,
    clear_fake_telegram_outbound,
)
from psychological_testing.integration.session_store import reset_session_store
from psychological_testing.integration.telegram_adapter import PsychTestingTelegramAdapter


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_session_store()
    clear_fake_telegram_outbound()
    yield
    reset_session_store()
    clear_fake_telegram_outbound()


@pytest.fixture
def fake_outbound() -> FakeTelegramOutbound:
    return FakeTelegramOutbound()


@pytest.fixture
def adapter(fake_outbound: FakeTelegramOutbound) -> PsychTestingTelegramAdapter:
    os.environ["PSYCH_TESTING_MBTI_QUESTIONS_PER_AXIS"] = "1"
    return PsychTestingTelegramAdapter(
        token="1234567890:FAKE_TOKEN_FOR_TESTS",
        outbound=fake_outbound,
    )


def test_start_test_blocked_without_consent(
    adapter: PsychTestingTelegramAdapter,
    fake_outbound: FakeTelegramOutbound,
    monkeypatch: pytest.MonkeyPatch,
):
    from tests.conftest import ensure_employee_consent_schema

    ensure_employee_consent_schema()
    monkeypatch.setenv("PSYCH_TESTING_DEV_CLIENT_ID", "c_no_pd_consent")
    monkeypatch.setenv("PSYCH_TESTING_DEV_EMPLOYEE_ID", "e_no_pd_consent")
    adapter.start_test("5001", "mbti")
    assert fake_outbound.messages
    last = fake_outbound.messages[-1]["text"]
    assert "персональных данных" in last.lower()
    assert adapter._store.get_engine("5001") is None


def test_start_test_allowed_after_consent(adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound):
    from app.db import SessionLocal
    from app.services.employee_consent import record_pd_consent_yes
    from tests.conftest import ensure_employee_consent_schema

    ensure_employee_consent_schema()
    client_id = (os.getenv("PSYCH_TESTING_DEV_CLIENT_ID") or "dev-client").strip()
    employee_id = (os.getenv("PSYCH_TESTING_DEV_EMPLOYEE_ID") or "dev-employee").strip()
    with SessionLocal() as db:
        record_pd_consent_yes(db, client_id, employee_id)
        db.commit()

    adapter.start_test("5002", "mbti")
    assert adapter._store.get_engine("5002") is not None
