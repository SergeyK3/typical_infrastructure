"""Persist report manifests and optional PDF cache (Phase E file store)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from psychological_testing.domain.test_registry import package_root


def exports_root() -> Path:
    raw = os.getenv("PSYCH_TESTING_EXPORTS_DIR", "").strip()
    if raw:
        return Path(raw)
    return package_root() / "data" / "report_exports"


def _slug_name(value: str, *, max_len: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "_", text.strip())
    return (text or "employee")[:max_len]


def pdf_cache_mode() -> str:
    return (os.getenv("PSYCH_TESTING_PDF_CACHE", "off") or "off").strip().lower()


def manifest_cache_key(manifest: dict[str, Any]) -> str:
    payload = {
        "schema_version": manifest.get("schema_version"),
        "template_id": manifest.get("template_id"),
        "session_refs": manifest.get("session_refs"),
        "sections": manifest.get("sections"),
        "ai_cache": manifest.get("ai_cache"),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def save_manifest(
    manifest: dict[str, Any],
    *,
    employee_display_name: str | None = None,
) -> Path:
    """Write manifest JSON under ``{exports_root}/{client_id}/``."""
    client_id = str(manifest.get("client_id") or "unknown")
    manifest_id = str(manifest.get("manifest_id") or uuid4())
    manifest["manifest_id"] = manifest_id
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = exports_root() / client_id / day
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug_name(employee_display_name or str(manifest.get("employee_id") or "emp"))
    path = out_dir / f"{slug}_{manifest_id[:8]}_manifest.json"
    wrapper = {
        "schema_version": "1.0.0",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest,
    }
    path.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_pdf_cache(
    manifest: dict[str, Any],
    pdf_bytes: bytes,
    *,
    employee_display_name: str | None = None,
) -> str | None:
    """
    Store PDF when ``PSYCH_TESTING_PDF_CACHE`` is ``hash`` or ``on``.

    Returns ``pdf_ref`` relative path from package root, or None.
    """
    mode = pdf_cache_mode()
    if mode not in ("hash", "on", "1", "true"):
        return None
    client_id = str(manifest.get("client_id") or "unknown")
    manifest_id = str(manifest.get("manifest_id") or uuid4())
    cache_key = manifest_cache_key(manifest) if mode == "hash" else manifest_id[:12]
    slug = _slug_name(employee_display_name or str(manifest.get("employee_id") or "emp"))
    rel = Path("data/report_exports") / client_id / f"{slug}_{cache_key}.pdf"
    path = package_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    return str(rel).replace("\\", "/")


def resolve_pdf_ref(pdf_ref: str) -> Path | None:
    """Resolve local ``pdf_ref`` to absolute path if file exists (not Drive)."""
    from psychological_testing.integration.report_storage import is_gdrive_ref

    if is_gdrive_ref(pdf_ref):
        return None
    ref = pdf_ref.strip().lstrip("/")
    candidates = [
        package_root() / ref,
        exports_root() / ref,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None
