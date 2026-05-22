"""Единый слой согласия ПДн: сервис и Telegram gate."""

from __future__ import annotations

import pytest

from app.db import Base, SessionLocal, engine
from app.migrate import migrate_employee_consent_records
from app.models import EmployeeConsentRecord
from app.services.employee_consent import (
    STATUS_ACCEPTED,
    STATUS_DECLINED,
    STATUS_DECLINE_PENDING,
    PdConsentGate,
    build_pd_consent_keyboard,
    get_pd_consent,
    handle_pd_consent_no,
    is_pd_consent_blocked,
    is_pd_consent_valid,
    record_pd_consent_yes,
    require_pd_consent_or_prompt,
)
from app.services.telegram_employee_consent import GateResult, consent_gate, handle_consent_callback
from app.utils import new_id32


@pytest.fixture(autouse=True)
def _doc_version(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_PD_CONSENT_DOCUMENT_VERSION", "1.0")


@pytest.fixture(autouse=True)
def _ensure_db_tables():
    import app.models  # noqa: F401
    import skill_assessment.infrastructure.db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_employee_consent_records()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _dev_binding(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_DEV_CLIENT_ID", "c1")
    monkeypatch.setenv("TELEGRAM_DEV_EMPLOYEE_ID", "e1")


def test_two_step_decline_then_block(db):
    r1 = handle_pd_consent_no(db, "c1", "e1")
    assert r1.status == STATUS_DECLINE_PENDING
    assert r1.is_final_decline is False
    assert r1.warning_message

    snap = get_pd_consent(db, "c1", "e1")
    assert snap.status == STATUS_DECLINE_PENDING
    assert not is_pd_consent_blocked(snap)

    gate_pending = require_pd_consent_or_prompt(db, "c1", "e1")
    assert gate_pending.outcome == PdConsentGate.PROMPT
    assert "Без согласия" in (gate_pending.message or "")
    assert "Здравствуйте" not in (gate_pending.message or "")

    r2 = handle_pd_consent_no(db, "c1", "e1")
    assert r2.is_final_decline
    snap2 = get_pd_consent(db, "c1", "e1")
    assert snap2.status == STATUS_DECLINED
    assert is_pd_consent_blocked(snap2)


def test_epc_callback_first_no_sends_warning_only(db):
    turn = handle_consent_callback(db, "900001", "epc|n|e1")
    assert turn is not None
    db.commit()
    assert len(turn.outgoing) == 1
    text, kb = turn.outgoing[0]
    assert "Без согласия" in text
    assert kb is not None
    assert "epc|y|e1" in str(kb)


def test_accept_after_decline_pending(db):
    handle_pd_consent_no(db, "c1", "e1")
    record_pd_consent_yes(db, "c1", "e1")
    db.commit()
    snap = get_pd_consent(db, "c1", "e1")
    assert is_pd_consent_valid(snap)
    assert snap.document_version == "1.0"


def test_version_mismatch_requires_new_consent(db):
    row = EmployeeConsentRecord(
        id=new_id32(),
        client_id="c_ver",
        employee_id="e_ver",
        consent_type="pd_processing",
        status=STATUS_ACCEPTED,
        document_version="0.9",
        source="telegram",
    )
    db.add(row)
    db.commit()
    snap = get_pd_consent(db, "c_ver", "e_ver")
    assert not is_pd_consent_valid(snap)


def test_epc_callback_yes(db):
    turn = handle_consent_callback(db, "900001", "epc|y|e1")
    assert turn is not None
    db.commit()
    assert is_pd_consent_valid(get_pd_consent(db, "c1", "e1"))
    assert turn.outgoing
    assert "Согласие принято" in (turn.popup_text or "")


def test_consent_gate_blocks_without_consent(db, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_DEV_CLIENT_ID", "c_gate")
    monkeypatch.setenv("TELEGRAM_DEV_EMPLOYEE_ID", "e_gate")
    result, outgoing = consent_gate(db, "900001")
    assert result == GateResult.HANDLED
    assert outgoing
    assert "персональных данных" in outgoing[0][0].lower()


def test_require_pd_consent_or_prompt_outcomes(db, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TELEGRAM_DEV_CLIENT_ID", "c_req")
    monkeypatch.setenv("TELEGRAM_DEV_EMPLOYEE_ID", "e_req")

    gate_pending = require_pd_consent_or_prompt(db, "c_req", "e_req")
    assert gate_pending.outcome == PdConsentGate.PROMPT
    assert gate_pending.message
    assert gate_pending.reply_markup

    record_pd_consent_yes(db, "c_req", "e_req")
    db.commit()
    assert require_pd_consent_or_prompt(db, "c_req", "e_req").outcome == PdConsentGate.ALLOW

    handle_pd_consent_no(db, "c_req", "e_req")
    handle_pd_consent_no(db, "c_req", "e_req")
    db.commit()
    gate_blocked = require_pd_consent_or_prompt(db, "c_req", "e_req")
    assert gate_blocked.outcome == PdConsentGate.BLOCKED


def test_consent_gate_allows_after_accept(db):
    record_pd_consent_yes(db, "c1", "e1")
    db.commit()
    result, _ = consent_gate(db, "900001")
    assert result == GateResult.ALLOW


def test_build_pd_consent_prompt_with_intro():
    text = __import__(
        "app.services.employee_consent", fromlist=["build_pd_consent_prompt"]
    ).build_pd_consent_prompt(intro="Здравствуйте, Айгуль!\n\nВам назначено тестирование.")
    assert "Здравствуйте, Айгуль" in text
    assert "Согласие на обработку" not in text
    assert "персональных данных" in text.lower()


def test_keyboard_callback_prefix():
    kb = build_pd_consent_keyboard("e1")
    y = kb["inline_keyboard"][0][0]["callback_data"]
    n = kb["inline_keyboard"][1][0]["callback_data"]
    assert y == "epc|y|e1"
    assert n == "epc|n|e1"


def test_backfill_from_part1_accepted(db, monkeypatch: pytest.MonkeyPatch):
    from skill_assessment.infrastructure.db_models import AssessmentSessionRow

    monkeypatch.setenv("TELEGRAM_PD_CONSENT_DOCUMENT_VERSION", "1.0")
    row = AssessmentSessionRow(
        id=new_id32(),
        client_id="bc1",
        employee_id="be1",
        docs_survey_pd_consent_status="accepted",
    )
    db.add(row)
    db.commit()
    migrate_employee_consent_records()
    snap = get_pd_consent(db, "bc1", "be1")
    assert snap.status == STATUS_ACCEPTED
    assert is_pd_consent_valid(snap)
