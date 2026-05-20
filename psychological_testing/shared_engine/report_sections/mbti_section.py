"""MBTI PDF section: static YAML profile + charts + AI slot."""

from __future__ import annotations

import logging
from typing import Any

from reportlab.platypus import Spacer

from psychological_testing.shared_engine.charts import render_chart_bytes
from psychological_testing.shared_engine.pdf_composer import PdfComposer
from psychological_testing.shared_engine.report_contract import SectionSpec, get_ai_section_text
from psychological_testing.shared_engine.report_sections.constants import TEST_SECTION_INTROS
from psychological_testing.shared_engine.report_sections.scores_block import mini_bank_footnote

_log = logging.getLogger(__name__)

AXIS_LABELS_RU: dict[str, dict[str, str]] = {
    "E/I": {"E": "Экстраверсия", "I": "Интроверсия"},
    "S/N": {"S": "Сенсорика", "N": "Интуиция"},
    "T/F": {"T": "Мышление", "F": "Чувство"},
    "J/P": {"J": "Суждение", "P": "Восприятие"},
}


def _axis_lines(session: dict[str, Any]) -> list[str]:
    interp = session.get("interpretation") or {}
    axis_details = interp.get("axis_details") if isinstance(interp, dict) else None
    if not isinstance(axis_details, dict):
        scores = session.get("scores") or {}
        axis_details = scores.get("axis_details") if isinstance(scores, dict) else {}
    lines: list[str] = []
    if not isinstance(axis_details, dict):
        return lines
    for axis in ("E/I", "S/N", "T/F", "J/P"):
        detail = axis_details.get(axis)
        if not isinstance(detail, dict):
            continue
        dom = str(detail.get("dominant") or "?")
        level = detail.get("level", "?")
        label = AXIS_LABELS_RU.get(axis, {}).get(dom, dom)
        lines.append(f"{axis}: {label} ({dom}) — уровень {level}/3")
    return lines


def _static_profile_block(session: dict[str, Any]) -> list[str]:
    interp = session.get("interpretation") or {}
    if not isinstance(interp, dict):
        return []
    profile = interp.get("profile")
    if not isinstance(profile, dict):
        code = interp.get("typology_code") or (session.get("scores") or {}).get("typology_code")
        return [f"Тип личности: {code}"] if code else []

    lines = [
        f"Тип личности: {profile.get('code')} — {profile.get('name_ru', '')}",
        str(profile.get("tagline") or ""),
        "",
        "Сильные стороны:",
    ]
    for s in profile.get("strengths") or []:
        lines.append(f"  • {s}")
    lines.extend(["", "Зоны роста:"])
    for g in profile.get("growth_areas") or []:
        lines.append(f"  • {g}")
    return lines


def render_mbti_section(
    composer: PdfComposer,
    *,
    section: SectionSpec,
    section_cfg: dict[str, Any],
    session: dict[str, Any],
    section_number: int | None = None,
) -> list[Any]:
    title = section.label_ru
    if section_number is not None:
        title = f"{section_number}. {title.upper()}"

    elements: list[Any] = [composer.section_title(title), Spacer(1, 4)]
    elements.append(composer.paragraph(TEST_SECTION_INTROS["mbti"]))
    elements.append(Spacer(1, 4))

    profile_lines = _static_profile_block(session)
    if profile_lines:
        elements.append(composer.paragraph("\n".join(profile_lines)))

    axis_lines = _axis_lines(session)
    if axis_lines:
        elements.append(Spacer(1, 4))
        elements.append(composer.paragraph("Детали по осям:"))
        elements.extend(composer.bullets(axis_lines))

    elements.append(Spacer(1, 6))
    scores = session.get("scores") or {}
    axis_details = scores.get("axis_details") if isinstance(scores, dict) else None
    charts = section_cfg.get("charts") or list(section.charts_available)[:2]
    for chart_type in charts:
        try:
            png = render_chart_bytes(
                str(chart_type),
                test_id="mbti",
                scores=scores if isinstance(scores, dict) else None,
                axis_details=axis_details if isinstance(axis_details, dict) else None,
                title=section.label_ru,
            )
            elements.append(composer.chart_image(png))
            elements.append(Spacer(1, 8))
        except Exception as exc:
            _log.warning("mbti chart %s failed: %s", chart_type, exc)

    ai_text = None
    for slot in section.ai_slots:
        ai_text = get_ai_section_text(session, slot)
        if ai_text:
            break
    if ai_text:
        elements.append(composer.subheading("Интерпретация (AI)"))
        elements.append(composer.paragraph(ai_text))
    else:
        report = session.get("report") or {}
        if isinstance(report, dict):
            tg = str(report.get("text_telegram") or "").strip()
            if tg and "Интерпретация" not in tg:
                elements.append(composer.subheading("Сводка"))
                elements.append(composer.paragraph(tg[:2000]))

    responses = session.get("responses") or []
    footnote = mini_bank_footnote("mbti", len(responses) if isinstance(responses, list) else 0)
    if footnote:
        elements.append(composer.paragraph(footnote, "PTMeta"))

    elements.append(Spacer(1, 10))
    return elements
