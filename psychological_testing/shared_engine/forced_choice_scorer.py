"""Forced-choice scoring — count selections per scale (PAEI)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

PAEI_SCALES = frozenset({"P", "A", "E", "I"})


@dataclass(frozen=True)
class ForcedChoiceAnswer:
    item_id: str
    scale: str


@dataclass(frozen=True)
class ScaleCount:
    scale: str
    count: int


def score_forced_choice(
    answers: Sequence[ForcedChoiceAnswer | tuple[str, str]],
    *,
    valid_scales: frozenset[str] | None = None,
) -> list[ScaleCount]:
    """Count how often each scale was selected."""
    allowed = valid_scales or PAEI_SCALES
    totals: dict[str, int] = defaultdict(int)

    for entry in answers:
        if isinstance(entry, ForcedChoiceAnswer):
            item_id, scale = entry.item_id, entry.scale
        else:
            item_id, scale = entry
        scale = str(scale).strip().upper()
        if scale not in allowed:
            raise ValueError(f"Invalid scale {scale!r} for item {item_id!r}")
        totals[scale] += 1

    for scale in sorted(allowed):
        totals.setdefault(scale, 0)

    return [ScaleCount(scale=s, count=totals[s]) for s in sorted(totals)]
