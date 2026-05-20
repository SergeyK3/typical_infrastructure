"""Phase 2 — DISC / HEXACO likert_sum plugins."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from psychological_testing.domain.test_registry import TestRegistry as PluginRegistry
from psychological_testing.shared_engine.item_bank_loader import load_csv_bank
from psychological_testing.shared_engine.scoring_pipeline import score

_ROOT = Path(__file__).resolve().parents[1]
_LEGACY_DISC = _ROOT.parent / "07 PsychTest" / "data" / "bank" / "disc_items.csv"
_LEGACY_HEXACO = _ROOT.parent / "07 PsychTest" / "data" / "bank" / "hexaco_items.csv"
_LEGACY_SRC = _ROOT.parent / "07 PsychTest" / "src"
_V1_DISC = _ROOT / "psychological_testing" / "data" / "banks" / "v1" / "disc_items.csv"
_V1_HEXACO = _ROOT / "psychological_testing" / "data" / "banks" / "v1" / "hexaco_items.csv"


class TestDiscHexacoRegistry:
    def test_discovers_disc_and_hexaco(self) -> None:
        registry = PluginRegistry()
        ids = registry.list_test_ids()
        assert "disc" in ids
        assert "hexaco" in ids
        assert "mbti" in ids

        disc = registry.get("disc")
        assert disc.scoring_type == "likert_sum"
        assert disc.scales == ["D", "I", "S", "C"]
        assert disc.normalization["method"] == "average_per_scale"


class TestDiscScoringPipeline:
    @pytest.fixture
    def disc(self):
        return PluginRegistry().get("disc")

    def test_raw_sums_match_legacy_scorer(self, disc) -> None:
        items = load_csv_bank(disc.item_bank)  # type: ignore[arg-type]
        answers = [("201", 5), ("202", 4), ("203", 3), ("204", 2)]
        result = score(disc, answers)
        assert result.raw_scores == {"C": 2.0, "D": 5.0, "I": 4.0, "S": 3.0}

    def test_normalized_averages_per_scale(self, disc) -> None:
        answers = [("201", 5), ("202", 4), ("203", 3), ("204", 2)]
        result = score(disc, answers)
        assert result.normalized_scores == {"D": 5.0, "I": 4.0, "S": 3.0, "C": 2.0}


class TestHexacoScoringPipeline:
    @pytest.fixture
    def hexaco(self):
        return PluginRegistry().get("hexaco")

    def test_six_factors_one_item_each(self, hexaco) -> None:
        answers = [("101", 5), ("102", 4), ("103", 3), ("104", 4), ("105", 3), ("106", 5)]
        result = score(hexaco, answers)
        assert set(result.raw_scores.keys()) == {"H", "E", "X", "A", "C", "O"}
        assert result.raw_scores["H"] == 5.0
        assert result.normalized_scores["H"] == 5.0

    def test_reverse_item_applied(self, hexaco) -> None:
        rows = load_csv_bank(hexaco.item_bank)  # type: ignore[arg-type]
        assert len(rows) == 6


@pytest.mark.skipif(
    not _LEGACY_DISC.exists() or not _LEGACY_SRC.exists(),
    reason="07 PsychTest sibling not found",
)
class TestPipelineLegacyParity:
    def test_v1_disc_matches_legacy_pandas_scorer(self) -> None:
        if str(_LEGACY_SRC) not in sys.path:
            sys.path.insert(0, str(_LEGACY_SRC))
        import pandas as pd  # noqa: WPS433
        from psytest.scoring import score_disc  # noqa: WPS433

        items = pd.read_csv(_V1_DISC)
        answers = [5, 4, 3, 2]
        responses = pd.DataFrame(
            {"item_id": items["item_id"].tolist(), "answer": answers}
        )
        legacy = {row["scale"]: int(row["raw"]) for _, row in score_disc(items, responses).iterrows()}

        disc = PluginRegistry().get("disc")
        pairs = list(zip(items["item_id"].astype(str), answers, strict=True))
        ours = score(disc, pairs)
        assert ours.raw_scores == {k: float(v) for k, v in legacy.items()}

    def test_v1_hexaco_matches_legacy(self) -> None:
        if str(_LEGACY_SRC) not in sys.path:
            sys.path.insert(0, str(_LEGACY_SRC))
        import pandas as pd  # noqa: WPS433
        from psytest.scoring import score_hexaco  # noqa: WPS433

        items = pd.read_csv(_V1_HEXACO)
        answers = [5, 4, 3, 4, 3, 5]
        responses = pd.DataFrame(
            {"item_id": items["item_id"].tolist(), "answer": answers}
        )
        legacy = {
            row["scale"]: int(row["raw"])
            for _, row in score_hexaco(items, responses).iterrows()
        }

        hexaco = PluginRegistry().get("hexaco")
        pairs = [(str(i), a) for i, a in zip(items["item_id"], answers, strict=True)]
        ours = score(hexaco, pairs)
        assert ours.raw_scores == {k: float(v) for k, v in legacy.items()}
