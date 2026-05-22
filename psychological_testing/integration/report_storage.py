"""
Report artifact storage: local files + optional Google Drive (service account).

``pdf_ref``: local path, ``gdrive:{file_id}``, or full Drive URL.
Use :func:`artifact_open_url` for UI/API links (storage-agnostic).
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from psychological_testing.integration import google_drive_client as gdrive
from psychological_testing.integration.filename_translit import ascii_slug_from_name

_log = logging.getLogger(__name__)

GDRIVE_REF_PREFIX = "gdrive:"
DEFAULT_API_PREFIX = "/api/psychological-testing"


def _load_gdrive_env() -> None:
    from psychological_testing.env import load_plugin_env

    load_plugin_env(override=False)


def gdrive_enabled() -> bool:
    _load_gdrive_env()
    return os.getenv("PSYCH_TESTING_GDRIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def gdrive_upload_sessions_enabled() -> bool:
    if not gdrive_enabled():
        return False
    return os.getenv("PSYCH_TESTING_GDRIVE_UPLOAD_SESSIONS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def gdrive_upload_manifest_enabled() -> bool:
    if not gdrive_enabled():
        return False
    raw = os.getenv("PSYCH_TESTING_GDRIVE_UPLOAD_MANIFEST", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def make_gdrive_ref(file_id: str) -> str:
    return f"{GDRIVE_REF_PREFIX}{file_id}"


def is_gdrive_ref(ref: str) -> bool:
    text = ref.strip()
    return text.startswith(GDRIVE_REF_PREFIX) or "drive.google.com/file/d/" in text


def parse_gdrive_file_id(ref: str) -> str | None:
    text = ref.strip()
    if text.startswith(GDRIVE_REF_PREFIX):
        return text[len(GDRIVE_REF_PREFIX) :] or None
    match = re.search(r"drive\.google\.com/file/d/([^/]+)", text)
    if match:
        return match.group(1)
    return None


def gdrive_web_link(ref: str) -> str | None:
    file_id = parse_gdrive_file_id(ref)
    if not file_id:
        return None
    return gdrive.web_view_link(file_id)


def storage_kind_for_ref(pdf_ref: str | None) -> str | None:
    """``gdrive`` | ``local`` | ``url`` | None."""
    if not pdf_ref or not str(pdf_ref).strip():
        return None
    ref = str(pdf_ref).strip()
    if is_gdrive_ref(ref):
        return "gdrive"
    if ref.startswith("http://") or ref.startswith("https://"):
        return "url"
    return "local"


def artifact_open_url(
    pdf_ref: str | None,
    *,
    client_id: str | None = None,
    api_prefix: str = DEFAULT_API_PREFIX,
) -> str | None:
    """
    Browser-openable URL for HR (Drive view, API download for local cache, passthrough URL).
    """
    if not pdf_ref or not str(pdf_ref).strip():
        return None
    ref = str(pdf_ref).strip()
    if is_gdrive_ref(ref):
        return gdrive_web_link(ref)
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref
    if not client_id:
        return None
    qs = urlencode({"pdf_ref": ref, "client_id": client_id})
    return f"{api_prefix.rstrip('/')}/export-pdf/file?{qs}"


def artifact_link_label(storage_kind: str | None) -> str:
    if storage_kind == "gdrive":
        return "Открыть в Google Drive"
    if storage_kind == "local":
        return "Скачать PDF"
    if storage_kind == "url":
        return "Открыть отчёт"
    return "Открыть отчёт"


def storage_status_label(
    *,
    gdrive_enabled_flag: bool | None = None,
    gdrive_configured_flag: bool | None = None,
) -> str:
    """Human-readable line for workspace /status."""
    if gdrive_configured_flag is None or gdrive_enabled_flag is None:
        st = storage_status(include_label=False)
        gdrive_enabled_flag = bool(st["gdrive_enabled"])
        gdrive_configured_flag = bool(st["gdrive_configured"])
    if gdrive_configured_flag:
        return "Google Drive (настроено)"
    if gdrive_enabled_flag:
        return (
            "Google Drive (включено, не настроено — "
            "проверьте SA и PSYCH_TESTING_GDRIVE_FOLDER_ID)"
        )
    return "локально (data/report_exports/)"


def _resolve_client_display_name(client_id: str) -> str:
    """Organization title from HR ``clients.name`` (fallback: ``code``, then ``client_id``)."""
    cid = str(client_id or "").strip()
    if not cid:
        return "unknown"
    try:
        from app.db import SessionLocal
        from app.models import Client

        db = SessionLocal()
        try:
            client = db.get(Client, cid)
            if client is not None:
                name = str(client.name or "").strip()
                if name:
                    return name
                code = str(client.code or "").strip()
                if code:
                    return code
        finally:
            db.close()
    except Exception as exc:
        _log.warning(
            "psych_testing: client name lookup failed for %s: %s",
            cid,
            exc,
        )
    return cid


def client_folder_slug(*, client_id: str, client_name: str | None = None) -> str:
    """Folder slug from ``client_name`` or HR lookup: ``ТОО Один`` → ``TOO_Odin``."""
    explicit = str(client_name or "").strip()
    label = explicit or _resolve_client_display_name(client_id)
    slug = ascii_slug_from_name(label, max_len=80, fallback="")
    if slug:
        return slug
    return str(client_id or "unknown")


def client_drive_folder_name(client_id: str, client_name: str | None = None) -> str:
    return client_folder_slug(client_id=client_id, client_name=client_name)


def drive_export_path_parts(
    client_id: str,
    day: str | None = None,
    *,
    client_name: str | None = None,
) -> list[str]:
    """Shared Drive layout under configured root: ``{YYYY-MM-DD}/{client_name}/``."""
    resolved_day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [resolved_day, client_folder_slug(client_id=client_id, client_name=client_name)]


def _drive_target_folder(
    client_id: str,
    day: str | None = None,
    *,
    client_name: str | None = None,
) -> str:
    service = gdrive._build_drive_service()
    root = gdrive.root_folder_id()
    return gdrive.ensure_path_folder(
        service,
        root,
        drive_export_path_parts(client_id, day, client_name=client_name),
    )


def upload_pdf_to_drive(
    pdf_bytes: bytes,
    *,
    filename: str,
    client_id: str,
    day: str | None = None,
    client_name: str | None = None,
) -> str:
    """Upload PDF; return ``gdrive:{file_id}`` ref."""
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_id = _drive_target_folder(client_id, day, client_name=client_name)
    result = gdrive.upload_bytes(
        pdf_bytes,
        filename=filename,
        mime_type="application/pdf",
        parent_folder_id=folder_id,
    )
    return make_gdrive_ref(result["file_id"])


def upload_json_to_drive(
    payload: dict[str, Any] | bytes,
    *,
    filename: str,
    client_id: str,
    day: str | None = None,
    client_name: str | None = None,
) -> str:
    if isinstance(payload, dict):
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    else:
        data = payload
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_id = _drive_target_folder(client_id, day, client_name=client_name)
    result = gdrive.upload_bytes(
        data,
        filename=filename,
        mime_type="application/json",
        parent_folder_id=folder_id,
    )
    return make_gdrive_ref(result["file_id"])


def upload_manifest_file(manifest_path: Path, *, client_id: str) -> str | None:
    if not gdrive_upload_manifest_enabled():
        return None
    try:
        wrapper = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("psych_testing: manifest upload skipped: %s", exc)
        return None
    manifest = wrapper.get("manifest") if isinstance(wrapper, dict) else wrapper
    if not isinstance(manifest, dict):
        manifest = wrapper
    manifest_id = str((manifest or {}).get("manifest_id") or manifest_path.stem)
    client_name = (manifest or {}).get("client_name")
    day = manifest_path.parent.name
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = None
    return upload_json_to_drive(
        wrapper if isinstance(wrapper, dict) else {"manifest": manifest},
        filename=f"{manifest_id[:8]}_manifest.json",
        client_id=client_id,
        day=day,
        client_name=str(client_name).strip() if client_name else None,
    )


def download_pdf(ref: str) -> bytes | None:
    """Load PDF bytes from Drive ref."""
    if not is_gdrive_ref(ref):
        return None
    file_id = parse_gdrive_file_id(ref)
    if not file_id:
        return None
    try:
        return gdrive.download_bytes(file_id)
    except Exception as exc:
        _log.warning("psych_testing: Drive download failed %s: %s", file_id, exc)
        return None


def sync_pdf_ref_to_sessions(
    manifest: dict[str, Any],
    pdf_ref: str,
) -> int:
    """Write ``report.pdf_ref`` into persisted session JSONs listed in manifest."""
    from psychological_testing.integration.session_persistence import (
        persist_json_enabled,
        persist_session_result,
    )
    from psychological_testing.integration.session_repository import get_session_document

    if not persist_json_enabled() or not pdf_ref:
        return 0

    updated = 0
    for ref in manifest.get("session_refs") or []:
        if not isinstance(ref, dict):
            continue
        session_id = str(ref.get("session_id") or "").strip()
        if not session_id:
            continue
        doc = get_session_document(session_id)
        if doc is None:
            continue
        report = doc.get("report")
        if not isinstance(report, dict):
            report = {}
            doc["report"] = report
        if report.get("pdf_ref") == pdf_ref:
            continue
        report["pdf_ref"] = pdf_ref
        if persist_session_result(doc):
            updated += 1
    return updated


def export_artifact_metadata(
    pdf_ref: str | None,
    *,
    client_id: str | None,
) -> dict[str, str | None]:
    """``pdf_ref``, ``pdf_open_url``, ``storage_kind`` for API responses."""
    kind = storage_kind_for_ref(pdf_ref)
    return {
        "pdf_ref": pdf_ref,
        "pdf_open_url": artifact_open_url(pdf_ref, client_id=client_id),
        "storage_kind": kind,
    }


def storage_status(*, include_label: bool = True) -> dict[str, Any]:
    """Flags for module status / workspace."""
    enabled = gdrive_enabled()
    creds = bool(
        os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "").strip()
        or os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_INLINE", "").strip()
    )
    configured = enabled and creds and bool(
        os.getenv("PSYCH_TESTING_GDRIVE_FOLDER_ID", "").strip()
    )
    result: dict[str, Any] = {
        "gdrive_enabled": enabled,
        "gdrive_configured": configured,
        "gdrive_upload_sessions": gdrive_upload_sessions_enabled(),
        "gdrive_upload_manifest": gdrive_upload_manifest_enabled() if enabled else False,
    }
    if include_label:
        result["storage_label"] = storage_status_label(
            gdrive_enabled_flag=enabled,
            gdrive_configured_flag=configured,
        )
    return result


__all__ = [
    "DEFAULT_API_PREFIX",
    "GDRIVE_REF_PREFIX",
    "artifact_link_label",
    "artifact_open_url",
    "client_drive_folder_name",
    "client_folder_slug",
    "download_pdf",
    "drive_export_path_parts",
    "export_artifact_metadata",
    "gdrive_enabled",
    "gdrive_upload_manifest_enabled",
    "gdrive_upload_sessions_enabled",
    "gdrive_web_link",
    "is_gdrive_ref",
    "make_gdrive_ref",
    "parse_gdrive_file_id",
    "storage_kind_for_ref",
    "storage_status",
    "storage_status_label",
    "sync_pdf_ref_to_sessions",
    "upload_json_to_drive",
    "upload_manifest_file",
    "upload_pdf_to_drive",
]
