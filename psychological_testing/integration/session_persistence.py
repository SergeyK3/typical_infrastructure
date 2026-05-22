"""
Canonical session result JSON (Phase 3b: files; Phase 4: ``pt_*`` tables).

Enable file sink: ``PSYCH_TESTING_PERSIST_JSON=1``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psychological_testing.domain.entities import (
    ScoreResult,
    SessionStatus,
    StructuredAnswer,
    TestSession,
)
from psychological_testing.research.mbti.scripts.akma_dialog_engine import AkmaDialogEngine
from psychological_testing.shared_engine.interpretation_engine import (
    InterpretationResult,
    profile_to_dict,
)
from psychological_testing.shared_engine.session_state_machine import SessionEngine

from psychological_testing.shared_engine.report_contract import (
    AI_ENRICHMENT_SCHEMA_VERSION,
    merge_ai_enrichment,
    validate_ai_enrichment,
)

_log = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"
SESSION_SCHEMA_VERSION_WITH_AI = "1.1.0"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def persist_json_enabled() -> bool:
    return os.getenv("PSYCH_TESTING_PERSIST_JSON", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def sessions_dir() -> Path:
    raw = os.getenv("PSYCH_TESTING_SESSIONS_DIR", "").strip()
    if raw:
        return Path(raw)
    root = Path(__file__).resolve().parents[1]
    return root / "data" / "sessions" / "v1"


def _serialize_answer(a: StructuredAnswer) -> dict[str, Any]:
    return {
        "item_id": a.item_id,
        "axis": a.axis,
        "input_channel": a.input_channel,
        "raw_input": a.raw_input,
        "resolved_value": a.resolved_value,
        "confidence": a.confidence,
        "resolver_method": a.resolver_method,
    }


def _serialize_score(score: ScoreResult | None) -> dict[str, Any] | None:
    if score is None:
        return None
    return {
        "raw_scores": dict(score.raw_scores),
        "normalized_scores": dict(score.normalized_scores),
        "typology_code": score.typology_code,
        "axis_details": dict(score.axis_details),
        "metadata": dict(score.metadata),
    }


def _serialize_interpretation(interp: Any) -> dict[str, Any] | None:
    if interp is None:
        return None
    if isinstance(interp, InterpretationResult):
        profile = None
        if interp.profile is not None:
            profile = profile_to_dict(interp.profile)
        return {
            "typology_code": interp.typology_code,
            "profile": profile,
            "axis_details": dict(interp.axis_details),
            "metadata": dict(interp.metadata),
        }
    if is_dataclass(interp):
        return asdict(interp)
    return {"value": str(interp)}


def _audit_block() -> dict[str, str]:
    from psychological_testing.services.llm_service import llm_provider
    from psychological_testing.services.stt_service import stt_provider

    return {
        "stt_provider": stt_provider(),
        "llm_provider": llm_provider(),
    }


def build_session_result_document(
    engine: SessionEngine | AkmaDialogEngine,
    *,
    telegram_chat_id: str,
    report_text: str,
    employee_display_name: str | None = None,
    delivery_mode: str = "structured",
    assignment_id: str | None = None,
) -> dict[str, Any]:
    """Build canonical ``pt_session_result`` v1 dict (not yet persisted)."""
    session: TestSession = engine.session
    definition = engine.definition
    completed_at = _utc_now()

    dialog_akma: dict[str, Any] | None = None
    engine_kind = "session_engine"
    if isinstance(engine, AkmaDialogEngine):
        engine_kind = "akma_dialog_engine"
        delivery_mode = "dialog"
        st = engine.akma_state
        dialog_akma = {
            "counters": dict(st.counters),
            "type_code": st.type_code,
            "llm_calls": st.llm_calls,
            "errors_count": st.errors_count,
            "max_questions": st.max_questions,
            "questions_answered": st.num,
        }

    audit = _audit_block()
    audit["engine"] = engine_kind

    doc: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session.session_id,
        "client_id": session.client_id,
        "employee_id": session.employee_id,
        "employee_display_name": employee_display_name,
        "telegram_chat_id": str(telegram_chat_id),
        "test_id": session.test_id,
        "test_version": session.test_version,
        "delivery_mode": delivery_mode,
        "scoring_type": definition.scoring_type,
        "status": SessionStatus.DONE.value,
        "started_at": _iso(session.started_at),
        "completed_at": _iso(completed_at),
        "responses": [_serialize_answer(r) for r in session.responses],
        "raw_transcripts": list(session.raw_transcripts),
        "scores": _serialize_score(session.score_result),
        "interpretation": _serialize_interpretation(session.interpretation),
        "report": {
            "text_telegram": report_text,
            "pdf_ref": None,
        },
        "dialog_akma": dialog_akma,
        "audit": audit,
    }
    if assignment_id:
        doc["assignment_id"] = assignment_id
    return doc


def apply_ai_enrichment(
    document: dict[str, Any],
    enrichment: dict[str, Any],
    *,
    merge_sections: bool = True,
) -> dict[str, Any]:
    """Return session document with merged ``ai_enrichment`` (schema v1.1)."""
    return merge_ai_enrichment(
        document,
        enrichment,
        merge_sections=merge_sections,
    )


def update_session_ai_enrichment(
    session_id: str,
    enrichment: dict[str, Any],
    *,
    merge_sections: bool = True,
) -> Path | None:
    """
    Load persisted session JSON, merge ``ai_enrichment``, write back.

    Returns path when ``PSYCH_TESTING_PERSIST_JSON=1``, else None.
    """
    from psychological_testing.integration.session_repository import get_session_document

    doc = get_session_document(session_id)
    if doc is None:
        raise KeyError(f"session not found: {session_id}")
    updated = apply_ai_enrichment(doc, enrichment, merge_sections=merge_sections)
    return persist_session_result(updated)


def validate_session_ai_enrichment(enrichment: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Validate ``ai_enrichment`` block against contract v1."""
    return validate_ai_enrichment(enrichment)


def persist_session_result(document: dict[str, Any]) -> Path | None:
    """
    Phase 3b: write JSON file under ``data/sessions/v1/YYYY-MM-DD/{session_id}.json``.

    Phase 4: replace body with INSERT into ``pt_test_sessions`` (same document shape).
    """
    if not persist_json_enabled():
        return None
    session_id = str(document.get("session_id") or "unknown")
    completed = document.get("completed_at") or _iso(_utc_now())
    day = str(completed)[:10] if completed else _utc_now().date().isoformat()
    out_dir = sessions_dir() / day
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{session_id}.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    _log.info("psych_testing: session result saved %s", path)
    _maybe_upload_session_to_drive(document, path)
    _maybe_persist_session_db(document)
    return path


def _maybe_persist_session_db(document: dict[str, Any]) -> None:
    try:
        from app.services.psych_session_db import persist_db_enabled, save_completed_session_document

        if not persist_db_enabled():
            return
        from app.db import SessionLocal

        db = SessionLocal()
        try:
            save_completed_session_document(db, document)
        finally:
            db.close()
    except Exception:
        _log.exception("psych_testing: DB session persist failed")


def _maybe_upload_session_to_drive(document: dict[str, Any], local_path: Path) -> None:
    from psychological_testing.integration.report_storage import (
        gdrive_upload_sessions_enabled,
        upload_json_to_drive,
    )

    if not gdrive_upload_sessions_enabled():
        return
    try:
        client_id = str(document.get("client_id") or "unknown")
        session_id = str(document.get("session_id") or local_path.stem)
        completed = str(document.get("completed_at") or "")[:10]
        ref = upload_json_to_drive(
            document,
            filename=f"{session_id}.json",
            client_id=client_id,
            day=completed or None,
        )
        report = document.get("report")
        if not isinstance(report, dict):
            report = {}
            document["report"] = report
        report["session_json_drive_ref"] = ref
        local_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        _log.warning("psych_testing: session Drive upload failed: %s", exc)


__all__ = [
    "AI_ENRICHMENT_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "SESSION_SCHEMA_VERSION_WITH_AI",
    "apply_ai_enrichment",
    "build_session_result_document",
    "persist_json_enabled",
    "persist_session_result",
    "sessions_dir",
    "update_session_ai_enrichment",
    "validate_session_ai_enrichment",
]
