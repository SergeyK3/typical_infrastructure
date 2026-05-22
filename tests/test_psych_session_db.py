"""Phase 4: DB sessions, runtime restore, reminders, RBAC."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Account, Employee, PtTestAssignment
from app.services.psych_assignment_reminders import process_assignment_due_reminders_once
from app.services.psych_rbac import assign_rbac_enforced
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.integration.session_runtime import (
    restore_session_engine,
    serialize_session_engine,
)
from psychological_testing.integration.session_store import reset_session_store
from psychological_testing.shared_engine.session_state_machine import SessionEngine
from tests.conftest import onboarding_payload


def test_serialize_restore_session_engine_roundtrip() -> None:
    registry = TestRegistry()
    definition = registry.get("disc")
    engine = SessionEngine.start(
        definition,
        client_id="c1",
        employee_id="e1",
        session_id="restore-disc-001",
    )
    engine.submit_button("4")
    payload = serialize_session_engine(engine)
    restored = restore_session_engine(payload, registry)
    assert restored is not None
    assert restored.session.session_id == "restore-disc-001"
    assert len(restored.session.responses) == 1
    assert restored.session.current_item_index == engine.session.current_item_index


def test_save_and_restore_runtime_from_db(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_DB", "1")
    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_db_restore",
            client_name="Psych DB Restore",
            admin_login="psych_db_restore_admin",
        ),
    )
    client_id = onboard.json()["client_id"]
    emp_id = onboard.json()["created_entities"]["employee_id"]

    from app.db import SessionLocal
    from app.services.psych_session_db import (
        save_in_progress_engine,
        try_restore_engine_for_chat,
    )
    from psychological_testing.integration.session_store import get_session_store

    registry = TestRegistry()
    definition = registry.get("hexaco")
    engine = SessionEngine.start(
        definition,
        client_id=client_id,
        employee_id=emp_id,
        session_id="hexaco-restore-001",
    )
    store = get_session_store()
    reset_session_store()
    store = get_session_store()
    chat_id = "900001"
    binding = store.ensure_binding(chat_id, client_id=client_id, employee_id=emp_id)
    binding.context = "psych_testing"
    binding.active_test_id = "hexaco"
    store.set_engine(chat_id, engine)

    db = SessionLocal()
    try:
        save_in_progress_engine(db, telegram_chat_id=chat_id, engine=engine, binding=binding)
    finally:
        db.close()

    store.clear_engine(chat_id)
    assert store.get_engine(chat_id) is None

    db = SessionLocal()
    try:
        restored = try_restore_engine_for_chat(
            db,
            store,
            telegram_chat_id=chat_id,
            registry=registry,
        )
    finally:
        db.close()
    assert restored is not None
    assert restored.session.test_id == "hexaco"
    assert restored.session.responses == []


def test_assignment_due_reminder_once(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_REMINDERS", "1")
    sent: list[tuple[str, str]] = []

    def fake_send(chat_id: str, text: str) -> bool:
        sent.append((chat_id, text))
        return True

    monkeypatch.setattr(
        "app.services.psych_assignment_reminders._send_telegram",
        fake_send,
    )

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_remind_org",
            client_name="Psych Remind",
            admin_login="psych_remind_admin",
        ),
    )
    client_id = onboard.json()["client_id"]
    emp_id = onboard.json()["created_entities"]["employee_id"]

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        emp = db.get(Employee, emp_id)
        assert emp is not None
        emp.telegram_id = "555001"
        row = PtTestAssignment(
            id="assign-remind-1",
            client_id=client_id,
            employee_id=emp_id,
            test_id="mbti",
            program_id="mbti",
            status="scheduled",
            due_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=6),
            notified_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(row)
        db.commit()

        count = process_assignment_due_reminders_once(db)
        assert count == 1
        db.refresh(row)
        assert row.due_reminder_sent_at is not None
    finally:
        db.close()
    assert sent and sent[0][0] == "555001"


def test_assign_rbac_enforced(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_RBAC_ASSIGN", "1")
    assert assign_rbac_enforced() is True

    onboard = client.post(
        "/api/onboarding-runs",
        json=onboarding_payload(
            client_code="psych_rbac_assign",
            client_name="Psych RBAC Assign",
            admin_login="psych_rbac_assign_admin",
        ),
    )
    client_id = onboard.json()["client_id"]
    emp_id = onboard.json()["created_entities"]["employee_id"]

    r = client.post(
        "/api/psychological-testing/assignments",
        json={
            "client_id": client_id,
            "employee_id": emp_id,
            "test_id": "mbti",
        },
    )
    assert r.status_code == 403

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        acc = db.scalars(select(Account).where(Account.login == "psych_rbac_assign_admin")).first()
        assert acc is not None
        r2 = client.post(
            "/api/psychological-testing/assignments",
            json={
                "client_id": client_id,
                "employee_id": emp_id,
                "test_id": "mbti",
                "account_id": acc.id,
            },
        )
        assert r2.status_code == 200
    finally:
        db.close()
