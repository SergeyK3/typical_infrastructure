"""On-demand PDF export from manifest + session JSON documents."""

from __future__ import annotations

import logging
from typing import Any

from reportlab.platypus import Spacer

from psychological_testing.integration.session_repository import get_session_document
from psychological_testing.services.interpretation_llm import (
    ensure_export_ai_enrichment,
    get_manifest_ai_text,
)
from psychological_testing.shared_engine.pdf_composer import PdfComposer
from psychological_testing.shared_engine.report_contract import (
    SectionRegistry,
    SectionSpec,
    load_section_registry,
    validate_manifest,
)
from psychological_testing.shared_engine.report_sections import (
    render_appendix_qa,
    render_mbti_section,
    render_test_section,
)
from psychological_testing.shared_engine.report_sections.constants import (
    COVER_TEST_ORDER,
    TEST_COVER_DESCRIPTIONS,
)
from psychological_testing.shared_engine.report_sections.scores_block import score_bullets_for_test

_log = logging.getLogger(__name__)

DISCLAIMER = (
    "Результат отражает ответы на структурированные вопросы "
    "и не является единственным критерием HR-оценки."
)

_TEST_SECTION_IDS = frozenset({"paei", "disc", "hexaco", "soft_skills", "mbti"})


def _session_for_section(
    section: SectionSpec,
    sessions_by_test: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not section.test_id:
        return None
    return sessions_by_test.get(section.test_id)


def _report_text(session: dict[str, Any]) -> str:
    report = session.get("report") or {}
    if isinstance(report, dict):
        return str(report.get("text_telegram") or "").strip()
    return ""


def _test_result_preview(test_id: str, session: dict[str, Any]) -> str:
    """One-line summary for cross-test sections (no legacy ``===`` report headers)."""
    label, desc = TEST_COVER_DESCRIPTIONS.get(test_id, (test_id.upper(), "завершён"))
    if test_id == "mbti":
        scores = session.get("scores") or {}
        code = scores.get("typology_code") if isinstance(scores, dict) else None
        if not code:
            interp = session.get("interpretation") or {}
            if isinstance(interp, dict):
                code = interp.get("typology_code")
        if code:
            return f"{label}: тип {code}"
    bullets = score_bullets_for_test(test_id, session)
    if bullets:
        return f"{label}: {bullets[0]}"
    return f"{label}: {desc}"


def load_sessions_for_manifest(
    manifest: dict[str, Any],
    *,
    fallback_latest: bool = True,
) -> dict[str, dict[str, Any]]:
    """Resolve session documents referenced by manifest."""
    from psychological_testing.integration.session_repository import (
        latest_sessions_by_test_for_employee,
    )

    employee_id = str(manifest.get("employee_id") or "")
    client_id = str(manifest.get("client_id") or "") or None
    sessions: dict[str, dict[str, Any]] = {}

    refs = manifest.get("session_refs") or []
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            test_id = str(ref.get("test_id") or "").strip()
            session_id = str(ref.get("session_id") or "").strip()
            if not test_id or not session_id:
                continue
            doc = get_session_document(session_id)
            if doc:
                sessions[test_id] = doc

    if fallback_latest and employee_id:
        latest = latest_sessions_by_test_for_employee(employee_id, client_id=client_id)
        for test_id, doc in latest.items():
            sessions.setdefault(test_id, doc)

    return sessions


def _cover_story(
    composer: PdfComposer,
    *,
    manifest: dict[str, Any],
    registry: SectionRegistry,
    sessions_by_test: dict[str, dict[str, Any]],
) -> list[Any]:
    template_id = str(manifest.get("template_id") or "")
    template = registry.templates.get(template_id)
    title = template.title_ru if template else "Отчёт психологического тестирования"

    employee_name = ""
    completed = ""
    for doc in sessions_by_test.values():
        if not employee_name:
            employee_name = str(doc.get("employee_display_name") or doc.get("employee_id") or "")
        if not completed:
            completed = str(doc.get("completed_at") or "")[:16].replace("T", " ")

    elements: list[Any] = [
        composer.main_title(title),
        Spacer(1, 8),
    ]
    if employee_name:
        elements.append(composer.paragraph(employee_name, "PTMeta"))
    if completed:
        elements.append(composer.paragraph(f"Дата формирования отчёта: {completed}", "PTMeta"))

    if sessions_by_test:
        elements.append(Spacer(1, 6))
        elements.append(composer.subheading("Включённые тесты"))
        summaries: list[str] = []
        seen: set[str] = set()
        for test_id in COVER_TEST_ORDER:
            if test_id not in sessions_by_test:
                continue
            label, desc = TEST_COVER_DESCRIPTIONS.get(
                test_id,
                (test_id.upper(), "завершён"),
            )
            summaries.append(f"{label}: {desc}")
            seen.add(test_id)
        for test_id in sorted(sessions_by_test.keys()):
            if test_id in seen:
                continue
            label, desc = TEST_COVER_DESCRIPTIONS.get(
                test_id,
                (test_id.upper(), "завершён"),
            )
            summaries.append(f"{label}: {desc}")
        elements.extend(composer.bullets(summaries))

    elements.append(Spacer(1, 12))
    return elements


def _general_summary_story(
    composer: PdfComposer,
    sessions_by_test: dict[str, dict[str, Any]],
    *,
    manifest: dict[str, Any] | None = None,
) -> list[Any]:
    ai_text = get_manifest_ai_text(manifest, "general_summary") if manifest else None
    if ai_text:
        body = ai_text
    else:
        lines = [
            "На основе завершённых тестов сформирован сводный профиль.",
            "",
            "Краткие результаты:",
        ]
        seen: set[str] = set()
        for test_id in COVER_TEST_ORDER:
            if test_id not in sessions_by_test:
                continue
            lines.append(f"• {_test_result_preview(test_id, sessions_by_test[test_id])}")
            seen.add(test_id)
        for test_id in sorted(sessions_by_test.keys()):
            if test_id in seen:
                continue
            lines.append(f"• {_test_result_preview(test_id, sessions_by_test[test_id])}")
        body = "\n".join(lines)
    return [
        composer.section_title("Общее заключение и рекомендации"),
        Spacer(1, 6),
        composer.paragraph(body),
        Spacer(1, 10),
    ]


def _career_recommendations_story(
    composer: PdfComposer,
    *,
    manifest: dict[str, Any] | None = None,
) -> list[Any]:
    ai_text = get_manifest_ai_text(manifest, "career_recommendations") if manifest else None
    body = ai_text or (
        "Рекомендации по развитию будут сформированы после AI enrichment "
        "(включите PSYCH_TESTING_PDF_AI=1 или задайте manifest.ai_cache)."
    )
    return [
        composer.section_title("Рекомендации по профессиональному развитию"),
        Spacer(1, 6),
        composer.paragraph(body),
        Spacer(1, 10),
    ]


def _assign_test_section_numbers(
    sections_cfg: list[dict[str, Any]],
    registry: SectionRegistry,
) -> dict[str, int]:
    """Map ``section_id`` → 1-based index among enabled test sections (registry order)."""
    enabled_ids = [
        str(item.get("section_id") or "")
        for item in sections_cfg
        if isinstance(item, dict) and item.get("enabled", True)
    ]
    test_sections = sorted(
        [
            (registry.sections[sid].order, sid)
            for sid in enabled_ids
            if sid in registry.sections and registry.sections[sid].test_id
        ],
        key=lambda x: x[0],
    )
    return {sid: idx + 1 for idx, (_, sid) in enumerate(test_sections)}


def build_pdf_bytes(
    manifest: dict[str, Any],
    *,
    sessions_by_test: dict[str, dict[str, Any]] | None = None,
    registry: SectionRegistry | None = None,
    regenerate_ai: bool = False,
    skip_ai_enrichment: bool = False,
    llm: Any = None,
) -> bytes:
    """Render PDF bytes for a validated manifest."""
    reg = registry or load_section_registry()
    validation = validate_manifest(manifest, registry=reg)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))

    sessions = sessions_by_test or load_sessions_for_manifest(manifest)
    options = manifest.get("options") or {}
    effective_regenerate = regenerate_ai or bool(options.get("regenerate_ai"))
    persist_sessions = sessions_by_test is None
    if not skip_ai_enrichment:
        manifest, sessions = ensure_export_ai_enrichment(
            manifest,
            sessions,
            registry=reg,
            regenerate_ai=effective_regenerate,
            llm=llm,
            persist_sessions=persist_sessions,
        )
    composer = PdfComposer()
    story: list[Any] = []

    sections_cfg = manifest.get("sections") or []
    if not isinstance(sections_cfg, list):
        raise ValueError("manifest.sections must be a list")

    include_disclaimer = bool(options.get("include_disclaimer", True))
    page_numbers = bool(options.get("page_numbers", True))
    section_numbers = _assign_test_section_numbers(sections_cfg, reg)

    for section_cfg in sections_cfg:
        if not isinstance(section_cfg, dict) or not section_cfg.get("enabled", True):
            continue
        section_id = str(section_cfg.get("section_id") or "")
        spec = reg.sections.get(section_id)
        if spec is None:
            continue

        if section_id == "cover":
            story.extend(_cover_story(composer, manifest=manifest, registry=reg, sessions_by_test=sessions))
            continue

        if section_id == "general_summary":
            story.extend(_general_summary_story(composer, sessions, manifest=manifest))
            continue

        if section_id == "career_recommendations":
            story.extend(_career_recommendations_story(composer, manifest=manifest))
            continue

        if section_id == "appendix_qa":
            story.extend(
                render_appendix_qa(
                    composer,
                    section=spec,
                    sessions_by_test=sessions,
                )
            )
            continue

        session = _session_for_section(spec, sessions)
        if session is None:
            story.append(composer.section_title(spec.label_ru))
            story.append(composer.paragraph("Сессия теста не найдена — секция пропущена."))
            story.append(Spacer(1, 10))
            continue

        num = section_numbers.get(section_id)
        if section_id == "mbti":
            story.extend(
                render_mbti_section(
                    composer,
                    section=spec,
                    section_cfg=section_cfg,
                    session=session,
                    section_number=num,
                )
            )
        elif section_id in _TEST_SECTION_IDS:
            story.extend(
                render_test_section(
                    composer,
                    section=spec,
                    section_cfg=section_cfg,
                    session=session,
                    section_number=num,
                )
            )
        else:
            _log.warning("unknown test section renderer: %s", section_id)

    if include_disclaimer:
        story.extend([Spacer(1, 12), composer.paragraph(DISCLAIMER, "PTMeta")])

    return composer.build_pdf_bytes(story, page_numbers=page_numbers)


def export_pdf_to_path(
    manifest: dict[str, Any],
    out_path: str,
    *,
    sessions_by_test: dict[str, dict[str, Any]] | None = None,
    regenerate_ai: bool = False,
    manifest_path: str | None = None,
    llm: Any = None,
) -> bytes:
    """Write PDF to ``out_path`` and return bytes."""
    reg = load_section_registry()
    sessions = sessions_by_test or load_sessions_for_manifest(manifest)
    options = manifest.get("options") or {}
    effective_regenerate = regenerate_ai or bool(options.get("regenerate_ai"))
    manifest, sessions = ensure_export_ai_enrichment(
        manifest,
        sessions,
        registry=reg,
        regenerate_ai=effective_regenerate,
        llm=llm,
    )
    pdf_bytes = build_pdf_bytes(
        manifest,
        sessions_by_test=sessions,
        registry=reg,
        skip_ai_enrichment=True,
    )
    if manifest_path:
        from psychological_testing.services.interpretation_llm import persist_manifest_file

        persist_manifest_file(manifest_path, manifest)
    from pathlib import Path

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    return pdf_bytes

