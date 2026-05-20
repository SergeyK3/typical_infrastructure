"""Phase 1 — session state machine + response collector (button/voice, no Telegram)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from psychological_testing.domain.entities import SessionStatus
from psychological_testing.domain.test_registry import TestRegistry as PluginRegistry
from psychological_testing.shared_engine.session_state_machine import SessionEngine
from psychological_testing.shared_engine.voice_pipeline import MockSttProvider, VoicePipeline


def _mbti_short_definition():
    """One question per axis (4 total) for fast session tests."""
    base = PluginRegistry().get("mbti")
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


def _answer_all_intj(engine: SessionEngine) -> None:
    """Submit pole-aligned button answers for each selected item."""
    poles_by_axis = {"E/I": "I", "S/N": "N", "T/F": "T", "J/P": "J"}
    while engine.session.status not in (SessionStatus.DONE, SessionStatus.CANCELLED):
        item = engine.current_item()
        if item is None:
            break
        pole = poles_by_axis[item.axis]
        choice = "A" if pole == item.option_a_pole else "B"
        engine.submit_button(choice)


class TestSessionButtonPath:
    def test_full_session_via_buttons_intj(self) -> None:
        engine = SessionEngine.start(
            _mbti_short_definition(),
            client_id="c1",
            employee_id="e1",
        )
        assert engine.session.status == SessionStatus.QUESTIONING
        assert len(engine.session.items) == 4

        _answer_all_intj(engine)

        assert engine.session.status == SessionStatus.DONE
        assert engine.session.score_result is not None
        assert engine.session.score_result.typology_code == "INTJ"
        assert engine.session.interpretation is not None
        assert "INTJ" in engine.session.interpretation.report_text
        assert len(engine.session.responses) == 4
        assert all(r.input_channel == "button" for r in engine.session.responses)
        assert all(r.confidence == 1.0 for r in engine.session.responses)

    def test_callback_data_with_prefix(self) -> None:
        engine = SessionEngine.start(
            _mbti_short_definition(),
            client_id="c1",
            employee_id="e1",
        )
        item = engine.current_item()
        assert item is not None
        choice = "A" if item.option_a_pole == "I" else "B"
        transition = engine.submit_button(f"mbti:{choice}")
        assert transition.status in (SessionStatus.QUESTIONING, SessionStatus.DONE)
        assert len(engine.session.responses) == 1


class TestSessionTextAndReprompt:
    def test_ambiguous_text_reprompts_without_advancing(self) -> None:
        engine = SessionEngine.start(
            _mbti_short_definition(),
            client_id="c1",
            employee_id="e1",
        )
        transition = engine.submit_text("не знаю")
        assert transition.status == SessionStatus.REPROMPT
        assert transition.reprompt_message
        assert engine.session.current_item_index == 0
        assert len(engine.session.responses) == 0

    def test_text_then_button_completes(self) -> None:
        engine = SessionEngine.start(
            _mbti_short_definition(),
            client_id="c1",
            employee_id="e1",
        )
        engine.submit_text("а или б")
        item = engine.current_item()
        assert item is not None
        choice = "A" if item.option_a_pole == "I" else "B"
        engine.submit_button(choice)
        _answer_all_intj(engine)
        assert engine.session.status == SessionStatus.DONE


class TestSessionVoicePath:
    def test_mock_stt_voice_without_external_api(self) -> None:
        definition = _mbti_short_definition()
        pipeline = VoicePipeline(MockSttProvider())
        engine = SessionEngine.start(
            definition,
            client_id="c1",
            employee_id="e1",
            voice_pipeline=pipeline,
        )

        for _ in range(4):
            item = engine.current_item()
            assert item is not None
            choice = "A" if item.option_a_pole in ("I", "N", "T", "J") else "B"
            audio = f"вариант {choice.lower()}".encode("utf-8")
            transition = engine.submit_voice(audio)
            assert transition.status in (
                SessionStatus.QUESTIONING,
                SessionStatus.DONE,
                SessionStatus.REPORT,
            )

        assert engine.session.status == SessionStatus.DONE
        assert len(engine.session.raw_transcripts) == 4
        assert all(r.input_channel == "voice" for r in engine.session.responses)


class TestSessionCancel:
    def test_cancel_stops_session(self) -> None:
        engine = SessionEngine.start(
            _mbti_short_definition(),
            client_id="c1",
            employee_id="e1",
        )
        transition = engine.cancel()
        assert transition.status == SessionStatus.CANCELLED
        assert engine.submit_button("A").status == SessionStatus.CANCELLED
