"""MBTI dialog — voice input path (STT → free text → LLM)."""

from __future__ import annotations

import os

import pytest

from psychological_testing.adapters.telegram_outbound import (
    FakeTelegramOutbound,
    clear_fake_telegram_outbound,
)
from psychological_testing.domain.entities import SessionStatus
from psychological_testing.domain.mbti_delivery import DIALOG_VOICE_HINT_RU, dialog_accepts_text
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.integration.session_store import reset_session_store
from psychological_testing.integration.telegram_adapter import PsychTestingTelegramAdapter
from psychological_testing.services.llm_service import MockLlmClient
from psychological_testing.research.mbti.scripts.akma_dialog_engine import AkmaDialogEngine
from psychological_testing.shared_engine.voice_pipeline import MockSttProvider, VoicePipeline


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_session_store()
    clear_fake_telegram_outbound()
    for key in (
        "PSYCH_TESTING_STT_PROVIDER",
        "PSYCH_TESTING_OPENAI_API_KEY",
        "PSYCH_TESTING_MBTI_DIALOG_ALLOW_TEXT",
        "PSYCH_TESTING_MBTI_DIALOG_VOICE_PRIMARY",
    ):
        os.environ.pop(key, None)
    yield
    reset_session_store()
    clear_fake_telegram_outbound()


def test_dialog_voice_advances_with_injected_stt() -> None:
    """Same pattern as structured MBTI phase3: env openai + MockSttProvider."""
    os.environ["PSYCH_TESTING_STT_PROVIDER"] = "openai"
    os.environ["PSYCH_TESTING_OPENAI_API_KEY"] = "test-key"
    llm = MockLlmClient(
        akma_replies=["Вопрос 2.", "Вопрос 3."],
        eval_choices=["E", "S", "T"],
        report_text="Report.",
    )
    pipeline = VoicePipeline(MockSttProvider())
    outbound = FakeTelegramOutbound()
    adapter = PsychTestingTelegramAdapter(
        token="fake",
        outbound=outbound,
        registry=TestRegistry(),
        voice_pipeline=pipeline,
    )
    definition = TestRegistry().get("mbti")
    engine = AkmaDialogEngine.start(
        definition,
        client_id="c",
        employee_id="e",
        llm=llm,
        voice_pipeline=pipeline,
    )
    engine.akma_state.max_questions = 2
    adapter._store.set_engine("1", engine)
    engine.current_question_message()

    for phrase in (
        "Я руковожу отделом.",
        "Люблю общаться с людьми.",
        "Опираюсь на цифры.",
    ):
        adapter.handle_voice("1", phrase.encode("utf-8"))

    assert engine.session.status == SessionStatus.DONE
    texts = [m["text"] for m in outbound.messages]
    assert any("Распознано" in t for t in texts)


def test_dialog_blocks_text_when_voice_primary_and_stt_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PSYCH_TESTING_STT_PROVIDER", "openai")
    monkeypatch.setenv("PSYCH_TESTING_OPENAI_API_KEY", "k")
    monkeypatch.setenv("PSYCH_TESTING_MBTI_DIALOG_VOICE_PRIMARY", "1")
    assert dialog_accepts_text() is False

    outbound = FakeTelegramOutbound()
    adapter = PsychTestingTelegramAdapter(token="fake", outbound=outbound, registry=TestRegistry())
    adapter.start_test("1", "mbti", delivery_mode="dialog")
    adapter.handle_text("1", "текстовый ответ")
    assert "Текстовые ответы в dialog-режиме отключены" in outbound.messages[-1]["text"]


def test_dialog_allows_text_when_stt_mock() -> None:
    os.environ["PSYCH_TESTING_STT_PROVIDER"] = "mock"
    assert dialog_accepts_text() is True


def test_dialog_akma_text_question_separate_from_voice_ack() -> None:
    os.environ["PSYCH_TESTING_STT_PROVIDER"] = "openai"
    os.environ["PSYCH_TESTING_OPENAI_API_KEY"] = "test-key"
    llm = MockLlmClient(
        akma_replies=["Расскажите, как вы принимаете решения в команде?"],
        eval_choices=["I"],
        report_text="Report.",
    )
    pipeline = VoicePipeline(MockSttProvider())
    outbound = FakeTelegramOutbound()
    adapter = PsychTestingTelegramAdapter(
        token="fake",
        outbound=outbound,
        registry=TestRegistry(),
        voice_pipeline=pipeline,
    )
    definition = TestRegistry().get("mbti")
    engine = AkmaDialogEngine.start(
        definition, client_id="c", employee_id="e", llm=llm, voice_pipeline=pipeline
    )
    engine.akma_state.max_questions = 4
    adapter._store.set_engine("1", engine)
    engine.current_question_message()

    adapter.handle_voice("1", "Я руковожу отделом продаж.".encode("utf-8"))

    texts = [m["text"] for m in outbound.messages]
    assert any("Распознано" in t for t in texts)
    assert any("решения" in t for t in texts)
    assert any(DIALOG_VOICE_HINT_RU in t for t in texts)
    # Ack and Akma question are separate Telegram messages
    ack_idx = next(i for i, t in enumerate(texts) if "Распознано" in t)
    q_idx = next(i for i, t in enumerate(texts) if "решения" in t)
    assert ack_idx != q_idx


def test_dialog_start_first_question_is_text_with_voice_hint() -> None:
    outbound = FakeTelegramOutbound()
    adapter = PsychTestingTelegramAdapter(token="fake", outbound=outbound, registry=TestRegistry())
    adapter.start_test("1", "mbti", delivery_mode="dialog")
    question_msgs = [m for m in outbound.messages if "нейро-психолог" in m["text"]]
    assert len(question_msgs) == 1
    assert DIALOG_VOICE_HINT_RU in question_msgs[0]["text"]
    assert question_msgs[0]["reply_markup"] is None
