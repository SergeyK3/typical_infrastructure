"""Generic question selection (weight-based sampling per axis)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Literal, Sequence


@dataclass(frozen=True)
class SelectableItem:
    id: str
    axis: str
    text: str
    option_a_text: str
    option_a_pole: str
    option_b_text: str
    option_b_pole: str
    weight: int = 1


def item_from_dict(raw: dict[str, Any]) -> SelectableItem:
    opt_a = raw.get("option_a") or {}
    opt_b = raw.get("option_b") or {}
    if not isinstance(opt_a, dict):
        opt_a = {}
    if not isinstance(opt_b, dict):
        opt_b = {}
    return SelectableItem(
        id=str(raw["id"]),
        axis=str(raw["axis"]),
        text=str(raw.get("text", "")),
        option_a_text=str(opt_a.get("text", "")),
        option_a_pole=str(opt_a.get("pole", "")),
        option_b_text=str(opt_b.get("text", "")),
        option_b_pole=str(opt_b.get("pole", "")),
        weight=int(raw.get("weight", 1)),
    )


def select_questions(
    items: Sequence[dict[str, Any] | SelectableItem],
    *,
    questions_per_axis: int = 4,
    max_per_axis: int = 12,
    sort_by: Literal["weight_desc", "id"] = "weight_desc",
    shuffle_axes: bool = True,
    seed: int | None = 42,
) -> list[SelectableItem]:
    """Pick up to ``questions_per_axis`` items per axis, highest weight first."""
    parsed = [
        item if isinstance(item, SelectableItem) else item_from_dict(item)
        for item in items
    ]

    by_axis: dict[str, list[SelectableItem]] = {}
    for item in parsed:
        by_axis.setdefault(item.axis, []).append(item)

    selected: list[SelectableItem] = []
    axes = sorted(by_axis.keys())
    rng = random.Random(seed)
    if shuffle_axes:
        rng.shuffle(axes)

    for axis in axes:
        pool = by_axis[axis][:max_per_axis]
        if sort_by == "weight_desc":
            pool = sorted(pool, key=lambda x: (-x.weight, x.id))
        else:
            pool = sorted(pool, key=lambda x: x.id)
        selected.extend(pool[:questions_per_axis])

    return selected


def select_from_definition(
    items: Sequence[dict[str, Any] | SelectableItem],
    selection: dict[str, Any],
) -> list[SelectableItem]:
    """Apply ``TestDefinition.selection`` block to an item pool."""
    return select_questions(
        items,
        questions_per_axis=int(selection.get("questions_per_axis", 4)),
        max_per_axis=int(selection.get("max_per_axis", 12)),
        sort_by=selection.get("sort_by", "weight_desc"),  # type: ignore[arg-type]
        shuffle_axes=bool(selection.get("shuffle_axes", True)),
        seed=selection.get("seed"),
    )
