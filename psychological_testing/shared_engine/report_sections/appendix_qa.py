"""Appendix: questions and answers from ``responses[]`` + item banks."""

from __future__ import annotations

from typing import Any

from reportlab.platypus import PageBreak, Spacer

from psychological_testing.shared_engine.item_lookup import (
    TEST_BANK_PATHS,
    format_answer_display,
    load_item_index,
)
from psychological_testing.shared_engine.pdf_composer import PdfComposer
from psychological_testing.shared_engine.report_contract import SectionSpec

_APPENDIX_TEST_ORDER = ("paei", "soft_skills", "hexaco", "disc", "mbti")

# Ширина столбца «Ответ» (мм): короткие баллы/буквы vs развёрнутый PAEI.
_APPENDIX_ANSWER_COL_MM: dict[str, float] = {
    "soft_skills": 14,
    "hexaco": 14,
    "disc": 14,
    "mbti": 14,
    "paei": 34,
}


def _responses_list(session: dict[str, Any]) -> list[dict[str, Any]]:
    raw = session.get("responses") or []
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def render_appendix_qa(
    composer: PdfComposer,
    *,
    section: SectionSpec,
    sessions_by_test: dict[str, dict[str, Any]],
) -> list[Any]:
    """Build appendix story; one block per test present in ``sessions_by_test``."""
    elements: list[Any] = [PageBreak(), composer.section_title(section.label_ru), Spacer(1, 6)]
    elements.append(
        composer.paragraph(
            "Детализация вопросов и ответов для контроля выводов. "
            "Тексты вопросов — из банка v1; баллы — из session JSON."
        )
    )
    elements.append(Spacer(1, 8))

    any_content = False
    for test_id in _APPENDIX_TEST_ORDER:
        session = sessions_by_test.get(test_id)
        if not session:
            continue
        responses = _responses_list(session)
        if not responses:
            continue
        any_content = True
        index = load_item_index(test_id)
        label = test_id.replace("_", " ").upper()
        elements.append(composer.subheading(f"{label}"))
        elements.append(
            composer.paragraph(
                f"Вопросов в сессии: {len(responses)} "
                f"(банк: {TEST_BANK_PATHS.get(test_id, '—')})",
                "PTMeta",
            )
        )
        elements.append(Spacer(1, 4))

        rows: list[tuple[str, str, str]] = []
        for idx, resp in enumerate(responses, start=1):
            item_id = str(resp.get("item_id") or "")
            item = index.get(item_id)
            question = item.text if item else f"[item_id={item_id}]"
            answer = format_answer_display(test_id, resp, item)
            rows.append((str(idx), question, answer))

        elements.extend(
            composer.qa_table(
                rows,
                answer_col_mm=_APPENDIX_ANSWER_COL_MM.get(test_id, 14),
            )
        )
        elements.append(Spacer(1, 10))

    if not any_content:
        elements.append(
            composer.paragraph("Нет завершённых сессий с ответами для приложения.")
        )
    return elements
