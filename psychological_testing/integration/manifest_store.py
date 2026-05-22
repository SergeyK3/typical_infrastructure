"""Persist report manifests and optional PDF cache (Phase E file store)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from psychological_testing.domain.test_registry import package_root


def exports_root() -> Path:
    from psychological_testing.env import load_plugin_env

    load_plugin_env(override=False)
    raw = os.getenv("PSYCH_TESTING_EXPORTS_DIR", "").strip()
    if raw:
        return Path(raw)
    return package_root() / "data" / "report_exports"


from psychological_testing.integration.filename_translit import ascii_slug_from_name

_log = logging.getLogger(__name__)


def _slug_name(value: str, *, max_len: int = 40) -> str:
    slug = ascii_slug_from_name(value, max_len=max_len, fallback="")
    if slug:
        return slug
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"emp_{digest}"


def export_day_string(*, at: datetime | None = None) -> str:
    """UTC date folder name ``YYYY-MM-DD``."""
    moment = at or datetime.now(timezone.utc)
    return moment.strftime("%Y-%m-%d")


def _manifest_client_name(manifest: dict[str, Any]) -> str | None:
    raw = manifest.get("client_name")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _ensure_manifest_client_name(manifest: dict[str, Any]) -> str | None:
    """Set ``manifest['client_name']`` from HR DB when missing."""
    name = _manifest_client_name(manifest)
    if name:
        return name
    client_id = str(manifest.get("client_id") or "").strip()
    if not client_id:
        return None
    from psychological_testing.integration.report_storage import _resolve_client_display_name

    resolved = _resolve_client_display_name(client_id).strip()
    if resolved and resolved != client_id:
        manifest["client_name"] = resolved
        _log.info("psych_testing: resolved client_name %r for %s", resolved, client_id[:8])
        return resolved
    return None


def export_client_folder_label(
    client_id: str,
    *,
    client_name: str | None = None,
) -> str:
    """Human-readable client folder (translit), shared with Google Drive layout."""
    from psychological_testing.integration.report_storage import client_folder_slug

    return client_folder_slug(client_id=client_id, client_name=client_name)


def export_client_day_dir(
    client_id: str,
    day: str | None = None,
    *,
    client_name: str | None = None,
) -> Path:
    """``{exports_root}/{client_name_slug}/{YYYY-MM-DD}/`` (mkdir on write)."""
    folder = exports_root() / export_client_folder_label(
        client_id, client_name=client_name
    ) / (day or export_day_string())
    folder.mkdir(parents=True, exist_ok=True)
    _log.info("psych_testing: export dir %s", folder)
    return folder


def _client_export_roots(client_id: str, *, client_name: str | None = None) -> list[Path]:
    """Current translit folder + legacy ``client_id`` folder for cache lookup."""
    label = export_client_folder_label(client_id, client_name=client_name)
    roots: list[Path] = []
    seen: set[str] = set()
    for name in (label, str(client_id or "unknown")):
        if not name or name in seen:
            continue
        seen.add(name)
        roots.append(exports_root() / name)
    return roots


def _pdf_cache_basename(
    manifest: dict[str, Any],
    *,
    employee_display_name: str | None = None,
) -> tuple[str, str]:
    client_id = str(manifest.get("client_id") or "unknown")
    manifest_id = str(manifest.get("manifest_id") or uuid4())
    mode = pdf_cache_mode()
    cache_key = manifest_cache_key(manifest) if mode == "hash" else manifest_id[:12]
    slug = _slug_name(employee_display_name or str(manifest.get("employee_id") or "emp"))
    filename = f"{slug}_{cache_key}.pdf"
    return client_id, filename


def find_cached_pdf_path(
    manifest: dict[str, Any],
    *,
    employee_display_name: str | None = None,
) -> Path | None:
    """Locate cached PDF under ``{client_name}/{day}/``, legacy ``{client_id}/``, or flat."""
    client_id, filename = _pdf_cache_basename(
        manifest, employee_display_name=employee_display_name
    )
    client_name = _ensure_manifest_client_name(manifest)
    today = export_day_string()
    candidates: list[Path] = []
    for client_root in _client_export_roots(client_id, client_name=client_name):
        if not client_root.is_dir():
            continue
        candidates.extend(
            [
                client_root / today / filename,
                client_root / filename,
            ]
        )
        for day_dir in sorted(
            (
                p
                for p in client_root.iterdir()
                if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)
            ),
            reverse=True,
        ):
            if day_dir.name != today:
                candidates.append(day_dir / filename)

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return path
    return None


def local_pdf_ref(path: Path) -> str:
    root = exports_root()
    default_root = package_root() / "data" / "report_exports"
    try:
        rel = path.relative_to(root)
        prefix = "data/report_exports" if root == default_root else "report_exports"
        return f"{prefix}/{rel.as_posix()}"
    except ValueError:
        pass
    try:
        return path.relative_to(package_root()).as_posix()
    except ValueError:
        return path.name


def pdf_cache_mode() -> str:
    from psychological_testing.env import load_plugin_env

    load_plugin_env(override=False)
    return (os.getenv("PSYCH_TESTING_PDF_CACHE", "off") or "off").strip().lower()


def manifest_cache_key(manifest: dict[str, Any]) -> str:
    from psychological_testing.shared_engine.pdf_render_version import PDF_RENDERER_VERSION

    payload = {
        "schema_version": manifest.get("schema_version"),
        "template_id": manifest.get("template_id"),
        "session_refs": manifest.get("session_refs"),
        "sections": manifest.get("sections"),
        "ai_cache": manifest.get("ai_cache"),
        "pdf_renderer_version": PDF_RENDERER_VERSION,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def save_manifest(
    manifest: dict[str, Any],
    *,
    employee_display_name: str | None = None,
) -> Path:
    """Write manifest JSON under ``{exports_root}/{client_name_slug}/{date}/``."""
    client_id = str(manifest.get("client_id") or "unknown")
    manifest_id = str(manifest.get("manifest_id") or uuid4())
    manifest["manifest_id"] = manifest_id
    client_name = _ensure_manifest_client_name(manifest)
    day = export_day_string()
    out_dir = export_client_day_dir(client_id, day, client_name=client_name)
    slug = _slug_name(employee_display_name or str(manifest.get("employee_id") or "emp"))
    path = out_dir / f"{slug}_{manifest_id[:8]}_manifest.json"
    wrapper = {
        "schema_version": "1.0.0",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "manifest": manifest,
    }
    path.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_export_bundle(
    manifest: dict[str, Any],
    pdf_bytes: bytes,
    *,
    employee_display_name: str | None = None,
) -> tuple[Path, Path, str]:
    """
    Save manifest JSON and paired PDF in the same dated folder.

    Files share stem ``{slug}_{manifest_id[:8]}`` so each export is visible locally
    (unlike hash-only PDF cache which overwrites one filename).
    """
    client_id = str(manifest.get("client_id") or "unknown")
    manifest_id = str(manifest.get("manifest_id") or uuid4())
    manifest["manifest_id"] = manifest_id
    client_name = _ensure_manifest_client_name(manifest)
    day = export_day_string()
    out_dir = export_client_day_dir(client_id, day, client_name=client_name)
    slug = _slug_name(employee_display_name or str(manifest.get("employee_id") or "emp"))
    stem = f"{slug}_{manifest_id[:8]}"
    pdf_path = out_dir / f"{stem}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    pdf_ref = local_pdf_ref(pdf_path)
    manifest_path = out_dir / f"{stem}_manifest.json"
    wrapper = {
        "schema_version": "1.0.0",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "pdf_ref": pdf_ref,
        "pdf_filename": pdf_path.name,
        "manifest": manifest,
    }
    manifest_path.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding="utf-8")
    _log.info(
        "psych_testing: export bundle %s + %s (%s bytes)",
        manifest_path.name,
        pdf_path.name,
        len(pdf_bytes),
    )
    return manifest_path, pdf_path, pdf_ref


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
    client_id, filename = _pdf_cache_basename(
        manifest, employee_display_name=employee_display_name
    )
    _ensure_manifest_client_name(manifest)
    client_name = _manifest_client_name(manifest)
    day = export_day_string()
    path = export_client_day_dir(client_id, day, client_name=client_name) / filename
    path.write_bytes(pdf_bytes)
    return local_pdf_ref(path)


def resolve_pdf_ref(pdf_ref: str) -> Path | None:
    """Resolve local ``pdf_ref`` to absolute path if file exists (not Drive)."""
    from psychological_testing.integration.report_storage import is_gdrive_ref

    if is_gdrive_ref(pdf_ref):
        return None
    ref = pdf_ref.strip().lstrip("/")
    root = exports_root()
    candidates: list[Path] = [package_root() / ref, root / ref]
    for prefix in ("data/report_exports/", "report_exports/"):
        if ref.startswith(prefix):
            candidates.append(root / ref[len(prefix) :])
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return path
    return None
