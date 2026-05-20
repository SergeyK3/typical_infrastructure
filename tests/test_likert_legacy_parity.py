"""Likert scorer parity with 07 PsychTest scoring.py on CSV item banks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from psychological_testing.research.scripts.likert_scorer import score_likert_from_mappings
from psychological_testing.research.scripts.load_item_bank import load_csv_bank

_ROOT = Path(__file__).resolve().parents[1]
_LEGACY_ROOT = _ROOT.parent / "07 PsychTest"
_LEGACY_SRC = _LEGACY_ROOT / "src"
_DISC_CSV = _LEGACY_ROOT / "data" / "bank" / "disc_items.csv"
_HEXACO_CSV = _LEGACY_ROOT / "data" / "bank" / "hexaco_items.csv"

pytestmark = pytest.mark.skipif(
    not _DISC_CSV.exists() or not _LEGACY_SRC.exists(),
    reason="07 PsychTest sibling not found",
)


def _legacy_score(csv_path: Path, answers: list[int]) -> dict[str, int]:
    if str(_LEGACY_SRC) not in sys.path:
        sys.path.insert(0, str(_LEGACY_SRC))
    import pandas as pd  # noqa: WPS433 — legacy parity only
    from psytest.scoring import score_disc, score_hexaco  # noqa: WPS433

    items = pd.read_csv(csv_path)
    responses = pd.DataFrame(
        {"item_id": items["item_id"].tolist(), "answer": answers}
    )
    if "disc" in csv_path.name:
        scores = score_disc(items, responses)
    else:
        scores = score_hexaco(items, responses)
    return {row["scale"]: int(row["raw"]) for _, row in scores.iterrows()}


def _ours_score(csv_path: Path, answers: list[int]) -> dict[str, int]:
    items = load_csv_bank(csv_path)
    responses = [
        {"item_id": items[i]["item_id"], "answer": answers[i]}
        for i in range(len(answers))
    ]
    result = score_likert_from_mappings(items, responses, max_val=5)
    return {s.scale: s.raw for s in result}


class TestLikertLegacyParity:
    def test_disc_csv_matches_legacy(self) -> None:
        answers = [5, 4, 3, 2]
        assert _ours_score(_DISC_CSV, answers) == _legacy_score(_DISC_CSV, answers)

    def test_hexaco_csv_matches_legacy(self) -> None:
        answers = [5, 1]
        assert _ours_score(_HEXACO_CSV, answers) == _legacy_score(_HEXACO_CSV, answers)

    def test_disc_item_count_vs_bot(self) -> None:
        """CSV bank is short form; bot uses 8 questions from disc_user.txt."""
        items = load_csv_bank(_DISC_CSV)
        assert len(items) == 4
        disc_prompts = _LEGACY_ROOT / "data" / "prompts" / "disc_user.txt"
        if disc_prompts.exists():
            import re

            text = disc_prompts.read_text(encoding="utf-8")
            sub_questions = re.findall(r"^\s*\d+\.\d+", text, re.MULTILINE)
            assert len(sub_questions) == 8
