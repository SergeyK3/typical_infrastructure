"""Assemble deliverable report artifacts from interpretation output."""

from __future__ import annotations

from psychological_testing.domain.entities import ScoreResult
from psychological_testing.shared_engine.interpretation_engine import InterpretationResult

PAEI_SCALE_NAMES = {
    "P": "Producer (Производитель)",
    "A": "Administrator (Администратор)",
    "E": "Entrepreneur (Предприниматель)",
    "I": "Integrator (Интегратор)",
}

DISC_SCALE_NAMES = {
    "D": "Dominance (Доминирование)",
    "I": "Influence (Влияние)",
    "S": "Steadiness (Стабильность)",
    "C": "Compliance (Согласованность)",
}

HEXACO_SCALE_NAMES = {
    "H": "Honesty-Humility (Честность–Скромность)",
    "E": "Emotionality (Эмоциональность)",
    "X": "eXtraversion (Экстраверсия)",
    "A": "Agreeableness (Доброжелательность)",
    "C": "Conscientiousness (Добросовестность)",
    "O": "Openness (Открытость опыту)",
}


def build_text_report(result: InterpretationResult | ScoreResult) -> str:
    """Return plain-text report (Telegram / preview)."""
    if isinstance(result, InterpretationResult):
        return result.report_text
    return format_paei_report(result)


def format_paei_report(score: ScoreResult) -> str:
    """Static PAEI report from counts and percentage normalization."""
    lines = [
        "=== РЕЗУЛЬТАТ PAEI (Адизес) ===",
        "",
        "Распределение выборов по ролям:",
    ]
    for scale in ("P", "A", "E", "I"):
        raw = int(score.raw_scores.get(scale, 0))
        pct = score.normalized_scores.get(scale, 0.0)
        label = PAEI_SCALE_NAMES.get(scale, scale)
        lines.append(f"  {scale} — {label}: {raw} ({pct:.0f}%)")
    lines.extend(
        [
            "",
            "Результат отражает предпочтения в forced-choice ответах "
            "и не является единственным критерием HR-оценки.",
        ]
    )
    return "\n".join(lines)


def format_likert_sum_report(score: ScoreResult, *, test_id: str) -> str:
    """Static Likert-sum report (DISC / HEXACO mini banks)."""
    labels = DISC_SCALE_NAMES if test_id == "disc" else HEXACO_SCALE_NAMES
    title = "DISC" if test_id == "disc" else "HEXACO"
    lines = [
        f"=== РЕЗУЛЬТАТ {title} ===",
        "",
        "Сумма баллов и среднее по шкале (1–5):",
    ]
    scale_order = (
        list(DISC_SCALE_NAMES.keys())
        if test_id == "disc"
        else list(HEXACO_SCALE_NAMES.keys())
    )
    for scale in scale_order:
        if scale not in score.raw_scores:
            continue
        raw = score.raw_scores[scale]
        avg = score.normalized_scores.get(scale, raw)
        label = labels.get(scale, scale)
        lines.append(f"  {scale} — {label}: сумма {raw:.0f}, среднее {avg:.1f}/5")
    lines.extend(
        [
            "",
            "Результат отражает ответы на структурированные вопросы "
            "и не является единственным критерием HR-оценки.",
        ]
    )
    return "\n".join(lines)


def format_soft_skills_report(score: ScoreResult) -> str:
    """Static Soft Skills report — score per dimension (1–5)."""
    skills = score.metadata.get("skills") or {}
    lines = [
        "=== РЕЗУЛЬТАТ SOFT SKILLS ===",
        "",
        "Оценка по навыкам (шкала 1–5):",
    ]
    for dimension in sorted(score.raw_scores.keys()):
        label = skills.get(dimension, dimension)
        value = score.raw_scores[dimension]
        lines.append(f"  {label}: {value:.0f}/5")
    lines.extend(
        [
            "",
            "Результат отражает самооценку по структурированным вопросам "
            "и не является единственным критерием HR-оценки.",
        ]
    )
    return "\n".join(lines)
