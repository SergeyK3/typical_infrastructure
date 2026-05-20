"""Phase 2 — PAEI forced_choice_count plugin."""

from __future__ import annotations

import pytest

from psychological_testing.domain.entities import SessionStatus
from psychological_testing.domain.test_registry import TestRegistry as PluginRegistry
from psychological_testing.shared_engine.answer_resolver import resolve_paei_choice
from psychological_testing.shared_engine.item_bank_loader import load_paei_items
from psychological_testing.shared_engine.scoring_pipeline import score
from psychological_testing.shared_engine.session_state_machine import SessionEngine


class TestPaeiRegistry:
    def test_discovers_paei(self) -> None:
        paei = PluginRegistry().get("paei")
        assert paei.scoring_type == "forced_choice_count"
        assert paei.scales == ["P", "A", "E", "I"]
        assert paei.normalization["method"] == "percentage_of_total"


class TestPaeiScoring:
    @pytest.fixture
    def paei(self):
        return PluginRegistry().get("paei")

    def test_counts_and_percentages(self, paei) -> None:
        answers = [
            ("paei_001", "P"),
            ("paei_002", "P"),
            ("paei_003", "A"),
            ("paei_004", "E"),
            ("paei_005", "I"),
        ]
        result = score(paei, answers)
        assert result.raw_scores == {"A": 1.0, "E": 1.0, "I": 1.0, "P": 2.0}
        assert result.normalized_scores["P"] == 40.0
        assert sum(result.normalized_scores.values()) == pytest.approx(100.0)

    def test_item_bank_five_questions(self, paei) -> None:
        items = load_paei_items(paei.item_bank)  # type: ignore[arg-type]
        assert len(items) == 5
        assert all(set(item.options.keys()) == {"P", "A", "E", "I"} for item in items)


class TestPaeiResolver:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("P", "P"),
            ("п", "P"),
            ("администратор", "A"),
        ],
    )
    def test_resolve_scale(self, text: str, expected: str) -> None:
        result = resolve_paei_choice(text)
        assert result is not None
        assert result.value == expected


class TestPaeiSession:
    def test_full_session_via_buttons(self) -> None:
        engine = SessionEngine.start(
            PluginRegistry().get("paei"),
            client_id="c1",
            employee_id="e1",
        )
        assert len(engine.session.items) == 5
        last = None
        for choice in ("P", "P", "A", "E", "I"):
            item = engine.current_item()
            assert item is not None
            last = engine.submit_button(f"paei_{choice}")

        assert engine.session.status == SessionStatus.DONE
        assert engine.session.score_result is not None
        assert engine.session.score_result.raw_scores["P"] == 2.0
        assert last is not None
        assert "PAEI" in (last.report_text or "")
