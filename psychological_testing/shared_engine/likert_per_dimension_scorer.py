"""Likert per dimension — one score per skill (Soft Skills)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class DimensionItem:
    item_id: str
    dimension: str
    skill: str


@dataclass(frozen=True)
class DimensionScore:
    dimension: str
    skill: str
    score: float


def dimension_items_from_mappings(items: Iterable[Mapping[str, object]]) -> list[DimensionItem]:
    result: list[DimensionItem] = []
    for raw in items:
        dimension = str(raw.get("dimension") or raw.get("scale") or raw["id"])
        result.append(
            DimensionItem(
                item_id=str(raw["id"]),
                dimension=dimension,
                skill=str(raw.get("skill") or dimension),
            )
        )
    return result


def score_likert_per_dimension(
    items: Sequence[DimensionItem],
    answers: Sequence[tuple[str, int]],
    *,
    min_val: int = 1,
    max_val: int = 5,
) -> list[DimensionScore]:
    """Map each item answer to its dimension score (no aggregation)."""
    meta = {item.item_id: item for item in items}
    seen: set[str] = set()
    scores: list[DimensionScore] = []

    for item_id, answer in answers:
        item = meta.get(item_id)
        if item is None:
            raise ValueError(f"Unknown item_id: {item_id!r}")
        if item_id in seen:
            raise ValueError(f"Duplicate answer for item_id: {item_id!r}")
        seen.add(item_id)
        if answer < min_val or answer > max_val:
            raise ValueError(
                f"Answer {answer} for {item_id} out of range [{min_val}, {max_val}]"
            )
        scores.append(
            DimensionScore(
                dimension=item.dimension,
                skill=item.skill,
                score=float(answer),
            )
        )

    return sorted(scores, key=lambda s: s.dimension)
