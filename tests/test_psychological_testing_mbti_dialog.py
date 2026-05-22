"""MBTI Akma dialog — delivery mode switch and state machine."""

from __future__ import annotations

import os

import pytest

from psychological_testing.adapters.telegram_outbound import (
    FakeTelegramOutbound,
    clear_fake_telegram_outbound,
)
from psychological_testing.domain.mbti_delivery import (
    mbti_delivery_mode_from_env,
    participant_greeting_name,
    resolve_mbti_start_arg,
)
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.integration.session_store import reset_session_store
from psychological_testing.integration.telegram_adapter import PsychTestingTelegramAdapter
from psychological_testing.research.mbti.scripts.akma_dialog import (
    UserProfile,
    begin_dialog,
    parse_eval_choice,
    process_user_message,
    type_code_from_counters,
)
from psychological_testing.research.mbti.scripts.akma_dialog_engine import AkmaDialogEngine
from psychological_testing.services.llm_service import MockLlmClient


@pytest.fixture(autouse=True)
def _pd_consent_for_dev_employee() -> None:
    from app.db import SessionLocal
    from app.services.employee_consent import record_pd_consent_yes
    from tests.conftest import ensure_employee_consent_schema

    ensure_employee_consent_schema()
    client_id = (os.getenv("PSYCH_TESTING_DEV_CLIENT_ID") or "dev-client").strip()
    employee_id = (os.getenv("PSYCH_TESTING_DEV_EMPLOYEE_ID") or "dev-employee").strip()
    with SessionLocal() as db:
        record_pd_consent_yes(db, client_id, employee_id)
        db.commit()


@pytest.fixture(autouse=True)
def _clean() -> None:
    reset_session_store()
    clear_fake_telegram_outbound()
    for key in (
        "PSYCH_TESTING_MBTI_DELIVERY_MODE",
        "PSYCH_TESTING_MBTI_DIALOG_MAX_QUESTIONS",
        "PSYCH_TESTING_AI_PROVIDER",
    ):
        os.environ.pop(key, None)
    yield
    reset_session_store()
    clear_fake_telegram_outbound()


def test_resolve_mbti_start_arg_explicit_modes() -> None:
    assert resolve_mbti_start_arg("mbti_structured") == ("mbti", "structured")
    assert resolve_mbti_start_arg("mbti_dialog") == ("mbti", "dialog")
    assert resolve_mbti_start_arg("mbti_akma") == ("mbti", "dialog")


def test_resolve_mbti_start_arg_env_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_MBTI_DELIVERY_MODE", "dialog")
    assert resolve_mbti_start_arg("mbti") == ("mbti", "dialog")
    monkeypatch.setenv("PSYCH_TESTING_MBTI_DELIVERY_MODE", "structured")
    assert resolve_mbti_start_arg("mbti") == ("mbti", "structured")


def test_mbti_delivery_mode_from_env_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PSYCH_TESTING_MBTI_DELIVERY_MODE", "unknown")
    assert mbti_delivery_mode_from_env() == "structured"


def test_parse_eval_choice() -> None:
    assert parse_eval_choice('{"choice": "E"}', "EI") == "E"
    assert parse_eval_choice('{"choice": "x"}', "EI") == "x"


def test_type_code_from_counters() -> None:
    assert type_code_from_counters({"EI": -1, "SN": -1, "TF": 1, "JP": 1}) == "INTJ"


def test_dialog_zero_then_eval_with_mock_llm() -> None:
    llm = MockLlmClient(
        akma_replies=["Расскажите, как вы принимаете решения в команде?"],
        eval_choices=["I"],
        report_text="Отчёт mock.",
    )
    state, zero = begin_dialog(UserProfile(name="Анна"), max_questions=4)
    assert "Анна" in zero

    r1 = process_user_message(
        state,
        "Я руковожу отделом продаж.",
        llm_chat=llm.chat,
        model_akma="mock",
        model_eval="mock",
        model_report="mock",
    )
    assert r1.assistant_message == "Расскажите, как вы принимаете решения в команде?"
    assert r1.state.phase == "questioning"

    r2 = process_user_message(
        r1.state,
        "Сначала собираю мнения, потом решаю сам.",
        llm_chat=llm.chat,
        model_akma="mock",
        model_eval="mock",
        model_report="mock",
    )
    assert r2.eval_note and "I" in r2.eval_note
    assert r2.state.counters["EI"] == -1


def test_participant_greeting_name_skips_dev_placeholder() -> None:
    assert participant_greeting_name("dev-employee") is None
    assert participant_greeting_name("dev-employee", hr_display_name="Сергей") == "Сергей"
    assert participant_greeting_name("emp-42", hr_display_name="Анна") == "Анна"


def test_begin_dialog_greeting_without_dev_name() -> None:
    _, zero_q = begin_dialog(UserProfile(name="Участник"), max_questions=4)
    assert zero_q.startswith("Здравствуйте!")
    assert "dev-employee" not in zero_q
    assert ", Участник" not in zero_q


def test_resolve_mbti_start_arg_strips_bot_suffix() -> None:
    assert resolve_mbti_start_arg("mbti_dialog@orgskilldevbot") == ("mbti", "dialog")
    assert resolve_mbti_start_arg("mbti_structured@bot") == ("mbti", "structured")


def test_telegram_start_mbti_dialog() -> None:
    os.environ["PSYCH_TESTING_MBTI_DIALOG_MAX_QUESTIONS"] = "4"
    os.environ["PSYCH_TESTING_AI_PROVIDER"] = "mock"
    outbound = FakeTelegramOutbound()
    adapter = PsychTestingTelegramAdapter(token="fake", outbound=outbound, registry=TestRegistry())
    adapter.start_test("42", "mbti", delivery_mode="dialog")
    assert len(outbound.messages) == 1
    question = outbound.messages[0]["text"]
    assert "нейро-психолог" in question
    assert "Здравствуйте, dev-employee" not in question
    assert "Шагов в сессии" not in question
    assert "LLM:" not in question
    assert "/cancel" in question
    assert "голосовым" in question
    assert "Ось:" not in question
    assert "[1/" not in question


def test_handle_start_mbti_dialog_command_with_bot_suffix() -> None:
    outbound = FakeTelegramOutbound()
    adapter = PsychTestingTelegramAdapter(token="fake", outbound=outbound, registry=TestRegistry())
    adapter.handle_text("99", "/start mbti_dialog@testbot", is_command=True)
    engine = adapter._store.get_engine("99")
    assert engine is not None
    from psychological_testing.research.mbti.scripts.akma_dialog_engine import AkmaDialogEngine

    assert isinstance(engine, AkmaDialogEngine)
    assert "структурированный" not in outbound.messages[0]["text"]


def test_akma_dialog_engine_finishes_with_report() -> None:
    llm = MockLlmClient(
        akma_replies=["Вопрос 2.", "Вопрос 3."],
        eval_choices=["E", "S", "T"],
        report_text="Сильные стороны: mock.",
    )
    definition = TestRegistry().get("mbti")
    engine = AkmaDialogEngine.start(
        definition,
        client_id="c",
        employee_id="e",
        llm=llm,
    )
    engine.akma_state.max_questions = 3
    engine.current_question_message()
    engine.submit_text("Работаю инженером.")
    engine.submit_text("Люблю общаться с командой.")
    engine.submit_text("Опираюсь на факты.")
    t = engine.submit_text("Планирую заранее.")
    assert t.report_text
    assert "MBTI" in t.report_text
    assert engine.akma_state.type_code
