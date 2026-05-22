"""Phase 0 research scripts — unit-style validation (no Colab runtime)."""

from __future__ import annotations

from pathlib import Path

import pytest

from psychological_testing.research.mbti.scripts.dichotomy_scorer import (
    VALID_TYPE_CODES,
    calculate_type_from_answers,
)
from psychological_testing.research.mbti.scripts.export_mbti_items_from_colab import (
    colab_calculate_type_from_answers,
)
from psychological_testing.research.mbti.scripts.question_selector import select_questions
from psychological_testing.research.scripts.likert_scorer import (
    ItemRow,
    ResponseRow,
    score_likert,
)
from psychological_testing.research.scripts.load_item_bank import (
    load_csv_bank,
    load_mbti_items,
    load_yaml_file,
)

_ROOT = Path(__file__).resolve().parents[1]
_LEGACY_DISC = _ROOT.parent / "07 PsychTest" / "data" / "bank" / "disc_items.csv"


class TestDichotomyScorer:
    def test_intj_from_eight_answers(self) -> None:
        answers = [
            ("E/I", "I"),
            ("S/N", "N"),
            ("T/F", "T"),
            ("J/P", "J"),
        ] * 2
        result = calculate_type_from_answers(answers)
        assert result.type_code == "INTJ"
        assert result.axes["E/I"].dominant == "I"
        assert result.axes["S/N"].dominant == "N"

    @pytest.mark.parametrize(
        "type_code,answers",
        [
            (
                "ENFP",
                [
                    ("E/I", "E"),
                    ("S/N", "N"),
                    ("T/F", "F"),
                    ("J/P", "P"),
                ]
                * 3,
            ),
            (
                "ESTJ",
                [
                    ("E/I", "E"),
                    ("S/N", "S"),
                    ("T/F", "T"),
                    ("J/P", "J"),
                ]
                * 3,
            ),
        ],
    )
    def test_sample_type_codes(self, type_code: str, answers: list) -> None:
        result = calculate_type_from_answers(answers)
        assert result.type_code == type_code
        assert result.type_code in VALID_TYPE_CODES

    @pytest.mark.parametrize(
        "answers",
        [
            [("E/I", "I"), ("S/N", "N"), ("T/F", "T"), ("J/P", "J")] * 4,
            [("E/I", "E"), ("E/I", "E"), ("S/N", "S"), ("T/F", "F"), ("J/P", "P")],
            [("E/I", "I"), ("S/N", "S"), ("T/F", "T"), ("J/P", "P")] * 2,
        ],
    )
    def test_matches_colab_reference(self, answers: list) -> None:
        ours = calculate_type_from_answers(answers)
        ref = colab_calculate_type_from_answers(answers)
        assert ours.type_code == ref["type_code"]
        for axis in ("E/I", "S/N", "T/F", "J/P"):
            assert ours.axes[axis].dominant == ref["axes"][axis]["dominant"]
            assert ours.axes[axis].level == ref["axes"][axis]["level"]


class TestMbtiInterpretations:
    def test_all_16_types_have_content(self) -> None:
        doc = load_yaml_file("data/interpretations/v1/mbti_16_types.yaml")
        types = doc["types"]
        assert len(types) == 16
        for code, profile in types.items():
            assert profile["code"] == code
            assert profile.get("archetype_ru")
            assert profile.get("alt_names_ru")
            assert profile.get("summary_ru")
            assert len(profile.get("strengths", [])) >= 2
            assert len(profile.get("growth_areas", [])) >= 2


class TestMbtiItemBank:
    def test_full_bank_48_items(self) -> None:
        items = load_mbti_items()
        assert len(items) == 48
        per_axis: dict[str, int] = {}
        for item in items:
            per_axis[item["axis"]] = per_axis.get(item["axis"], 0) + 1
        assert per_axis == {"E/I": 12, "S/N": 12, "T/F": 12, "J/P": 12}


class TestLikertScorer:
    def test_reverse_and_sum(self) -> None:
        items = [
            ItemRow("1", "D", reverse=0),
            ItemRow("2", "D", reverse=1),
            ItemRow("3", "I", reverse=0),
        ]
        responses = [
            ResponseRow("1", 5),
            ResponseRow("2", 1),
            ResponseRow("3", 4),
        ]
        scores = {s.scale: s.raw for s in score_likert(items, responses, max_val=5)}
        assert scores["D"] == 5 + 5
        assert scores["I"] == 4

    @pytest.mark.skipif(not _LEGACY_DISC.exists(), reason="07 PsychTest sibling not found")
    def test_legacy_disc_csv_shape(self) -> None:
        rows = load_csv_bank(_LEGACY_DISC)
        assert len(rows) >= 4
        assert "item_id" in rows[0]
        assert "scale" in rows[0]


class TestQuestionSelector:
    def test_selects_per_axis(self) -> None:
        items = load_mbti_items()
        picked = select_questions(items, questions_per_axis=1, shuffle_axes=False, seed=1)
        axes = {q.axis for q in picked}
        assert axes == {"E/I", "S/N", "T/F", "J/P"}
        assert len(picked) == 4
