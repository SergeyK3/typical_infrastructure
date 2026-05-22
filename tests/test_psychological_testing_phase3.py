"""Phase 3 — Telegram adapter (mock outbound, no live Bot API)."""

from __future__ import annotations

import os
from dataclasses import replace
from types import SimpleNamespace

import pytest

from psychological_testing.adapters.telegram_keyboards import (
    build_callback_data,
    build_menu_callback_data,
    build_step_menu_callback_data,
    keyboard_for_item,
    parse_callback_data,
    parse_menu_callback,
    parse_menu_step_action,
    welcome_menu_keyboard,
)
from psychological_testing.adapters.telegram_outbound import (
    FakeTelegramOutbound,
    clear_fake_telegram_outbound,
)
from psychological_testing.domain.entities import SessionStatus
from psychological_testing.domain.test_registry import TestRegistry as PluginRegistry
from psychological_testing.integration.session_store import reset_session_store
from psychological_testing.integration.telegram_adapter import PsychTestingTelegramAdapter
from psychological_testing.shared_engine.session_state_machine import SessionEngine
from psychological_testing.shared_engine.voice_pipeline import MockSttProvider, VoicePipeline


@pytest.fixture(autouse=True)
def _clean_store_and_fake() -> None:
    reset_session_store()
    clear_fake_telegram_outbound()
    yield
    reset_session_store()
    clear_fake_telegram_outbound()


@pytest.fixture(autouse=True)
def _pd_consent_for_dev_employee() -> None:
    """Phase 3 adapter uses PSYCH_TESTING_DEV_* — принимаем ПДн, чтобы не ломать старые тесты."""
    from app.db import SessionLocal
    from app.services.employee_consent import record_pd_consent_yes
    from tests.conftest import ensure_employee_consent_schema

    ensure_employee_consent_schema()
    client_id = (os.getenv("PSYCH_TESTING_DEV_CLIENT_ID") or "dev-client").strip()
    employee_id = (os.getenv("PSYCH_TESTING_DEV_EMPLOYEE_ID") or "dev-employee").strip()
    with SessionLocal() as db:
        record_pd_consent_yes(db, client_id, employee_id)
        db.commit()


@pytest.fixture
def fake_outbound() -> FakeTelegramOutbound:
    return FakeTelegramOutbound()


@pytest.fixture
def adapter(fake_outbound: FakeTelegramOutbound) -> PsychTestingTelegramAdapter:
    os.environ["PSYCH_TESTING_MBTI_QUESTIONS_PER_AXIS"] = "1"
    pipeline = VoicePipeline(MockSttProvider())
    return PsychTestingTelegramAdapter(
        token="1234567890:FAKE_TOKEN_FOR_TESTS",
        outbound=fake_outbound,
        voice_pipeline=pipeline,
    )


def _mbti_one_per_axis():
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


class TestCallbackKeyboard:
    def test_parse_roundtrip(self) -> None:
        cb = build_callback_data("sid-1", "q1", "A")
        assert parse_callback_data(cb) == ("sid-1", "q1", "A")

    def test_menu_callback_roundtrip(self) -> None:
        cb = build_menu_callback_data("mbti_dialog")
        assert parse_menu_callback(cb) == "mbti_dialog"
        assert parse_callback_data(cb) is None

    def test_step_menu_callback_roundtrip(self) -> None:
        cb = build_step_menu_callback_data("soft_skills_2")
        assert parse_menu_callback(cb) == "step:soft_skills_2"
        assert parse_menu_step_action("step:soft_skills_2") == ("soft_skills_2", False)
        dialog_cb = build_step_menu_callback_data("mbti_1", dialog=True)
        assert parse_menu_step_action(parse_menu_callback(dialog_cb) or "") == (
            "mbti_1",
            True,
        )

    def test_welcome_menu_assignment_steps(self) -> None:
        kb = welcome_menu_keyboard(
            allowed_steps=[
                {"step_key": "soft_skills_1", "test_id": "soft_skills", "label_ru": "Soft Skills (1)"},
                {"step_key": "soft_skills_2", "test_id": "soft_skills", "label_ru": "Soft Skills (2)"},
            ]
        )
        callbacks = [
            btn["callback_data"]
            for row in kb["inline_keyboard"]
            for btn in row
        ]
        assert "pt:menu:step:soft_skills_1" in callbacks
        assert "pt:menu:step:soft_skills_2" in callbacks
        labels = [btn["text"] for row in kb["inline_keyboard"] for btn in row]
        assert "Soft Skills (1)" in labels
        assert "Soft Skills (2)" in labels

    def test_welcome_menu_has_test_buttons(self) -> None:
        kb = welcome_menu_keyboard()
        labels = [
            btn["text"]
            for row in kb["inline_keyboard"]
            for btn in row
        ]
        assert "MBTI" in labels
        assert "PAEI" in labels
        assert "Отменить текущий тест" not in labels
        assert "Справка" not in labels

    def test_welcome_menu_single_assignment_proiti(self) -> None:
        kb = welcome_menu_keyboard(allowed_test_ids=frozenset({"paei"}))
        labels = [btn["text"] for row in kb["inline_keyboard"] for btn in row]
        assert labels == ["Пройти"]
        assert kb["inline_keyboard"][0][0]["callback_data"] == "pt:menu:paei"

    def test_mbti_keyboard_two_buttons(self) -> None:
        engine = SessionEngine.start(
            _mbti_one_per_axis(),
            client_id="c",
            employee_id="e",
        )
        item = engine.current_item()
        assert item is not None
        kb = keyboard_for_item(engine.definition, engine.session.session_id, item)
        assert kb is not None
        row = kb["inline_keyboard"][0]
        assert len(row) == 2
        assert row[0]["text"] == "A"


class TestTelegramAdapterMock:
    def test_start_without_arg_shows_welcome_not_session(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.handle_text("1001", "/start", is_command=True)
        assert adapter._store.get_engine("1001") is None
        assert len(fake_outbound.messages) == 1
        msg = fake_outbound.messages[0]
        assert "Психологическое тестирование" in msg["text"]
        assert "Выберите тест" in msg["text"]
        assert msg["reply_markup"] is not None
        assert msg["reply_markup"]["inline_keyboard"]

    def test_menu_button_starts_mbti(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.handle_callback("1001", "q1", build_menu_callback_data("mbti"))
        engine = adapter._store.get_engine("1001")
        assert engine is not None
        assert engine.session.test_id == "mbti"
        assert len(fake_outbound.messages) >= 2

    def test_menu_step_button_sets_active_step_key(
        self,
        adapter: PsychTestingTelegramAdapter,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            adapter,
            "_assignment_gate",
            lambda *_a, **_k: (True, None, SimpleNamespace(id="asgn-phase3-mbti")),
        )
        monkeypatch.setattr(
            adapter,
            "_assignment_menu_context",
            lambda _chat_id: {
                "allowed_steps": [
                    {"step_key": "mbti_1", "test_id": "mbti", "label_ru": "MBTI"},
                ],
                "all_steps": [
                    {"step_key": "mbti_1", "test_id": "mbti", "label_ru": "MBTI"},
                ],
            },
        )
        adapter.handle_callback("1001", "q1", build_step_menu_callback_data("mbti_1"))
        binding = adapter._store.get_binding("1001")
        assert binding is not None
        assert binding.active_step_key == "mbti_1"
        assert binding.active_test_id == "mbti"
        assert binding.active_assignment_id == "asgn-phase3-mbti"

    def test_menu_help_shows_text_not_menu(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.handle_callback("1001", "q1", build_menu_callback_data("help"))
        assert len(fake_outbound.messages) == 1
        assert fake_outbound.messages[0]["reply_markup"] is None
        assert "Психологическое тестирование" in fake_outbound.messages[0]["text"]

    def test_start_while_active_session_blocked(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.start_test("1001", "paei")
        engine = adapter._store.get_engine("1001")
        assert engine is not None
        assert engine.session.test_id == "paei"
        n_before = len(fake_outbound.messages)
        adapter.handle_text("1001", "/start soft_skills", is_command=True)
        assert adapter._store.get_engine("1001") is engine
        assert engine.session.test_id == "paei"
        new_msgs = fake_outbound.messages[n_before:]
        assert len(new_msgs) == 1
        assert "уже идёт" in new_msgs[0]["text"].lower()
        assert "/cancel" in new_msgs[0]["text"]

    def test_start_sends_intro_and_question_with_buttons(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.start_test("1001", "mbti")
        assert len(fake_outbound.messages) >= 2
        intro = fake_outbound.messages[0]
        question = fake_outbound.messages[1]
        assert intro["chat_id"] == "1001"
        assert "MBTI" in intro["text"]
        assert "48" in intro["text"] or "4" in intro["text"]
        assert "A)" in question["text"]
        assert "/cancel" in question["text"]
        assert question["reply_markup"] is not None

    def test_voice_in_mock_stt_shows_hint_not_reprompt(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        import os

        os.environ["PSYCH_TESTING_STT_PROVIDER"] = "mock"
        adapter.start_test("1001", "mbti")
        adapter.handle_voice("1001", b"\x00\x01\x02")
        texts = [m["text"] for m in fake_outbound.messages]
        assert any("в разработке" in t for t in texts)
        assert not any("Не удалось распознать ответ" in t for t in texts)

    def test_full_mbti_via_buttons(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.start_test("1001", "mbti")
        engine = adapter._store.get_engine("1001")
        assert engine is not None

        while engine.session.status not in (SessionStatus.DONE, SessionStatus.CANCELLED):
            item = engine.current_item()
            if item is None:
                break
            choice = "A" if item.option_a_pole in ("I", "N", "T", "J") else "B"
            cb = build_callback_data(engine.session.session_id, item.id, choice)
            adapter.handle_callback("1001", "cq1", cb)
            if engine.session.status == SessionStatus.DONE:
                break

        assert engine.session.status == SessionStatus.DONE
        texts = [m["text"] for m in fake_outbound.messages]
        assert any("INTJ" in t or "Ваш тип" in t for t in texts)

    def test_ambiguous_text_reprompts(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.start_test("1001", "mbti")
        before = len(fake_outbound.messages)
        adapter.handle_text("1001", "не знаю")
        assert len(fake_outbound.messages) > before
        assert "Не удалось распознать" in fake_outbound.messages[-1]["text"]

    def test_cancel_clears_session(
        self, adapter: PsychTestingTelegramAdapter, fake_outbound: FakeTelegramOutbound
    ) -> None:
        adapter.start_test("1001", "mbti")
        adapter.cancel_session("1001")
        assert adapter._store.get_engine("1001") is None

    def test_voice_with_pipeline_mock_advances_session(
        self, fake_outbound: FakeTelegramOutbound
    ) -> None:
        """Adapter STT gate is mock-only; injected MockSttProvider skips real Whisper."""
        os.environ["PSYCH_TESTING_STT_PROVIDER"] = "openai"
        os.environ["PSYCH_TESTING_OPENAI_API_KEY"] = "test-key"
        pipeline = VoicePipeline(MockSttProvider())
        adapter = PsychTestingTelegramAdapter(
            token="1234567890:FAKE_TOKEN_FOR_TESTS",
            outbound=fake_outbound,
            voice_pipeline=pipeline,
        )
        adapter.start_test("1001", "mbti")
        engine = adapter._store.get_engine("1001")
        assert engine is not None

        for _ in range(4):
            item = engine.current_item()
            assert item is not None
            choice = "A" if item.option_a_pole in ("I", "N", "T", "J") else "B"
            audio = f"вариант {choice.lower()}".encode("utf-8")
            adapter.handle_voice("1001", audio)

        assert engine.session.status == SessionStatus.DONE


def _full_adapter() -> tuple[PsychTestingTelegramAdapter, FakeTelegramOutbound]:
    """Adapter без dev-сокращения MBTI (16 вопросов, 4 на ось)."""
    os.environ.pop("PSYCH_TESTING_MBTI_QUESTIONS_PER_AXIS", None)
    pipeline = VoicePipeline(MockSttProvider())
    outbound = FakeTelegramOutbound()
    adapter = PsychTestingTelegramAdapter(
        token="1234567890:FAKE_TOKEN_FOR_TESTS",
        outbound=outbound,
        voice_pipeline=pipeline,
    )
    return adapter, outbound


def _complete_via_buttons(
    adapter: PsychTestingTelegramAdapter,
    chat_id: str,
    test_id: str,
    answer_fn,
) -> None:
    adapter.start_test(chat_id, test_id)
    engine = adapter._store.get_engine(chat_id)
    assert engine is not None
    steps = 0
    while engine.session.status not in (SessionStatus.DONE, SessionStatus.CANCELLED):
        item = engine.current_item()
        assert item is not None, f"no item at step {steps}, status={engine.session.status}"
        val = answer_fn(item, steps)
        cb = build_callback_data(engine.session.session_id, item.id, val)
        adapter.handle_callback(chat_id, f"cq{steps}", cb)
        steps += 1
        assert steps <= 20, "session did not finish in reasonable steps"
    assert engine.session.status == SessionStatus.DONE


class TestTelegramAdapterE2EFull:
    def test_full_mbti_16_via_buttons(self) -> None:
        adapter, outbound = _full_adapter()
        _complete_via_buttons(
            adapter,
            "2001",
            "mbti",
            lambda item, _s: "A" if item.option_a_pole in ("I", "N", "T", "J") else "B",
        )
        engine = adapter._store.get_engine("2001")
        assert engine is None  # cleared after report
        texts = [m["text"] for m in outbound.messages]
        assert any("Ваш тип" in t for t in texts)
        assert any("INTJ" in t for t in texts)
        intro = outbound.messages[0]["text"]
        assert "Вопросов в сессии: 16" in intro

    def test_full_paei_via_buttons(self) -> None:
        adapter, outbound = _full_adapter()
        choices = ("P", "P", "A", "E", "I")
        _complete_via_buttons(
            adapter,
            "2002",
            "paei",
            lambda _item, s: choices[s],
        )
        texts = [m["text"] for m in outbound.messages]
        assert any("=== РЕЗУЛЬТАТ PAEI" in t for t in texts)
        assert any("40%" in t for t in texts)

    def test_full_soft_skills_via_buttons(self) -> None:
        adapter, outbound = _full_adapter()
        _complete_via_buttons(
            adapter,
            "2003",
            "soft_skills",
            lambda _item, s: str((s % 5) + 1),
        )
        texts = [m["text"] for m in outbound.messages]
        assert any("=== РЕЗУЛЬТАТ SOFT SKILLS" in t for t in texts)
        assert any("/5" in t for t in texts)
        intro = outbound.messages[0]["text"]
        assert "10" in intro

    def test_paei_text_answer_completes(self) -> None:
        adapter, _outbound = _full_adapter()
        adapter.start_test("2004", "paei")
        engine = adapter._store.get_engine("2004")
        assert engine is not None
        for text in ("п", "a", "e", "i", "p"):
            adapter.handle_text("2004", text)
        assert engine.session.status == SessionStatus.DONE

    def test_soft_skills_keyboard_one_row(self) -> None:
        soft = PluginRegistry().get("soft_skills")
        engine = SessionEngine.start(soft, client_id="c", employee_id="e")
        item = engine.current_item()
        assert item is not None
        kb = keyboard_for_item(soft, engine.session.session_id, item)
        assert kb is not None
        rows = kb["inline_keyboard"]
        assert len(rows) == 1
        assert [b["text"] for b in rows[0]] == ["1", "2", "3", "4", "5"]

    def test_full_disc_via_buttons(self) -> None:
        adapter, outbound = _full_adapter()
        _complete_via_buttons(
            adapter,
            "2005",
            "disc",
            lambda _item, s: str((s % 5) + 1),
        )
        texts = [m["text"] for m in outbound.messages]
        assert any("=== РЕЗУЛЬТАТ DISC" in t for t in texts)

    def test_full_hexaco_via_buttons(self) -> None:
        adapter, outbound = _full_adapter()
        _complete_via_buttons(
            adapter,
            "2006",
            "hexaco",
            lambda _item, s: str((s % 5) + 1),
        )
        engine = adapter._store.get_engine("2006")
        assert engine is None
        texts = [m["text"] for m in outbound.messages]
        assert any("=== РЕЗУЛЬТАТ HEXACO" in t for t in texts)
        intro = outbound.messages[0]["text"]
        assert "6" in intro
