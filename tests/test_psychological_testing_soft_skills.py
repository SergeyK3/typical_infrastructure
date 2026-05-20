"""Phase 2 — Soft Skills likert_per_dimension plugin."""

from __future__ import annotations

import pytest

from psychological_testing.domain.entities import SessionStatus
from psychological_testing.domain.test_registry import TestRegistry as PluginRegistry
from psychological_testing.shared_engine.answer_resolver import resolve_likert_value
from psychological_testing.shared_engine.item_bank_loader import load_soft_skills_items
from psychological_testing.shared_engine.scoring_pipeline import score
from psychological_testing.shared_engine.session_state_machine import SessionEngine


class TestSoftSkillsRegistry:
    def test_discovers_plugin(self) -> None:
        soft = PluginRegistry().get("soft_skills")
        assert soft.scoring_type == "likert_per_dimension"
        assert len(soft.scales) == 10
        assert soft.response_scale["max"] == 5


class TestSoftSkillsScoring:
    @pytest.fixture
    def soft(self):
        return PluginRegistry().get("soft_skills")

    def test_one_score_per_dimension(self, soft) -> None:
        answers = [(f"soft_{i:03d}", i % 5 + 1) for i in range(1, 11)]
        result = score(soft, answers)
        assert len(result.raw_scores) == 10
        assert result.raw_scores["communication"] == 2.0  # soft_001: 1 % 5 + 1
        assert result.raw_scores["creativity"] == 1.0  # soft_010: 10 % 5 + 1
        assert result.normalized_scores == result.raw_scores
        assert result.metadata["skills"]["leadership"] == "Лидерство"

    def test_duplicate_item_rejected(self, soft) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            score(soft, [("soft_001", 3), ("soft_001", 4)])

    def test_item_bank_ten_skills(self, soft) -> None:
        items = load_soft_skills_items(soft.item_bank)  # type: ignore[arg-type]
        assert len(items) == 10


class TestSoftSkillsResolver:
    @pytest.mark.parametrize(
        "text,expected",
        [("3", 3), ("три", 3), ("5", 5)],
    )
    def test_likert_voice(self, text: str, expected: int) -> None:
        result = resolve_likert_value(text)
        assert result is not None
        assert result.value == expected


class TestSoftSkillsSession:
    def test_short_session_three_items(self) -> None:
        """Full bank is 10 questions; spot-check first 3 via manual advance."""
        soft = PluginRegistry().get("soft_skills")
        engine = SessionEngine.start(soft, client_id="c1", employee_id="e1")
        assert len(engine.session.items) == 10

        scores = [4, 3, 5]
        last = None
        for score_val in scores:
            last = engine.submit_button(f"soft_{score_val}")
        assert engine.session.status == SessionStatus.QUESTIONING
        assert len(engine.session.responses) == 3

        for score_val in [2, 1, 4, 3, 5, 2, 1]:
            last = engine.submit_button(f"soft_{score_val}")

        assert engine.session.status == SessionStatus.DONE
        assert last is not None
        assert last.report_text
        assert engine.session.score_result is not None
        assert engine.session.score_result.raw_scores["communication"] == 4.0
        assert len(engine.session.score_result.raw_scores) == 10
