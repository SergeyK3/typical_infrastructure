"""Closing message after a completed psychological test in Telegram."""

from __future__ import annotations

import os
from typing import Any

from psychological_testing.research.mbti.scripts.akma_dialog_engine import AkmaDialogEngine
from psychological_testing.shared_engine.report_builder import (
    DISC_SCALE_NAMES,
    HEXACO_SCALE_NAMES,
    PAEI_SCALE_NAMES,
)
from psychological_testing.shared_engine.session_state_machine import SessionEngine

_TEST_LABELS: dict[str, str] = {
    "mbti": "MBTI",
    "paei": "PAEI",
    "soft_skills": "Soft Skills",
    "disc": "DISC",
    "hexaco": "HEXACO",
}


def _hr_contact_block() -> str:
    url = (os.getenv("PSYCH_TESTING_HR_CONTACT_URL") or "").strip()
    text = (os.getenv("PSYCH_TESTING_HR_CONTACT_TEXT") or "").strip()
    if url:
        return f"За полным отчётом и обратной связью обратитесь в отдел кадров:\n{url}"
    if text:
        return f"За полным отчётом и обратной связью обратитесь в отдел кадров: {text}"
    return (
        "За полным отчётом, интерпретацией результатов и обратной связью "
        "обратитесь в отдел кадров вашей организации."
    )


def _top_scales(score_result: Any, labels: dict[str, str], *, limit: int = 2) -> str:
    if not score_result or not score_result.normalized_scores:
        return ""
    ranked = sorted(
        score_result.normalized_scores.items(),
        key=lambda item: float(item[1]),
        reverse=True,
    )
    parts: list[str] = []
    for scale, value in ranked[:limit]:
        name = labels.get(scale, scale)
        parts.append(f"{scale} ({name}) — {float(value):.1f}")
    return "; ".join(parts)


def build_quick_summary(
    engine: SessionEngine | AkmaDialogEngine,
    *,
    mbti_dialog: bool = False,
) -> str:
    """One-line summary for the closing block."""
    if isinstance(engine, AkmaDialogEngine):
        code = engine.akma_state.type_code or "—"
        return f"Предварительный тип: {code}."

    test_id = engine.session.test_id
    if test_id == "mbti" and engine.session.interpretation and engine.session.interpretation.profile:
        profile = engine.session.interpretation.profile
        code = engine.session.interpretation.typology_code or profile.code
        alt = ", ".join(profile.alt_names_ru)
        alt_part = f" ({alt})" if alt else ""
        summary = profile.summary_ru.strip()
        if summary:
            return f"Тип {code} — {profile.archetype_ru}{alt_part}. {summary}"
        return f"Тип {code} — {profile.archetype_ru}{alt_part}."

    score = engine.session.score_result
    if test_id == "paei" and score:
        top = _top_scales(score, PAEI_SCALE_NAMES)
        return f"Ведущие роли: {top}." if top else "Распределение по ролям PAEI — в блоке выше."
    if test_id == "soft_skills" and score and score.raw_scores:
        ranked = sorted(score.raw_scores.items(), key=lambda x: float(x[1]), reverse=True)
        skills = score.metadata.get("skills") or {}
        top = ranked[:2]
        parts = [f"{skills.get(dim, dim)} ({float(val):.0f}/5)" for dim, val in top]
        return f"Наиболее выраженные навыки: {', '.join(parts)}."
    if test_id == "disc" and score:
        top = _top_scales(score, DISC_SCALE_NAMES)
        return f"Ведущие шкалы DISC: {top}." if top else "Профиль DISC — в блоке выше."
    if test_id == "hexaco" and score:
        top = _top_scales(score, HEXACO_SCALE_NAMES)
        return f"Наиболее выраженные черты HEXACO: {top}." if top else "Профиль HEXACO — в блоке выше."

    label = _TEST_LABELS.get(test_id, test_id)
    if mbti_dialog:
        return f"Диалог MBTI с Акма завершён ({label})."
    return f"Результаты {label} — в блоке выше."


def build_completion_footer(
    engine: SessionEngine | AkmaDialogEngine,
    *,
    has_hr_assignment: bool,
    allowed_next_test_ids: list[str] | None = None,
    program_complete: bool = False,
    mbti_dialog: bool = False,
) -> str:
    """Thank-you + summary + HR guidance (appended after full report)."""
    if isinstance(engine, AkmaDialogEngine):
        test_id = "mbti"
    else:
        test_id = engine.session.test_id

    label = "MBTI (диалог с Акма)" if mbti_dialog else _TEST_LABELS.get(test_id, test_id)
    summary = build_quick_summary(engine, mbti_dialog=mbti_dialog)

    lines = [
        "—",
        f"Спасибо, что прошли тест «{label}»!",
        "",
        f"Краткое резюме: {summary}",
        "",
        _hr_contact_block(),
    ]

    if program_complete:
        lines.extend(["", "Программа психологического тестирования по назначению HR завершена."])
    elif has_hr_assignment:
        if allowed_next_test_ids:
            opts = ", ".join(_TEST_LABELS.get(t, t) for t in allowed_next_test_ids)
            lines.extend(
                [
                    "",
                    f"Следующий доступный этап: {opts}. Откройте /start и выберите тест кнопкой.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "Следующий этап программы откроет отдел кадров после обратной связи с вами.",
                ]
            )
    else:
        lines.extend(["", "При необходимости можно пройти другие тесты через меню /start."])

    return "\n".join(lines)
