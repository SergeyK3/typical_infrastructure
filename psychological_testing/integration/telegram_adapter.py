"""
Telegram tri-mode handler: inline buttons, text, voice → ``SessionEngine`` or ``AkmaDialogEngine``.

Commands:
  /start [mbti|mbti_dialog|mbti_structured|paei|...] — начать сессию
  /cancel — отменить активную сессию
  /help — краткая справка
"""

from __future__ import annotations

import logging
import os
from dataclasses import replace

from psychological_testing.adapters.telegram_keyboards import (
    keyboard_for_item,
    parse_callback_data,
)
from psychological_testing.adapters.telegram_outbound import (
    FakeTelegramOutbound,
    HttpxTelegramOutbound,
    get_telegram_outbound,
)
from psychological_testing.domain.entities import SessionStatus
from psychological_testing.domain.mbti_delivery import (
    DIALOG_VOICE_HINT_RU,
    DIALOG_VOICE_STT_SETUP,
    MbtiDeliveryMode,
    dialog_accepts_text,
    mbti_delivery_mode_from_env,
    resolve_mbti_start_arg,
)
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.integration.hr_core import (
    employee_display_label,
    resolve_employee_by_telegram,
)
from psychological_testing.integration.session_persistence import (
    build_session_result_document,
    persist_session_result,
)
from psychological_testing.integration.session_store import (
    PsychTestingSessionStore,
    get_session_store,
)
from psychological_testing.research.mbti.scripts.akma_dialog_engine import AkmaDialogEngine
from psychological_testing.shared_engine.session_state_machine import (
    SessionEngine,
    SessionTransition,
)
from psychological_testing.services.stt_service import stt_provider
from psychological_testing.shared_engine.voice_pipeline import VoicePipeline

_log = logging.getLogger(__name__)

_SUPPORTED_TESTS = frozenset({"mbti", "paei", "soft_skills", "disc", "hexaco"})
_VOICE_DEV_NOTE = "🎤 Голосовые ответы — в разработке."

_MBTI_START_ALIASES = frozenset(
    {"mbti", "mbti_structured", "mbti-structured", "mbti_dialog", "mbti-dialog", "mbti_akma", "mbti-akma"}
)


def _welcome_text() -> str:
    voice_note = "" if _voice_enabled() else f"\n{_VOICE_DEV_NOTE}"
    default_mbti = mbti_delivery_mode_from_env()
    mbti_hint = (
        "• /start mbti — MBTI (режим из .env: "
        f"{default_mbti}; сейчас PSYCH_TESTING_MBTI_DELIVERY_MODE)\n"
        "• /start mbti_structured — MBTI, кнопки A/B\n"
        "• /start mbti_dialog — MBTI, диалог с Акма (LLM)\n"
    )
    return (
        "Психологическое тестирование (HR OS).\n\n"
        "Команды:\n"
        f"{mbti_hint}"
        "• /start paei — PAEI\n"
        "• /start soft_skills — Soft Skills\n"
        "• /start disc — DISC\n"
        "• /start hexaco — HEXACO\n"
        "• /cancel — отменить текущий тест\n"
        "• /help — эта справка\n\n"
        "/start без названия теста — показать это меню.\n"
        f"Structured-тесты: кнопка или текст.{voice_note}"
    )

_VOICE_MOCK_HINT = f"{_VOICE_DEV_NOTE}\nИспользуйте кнопки или текст."


def _voice_enabled() -> bool:
    return stt_provider() != "mock"


def _answer_channels_note(*, for_likert: bool = False) -> str:
    if for_likert:
        return "Ответ: кнопка с цифрой 1–5 или текст («три», «4»)."
    return "Ответ: кнопка или текст."


_CANCEL_FOOTER = "Отмена: /cancel"


def _intro_footer(*, cancel: bool = True, cancel_text: str = _CANCEL_FOOTER) -> str:
    if cancel:
        return cancel_text
    return ""


def _with_cancel_footer(text: str) -> str:
    if "/cancel" in text.lower():
        return text
    return f"{text.rstrip()}\n\n{_CANCEL_FOOTER}"


def _session_lost_message(store: PsychTestingSessionStore, chat_id: str) -> str:
    binding = store.get_binding(chat_id)
    test_id = (binding.active_test_id if binding else None) or "soft_skills"
    restart = f"/start {test_id}"
    if binding and binding.active_test_id == "mbti" and binding.mbti_delivery_mode == "dialog":
        restart = "/start mbti_dialog"
    return (
        "Сессия прервана: бот перезапускался или одновременно работает "
        "несколько процессов telegram_worker (Telegram 409).\n\n"
        f"Начните тест заново: {restart}\n"
        "Перед запуском worker должен быть только один."
    )


def _stale_button_message(store: PsychTestingSessionStore, chat_id: str) -> str:
    binding = store.get_binding(chat_id)
    if binding and binding.active_test_id == "mbti" and binding.mbti_delivery_mode == "dialog":
        return "Устаревшая кнопка. Начните заново: /start mbti_dialog"
    test_id = (binding.active_test_id if binding else None) or "mbti"
    return f"Устаревшая кнопка. Начните тест заново: /start {test_id}"


def _likert_intro_block(*, scales_note: str) -> str:
    return (
        "Каждый пункт — утверждение; оцените согласие (шкала 1–5).\n\n"
        f"{scales_note}\n"
        "1 — совсем не согласен … 5 — полностью согласен\n"
        "Под каждым вопросом — расшифровка всех пяти баллов.\n"
        "На кнопках — цифры 1–5 (смотрите пояснения в тексте выше).\n\n"
        f"{_answer_channels_note(for_likert=True)}\n"
        f"{_intro_footer()}"
    )


def _is_dialog_engine(engine: object) -> bool:
    return isinstance(engine, AkmaDialogEngine)


_TEST_DISPLAY_NAMES: dict[str, str] = {
    "mbti": "MBTI",
    "paei": "PAEI",
    "soft_skills": "Soft Skills",
    "disc": "DISC",
    "hexaco": "HEXACO",
}


def _session_is_active(engine: SessionEngine | AkmaDialogEngine) -> bool:
    if _is_dialog_engine(engine):
        return engine.akma_state.is_active
    return engine.session.status in (SessionStatus.QUESTIONING, SessionStatus.REPROMPT)


def _active_test_label(
    engine: SessionEngine | AkmaDialogEngine,
    store: PsychTestingSessionStore,
    chat_id: str,
) -> str:
    binding = store.get_binding(chat_id)
    if binding and binding.active_test_id == "mbti" and binding.mbti_delivery_mode == "dialog":
        return "MBTI (диалог с Акма)"
    test_id = engine.session.test_id
    return _TEST_DISPLAY_NAMES.get(test_id, test_id)


def _format_akma_question(question: str) -> str:
    """Akma → user: question + voice hint + отмена."""
    text = question
    if DIALOG_VOICE_HINT_RU not in text:
        text = f"{text}\n\n{DIALOG_VOICE_HINT_RU}"
    return _with_cancel_footer(text)


def _session_intro(
    test_id: str,
    *,
    question_count: int,
    questions_per_axis: int,
    delivery_mode: MbtiDeliveryMode = "structured",
) -> str:
    if test_id == "mbti" and delivery_mode == "dialog":
        return ""
    if test_id == "mbti":
        if questions_per_axis <= 1:
            length_note = (
                "Короткий dev-режим: 1 вопрос на ось (всего 4). "
                "Полная сессия — 16 вопросов (4 на ось); в банке 48 формулировок."
            )
        else:
            length_note = (
                f"В этой сессии {question_count} вопросов "
                f"({questions_per_axis} на ось E/I, S/N, T/F, J/P). "
                "В банке 48 формулировок."
            )
        return (
            "Добро пожаловать в MBTI (структурированный опрос, HR OS).\n\n"
            "Что делать:\n"
            "1. На каждый вопрос выберите вариант A или B.\n"
            "2. После всех ответов придёт тип личности и краткий портрет.\n\n"
            f"{length_note}\n\n"
            f"{_answer_channels_note()}\n"
            f"{_intro_footer(cancel_text='Отмена в любой момент: /cancel')}"
        )
    if test_id == "paei":
        return (
            "Добро пожаловать в опрос PAEI (Адизес).\n\n"
            f"Вопросов в сессии: {question_count}.\n"
            f"{_answer_channels_note()}\n\n"
            f"{_intro_footer()}"
        )
    if test_id == "soft_skills":
        return (
            "Добро пожаловать в опрос Soft Skills.\n\n"
            f"Вопросов в сессии: {question_count}.\n"
            + _likert_intro_block(scales_note="10 навыков soft skills, по одному утверждению на навык.")
        )
    if test_id == "disc":
        return (
            "Добро пожаловать в опрос DISC.\n\n"
            f"Вопросов в сессии: {question_count}.\n"
            + _likert_intro_block(
                scales_note="Шкалы: D (Доминирование), I (Влияние), S (Стабильность), C (Согласованность)."
            )
        )
    if test_id == "hexaco":
        return (
            "Добро пожаловать в опрос HEXACO.\n\n"
            f"Вопросов в сессии: {question_count}.\n"
            "Оцените согласие с каждым утверждением (шкала 1–5).\n"
            "После последнего ответа — итоговый отчёт.\n"
            + _likert_intro_block(
                scales_note="6 утверждений о поведении и реакциях."
            )
        )
    return f"Тест «{test_id}»: {question_count} вопросов. Отмена: /cancel"


class PsychTestingTelegramAdapter:
    def __init__(
        self,
        *,
        token: str,
        registry: TestRegistry | None = None,
        store: PsychTestingSessionStore | None = None,
        outbound: FakeTelegramOutbound | HttpxTelegramOutbound | None = None,
        voice_pipeline: VoicePipeline | None = None,
    ) -> None:
        self._token = token
        self._registry = registry or TestRegistry()
        self._store = store or get_session_store()
        self._outbound = outbound or get_telegram_outbound()
        self._voice_pipeline = voice_pipeline or VoicePipeline()

    def _dev_ids(self) -> tuple[str, str]:
        client_id = (os.getenv("PSYCH_TESTING_DEV_CLIENT_ID") or "dev-client").strip()
        employee_id = (os.getenv("PSYCH_TESTING_DEV_EMPLOYEE_ID") or "dev-employee").strip()
        return client_id, employee_id

    def _resolve_participant(self, chat_id: str) -> tuple[str, str, str | None]:
        """``(client_id, employee_id, display_name)`` via HR или dev fallback."""
        default_client, default_employee = self._dev_ids()
        try:
            from app.db import SessionLocal

            db = SessionLocal()
            try:
                snap = resolve_employee_by_telegram(
                    db,
                    chat_id,
                    default_client_id=default_client,
                    default_employee_id=default_employee,
                )
                return snap.client_id, snap.id, employee_display_label(snap)
            finally:
                db.close()
        except Exception:
            _log.debug("psych_testing: HR resolve unavailable, using dev ids", exc_info=True)
        return default_client, default_employee, None

    def _send(
        self,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
    ) -> None:
        result = self._outbound.send_message(
            token=self._token,
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
        )
        if not result.ok:
            _log.warning("send_message failed chat=%s: %s", chat_id, result.description)

    def _send_akma_question(self, chat_id: str, question: str) -> None:
        self._send(chat_id, _format_akma_question(question))

    def _apply_dialog_transition(self, chat_id: str, transition: SessionTransition) -> None:
        if transition.user_ack:
            self._send(chat_id, transition.user_ack)
        if transition.reprompt_message:
            self._send(chat_id, transition.reprompt_message)
        if transition.akma_question:
            self._send_akma_question(chat_id, transition.akma_question)

    def _answer_callback(self, query_id: str, text: str | None = None) -> None:
        self._outbound.answer_callback_query(
            token=self._token,
            callback_query_id=query_id,
            text=text,
        )

    def _definition_for_start(self, test_id: str):
        definition = self._registry.get(test_id)
        if test_id == "mbti":
            qpa = os.getenv("PSYCH_TESTING_MBTI_QUESTIONS_PER_AXIS", "").strip()
            if qpa.isdigit():
                definition = replace(
                    definition,
                    selection={**definition.selection, "questions_per_axis": int(qpa)},
                )
        return definition

    def start_test(
        self,
        chat_id: str,
        test_id: str,
        *,
        delivery_mode: MbtiDeliveryMode | None = None,
    ) -> None:
        if test_id not in _SUPPORTED_TESTS:
            self._send(
                chat_id,
                f"Тест {test_id!r} пока недоступен в Telegram. Доступны: {', '.join(sorted(_SUPPORTED_TESTS))}.",
            )
            return

        client_id, employee_id, _display_name = self._resolve_participant(chat_id)
        binding = self._store.ensure_binding(
            chat_id, client_id=client_id, employee_id=employee_id
        )
        existing = self._store.get_engine(chat_id)
        if existing is not None and _session_is_active(existing):
            label = _active_test_label(existing, self._store, chat_id)
            self._send(
                chat_id,
                f"У вас уже идёт тест «{label}».\n\n"
                f"Отмена текущего теста: /cancel\n"
                f"Затем начните новый, например /start {test_id}.",
            )
            return

        binding.context = "psych_testing"
        binding.active_test_id = test_id
        binding.mbti_delivery_mode = None

        self._store.clear_engine(chat_id)

        try:
            definition = self._definition_for_start(test_id)
            mode: MbtiDeliveryMode = delivery_mode or str(
                definition.extra.get("delivery_mode") or "structured"
            )  # type: ignore[assignment]
            if mode not in ("structured", "dialog"):
                mode = "structured"
            if test_id == "mbti":
                binding.mbti_delivery_mode = mode
            _log.info("psych_testing start chat=%s test=%s mode=%s", chat_id, test_id, mode)

            if test_id == "mbti" and mode == "dialog":
                engine: SessionEngine | AkmaDialogEngine = AkmaDialogEngine.start(
                    definition,
                    client_id=client_id,
                    employee_id=employee_id,
                    voice_pipeline=self._voice_pipeline,
                )
                qpa = engine.akma_state.max_questions
                question_count = qpa
            else:
                engine = SessionEngine.start(
                    definition,
                    client_id=client_id,
                    employee_id=employee_id,
                    voice_pipeline=self._voice_pipeline,
                )
                qpa = int(definition.selection.get("questions_per_axis", 4))
                question_count = len(engine.session.items)
        except Exception as e:
            _log.exception("start_test failed")
            self._send(chat_id, f"Не удалось начать тест: {e}")
            return

        self._store.set_engine(chat_id, engine)
        dialog = _is_dialog_engine(engine)
        intro = _session_intro(
            test_id,
            question_count=question_count,
            questions_per_axis=qpa,
            delivery_mode=mode if test_id == "mbti" else "structured",
        )
        if intro:
            self._send(chat_id, intro)

        msg = engine.current_question_message(voice_hint=True if dialog else _voice_enabled())
        if msg is None:
            self._send(chat_id, "Нет вопросов для выбранного теста.")
            return
        item = engine.current_item()
        keyboard = None
        if item is not None:
            keyboard = keyboard_for_item(definition, engine.session.session_id, item)
        if dialog:
            self._send_akma_question(chat_id, msg)
        else:
            self._send(chat_id, _with_cancel_footer(msg), keyboard)

    def cancel_session(self, chat_id: str) -> None:
        engine = self._store.get_engine(chat_id)
        if engine is None:
            self._send(chat_id, "Нет активной сессии.")
            return
        engine.cancel()
        self._store.clear_engine(chat_id)
        binding = self._store.get_binding(chat_id)
        if binding:
            binding.context = "idle"
            binding.active_test_id = None
            binding.mbti_delivery_mode = None
        self._send(chat_id, "Сессия отменена.")

    def _apply_transition(self, chat_id: str, transition: SessionTransition) -> None:
        engine = self._store.get_engine(chat_id)
        if engine is None:
            return

        if transition.report_text:
            binding = self._store.get_binding(chat_id)
            delivery_mode = (
                binding.mbti_delivery_mode if binding and binding.mbti_delivery_mode else "structured"
            )
            _, _, display_name = self._resolve_participant(chat_id)
            try:
                doc = build_session_result_document(
                    engine,
                    telegram_chat_id=chat_id,
                    report_text=transition.report_text,
                    employee_display_name=display_name,
                    delivery_mode=delivery_mode,
                )
                persist_session_result(doc)
            except Exception:
                _log.exception("persist session result failed")
            self._store.clear_engine(chat_id)
            if binding:
                binding.context = "idle"
                binding.active_test_id = None
                binding.mbti_delivery_mode = None
            report = transition.report_text
            if transition.user_ack:
                report = f"{transition.user_ack}\n\n{report}"
            self._send(chat_id, report)
            return

        if _is_dialog_engine(engine):
            self._apply_dialog_transition(chat_id, transition)
            return

        if transition.reprompt_message:
            item = transition.current_item
            text = transition.reprompt_message
            if item is not None:
                q = engine.current_question_message(voice_hint=_voice_enabled())
                if q:
                    text = f"{transition.reprompt_message}\n\n{q}"
            keyboard = (
                keyboard_for_item(
                    engine.definition,
                    engine.session.session_id,
                    item,
                )
                if item is not None
                else None
            )
            self._send(chat_id, _with_cancel_footer(text), keyboard)
            return

        if transition.status == SessionStatus.CANCELLED:
            self._store.clear_engine(chat_id)
            self._send(chat_id, "Сессия завершена.")
            return

        if transition.current_item is not None:
            msg = engine.current_question_message(voice_hint=_voice_enabled())
            if msg:
                keyboard = keyboard_for_item(
                    engine.definition,
                    engine.session.session_id,
                    transition.current_item,
                )
                self._send(chat_id, _with_cancel_footer(msg), keyboard)

    def handle_text(self, chat_id: str, text: str, *, is_command: bool = False) -> None:
        stripped = text.strip()
        lower = stripped.lower()

        if is_command or lower.startswith("/"):
            parts = lower.split()
            cmd = parts[0].split("@")[0]
            if cmd in ("/start", "/test"):
                if len(parts) < 2:
                    self._send(chat_id, _welcome_text())
                    return
                arg = parts[1].split("@", 1)[0]
                test_id, delivery_mode = resolve_mbti_start_arg(arg)
                if test_id not in _SUPPORTED_TESTS:
                    _log.info("start arg %r unknown, defaulting to mbti", arg)
                    test_id, delivery_mode = "mbti", mbti_delivery_mode_from_env()
                self.start_test(
                    chat_id,
                    test_id,
                    delivery_mode=delivery_mode if test_id == "mbti" else None,
                )
                return
            if cmd == "/cancel":
                self.cancel_session(chat_id)
                return
            if cmd == "/help":
                self._send(chat_id, _welcome_text())
                return

        engine = self._store.get_engine(chat_id)
        if engine is None:
            self._send(chat_id, _welcome_text())
            return

        if _is_dialog_engine(engine) and not dialog_accepts_text():
            self._send(
                chat_id,
                f"{DIALOG_VOICE_HINT_RU}\n\nТекстовые ответы в dialog-режиме отключены.",
            )
            return

        transition = engine.submit_text(stripped)
        self._apply_transition(chat_id, transition)

    def handle_callback(self, chat_id: str, query_id: str, callback_data: str) -> None:
        self._answer_callback(query_id)

        engine = self._store.get_engine(chat_id)
        if engine is None:
            self._send(chat_id, _session_lost_message(self._store, chat_id))
            return

        value = callback_data
        parsed = parse_callback_data(callback_data)
        if parsed is not None:
            sid, _item_id, value = parsed
            if sid != engine.session.session_id:
                self._send(chat_id, _stale_button_message(self._store, chat_id))
                return

        transition = engine.submit_button(value)
        self._apply_transition(chat_id, transition)

    def handle_voice(self, chat_id: str, audio: bytes) -> None:
        engine = self._store.get_engine(chat_id)
        if engine is None:
            self._send(chat_id, _session_lost_message(self._store, chat_id))
            return

        is_dialog = _is_dialog_engine(engine)
        if stt_provider() == "mock" and not is_dialog:
            self._send(chat_id, _VOICE_MOCK_HINT)
            return

        try:
            transition = engine.submit_voice(audio)
        except ValueError as e:
            code = str(e)
            if code == "empty_audio":
                msg = (
                    "Не удалось распознать аудио. Повторите голосовое."
                    if is_dialog
                    else "Не удалось распознать аудио. Повторите или нажмите кнопку."
                )
                self._send(chat_id, msg)
                return
            if code == "audio_too_large":
                msg = (
                    "Файл слишком большой. Запишите короткое голосовое."
                    if is_dialog
                    else "Файл слишком большой. Короткое голосовое или кнопка."
                )
                self._send(chat_id, msg)
                return
            raise
        except Exception as e:
            from psychological_testing.services.stt_service import SttConfigurationError

            if isinstance(e, SttConfigurationError):
                self._send(
                    chat_id,
                    DIALOG_VOICE_STT_SETUP if is_dialog else (
                        "Голосовой ввод временно недоступен. Используйте кнопки или текст."
                    ),
                )
                return
            _log.exception("voice handling failed")
            self._send(
                chat_id,
                "Ошибка распознавания голоса. Повторите голосовое."
                if is_dialog
                else "Ошибка распознавания голоса. Используйте кнопку.",
            )
            return

        self._apply_transition(chat_id, transition)
