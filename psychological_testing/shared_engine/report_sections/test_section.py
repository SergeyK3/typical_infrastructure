"""Renderer for PAEI / DISC / HEXACO / Soft Skills PDF sections."""

from __future__ import annotations

import logging
from typing import Any

from reportlab.platypus import Spacer

from psychological_testing.shared_engine.charts import render_chart_bytes
from psychological_testing.shared_engine.pdf_composer import PdfComposer
from psychological_testing.shared_engine.report_contract import SectionSpec, get_ai_section_text
from psychological_testing.shared_engine.report_sections.constants import (
    DISC_LEGEND,
    HEXACO_LEGEND,
    PAEI_LEGEND,
    SOFT_SKILLS_BLURB,
    TEST_SECTION_INTROS,
)
from psychological_testing.shared_engine.report_sections.scores_block import (
    mini_bank_footnote,
    score_bullets_for_test,
)

_log = logging.getLogger(__name__)

_LEGEND_BY_TEST: dict[str, list[str]] = {
    "paei": PAEI_LEGEND,
    "hexaco": HEXACO_LEGEND,
    "disc": DISC_LEGEND,
}


def _report_text(session: dict[str, Any]) -> str:
    report = session.get("report") or {}
    if isinstance(report, dict):
        return str(report.get("text_telegram") or "").strip()
    return ""


def _ai_text(session: dict[str, Any], slot: str) -> str | None:
    return get_ai_section_text(session, slot)


def render_test_section(
    composer: PdfComposer,
    *,
    section: SectionSpec,
    section_cfg: dict[str, Any],
    session: dict[str, Any],
    section_number: int | None = None,
) -> list[Any]:
    """Build story elements for a standard test section (legacy layout)."""
    test_id = str(section.test_id or "")
    title = section.label_ru
    if section_number is not None:
        title = f"{section_number}. {title.upper()}"

    elements: list[Any] = [composer.section_title(title), Spacer(1, 4)]

    intro = TEST_SECTION_INTROS.get(test_id)
    if intro:
        elements.append(composer.paragraph(intro))
        elements.append(Spacer(1, 4))

    if test_id == "soft_skills":
        elements.append(composer.paragraph(SOFT_SKILLS_BLURB))
        elements.append(Spacer(1, 4))

    legend = _LEGEND_BY_TEST.get(test_id)
    if legend:
        elements.append(composer.paragraph("Расшифровка шкал:"))
        elements.extend(composer.bullets(legend))
        elements.append(Spacer(1, 4))

    bullets = score_bullets_for_test(test_id, session)
    if bullets:
        elements.append(composer.paragraph("Результаты:"))
        elements.extend(composer.bullets(bullets))
        elements.append(Spacer(1, 6))

    scores = session.get("scores") or {}
    axis_details = scores.get("axis_details") if isinstance(scores, dict) else None
    charts = section_cfg.get("charts") or list(section.charts_available)[:1]
    for chart_type in charts:
        try:
            png = render_chart_bytes(
                str(chart_type),
                test_id=test_id,
                scores=scores if isinstance(scores, dict) else None,
                axis_details=axis_details if isinstance(axis_details, dict) else None,
                title=section.label_ru,
            )
            elements.append(composer.chart_image(png))
            elements.append(Spacer(1, 8))
        except Exception as exc:
            _log.warning("chart render failed %s/%s: %s", test_id, chart_type, exc)
            elements.append(composer.paragraph(f"[Диаграмма {chart_type}: недоступна]"))

    ai_parts: list[str] = []
    for slot in section.ai_slots:
        text = _ai_text(session, slot)
        if text:
            ai_parts.append(text)

    if ai_parts:
        elements.append(composer.subheading("Интерпретация"))
        for part in ai_parts:
            elements.append(composer.paragraph(part))
    else:
        static = _report_text(session)
        if static and not static.startswith("==="):
            elements.append(composer.subheading("Краткий результат"))
            elements.append(composer.paragraph(static))
        elif static:
            lines = [ln for ln in static.splitlines() if ln.strip() and not ln.strip().startswith("===")]
            if lines:
                elements.append(composer.subheading("Краткий результат"))
                elements.append(composer.paragraph("\n".join(lines[:12])))

    responses = session.get("responses") or []
    footnote = mini_bank_footnote(test_id, len(responses) if isinstance(responses, list) else 0)
    if footnote:
        elements.append(Spacer(1, 4))
        elements.append(composer.paragraph(footnote, "PTMeta"))

    elements.append(Spacer(1, 10))
    return elements
