"""PDF export contract: section registry, manifest validation, ai_enrichment helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from psychological_testing.domain.test_registry import resolve_package_path
from psychological_testing.shared_engine.item_bank_loader import load_yaml_file

SESSION_SCHEMA_VERSION = "1.0.0"
SESSION_SCHEMA_VERSION_WITH_AI = "1.1.0"
AI_ENRICHMENT_SCHEMA_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "1.0.0"
REGISTRY_SCHEMA_VERSION = "1.0.0"

DEFAULT_REGISTRY_PATH = "data/report_sections/v1/registry.yaml"
DEFAULT_TEMPLATE_ID = "legacy_team_assessment_v1"


@dataclass(frozen=True)
class SectionSpec:
    section_id: str
    label_ru: str
    test_id: str | None
    order: int
    charts_available: tuple[str, ...] = ()
    ai_slots: tuple[str, ...] = ()
    cross_test: bool = False
    appendix: bool = False
    static_source: str | None = None


@dataclass(frozen=True)
class TemplateSectionDefault:
    section_id: str
    enabled: bool = True
    charts: tuple[str, ...] = ()
    requires_ai: bool = False


@dataclass(frozen=True)
class ReportTemplate:
    template_id: str
    title_ru: str
    registry_version: str
    program_id: str | None
    default_sections: tuple[TemplateSectionDefault, ...]


@dataclass(frozen=True)
class SectionRegistry:
    schema_version: str
    sections: dict[str, SectionSpec]
    templates: dict[str, ReportTemplate]


@dataclass(frozen=True)
class ManifestValidationResult:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def default_registry_path() -> Path:
    return resolve_package_path(DEFAULT_REGISTRY_PATH)


def load_section_registry(path: str | Path | None = None) -> SectionRegistry:
    """Load section registry YAML."""
    file_path = resolve_package_path(str(path or DEFAULT_REGISTRY_PATH))
    doc = load_yaml_file(file_path)
    schema_version = str(doc.get("schema_version") or REGISTRY_SCHEMA_VERSION)

    sections_raw = doc.get("sections") or {}
    if not isinstance(sections_raw, dict):
        raise ValueError(f"registry must contain 'sections' mapping: {file_path}")

    sections: dict[str, SectionSpec] = {}
    for section_id, raw in sections_raw.items():
        if not isinstance(raw, dict):
            raise ValueError(f"invalid section entry: {section_id}")
        charts = raw.get("charts_available") or []
        ai_slots = raw.get("ai_slots") or []
        test_id = raw.get("test_id")
        sections[str(section_id)] = SectionSpec(
            section_id=str(section_id),
            label_ru=str(raw.get("label_ru") or section_id),
            test_id=str(test_id) if test_id not in (None, "null") else None,
            order=int(raw.get("order") or 0),
            charts_available=tuple(str(c) for c in charts),
            ai_slots=tuple(str(s) for s in ai_slots),
            cross_test=bool(raw.get("cross_test")),
            appendix=bool(raw.get("appendix")),
            static_source=(
                str(raw["static_source"]) if raw.get("static_source") else None
            ),
        )

    templates_raw = doc.get("templates") or {}
    if not isinstance(templates_raw, dict):
        raise ValueError(f"registry must contain 'templates' mapping: {file_path}")

    templates: dict[str, ReportTemplate] = {}
    for template_id, raw in templates_raw.items():
        if not isinstance(raw, dict):
            raise ValueError(f"invalid template entry: {template_id}")
        defaults_raw = raw.get("default_sections") or []
        defaults: list[TemplateSectionDefault] = []
        for item in defaults_raw:
            if not isinstance(item, dict):
                continue
            sid = str(item.get("section_id") or "")
            if not sid:
                continue
            charts = item.get("charts") or []
            defaults.append(
                TemplateSectionDefault(
                    section_id=sid,
                    enabled=bool(item.get("enabled", True)),
                    charts=tuple(str(c) for c in charts),
                    requires_ai=bool(item.get("requires_ai")),
                )
            )
        templates[str(template_id)] = ReportTemplate(
            template_id=str(template_id),
            title_ru=str(raw.get("title_ru") or template_id),
            registry_version=str(raw.get("registry_version") or schema_version),
            program_id=str(raw["program_id"]) if raw.get("program_id") else None,
            default_sections=tuple(defaults),
        )

    return SectionRegistry(
        schema_version=schema_version,
        sections=sections,
        templates=templates,
    )


def get_template(registry: SectionRegistry, template_id: str) -> ReportTemplate:
    try:
        return registry.templates[template_id]
    except KeyError as exc:
        raise KeyError(f"Unknown template_id: {template_id}") from exc


def build_default_manifest(
    *,
    client_id: str,
    employee_id: str,
    template_id: str = DEFAULT_TEMPLATE_ID,
    created_by: str | None = None,
    session_refs: list[dict[str, str]] | None = None,
    locale: str = "ru",
    registry: SectionRegistry | None = None,
) -> dict[str, Any]:
    """Build ``pt_report_manifest`` v1 from template defaults."""
    reg = registry or load_section_registry()
    template = get_template(reg, template_id)
    sections: list[dict[str, Any]] = []
    for default in template.default_sections:
        spec = reg.sections.get(default.section_id)
        if spec is None:
            raise ValueError(f"template references unknown section: {default.section_id}")
        entry: dict[str, Any] = {
            "section_id": default.section_id,
            "enabled": default.enabled,
        }
        charts = default.charts or spec.charts_available
        if charts:
            entry["charts"] = list(charts)
        if default.requires_ai:
            entry["requires_ai"] = True
        sections.append(entry)

    now = datetime.now(timezone.utc).isoformat()
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": str(uuid4()),
        "client_id": client_id,
        "employee_id": employee_id,
        "created_by": created_by,
        "created_at": now,
        "template_id": template_id,
        "locale": locale,
        "sections": sections,
        "options": {
            "include_disclaimer": True,
            "page_numbers": True,
            "strict": False,
        },
    }
    if template.program_id:
        manifest["program_id"] = template.program_id
    if session_refs:
        manifest["session_refs"] = list(session_refs)
    manifest["ai_cache"] = {}
    return manifest


def align_manifest_sections_to_sessions(
    manifest: dict[str, Any],
    *,
    registry: SectionRegistry | None = None,
) -> list[str]:
    """
    Отключить секции тестов без session_refs (чтобы экспорт не требовал «лишних» сессий).

    Возвращает пояснения для UI (не ошибки).
    """
    reg = registry or load_section_registry()
    refs_by_test: dict[str, str] = {}
    for ref in manifest.get("session_refs") or []:
        if not isinstance(ref, dict):
            continue
        tid = str(ref.get("test_id") or "").strip()
        sid = str(ref.get("session_id") or "").strip()
        if tid and sid:
            refs_by_test[tid] = sid

    notes: list[str] = []
    for item in manifest.get("sections") or []:
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        section_id = str(item.get("section_id") or "")
        spec = reg.sections.get(section_id)
        if spec is None or not spec.test_id:
            continue
        if spec.test_id in refs_by_test:
            continue
        item["enabled"] = False
        notes.append(f"Секция «{spec.label_ru}» снята — нет завершённого теста {spec.test_id}.")

    if len(refs_by_test) == 1:
        for item in manifest.get("sections") or []:
            if not isinstance(item, dict) or not item.get("enabled", True):
                continue
            section_id = str(item.get("section_id") or "")
            spec = reg.sections.get(section_id)
            if spec is None or not spec.cross_test:
                continue
            item["enabled"] = False
            notes.append(
                f"Секция «{spec.label_ru}» снята — доступен один тест, сводка по батарее не формируется."
            )
    return notes


def validate_manifest(
    manifest: dict[str, Any],
    *,
    registry: SectionRegistry | None = None,
    strict: bool | None = None,
) -> ManifestValidationResult:
    """Validate manifest shape and section/chart ids against registry."""
    reg = registry or load_section_registry()
    errors: list[str] = []
    warnings: list[str] = []

    if str(manifest.get("schema_version") or "") != MANIFEST_SCHEMA_VERSION:
        errors.append(
            f"unsupported manifest schema_version: {manifest.get('schema_version')!r}"
        )

    template_id = str(manifest.get("template_id") or "")
    if not template_id:
        errors.append("template_id is required")
    elif template_id not in reg.templates:
        errors.append(f"unknown template_id: {template_id}")

    sections_raw = manifest.get("sections")
    if not isinstance(sections_raw, list) or not sections_raw:
        errors.append("sections must be a non-empty list")
        sections_iter: list[Any] = []
    else:
        sections_iter = sections_raw

    options = manifest.get("options") or {}
    effective_strict = (
        bool(options.get("strict")) if strict is None else bool(strict)
    )

    session_refs = manifest.get("session_refs") or []
    refs_by_test: dict[str, str] = {}
    if isinstance(session_refs, list):
        for ref in session_refs:
            if not isinstance(ref, dict):
                continue
            tid = str(ref.get("test_id") or "").strip()
            sid = str(ref.get("session_id") or "").strip()
            if tid and sid:
                refs_by_test[tid] = sid

    for item in sections_iter:
        if not isinstance(item, dict):
            errors.append("each sections[] entry must be an object")
            continue
        section_id = str(item.get("section_id") or "")
        if not section_id:
            errors.append("section_id is required in sections[]")
            continue
        spec = reg.sections.get(section_id)
        if spec is None:
            errors.append(f"unknown section_id: {section_id}")
            continue
        if not item.get("enabled", True):
            continue

        charts = item.get("charts") or []
        if charts and not isinstance(charts, list):
            errors.append(f"sections[{section_id}].charts must be a list")
        elif isinstance(charts, list):
            unknown = [c for c in charts if str(c) not in spec.charts_available]
            if unknown and spec.charts_available:
                errors.append(
                    f"sections[{section_id}]: charts not allowed: {unknown}"
                )

        if spec.test_id and spec.test_id not in refs_by_test:
            msg = (
                f"enabled section {section_id} requires session for test_id={spec.test_id}"
            )
            if effective_strict:
                errors.append(msg)
            else:
                warnings.append(msg)

    return ManifestValidationResult(
        ok=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_ai_enrichment(block: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Validate ``ai_enrichment`` block shape."""
    errors: list[str] = []
    if str(block.get("schema_version") or "") != AI_ENRICHMENT_SCHEMA_VERSION:
        errors.append(
            f"unsupported ai_enrichment.schema_version: {block.get('schema_version')!r}"
        )
    sections = block.get("sections")
    if sections is not None and not isinstance(sections, dict):
        errors.append("ai_enrichment.sections must be an object")
    usage = block.get("usage")
    if usage is not None and not isinstance(usage, dict):
        errors.append("ai_enrichment.usage must be an object")
    return (not errors, tuple(errors))


def normalize_ai_enrichment(block: dict[str, Any]) -> dict[str, Any]:
    """Return normalized ai_enrichment dict (does not validate content depth)."""
    sections = block.get("sections") or {}
    usage = block.get("usage") or {}
    return {
        "schema_version": str(block.get("schema_version") or AI_ENRICHMENT_SCHEMA_VERSION),
        "generated_at": block.get("generated_at"),
        "provider": block.get("provider"),
        "model": block.get("model"),
        "prompt_version": block.get("prompt_version"),
        "sections": dict(sections) if isinstance(sections, dict) else {},
        "usage": dict(usage) if isinstance(usage, dict) else {},
    }


def merge_ai_enrichment(
    document: dict[str, Any],
    enrichment: dict[str, Any],
    *,
    merge_sections: bool = True,
) -> dict[str, Any]:
    """
    Merge ``ai_enrichment`` into a session document copy.

    When ``merge_sections`` is True, new section texts are merged into existing keys.
    """
    ok, errors = validate_ai_enrichment(enrichment)
    if not ok:
        raise ValueError("; ".join(errors))

    out = dict(document)
    normalized = normalize_ai_enrichment(enrichment)
    existing = out.get("ai_enrichment")
    if merge_sections and isinstance(existing, dict):
        prev_sections = dict(existing.get("sections") or {})
        new_sections = dict(normalized.get("sections") or {})
        prev_sections.update(new_sections)
        normalized = {**normalized, "sections": prev_sections}

    out["ai_enrichment"] = normalized
    out["schema_version"] = SESSION_SCHEMA_VERSION_WITH_AI
    return out


def get_ai_section_text(document: dict[str, Any], slot: str) -> str | None:
    """Read cached AI text for a slot from session document."""
    block = document.get("ai_enrichment")
    if not isinstance(block, dict):
        return None
    sections = block.get("sections")
    if not isinstance(sections, dict):
        return None
    value = sections.get(slot)
    return str(value) if value else None
