"""Likert scoring for DISC/HEXACO (production — promoted from research)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class ItemRow:
    item_id: str
    scale: str
    reverse: int = 0


@dataclass(frozen=True)
class ResponseRow:
    item_id: str
    answer: int


@dataclass(frozen=True)
class ScaleScore:
    scale: str
    raw: int


def reverse_code(answer: int, max_val: int = 5) -> int:
    return max_val + 1 - answer


def score_likert(
    items: Sequence[ItemRow],
    responses: Sequence[ResponseRow],
    *,
    max_val: int = 5,
) -> list[ScaleScore]:
    """Sum adjusted answers per scale (DISC, HEXACO)."""
    meta = {row.item_id: row for row in items}
    totals: dict[str, int] = defaultdict(int)

    for resp in responses:
        item = meta.get(resp.item_id)
        if item is None:
            continue
        adj = (
            reverse_code(resp.answer, max_val)
            if item.reverse == 1
            else resp.answer
        )
        totals[item.scale] += adj

    return [ScaleScore(scale=s, raw=totals[s]) for s in sorted(totals)]


def item_rows_from_mappings(items: Iterable[Mapping[str, object]]) -> list[ItemRow]:
    return [
        ItemRow(
            item_id=str(r["item_id"]),
            scale=str(r["scale"]),
            reverse=int(r.get("reverse", 0) or 0),
        )
        for r in items
    ]


def count_items_per_scale(items: Sequence[ItemRow]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in items:
        counts[row.scale] += 1
    return dict(counts)


def score_likert_from_mappings(
    items: Iterable[Mapping[str, object]],
    responses: Iterable[Mapping[str, object]],
    *,
    max_val: int = 5,
) -> list[ScaleScore]:
    """Convenience for dict rows from CSV loaders."""
    item_rows = item_rows_from_mappings(items)
    resp_rows = [
        ResponseRow(item_id=str(r["item_id"]), answer=int(r["answer"]))
        for r in responses
    ]
    return score_likert(item_rows, resp_rows, max_val=max_val)
