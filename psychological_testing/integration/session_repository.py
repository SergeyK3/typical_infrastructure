"""Read persisted psychological testing session results (Phase 3b JSON files)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psychological_testing.integration.session_persistence import persist_json_enabled, sessions_dir


def _iter_session_files() -> list[Path]:
    root = sessions_dir()
    if not root.is_dir():
        return []
    return sorted(root.glob("*/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def _load_document(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _summary_from_document(doc: dict[str, Any]) -> dict[str, Any]:
    scores = doc.get("scores") or {}
    interpretation = doc.get("interpretation") or {}
    typology = scores.get("typology_code") if isinstance(scores, dict) else None
    if not typology and isinstance(interpretation, dict):
        typology = interpretation.get("typology_code")
    report = doc.get("report") or {}
    report_preview = ""
    if isinstance(report, dict):
        text = str(report.get("text_telegram") or "")
        report_preview = text[:240] + ("…" if len(text) > 240 else "")
    return {
        "session_id": doc.get("session_id"),
        "client_id": doc.get("client_id"),
        "employee_id": doc.get("employee_id"),
        "employee_display_name": doc.get("employee_display_name"),
        "test_id": doc.get("test_id"),
        "test_version": doc.get("test_version"),
        "delivery_mode": doc.get("delivery_mode"),
        "status": doc.get("status"),
        "started_at": doc.get("started_at"),
        "completed_at": doc.get("completed_at"),
        "typology_code": typology,
        "report_preview": report_preview,
    }


def list_session_summaries(
    *,
    client_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Return session summary dicts and total count (newest first)."""
    rows: list[dict[str, Any]] = []
    for path in _iter_session_files():
        doc = _load_document(path)
        if not doc:
            continue
        if client_id and str(doc.get("client_id") or "") != client_id:
            continue
        summary = _summary_from_document(doc)
        if not summary.get("session_id"):
            continue
        rows.append(summary)
    total = len(rows)
    page = rows[offset : offset + limit]
    return page, total


def latest_telegram_chat_for_employee(employee_id: str) -> str | None:
    """Last known ``telegram_chat_id`` from persisted session JSON for this employee."""
    eid = str(employee_id).strip()
    if not eid:
        return None
    for path in _iter_session_files():
        doc = _load_document(path)
        if not doc or str(doc.get("employee_id") or "") != eid:
            continue
        chat = str(doc.get("telegram_chat_id") or "").strip()
        if chat:
            return chat
    return None


def get_session_document(session_id: str) -> dict[str, Any] | None:
    for path in _iter_session_files():
        if path.stem != session_id:
            continue
        return _load_document(path)
    return None


def latest_sessions_by_test_for_employee(
    employee_id: str,
    *,
    client_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Return latest ``done`` session document per ``test_id`` for an employee.

    Newer ``completed_at`` wins; file mtime breaks ties.
    """
    eid = str(employee_id).strip()
    if not eid:
        return {}

    best: dict[str, tuple[str, float, dict[str, Any]]] = {}
    for path in _iter_session_files():
        doc = _load_document(path)
        if not doc:
            continue
        if str(doc.get("employee_id") or "") != eid:
            continue
        if client_id and str(doc.get("client_id") or "") != client_id:
            continue
        if str(doc.get("status") or "") != "done":
            continue
        test_id = str(doc.get("test_id") or "").strip()
        if not test_id:
            continue
        completed = str(doc.get("completed_at") or "")
        mtime = path.stat().st_mtime
        prev = best.get(test_id)
        if prev is None or completed > prev[0] or (completed == prev[0] and mtime > prev[1]):
            best[test_id] = (completed, mtime, doc)

    return {test_id: doc for test_id, (_, _, doc) in best.items()}


def build_session_refs_for_employee(
    employee_id: str,
    test_ids: list[str] | tuple[str, ...],
    *,
    client_id: str | None = None,
) -> list[dict[str, str]]:
    """Build manifest ``session_refs`` from latest persisted sessions."""
    latest = latest_sessions_by_test_for_employee(employee_id, client_id=client_id)
    refs: list[dict[str, str]] = []
    for test_id in test_ids:
        doc = latest.get(test_id)
        if doc is None:
            continue
        sid = str(doc.get("session_id") or "").strip()
        if sid:
            refs.append({"test_id": test_id, "session_id": sid})
    return refs


def module_status() -> dict[str, Any]:
    """Lightweight status for workspace UI."""
    from psychological_testing.domain.test_registry import TestRegistry
    from psychological_testing.integration.manifest_store import pdf_cache_mode
    from psychological_testing.integration.report_storage import storage_status

    registry = TestRegistry()
    test_ids = registry.list_test_ids()
    persist_on = persist_json_enabled()
    session_count = len(_iter_session_files()) if persist_on else 0
    return {
        "persist_json_enabled": persist_on,
        "sessions_dir": str(sessions_dir()),
        "session_count": session_count,
        "pdf_cache_mode": pdf_cache_mode(),
        **storage_status(),
        "available_tests": [
            {
                "test_id": tid,
                "display_name": registry.get(tid).display_name or tid,
            }
            for tid in sorted(test_ids)
        ],
        "telegram_commands": [f"/start {tid}" for tid in sorted(test_ids)],
    }
