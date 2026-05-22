"""Phase 4: pt_test_sessions, telegram bindings, process context, resume."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PtTelegramBinding,
    PtTelegramProcessContext,
    PtTestSession,
)
from psychological_testing.integration.session_runtime import (
    restore_session_engine,
    serialize_session_engine,
)
from psychological_testing.integration.session_store import ChatBinding, PsychTestingSessionStore
from psychological_testing.research.mbti.scripts.akma_dialog_engine import AkmaDialogEngine
from psychological_testing.shared_engine.session_state_machine import SessionEngine

_log = logging.getLogger(__name__)

ACTIVE_SESSION_STATUSES = frozenset({"questioning", "reprompt", "init"})


def persist_db_enabled() -> bool:
    return os.getenv("PSYCH_TESTING_PERSIST_DB", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "",
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def upsert_telegram_binding(
    db: Session,
    *,
    telegram_chat_id: str,
    client_id: str,
    employee_id: str,
) -> None:
    if not persist_db_enabled():
        return
    chat = str(telegram_chat_id).strip()
    row = db.scalars(
        select(PtTelegramBinding).where(PtTelegramBinding.telegram_chat_id == chat)
    ).first()
    if row is None:
        row = PtTelegramBinding(
            id=str(uuid.uuid4()),
            telegram_chat_id=chat,
            client_id=client_id,
            employee_id=employee_id,
        )
        db.add(row)
    else:
        row.client_id = client_id
        row.employee_id = employee_id
    db.commit()


def sync_process_context_from_binding(
    db: Session,
    *,
    telegram_chat_id: str,
    binding: ChatBinding | None,
    active_session_id: str | None = None,
) -> None:
    if not persist_db_enabled():
        return
    chat = str(telegram_chat_id).strip()
    row = db.scalars(
        select(PtTelegramProcessContext).where(PtTelegramProcessContext.telegram_chat_id == chat)
    ).first()
    if binding is None or binding.context != "psych_testing":
        if row is not None:
            row.active_flow = "idle"
            row.active_session_id = None
            row.active_test_id = None
            row.active_step_key = None
            row.active_assignment_id = None
            row.mbti_delivery_mode = None
            db.commit()
        return
    if row is None:
        row = PtTelegramProcessContext(
            id=str(uuid.uuid4()),
            telegram_chat_id=chat,
            client_id=binding.client_id,
            employee_id=binding.employee_id,
        )
        db.add(row)
    row.client_id = binding.client_id
    row.employee_id = binding.employee_id
    row.active_flow = binding.context
    row.active_test_id = binding.active_test_id
    row.active_step_key = binding.active_step_key
    row.active_assignment_id = binding.active_assignment_id
    row.mbti_delivery_mode = binding.mbti_delivery_mode
    if active_session_id:
        row.active_session_id = active_session_id
    db.commit()


def clear_process_context(db: Session, *, telegram_chat_id: str) -> None:
    sync_process_context_from_binding(db, telegram_chat_id=telegram_chat_id, binding=None)


def save_in_progress_engine(
    db: Session,
    *,
    telegram_chat_id: str,
    engine: SessionEngine,
    binding: ChatBinding | None,
) -> None:
    if not persist_db_enabled():
        return
    if isinstance(engine, AkmaDialogEngine):
        return
    session = engine.session
    if session.status.value not in ACTIVE_SESSION_STATUSES:
        return
    payload = serialize_session_engine(engine)
    started = session.started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    row = db.get(PtTestSession, session.session_id)
    if row is None:
        row = PtTestSession(
            id=session.session_id,
            client_id=session.client_id,
            employee_id=session.employee_id,
            test_id=session.test_id,
            test_version=session.test_version,
            status=session.status.value,
            assignment_id=binding.active_assignment_id if binding else None,
            telegram_chat_id=str(telegram_chat_id).strip(),
            delivery_mode="structured",
            step_key=binding.active_step_key if binding else None,
            started_at=started,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        db.add(row)
    else:
        row.status = session.status.value
        row.payload_json = json.dumps(payload, ensure_ascii=False)
        row.telegram_chat_id = str(telegram_chat_id).strip()
        if binding:
            row.assignment_id = binding.active_assignment_id
            row.step_key = binding.active_step_key
    db.commit()
    sync_process_context_from_binding(
        db,
        telegram_chat_id=telegram_chat_id,
        binding=binding,
        active_session_id=session.session_id,
    )


def save_completed_session_document(db: Session, document: dict[str, Any]) -> None:
    if not persist_db_enabled():
        return
    session_id = str(document.get("session_id") or "").strip()
    if not session_id:
        return
    completed = _parse_dt(str(document.get("completed_at") or "")) or _utc_now()
    started = _parse_dt(str(document.get("started_at") or ""))
    row = db.get(PtTestSession, session_id)
    if row is None:
        row = PtTestSession(
            id=session_id,
            client_id=str(document.get("client_id") or ""),
            employee_id=str(document.get("employee_id") or ""),
            test_id=str(document.get("test_id") or ""),
            test_version=str(document.get("test_version") or "1.0.0"),
            status=str(document.get("status") or "done"),
            assignment_id=str(document.get("assignment_id") or "") or None,
            telegram_chat_id=str(document.get("telegram_chat_id") or "") or None,
            delivery_mode=str(document.get("delivery_mode") or "structured"),
            step_key=str(document.get("step_key") or "") or None,
            started_at=started,
            completed_at=completed,
            payload_json=json.dumps(document, ensure_ascii=False),
        )
        db.add(row)
    else:
        row.status = str(document.get("status") or "done")
        row.completed_at = completed
        row.payload_json = json.dumps(document, ensure_ascii=False)
    db.commit()


def mark_session_cancelled(db: Session, session_id: str) -> None:
    if not persist_db_enabled():
        return
    row = db.get(PtTestSession, session_id)
    if row is None:
        return
    row.status = "cancelled"
    row.completed_at = _utc_now()
    db.commit()


def load_binding_into_store(
    db: Session,
    store: PsychTestingSessionStore,
    *,
    telegram_chat_id: str,
) -> ChatBinding | None:
    if not persist_db_enabled():
        return store.get_binding(telegram_chat_id)
    chat = str(telegram_chat_id).strip()
    ctx = db.scalars(
        select(PtTelegramProcessContext).where(PtTelegramProcessContext.telegram_chat_id == chat)
    ).first()
    if ctx is None or ctx.active_flow != "psych_testing":
        return store.get_binding(telegram_chat_id)
    binding = store.ensure_binding(
        chat,
        client_id=str(ctx.client_id or ""),
        employee_id=str(ctx.employee_id or ""),
    )
    binding.context = "psych_testing"
    binding.active_test_id = ctx.active_test_id
    binding.active_step_key = ctx.active_step_key
    binding.active_assignment_id = ctx.active_assignment_id
    binding.mbti_delivery_mode = ctx.mbti_delivery_mode
    return binding


def try_restore_engine_for_chat(
    db: Session,
    store: PsychTestingSessionStore,
    *,
    telegram_chat_id: str,
    registry: Any,
    voice_pipeline: Any | None = None,
) -> SessionEngine | None:
    if store.get_engine(telegram_chat_id) is not None:
        engine = store.get_engine(telegram_chat_id)
        return engine if isinstance(engine, SessionEngine) else None
    if not persist_db_enabled():
        return None
    chat = str(telegram_chat_id).strip()
    ctx = db.scalars(
        select(PtTelegramProcessContext).where(PtTelegramProcessContext.telegram_chat_id == chat)
    ).first()
    if ctx is None or not ctx.active_session_id or ctx.active_flow != "psych_testing":
        return None
    row = db.get(PtTestSession, str(ctx.active_session_id))
    if row is None or row.status not in ACTIVE_SESSION_STATUSES:
        return None
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        return None
    engine = restore_session_engine(payload, registry, voice_pipeline=voice_pipeline)
    if engine is None:
        return None
    load_binding_into_store(db, store, telegram_chat_id=chat)
    store.set_engine(chat, engine)
    _log.info(
        "psych_testing: restored in-progress session chat=%s session=%s test=%s idx=%s",
        chat,
        engine.session.session_id,
        engine.session.test_id,
        engine.session.current_item_index,
    )
    return engine


def session_document_from_row(row: PtTestSession) -> dict[str, Any] | None:
    try:
        doc = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(doc, dict):
        return None
    if str(doc.get("schema") or "") == "pt_runtime_v1":
        return None
    if row.status != "done":
        return None
    return doc


def list_completed_session_rows(
    db: Session,
    *,
    client_id: str | None = None,
) -> list[PtTestSession]:
    q = select(PtTestSession).where(PtTestSession.status == "done")
    if client_id:
        q = q.where(PtTestSession.client_id == client_id)
    q = q.order_by(PtTestSession.completed_at.desc(), PtTestSession.updated_at.desc())
    return list(db.scalars(q).all())


__all__ = [
    "clear_process_context",
    "list_completed_session_rows",
    "load_binding_into_store",
    "mark_session_cancelled",
    "persist_db_enabled",
    "save_completed_session_document",
    "save_in_progress_engine",
    "session_document_from_row",
    "sync_process_context_from_binding",
    "try_restore_engine_for_chat",
    "upsert_telegram_binding",
]
