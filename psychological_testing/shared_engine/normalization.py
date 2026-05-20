"""Config-driven post-scoring transforms."""

from __future__ import annotations

from collections import defaultdict

from psychological_testing.domain.entities import ScoreResult, TestDefinition
from psychological_testing.shared_engine.item_bank_loader import load_csv_bank
from psychological_testing.shared_engine.likert_scorer import item_rows_from_mappings


def _item_counts_per_scale(definition: TestDefinition) -> dict[str, int]:
    if not definition.item_bank:
        raise ValueError(f"item_bank required for normalization: {definition.test_id}")
    rows = load_csv_bank(definition.item_bank)
    item_rows = item_rows_from_mappings(rows)
    counts: dict[str, int] = defaultdict(int)
    for row in item_rows:
        counts[row.scale] += 1
    return dict(counts)


def normalize_scores(score: ScoreResult, definition: TestDefinition) -> ScoreResult:
    """Apply ``TestDefinition.normalization`` to a score result."""
    method = definition.normalization.get("method", "none")
    if method == "none":
        return score

    if method == "average_per_scale":
        counts = score.metadata.get("item_counts_per_scale")
        if not counts:
            counts = _item_counts_per_scale(definition)
        normalized: dict[str, float] = {}
        for scale, raw in score.raw_scores.items():
            n = counts.get(scale, 0)
            if n <= 0:
                raise ValueError(f"No items for scale {scale!r} in {definition.test_id}")
            normalized[scale] = raw / n
        return ScoreResult(
            raw_scores=dict(score.raw_scores),
            normalized_scores=normalized,
            typology_code=score.typology_code,
            axis_details=dict(score.axis_details),
            metadata={**score.metadata, "normalization": method},
        )

    if method == "percentage_of_total":
        total = sum(score.raw_scores.values())
        if total <= 0:
            scales = definition.scales or list(score.raw_scores.keys())
            return ScoreResult(
                raw_scores=dict(score.raw_scores),
                normalized_scores={s: 0.0 for s in scales},
                typology_code=score.typology_code,
                axis_details=dict(score.axis_details),
                metadata={**score.metadata, "normalization": method},
            )
        normalized = {scale: (raw / total) * 100.0 for scale, raw in score.raw_scores.items()}
        return ScoreResult(
            raw_scores=dict(score.raw_scores),
            normalized_scores=normalized,
            typology_code=score.typology_code,
            axis_details=dict(score.axis_details),
            metadata={**score.metadata, "normalization": method},
        )

    raise ValueError(f"Unknown normalization method: {method!r} for {definition.test_id}")
