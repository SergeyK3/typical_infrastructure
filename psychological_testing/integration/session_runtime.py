"""Serialize / restore in-progress SessionEngine for DB resume (Phase 4)."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from typing import Any

from psychological_testing.domain.entities import (
    SessionStatus,
    StructuredAnswer,
    TestDefinition,
    TestSession,
)
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.shared_engine.item_bank_loader import (
    DimensionBankItem,
    ForcedChoiceItem,
    LikertBankItem,
)
from psychological_testing.shared_engine.question_selector import SelectableItem
from psychological_testing.shared_engine.session_state_machine import SessionEngine
from psychological_testing.shared_engine.voice_pipeline import VoicePipeline

RUNTIME_SCHEMA = "pt_runtime_v1"


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _serialize_item(item: Any) -> dict[str, Any]:
    if isinstance(item, SelectableItem):
        return {"kind": "selectable", "data": asdict(item)}
    if isinstance(item, LikertBankItem):
        return {"kind": "likert", "data": asdict(item)}
    if isinstance(item, ForcedChoiceItem):
        return {"kind": "forced_choice", "data": asdict(item)}
    if isinstance(item, DimensionBankItem):
        return {"kind": "dimension", "data": asdict(item)}
    raise TypeError(f"unsupported session item type: {type(item)!r}")


def _deserialize_item(raw: dict[str, Any]) -> Any:
    kind = str(raw.get("kind") or "")
    data = raw.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("invalid item payload")
    if kind == "selectable":
        return SelectableItem(**data)
    if kind == "likert":
        return LikertBankItem(**data)
    if kind == "forced_choice":
        return ForcedChoiceItem(**data)
    if kind == "dimension":
        return DimensionBankItem(**data)
    raise ValueError(f"unknown item kind: {kind!r}")


def _serialize_answer(answer: StructuredAnswer) -> dict[str, Any]:
    return {
        "item_id": answer.item_id,
        "axis": answer.axis,
        "input_channel": answer.input_channel,
        "raw_input": answer.raw_input,
        "resolved_value": answer.resolved_value,
        "confidence": answer.confidence,
        "resolver_method": answer.resolver_method,
    }


def _deserialize_answer(raw: dict[str, Any]) -> StructuredAnswer:
    return StructuredAnswer(
        item_id=str(raw.get("item_id") or ""),
        input_channel=raw.get("input_channel") or "button",  # type: ignore[arg-type]
        raw_input=str(raw.get("raw_input") or ""),
        resolved_value=raw.get("resolved_value"),
        confidence=float(raw.get("confidence") or 1.0),
        resolver_method=str(raw.get("resolver_method") or "restored"),
        axis=raw.get("axis"),
    )


def serialize_session_engine(engine: SessionEngine) -> dict[str, Any]:
    session = engine.session
    return {
        "schema": RUNTIME_SCHEMA,
        "engine_kind": "session_engine",
        "definition_selection": dict(engine.definition.selection or {}),
        "session": {
            "session_id": session.session_id,
            "client_id": session.client_id,
            "employee_id": session.employee_id,
            "test_id": session.test_id,
            "test_version": session.test_version,
            "status": session.status.value,
            "started_at": _iso(session.started_at),
            "current_item_index": session.current_item_index,
            "responses": [_serialize_answer(r) for r in session.responses],
            "raw_transcripts": list(session.raw_transcripts),
            "items": [_serialize_item(i) for i in session.items],
            "reprompt_message": session.reprompt_message,
        },
    }


def restore_session_engine(
    payload: dict[str, Any],
    registry: TestRegistry,
    *,
    voice_pipeline: VoicePipeline | None = None,
) -> SessionEngine | None:
    if str(payload.get("schema") or "") != RUNTIME_SCHEMA:
        return None
    if str(payload.get("engine_kind") or "") != "session_engine":
        return None
    raw_session = payload.get("session")
    if not isinstance(raw_session, dict):
        return None
    test_id = str(raw_session.get("test_id") or "")
    if not test_id:
        return None
    try:
        definition = registry.get(test_id)
    except KeyError:
        return None
    selection = payload.get("definition_selection")
    if isinstance(selection, dict) and selection:
        definition = replace(definition, selection={**definition.selection, **selection})
    items_raw = raw_session.get("items") or []
    items = [_deserialize_item(x) for x in items_raw if isinstance(x, dict)]
    responses = [
        _deserialize_answer(x) for x in (raw_session.get("responses") or []) if isinstance(x, dict)
    ]
    status_raw = str(raw_session.get("status") or SessionStatus.QUESTIONING.value)
    try:
        status = SessionStatus(status_raw)
    except ValueError:
        status = SessionStatus.QUESTIONING
    session = TestSession(
        session_id=str(raw_session.get("session_id") or ""),
        client_id=str(raw_session.get("client_id") or ""),
        employee_id=str(raw_session.get("employee_id") or ""),
        test_id=test_id,
        test_version=str(raw_session.get("test_version") or definition.version),
        status=status,
        started_at=_parse_dt(raw_session.get("started_at")) or datetime.now(timezone.utc),
        items=items,
        responses=responses,
        raw_transcripts=[str(x) for x in (raw_session.get("raw_transcripts") or [])],
        current_item_index=int(raw_session.get("current_item_index") or 0),
        reprompt_message=raw_session.get("reprompt_message"),
    )
    return SessionEngine(
        definition,
        session,
        voice_pipeline=voice_pipeline or VoicePipeline(),
    )


__all__ = [
    "RUNTIME_SCHEMA",
    "restore_session_engine",
    "serialize_session_engine",
]
