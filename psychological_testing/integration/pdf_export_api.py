"""
HR export API helpers: manifest preview, PDF generation, cache (Phase E).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from psychological_testing.integration.manifest_store import (
    _slug_name,
    local_pdf_ref,
    pdf_cache_mode,
    resolve_pdf_ref,
    save_export_bundle,
    save_manifest,
    save_pdf_cache,
)
from psychological_testing.integration.report_storage import (
    gdrive_enabled,
    gdrive_upload_manifest_enabled,
    is_gdrive_ref,
    sync_pdf_ref_to_sessions,
    upload_manifest_file,
    upload_pdf_to_drive,
)
from psychological_testing.integration.session_repository import (
    build_session_refs_for_employee,
    latest_sessions_by_test_for_employee,
)
from psychological_testing.shared_engine.pdf_export_service import build_pdf_bytes
from psychological_testing.shared_engine.report_contract import (
    DEFAULT_TEMPLATE_ID,
    SectionRegistry,
    align_manifest_sections_to_sessions,
    build_default_manifest,
    load_section_registry,
    validate_manifest,
)


def sections_catalog(
    registry: SectionRegistry | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Sections and templates for workspace UI."""
    reg = registry or load_section_registry()
    templates = []
    for template_id, tpl in reg.templates.items():
        templates.append(
            {
                "template_id": template_id,
                "title_ru": tpl.title_ru,
                "program_id": tpl.program_id,
                "default_sections": [
                    {
                        "section_id": d.section_id,
                        "enabled": d.enabled,
                        "charts": list(d.charts),
                        "requires_ai": d.requires_ai,
                    }
                    for d in tpl.default_sections
                ],
            }
        )
    sections = []
    for section_id, spec in reg.sections.items():
        sections.append(
            {
                "section_id": section_id,
                "label_ru": spec.label_ru,
                "test_id": spec.test_id,
                "order": spec.order,
                "charts_available": list(spec.charts_available),
                "ai_slots": list(spec.ai_slots),
                "cross_test": spec.cross_test,
                "appendix": spec.appendix,
            }
        )
    return templates, sorted(sections, key=lambda x: x["order"])


def available_sessions_payload(
    employee_id: str,
    *,
    client_id: str | None = None,
) -> list[dict[str, Any]]:
    latest = latest_sessions_by_test_for_employee(employee_id, client_id=client_id)
    items: list[dict[str, Any]] = []
    for test_id, doc in sorted(latest.items()):
        scores = doc.get("scores") or {}
        typology = scores.get("typology_code") if isinstance(scores, dict) else None
        items.append(
            {
                "test_id": test_id,
                "session_id": doc.get("session_id"),
                "completed_at": doc.get("completed_at"),
                "employee_display_name": doc.get("employee_display_name"),
                "typology_code": typology,
                "has_ai_enrichment": bool(doc.get("ai_enrichment")),
            }
        )
    return items


def build_export_manifest(
    *,
    client_id: str,
    employee_id: str,
    template_id: str = DEFAULT_TEMPLATE_ID,
    created_by: str | None = None,
    session_refs: list[dict[str, str]] | None = None,
    sections: list[dict[str, Any]] | None = None,
    program_id: str | None = "standard_hr_v1",
    client_name: str | None = None,
) -> dict[str, Any]:
    """Build manifest with latest sessions unless ``session_refs`` provided."""
    reg = load_section_registry()
    refs = session_refs
    if not refs:
        test_ids = [spec.test_id for spec in reg.sections.values() if spec.test_id]
        refs = build_session_refs_for_employee(
            employee_id, test_ids, client_id=client_id
        )
    manifest = build_default_manifest(
        client_id=client_id,
        employee_id=employee_id,
        template_id=template_id,
        created_by=created_by,
        session_refs=refs,
        registry=reg,
    )
    if program_id:
        manifest["program_id"] = program_id
    if sections is not None:
        manifest["sections"] = sections
    if client_name and str(client_name).strip():
        manifest["client_name"] = str(client_name).strip()
    align_manifest_sections_to_sessions(manifest, registry=reg)
    return manifest


def _test_section_label(registry: SectionRegistry, test_id: str) -> str:
    tid = str(test_id or "").strip()
    for spec in registry.sections.values():
        if spec.test_id == tid:
            return spec.label_ru
    return tid or "тест"


def _export_ui_mode(available_sessions: list[dict[str, Any]]) -> str:
    count = len(available_sessions)
    if count == 0:
        return "empty"
    if count == 1:
        return "single_test"
    return "multi_test"


def export_preview(
    *,
    client_id: str,
    employee_id: str,
    template_id: str = DEFAULT_TEMPLATE_ID,
    sections: list[dict[str, Any]] | None = None,
    session_refs: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    reg = load_section_registry()
    manifest = build_export_manifest(
        client_id=client_id,
        employee_id=employee_id,
        template_id=template_id,
        sections=sections,
        session_refs=session_refs,
    )
    section_notes = align_manifest_sections_to_sessions(manifest, registry=reg)
    validation = validate_manifest(manifest, registry=reg, strict=False)
    templates, section_list = sections_catalog(reg)
    available_sessions = available_sessions_payload(employee_id, client_id=client_id)
    ui_mode = _export_ui_mode(available_sessions)
    primary_test: dict[str, Any] | None = None
    if ui_mode == "single_test":
        row = available_sessions[0]
        test_id = str(row.get("test_id") or "")
        primary_test = {
            "test_id": test_id,
            "label_ru": _test_section_label(reg, test_id),
            "session_id": row.get("session_id"),
            "typology_code": row.get("typology_code"),
        }
    return {
        "manifest": manifest,
        "validation": {
            "ok": validation.ok,
            "errors": list(validation.errors),
            "warnings": list(validation.warnings),
        },
        "section_notes": section_notes,
        "templates": templates,
        "sections_catalog": section_list,
        "available_sessions": available_sessions,
        "export_ui_mode": ui_mode,
        "primary_test": primary_test,
        "pdf_cache_enabled": pdf_cache_mode() not in ("off", "", "0", "false"),
        "gdrive_enabled": gdrive_enabled(),
    }


def _drive_pdf_filename(
    manifest: dict[str, Any],
    *,
    employee_display_name: str | None = None,
    fallback_name: str | None = None,
) -> str:
    client_id = str(manifest.get("client_id") or "unknown")
    slug = _slug_name(employee_display_name or str(manifest.get("employee_id") or "emp"))
    manifest_id = str(manifest.get("manifest_id") or "")[:8]
    if manifest_id:
        return f"{slug}_{manifest_id}.pdf"
    if fallback_name:
        return fallback_name
    return f"{slug}_{client_id[:8]}.pdf"


def _maybe_upload_pdf_to_drive(
    pdf_bytes: bytes,
    manifest: dict[str, Any],
    pdf_ref: str | None,
    *,
    employee_display_name: str | None = None,
    filename: str | None = None,
) -> str | None:
    """Upload to Drive when enabled (always re-upload fresh ``pdf_bytes``)."""
    if not gdrive_enabled():
        return pdf_ref
    try:
        from psychological_testing.integration.manifest_store import _ensure_manifest_client_name

        _ensure_manifest_client_name(manifest)
        client_id = str(manifest.get("client_id") or "unknown")
        client_name = manifest.get("client_name")
        drive_name = filename or _drive_pdf_filename(
            manifest, employee_display_name=employee_display_name
        )
        drive_ref = upload_pdf_to_drive(
            pdf_bytes,
            filename=drive_name,
            client_id=client_id,
            client_name=str(client_name).strip() if client_name else None,
        )
        sync_pdf_ref_to_sessions(manifest, drive_ref)
        return drive_ref
    except Exception as exc:
        _log_gdrive_upload_warning("pdf", exc)
        return pdf_ref


def export_employee_pdf(
    manifest: dict[str, Any],
    *,
    employee_display_name: str | None = None,
    regenerate_ai: bool = False,
    use_pdf_cache: bool = True,
    force_regenerate: bool = False,
    persist_manifest: bool = True,
) -> dict[str, Any]:
    """
    Generate PDF bytes; optionally read/write cache and persist manifest.

    Returns dict with ``pdf_bytes``, ``manifest``, ``pdf_ref``, ``manifest_path``, ``cache_hit``.
    """
    reg = load_section_registry()
    validation = validate_manifest(manifest, registry=reg, strict=False)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))

    cache_hit = False
    pdf_ref: str | None = None
    pdf_local_ref: str | None = None
    manifest_path: str | None = None
    manifest_drive_ref: str | None = None

    # Always render PDF — hash cache is write-only (reading stale bytes caused old layout in exports).
    pdf_bytes = build_pdf_bytes(manifest, regenerate_ai=regenerate_ai)
    bundle_pdf_path: Path | None = None
    if persist_manifest:
        saved_manifest, bundle_pdf_path, local_ref = save_export_bundle(
            manifest,
            pdf_bytes,
            employee_display_name=employee_display_name,
        )
        manifest_path = str(saved_manifest)
        pdf_local_ref = local_ref
        pdf_ref = local_ref
        if gdrive_enabled() and gdrive_upload_manifest_enabled():
            try:
                client_id = str(manifest.get("client_id") or "unknown")
                manifest_drive_ref = upload_manifest_file(saved_manifest, client_id=client_id)
            except Exception as exc:
                _log_gdrive_upload_warning("manifest", exc)

    if use_pdf_cache and not force_regenerate and pdf_cache_mode() in ("hash", "on", "1", "true"):
        hash_ref = save_pdf_cache(manifest, pdf_bytes, employee_display_name=employee_display_name)
    else:
        hash_ref = None

    drive_name = bundle_pdf_path.name if bundle_pdf_path is not None else None
    pdf_ref = _maybe_upload_pdf_to_drive(
        pdf_bytes,
        manifest,
        pdf_ref or hash_ref,
        employee_display_name=employee_display_name,
        filename=drive_name,
    ) or pdf_local_ref or hash_ref

    return {
        "pdf_bytes": pdf_bytes,
        "manifest": manifest,
        "pdf_ref": pdf_ref,
        "pdf_local_ref": pdf_local_ref,
        "manifest_path": manifest_path,
        "manifest_drive_ref": manifest_drive_ref,
        "cache_hit": cache_hit,
    }


def _log_gdrive_upload_warning(kind: str, exc: Exception) -> None:
    import logging

    logging.getLogger(__name__).warning(
        "psych_testing: Drive %s upload failed (local cache kept): %s: %s",
        kind,
        type(exc).__name__,
        exc,
    )


def load_cached_pdf(pdf_ref: str) -> bytes | None:
    from psychological_testing.integration.report_storage import download_pdf

    remote = download_pdf(pdf_ref)
    if remote is not None:
        return remote
    path = resolve_pdf_ref(pdf_ref)
    if path is None:
        return None
    return path.read_bytes()
