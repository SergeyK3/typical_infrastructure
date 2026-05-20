"""Dispatch scoring by ``TestDefinition.scoring_type``."""

from __future__ import annotations

from typing import Literal, Sequence, Union

from psychological_testing.domain.entities import ScoreResult, TestDefinition
from psychological_testing.shared_engine.dichotomy_scorer import (
    Answer,
    DichotomyResult,
    calculate_type_from_answers,
)
from psychological_testing.shared_engine.item_bank_loader import load_csv_bank
from psychological_testing.shared_engine.forced_choice_scorer import (
    score_forced_choice,
)
from psychological_testing.shared_engine.item_bank_loader import load_items_for_definition
from psychological_testing.shared_engine.likert_per_dimension_scorer import (
    dimension_items_from_mappings,
    score_likert_per_dimension,
)
from psychological_testing.shared_engine.likert_scorer import (
    ResponseRow,
    ScaleScore,
    count_items_per_scale,
    item_rows_from_mappings,
    score_likert,
)
from psychological_testing.shared_engine.normalization import normalize_scores

DichotomyAnswer = tuple[str, str]
LikertAnswer = tuple[str, int]
ForcedChoiceAnswer = tuple[str, str]
AnswerInput = Union[DichotomyAnswer, LikertAnswer, ForcedChoiceAnswer]
TieBreak = Literal["first_pole", "second_pole"]


def _dichotomy_config(definition: TestDefinition) -> tuple[TieBreak, tuple[float, float]]:
    cfg = definition.scoring
    tie_break: TieBreak = cfg.get("tie_break", "first_pole")  # type: ignore[assignment]
    if tie_break not in ("first_pole", "second_pole"):
        raise ValueError(f"Invalid tie_break for {definition.test_id}: {tie_break!r}")
    levels = cfg.get("expression_levels", [0.3, 0.7])
    if not isinstance(levels, (list, tuple)) or len(levels) != 2:
        raise ValueError(f"expression_levels must be [low, high] for {definition.test_id}")
    return tie_break, (float(levels[0]), float(levels[1]))


def _min_val(definition: TestDefinition) -> int:
    if definition.scoring.get("min_val") is not None:
        return int(definition.scoring["min_val"])
    return int(definition.response_scale.get("min", 1))


def _max_val(definition: TestDefinition) -> int:
    if definition.scoring.get("max_val") is not None:
        return int(definition.scoring["max_val"])
    return int(definition.response_scale.get("max", 5))


def _axis_details_payload(result: DichotomyResult) -> dict[str, dict]:
    return {
        axis: {
            "dominant": detail.dominant,
            "level": detail.level,
            "counts": dict(detail.counts),
        }
        for axis, detail in result.axes.items()
    }


def _dichotomy_to_score_result(
    definition: TestDefinition,
    result: DichotomyResult,
) -> ScoreResult:
    return ScoreResult(
        typology_code=result.type_code,
        axis_details=_axis_details_payload(result),
        metadata={
            "scoring_type": definition.scoring_type,
            "test_id": definition.test_id,
            "test_version": definition.version,
        },
    )


def _likert_to_score_result(
    definition: TestDefinition,
    scale_scores: list[ScaleScore],
    *,
    item_counts: dict[str, int],
) -> ScoreResult:
    raw = {s.scale: float(s.raw) for s in scale_scores}
    return ScoreResult(
        raw_scores=raw,
        metadata={
            "scoring_type": definition.scoring_type,
            "test_id": definition.test_id,
            "test_version": definition.version,
            "item_counts_per_scale": item_counts,
            "max_val": _max_val(definition),
        },
    )


def _score_dichotomy(
    definition: TestDefinition,
    answers: Sequence[DichotomyAnswer],
) -> ScoreResult:
    tie_break, thresholds = _dichotomy_config(definition)
    dichotomy_answers: list[Answer] = [(a, p) for a, p in answers]  # type: ignore[misc]
    result = calculate_type_from_answers(
        dichotomy_answers,
        tie_break=tie_break,
        thresholds=thresholds,
    )
    return normalize_scores(_dichotomy_to_score_result(definition, result), definition)


def _forced_choice_to_score_result(
    definition: TestDefinition,
    scale_counts: list,
) -> ScoreResult:
    raw = {entry.scale: float(entry.count) for entry in scale_counts}
    for scale in definition.scales:
        raw.setdefault(scale, 0.0)
    return ScoreResult(
        raw_scores=raw,
        metadata={
            "scoring_type": definition.scoring_type,
            "test_id": definition.test_id,
            "test_version": definition.version,
            "total_responses": int(sum(raw.values())),
        },
    )


def _score_forced_choice_count(
    definition: TestDefinition,
    answers: Sequence[ForcedChoiceAnswer],
) -> ScoreResult:
    valid = frozenset(definition.scales) if definition.scales else None
    scale_counts = score_forced_choice(answers, valid_scales=valid)
    raw = _forced_choice_to_score_result(definition, scale_counts)
    return normalize_scores(raw, definition)


def _per_dimension_to_score_result(
    definition: TestDefinition,
    dimension_scores: list,
) -> ScoreResult:
    raw = {entry.dimension: entry.score for entry in dimension_scores}
    skills = {entry.dimension: entry.skill for entry in dimension_scores}
    return ScoreResult(
        raw_scores=raw,
        normalized_scores=dict(raw),
        axis_details={
            dim: {"skill": skills[dim], "score": raw[dim]} for dim in raw
        },
        metadata={
            "scoring_type": definition.scoring_type,
            "test_id": definition.test_id,
            "test_version": definition.version,
            "skills": skills,
        },
    )


def _score_likert_per_dimension(
    definition: TestDefinition,
    answers: Sequence[LikertAnswer],
) -> ScoreResult:
    if not definition.item_bank:
        raise ValueError(f"likert_per_dimension requires item_bank for {definition.test_id}")
    bank = load_items_for_definition(definition.item_bank)
    if not isinstance(bank, list):
        raise ValueError(f"Expected list items in bank: {definition.item_bank}")
    items = dimension_items_from_mappings(bank)
    scores = score_likert_per_dimension(
        items,
        answers,
        min_val=_min_val(definition),
        max_val=_max_val(definition),
    )
    raw = _per_dimension_to_score_result(definition, scores)
    return normalize_scores(raw, definition)


def _score_likert_sum(
    definition: TestDefinition,
    answers: Sequence[LikertAnswer],
) -> ScoreResult:
    if not definition.item_bank:
        raise ValueError(f"likert_sum requires item_bank for {definition.test_id}")
    rows = load_csv_bank(definition.item_bank)
    item_rows = item_rows_from_mappings(rows)
    responses = [ResponseRow(item_id=i, answer=a) for i, a in answers]
    scale_scores = score_likert(item_rows, responses, max_val=_max_val(definition))
    counts = count_items_per_scale(item_rows)
    raw = _likert_to_score_result(definition, scale_scores, item_counts=counts)
    return normalize_scores(raw, definition)


class ScoringPipeline:
    """Score structured answers using the plugin's ``scoring_type``."""

    def score(
        self,
        definition: TestDefinition,
        answers: Sequence[AnswerInput],
    ) -> ScoreResult:
        return score(definition, answers)


def score(
    definition: TestDefinition,
    answers: Sequence[AnswerInput],
) -> ScoreResult:
    """Run scoring for a test definition.

    - ``dichotomy_weighted_choice``: ``[(axis, pole), ...]``
    - ``likert_sum``: ``[(item_id, answer_1_to_5), ...]``
    - ``forced_choice_count``: ``[(item_id, scale_letter), ...]``
    - ``likert_per_dimension``: ``[(item_id, likert_1_to_5), ...]``
    """
    if definition.scoring_type == "dichotomy_weighted_choice":
        return _score_dichotomy(definition, answers)  # type: ignore[arg-type]
    if definition.scoring_type == "likert_sum":
        return _score_likert_sum(definition, answers)  # type: ignore[arg-type]
    if definition.scoring_type == "forced_choice_count":
        return _score_forced_choice_count(definition, answers)  # type: ignore[arg-type]
    if definition.scoring_type == "likert_per_dimension":
        return _score_likert_per_dimension(definition, answers)  # type: ignore[arg-type]

    raise NotImplementedError(
        f"scoring_type {definition.scoring_type!r} is not implemented yet "
        f"(test_id={definition.test_id})"
    )
