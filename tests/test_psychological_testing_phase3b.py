"""Phase 3b — hr_core + session result JSON persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from psychological_testing.domain.entities import SessionStatus
from psychological_testing.domain.mbti_delivery import participant_greeting_name
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.integration.hr_core import (
    EmployeeSnapshot,
    employee_display_label,
    resolve_employee_by_telegram,
)
from psychological_testing.integration.session_persistence import (
    SCHEMA_VERSION,
    build_session_result_document,
    persist_session_result,
)
from psychological_testing.integration.session_store import reset_session_store
from psychological_testing.shared_engine.session_state_machine import SessionEngine


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_session_store()
    yield
    reset_session_store()


def test_participant_greeting_with_hr_name() -> None:
    assert participant_greeting_name("dev-employee", hr_display_name="Сергей") == "Сергей"


def test_build_session_result_document_paei() -> None:
    paei = TestRegistry().get("paei")
    engine = SessionEngine.start(paei, client_id="c1", employee_id="e1")
    for text in ("p", "a", "e", "i", "p"):
        engine.submit_text(text)
    assert engine.session.status == SessionStatus.DONE
    doc = build_session_result_document(
        engine,
        telegram_chat_id="100",
        report_text="=== РЕЗУЛЬТАТ PAEI ===",
        employee_display_name="Иванов Иван",
        delivery_mode="structured",
    )
    assert doc["schema_version"] == SCHEMA_VERSION
    assert doc["test_id"] == "paei"
    assert doc["employee_id"] == "e1"
    assert len(doc["responses"]) == 5
    assert doc["scores"] is not None
    assert doc["report"]["text_telegram"].startswith("===")
    assert doc["dialog_akma"] is None


def test_persist_session_result_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_PERSIST_JSON", "1")
    monkeypatch.setenv("PSYCH_TESTING_SESSIONS_DIR", str(tmp_path))
    doc = {
        "schema_version": SCHEMA_VERSION,
        "session_id": "test-session-1",
        "completed_at": "2026-05-20T12:00:00+00:00",
    }
    path = persist_session_result(doc)
    assert path is not None
    assert path.exists()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["session_id"] == "test-session-1"


def test_persist_disabled_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PSYCH_TESTING_PERSIST_JSON", raising=False)
    assert persist_session_result({"session_id": "x"}) is None


def test_employee_display_label_from_snapshot() -> None:
    snap = EmployeeSnapshot(
        id="e1",
        client_id="c1",
        display_name="Петров Пётр",
    )
    assert employee_display_label(snap) == "Петров Пётр"


def test_resolve_employee_dev_fallback_without_db() -> None:
    """Without app DB in test env — dev fallback ids."""
    class _FakeDb:
        pass

    snap = resolve_employee_by_telegram(
        _FakeDb(),  # type: ignore[arg-type]
        "999",
        default_client_id="dev-client",
        default_employee_id="dev-employee",
    )
    assert snap.client_id == "dev-client"
    assert snap.id == "dev-employee"
