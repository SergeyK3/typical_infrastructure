"""Generic dichotomy scoring (production — promoted from research notebook 1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

AxisId = Literal["E/I", "S/N", "T/F", "J/P"]
Pole = str
Answer = tuple[AxisId, Pole]

VALID_TYPE_CODES: frozenset[str] = frozenset(
    {
        "ISTJ", "ISFJ", "INFJ", "INTJ",
        "ISTP", "ISFP", "INFP", "INTP",
        "ESTP", "ESFP", "ENFP", "ENTP",
        "ESTJ", "ESFJ", "ENFJ", "ENTJ",
    }
)

AXIS_POLES: dict[AxisId, tuple[Pole, Pole]] = {
    "E/I": ("E", "I"),
    "S/N": ("S", "N"),
    "T/F": ("T", "F"),
    "J/P": ("J", "P"),
}

AXIS_ORDER: tuple[AxisId, ...] = ("E/I", "S/N", "T/F", "J/P")


@dataclass(frozen=True)
class AxisDetail:
    axis: AxisId
    dominant: Pole
    level: int
    counts: dict[Pole, int]


@dataclass(frozen=True)
class DichotomyResult:
    type_code: str
    axes: dict[AxisId, AxisDetail]


def _expression_level(diff: int, total: int, thresholds: tuple[float, float]) -> int:
    if total <= 0:
        return 1
    ratio = abs(diff) / total
    low, high = thresholds
    if ratio < low:
        return 1
    if ratio < high:
        return 2
    return 3


def calculate_type_from_answers(
    answers: Sequence[Answer],
    *,
    tie_break: Literal["first_pole", "second_pole"] = "first_pole",
    thresholds: tuple[float, float] = (0.3, 0.7),
) -> DichotomyResult:
    """Count poles per axis → type_code + axis details."""
    counts: dict[AxisId, dict[Pole, int]] = {
        axis: {pole: 0 for pole in AXIS_POLES[axis]} for axis in AXIS_ORDER
    }

    for axis, pole in answers:
        if axis not in counts:
            raise ValueError(f"Unknown axis: {axis}")
        poles = AXIS_POLES[axis]
        if pole not in poles:
            raise ValueError(f"Pole {pole!r} not valid for axis {axis}")
        counts[axis][pole] += 1

    type_letters: list[str] = []
    axis_details: dict[AxisId, AxisDetail] = {}

    for axis in AXIS_ORDER:
        pos, neg = AXIS_POLES[axis]
        pos_count = counts[axis][pos]
        neg_count = counts[axis][neg]
        total = pos_count + neg_count

        if pos_count > neg_count:
            dominant = pos
        elif neg_count > pos_count:
            dominant = neg
        else:
            dominant = pos if tie_break == "first_pole" else neg

        level = _expression_level(pos_count - neg_count, total, thresholds)
        type_letters.append(dominant)
        axis_details[axis] = AxisDetail(
            axis=axis,
            dominant=dominant,
            level=level,
            counts=dict(counts[axis]),
        )

    type_code = "".join(type_letters)
    if type_code not in VALID_TYPE_CODES:
        raise ValueError(f"Invalid type_code: {type_code}")

    return DichotomyResult(type_code=type_code, axes=axis_details)


def validate_type_code(type_code: str) -> bool:
    return type_code in VALID_TYPE_CODES
