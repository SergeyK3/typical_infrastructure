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
from psychological_testing.shared_engine.interpretation_engine import InterpretationResult
from psychological_testing.shared_engine.session_state_machine import SessionEngine

_log = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0.0"


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
            profile = {
                "code": interp.profile.code,
                "name_ru": interp.profile.name_ru,
                "tagline": interp.profile.tagline,
                "strengths": list(interp.profile.strengths),
                "growth_areas": list(interp.profile.growth_areas),
                "axes": dict(interp.profile.axes),
            }
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

    return {
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
    return path
