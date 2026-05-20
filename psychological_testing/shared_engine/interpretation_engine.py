"""Lookup interpretation profiles and build user-facing report text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from psychological_testing.domain.entities import ScoreResult, TestDefinition
from psychological_testing.shared_engine.item_bank_loader import load_yaml_file
from psychological_testing.shared_engine.normalization import normalize_scores

AXIS_LABELS_RU: dict[str, dict[str, str]] = {
    "E/I": {"E": "Экстраверсия", "I": "Интроверсия"},
    "S/N": {"S": "Сенсорика", "N": "Интуиция"},
    "T/F": {"T": "Мышление", "F": "Чувство"},
    "J/P": {"J": "Суждение", "P": "Восприятие"},
}


@dataclass(frozen=True)
class TypeProfile:
    code: str
    name_ru: str
    tagline: str
    strengths: list[str]
    growth_areas: list[str]
    axes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class InterpretationResult:
    typology_code: str | None
    profile: TypeProfile | None
    axis_details: dict[str, Any]
    report_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _profile_from_dict(code: str, raw: dict[str, Any]) -> TypeProfile:
    return TypeProfile(
        code=str(raw.get("code", code)),
        name_ru=str(raw.get("name_ru", "")),
        tagline=str(raw.get("tagline", "")),
        strengths=[str(s) for s in raw.get("strengths", [])],
        growth_areas=[str(g) for g in raw.get("growth_areas", [])],
        axes={str(k): str(v) for k, v in (raw.get("axes") or {}).items()},
    )


def load_type_profiles(path: str) -> dict[str, TypeProfile]:
    """Load ``types`` map from MBTI-style interpretation YAML."""
    doc = load_yaml_file(path)
    types_raw = doc.get("types")
    if not isinstance(types_raw, dict):
        raise ValueError(f"Interpretation file must contain 'types' mapping: {path}")
    return {
        code: _profile_from_dict(code, profile if isinstance(profile, dict) else {})
        for code, profile in types_raw.items()
    }


def lookup_type_profile(
    profiles: dict[str, TypeProfile],
    type_code: str,
) -> TypeProfile:
    try:
        return profiles[type_code]
    except KeyError as exc:
        raise KeyError(f"Unknown type_code in interpretation data: {type_code}") from exc


def _format_axis_line(axis: str, detail: dict[str, Any]) -> str:
    dominant = detail.get("dominant", "?")
    level = detail.get("level", 1)
    label = AXIS_LABELS_RU.get(axis, {}).get(str(dominant), str(dominant))
    return f"  {axis}: {label} ({dominant}) — уровень выраженности {level}/3"


def build_report_text(
    profile: TypeProfile,
    axis_details: dict[str, Any],
    *,
    disclaimer: str | None = None,
) -> str:
    """Assemble static user-facing report (HR OS §3.7 structure)."""
    lines = [
        "=== ИТОГОВЫЙ ПСИХОЛОГИЧЕСКИЙ ПОРТРЕТ ===",
        "",
        f"Ваш тип личности: {profile.code} — {profile.name_ru}",
        f"{profile.tagline}",
        "",
        "ДЕТАЛИ ПРОФИЛЯ:",
    ]
    for axis in ("E/I", "S/N", "T/F", "J/P"):
        if axis in axis_details:
            lines.append(_format_axis_line(axis, axis_details[axis]))
    lines.extend(["", "Сильные стороны:"])
    lines.extend(f"  • {s}" for s in profile.strengths)
    lines.extend(["", "Зоны роста:"])
    lines.extend(f"  • {g}" for g in profile.growth_areas)
    if disclaimer:
        lines.extend(["", disclaimer])
    return "\n".join(lines)


DEFAULT_DISCLAIMER = (
    "Результат отражает предпочтения в ответах на структурированные вопросы "
    "и не является единственным критерием HR-оценки."
)


def interpret(
    definition: TestDefinition,
    score: ScoreResult,
    *,
    profiles: dict[str, TypeProfile] | None = None,
    disclaimer: str | None = DEFAULT_DISCLAIMER,
) -> InterpretationResult:
    """Lookup interpretation for a scored session."""
    type_code = score.typology_code
    if not type_code:
        return InterpretationResult(
            typology_code=None,
            profile=None,
            axis_details=dict(score.axis_details),
            report_text="Результат теста недоступен: тип не определён.",
            metadata={"test_id": definition.test_id},
        )

    if profiles is None:
        if not definition.interpretation:
            raise ValueError(f"No interpretation path for {definition.test_id}")
        profiles = load_type_profiles(definition.interpretation)

    profile = lookup_type_profile(profiles, type_code)
    report_text = build_report_text(profile, score.axis_details, disclaimer=disclaimer)

    return InterpretationResult(
        typology_code=type_code,
        profile=profile,
        axis_details=dict(score.axis_details),
        report_text=report_text,
        metadata={
            "test_id": definition.test_id,
            "test_version": definition.version,
            "interpretation": definition.interpretation,
        },
    )


def evaluate(
    definition: TestDefinition,
    answers: list[tuple[str, str]],
) -> InterpretationResult:
    """Score → normalize → interpret (MBTI pole answers)."""
    from psychological_testing.shared_engine.scoring_pipeline import score as run_score

    score_result = normalize_scores(run_score(definition, answers), definition)
    return interpret(definition, score_result)
