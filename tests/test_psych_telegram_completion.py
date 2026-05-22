"""Telegram completion footer after psychological tests."""

from __future__ import annotations

from dataclasses import replace

from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.integration.telegram_completion import build_completion_footer
from psychological_testing.shared_engine.session_state_machine import SessionEngine


def _mbti_one_per_axis():
    base = TestRegistry().get("mbti")
    return replace(
        base,
        selection={
            "questions_per_axis": 1,
            "max_per_axis": 12,
            "sort_by": "weight_desc",
            "shuffle_axes": False,
            "seed": 1,
        },
    )


def test_completion_footer_thanks_and_hr_contact():
    engine = SessionEngine.start(_mbti_one_per_axis(), client_id="c", employee_id="e")
    item = engine.current_item()
    assert item is not None
    engine.submit_button("A")
    footer = build_completion_footer(
        engine,
        has_hr_assignment=True,
        allowed_next_test_ids=[],
        program_complete=False,
    )
    assert "Спасибо" in footer
    assert "отдел кадров" in footer.lower()
    assert "Следующий этап программы откроет отдел кадров" in footer
