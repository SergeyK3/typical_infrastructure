"""
Telegram tri-mode handler: inline buttons, text, voice → ``SessionEngine`` or ``AkmaDialogEngine``.

Commands:
  /start [mbti|mbti_dialog|paei|...] — начать сессию
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
    parse_menu_callback,
    parse_menu_step_action,
    welcome_menu_keyboard,
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
from psychological_testing.integration.telegram_completion import build_completion_footer
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


def _psych_help_text() -> str:
    return (
        "Психологическое тестирование (HR OS).\n\n"
        "• /start <тест> — начать тест\n"
        "• /cancel — прервать текущую сессию"
    )


def _welcome_text(*, has_assignment: bool = False, allowed_count: int = 0) -> str:
    voice_note = "" if _voice_enabled() else f"\n{_VOICE_DEV_NOTE}"
    if has_assignment and allowed_count == 0:
        body = (
            "Психологическое тестирование (HR OS).\n\n"
            "Сейчас нет открытых тестов. Отдел кадров сообщит, когда будет следующий этап.\n"
            "Команды /start и /cancel тоже работают."
        )
    elif has_assignment:
        body = "Психологическое тестирование (HR OS).\n\nНазначение от отдела кадров."
    else:
        body = "Психологическое тестирование (HR OS).\n\nВыберите тест кнопкой ниже."
    return f"{body}{voice_note}"

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
        "Сессия не активна в памяти бота (перезапуск worker или второй процесс polling).\n\n"
        f"Продолжите тест или начните заново: {restart}\n"
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
        return (
            "Добро пожаловать в MBTI (структурированный опрос, HR OS).\n\n"
            "Что делать:\n"
            "1. На каждый вопрос выберите вариант A или B.\n"
            "2. После всех ответов придёт тип личности и краткий портрет.\n\n"
            f"Вопросов в сессии: {question_count}.\n\n"
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

    def _ensure_runtime_loaded(self, chat_id: str) -> SessionEngine | AkmaDialogEngine | None:
        engine = self._store.get_engine(chat_id)
        if engine is not None:
            return engine
        try:
            from app.db import SessionLocal
            from app.services.psych_session_db import try_restore_engine_for_chat

            db = SessionLocal()
            try:
                return try_restore_engine_for_chat(
                    db,
                    self._store,
                    telegram_chat_id=chat_id,
                    registry=self._registry,
                    voice_pipeline=self._voice_pipeline,
                )
            finally:
                db.close()
        except Exception:
            _log.debug("psych_testing: runtime restore skipped", exc_info=True)
            return None

    def _persist_participant_binding(self, chat_id: str, client_id: str, employee_id: str) -> None:
        try:
            from app.db import SessionLocal
            from app.services.psych_session_db import upsert_telegram_binding

            db = SessionLocal()
            try:
                upsert_telegram_binding(
                    db,
                    telegram_chat_id=chat_id,
                    client_id=client_id,
                    employee_id=employee_id,
                )
            finally:
                db.close()
        except Exception:
            _log.debug("psych_testing: binding persist skipped", exc_info=True)

    def _persist_runtime(self, chat_id: str) -> None:
        engine = self._store.get_engine(chat_id)
        if engine is None or isinstance(engine, AkmaDialogEngine):
            return
        binding = self._store.get_binding(chat_id)
        try:
            from app.db import SessionLocal
            from app.services.psych_session_db import save_in_progress_engine

            db = SessionLocal()
            try:
                save_in_progress_engine(
                    db,
                    telegram_chat_id=chat_id,
                    engine=engine,
                    binding=binding,
                )
            finally:
                db.close()
        except Exception:
            _log.debug("psych_testing: runtime persist skipped", exc_info=True)

    def _clear_runtime_db(self, chat_id: str, *, session_id: str | None = None, cancelled: bool = False) -> None:
        try:
            from app.db import SessionLocal
            from app.services.psych_session_db import clear_process_context, mark_session_cancelled

            db = SessionLocal()
            try:
                clear_process_context(db, telegram_chat_id=chat_id)
                if cancelled and session_id:
                    mark_session_cancelled(db, session_id)
            finally:
                db.close()
        except Exception:
            _log.debug("psych_testing: runtime clear skipped", exc_info=True)

    def _dev_ids(self) -> tuple[str, str]:
        client_id = (os.getenv("PSYCH_TESTING_DEV_CLIENT_ID") or "dev-client").strip()
        employee_id = (os.getenv("PSYCH_TESTING_DEV_EMPLOYEE_ID") or "dev-employee").strip()
        return client_id, employee_id

    def _employee_snapshot(self, chat_id: str):
        """Карточка сотрудника по Telegram chat_id (HR или dev fallback)."""
        from psychological_testing.integration.hr_core import EmployeeSnapshot, resolve_employee_by_telegram

        default_client, default_employee = self._dev_ids()
        try:
            from app.db import SessionLocal

            db = SessionLocal()
            try:
                return resolve_employee_by_telegram(
                    db,
                    chat_id,
                    default_client_id=default_client,
                    default_employee_id=default_employee,
                )
            finally:
                db.close()
        except Exception:
            _log.debug("psych_testing: HR resolve unavailable, using dev ids", exc_info=True)
        return EmployeeSnapshot(id=default_employee, client_id=default_client)

    def _resolve_participant(self, chat_id: str) -> tuple[str, str, str | None]:
        """``(client_id, employee_id, display_name)`` via HR или dev fallback."""
        snap = self._employee_snapshot(chat_id)
        return snap.client_id, snap.id, employee_display_label(snap)

    def _apply_pd_consent_gate(self, chat_id: str, client_id: str, employee_id: str) -> bool:
        """
        Единый слой ПДн: False — сценарий остановлен (отправлен prompt или block).
        """
        try:
            from app.db import SessionLocal
            from app.services.employee_consent import PdConsentGate, require_pd_consent_or_prompt

            db = SessionLocal()
            try:
                gate = require_pd_consent_or_prompt(db, client_id, employee_id)
            finally:
                db.close()
            if gate.outcome == PdConsentGate.ALLOW:
                return True
            self._send(chat_id, gate.message or "", gate.reply_markup)
            return False
        except Exception:
            _log.debug("pd consent gate skipped", exc_info=True)
            return True

    def _assignment_gate(
        self,
        client_id: str,
        employee_id: str,
        test_id: str,
        *,
        step_key: str | None = None,
    ) -> tuple[bool, str | None, object | None]:
        try:
            from app.db import SessionLocal
            from app.services.psych_test_assignments import check_may_start_test, mark_test_started

            db = SessionLocal()
            try:
                ok, msg, assignment = check_may_start_test(
                    db,
                    client_id=client_id,
                    employee_id=employee_id,
                    test_id=test_id,
                    step_key=step_key,
                )
                if ok and assignment is not None:
                    mark_test_started(db, assignment)
                return ok, msg, assignment
            finally:
                db.close()
        except Exception:
            _log.debug("assignment gate skipped", exc_info=True)
            return True, None, None

    def _assignment_menu_context(self, chat_id: str) -> dict[str, object] | None:
        client_id, employee_id, _ = self._resolve_participant(chat_id)
        try:
            from app.db import SessionLocal
            from app.services.psych_test_assignments import assignment_menu_context

            db = SessionLocal()
            try:
                return assignment_menu_context(
                    db, client_id=client_id, employee_id=employee_id
                )
            finally:
                db.close()
        except Exception:
            _log.debug("assignment menu context skipped", exc_info=True)
            return None

    def _send_welcome(self, chat_id: str) -> None:
        client_id, employee_id, _ = self._resolve_participant(chat_id)
        if not self._apply_pd_consent_gate(chat_id, client_id, employee_id):
            return
        ctx = self._assignment_menu_context(chat_id)
        if ctx is None:
            self._send(
                chat_id,
                _welcome_text(has_assignment=False),
                welcome_menu_keyboard(),
            )
            return
        allowed_ids = list(ctx.get("allowed_test_ids") or [])
        allowed = frozenset(allowed_ids)
        text: str | None = None
        if len(allowed_ids) == 1:
            try:
                from app.db import SessionLocal
                from app.models import Employee
                from app.services.psych_test_assignments import (
                    build_notify_message,
                    get_active_assignment,
                )

                db = SessionLocal()
                try:
                    assignment = get_active_assignment(
                        db, client_id=client_id, employee_id=employee_id
                    )
                    emp = db.get(Employee, employee_id)
                    if assignment and emp:
                        text = build_notify_message(assignment, emp, db)
                finally:
                    db.close()
            except Exception:
                _log.debug("assignment welcome message skipped", exc_info=True)
        if text is None:
            text = _welcome_text(has_assignment=True, allowed_count=len(allowed_ids))
        self._send(
            chat_id,
            text,
            welcome_menu_keyboard(allowed_test_ids=allowed),
        )

    def _handle_menu_action(self, chat_id: str, action: str) -> None:
        if action == "cancel":
            self.cancel_session(chat_id)
            return
        if action == "help":
            self._send(chat_id, _psych_help_text())
            return
        step_parsed = parse_menu_step_action(action)
        if step_parsed is not None:
            step_key, is_dialog = step_parsed
            test_id, delivery_mode = self._test_id_for_step(chat_id, step_key)
            if test_id not in _SUPPORTED_TESTS:
                self._send_welcome(chat_id)
                return
            if is_dialog and test_id == "mbti":
                delivery_mode = "dialog"
            elif delivery_mode is None:
                delivery_mode = "structured" if test_id == "mbti" else None
            self.start_test(
                chat_id,
                test_id,
                delivery_mode=delivery_mode if test_id == "mbti" else None,
                step_key=step_key,
            )
            return
        test_id, delivery_mode = resolve_mbti_start_arg(action)
        if test_id not in _SUPPORTED_TESTS:
            self._send_welcome(chat_id)
            return
        self.start_test(
            chat_id,
            test_id,
            delivery_mode=delivery_mode if test_id == "mbti" else None,
        )

    def _test_id_for_step(self, chat_id: str, step_key: str) -> tuple[str, MbtiDeliveryMode | None]:
        ctx = self._assignment_menu_context(chat_id)
        if ctx:
            allowed_ids = ctx.get("allowed_test_ids") or []
            if len(allowed_ids) == 1:
                return str(allowed_ids[0]), None
            for step in ctx.get("allowed_steps") or []:
                if str(step.get("step_key")) == step_key:
                    return str(step["test_id"]), None
            for step in ctx.get("all_steps") or []:
                if str(step.get("step_key")) == step_key:
                    return str(step["test_id"]), None
        if step_key.endswith("_1"):
            return step_key[: -len("_1")], None
        return step_key, None

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
        step_key: str | None = None,
    ) -> None:
        if test_id not in _SUPPORTED_TESTS:
            self._send(
                chat_id,
                f"Тест {test_id!r} пока недоступен в Telegram. Доступны: {', '.join(sorted(_SUPPORTED_TESTS))}.",
            )
            return

        client_id, employee_id, _display_name = self._resolve_participant(chat_id)

        if not self._apply_pd_consent_gate(chat_id, client_id, employee_id):
            return

        allowed, block_msg, assignment = self._assignment_gate(
            client_id, employee_id, test_id, step_key=step_key
        )
        if not allowed:
            self._send(chat_id, block_msg or "Тест недоступен по назначению HR.")
            return

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

        binding = self._store.ensure_binding(
            chat_id, client_id=client_id, employee_id=employee_id
        )
        binding.context = "psych_testing"
        binding.active_test_id = test_id
        binding.active_step_key = step_key or test_id
        binding.active_assignment_id = assignment.id if assignment is not None else None
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
                from psychological_testing.integration.hr_core import employee_greeting_label
                from psychological_testing.research.mbti.scripts.akma_dialog import UserProfile

                snap = self._employee_snapshot(chat_id)
                greeting = employee_greeting_label(snap)
                engine: SessionEngine | AkmaDialogEngine = AkmaDialogEngine.start(
                    definition,
                    client_id=client_id,
                    employee_id=employee_id,
                    user=UserProfile(name=greeting or "Участник"),
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
        self._persist_participant_binding(chat_id, client_id, employee_id)
        self._persist_runtime(chat_id)
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
            engine = self._ensure_runtime_loaded(chat_id)
        if engine is None:
            self._send(chat_id, "Нет активной сессии.")
            return
        session_id = engine.session.session_id
        engine.cancel()
        self._store.clear_engine(chat_id)
        binding = self._store.get_binding(chat_id)
        if binding:
            binding.context = "idle"
            binding.active_test_id = None
            binding.active_step_key = None
            binding.active_assignment_id = None
            binding.mbti_delivery_mode = None
        self._clear_runtime_db(chat_id, session_id=session_id, cancelled=True)
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
            client_id, employee_id, display_name = self._resolve_participant(chat_id)
            assignment_id = binding.active_assignment_id if binding else None
            completed_step_key = binding.active_step_key if binding else None
            updated = None
            try:
                from app.db import SessionLocal
                from app.services.psych_test_assignments import record_test_completed

                db = SessionLocal()
                try:
                    doc = build_session_result_document(
                        engine,
                        telegram_chat_id=chat_id,
                        report_text=transition.report_text,
                        employee_display_name=display_name,
                        delivery_mode=delivery_mode,
                        assignment_id=assignment_id,
                    )
                    if completed_step_key:
                        doc["step_key"] = completed_step_key
                    persist_session_result(doc)
                    test_id = str(doc.get("test_id") or "")
                    session_id = str(doc.get("session_id") or "")
                    updated = record_test_completed(
                        db,
                        client_id=client_id,
                        employee_id=employee_id,
                        test_id=test_id,
                        assignment_id=assignment_id,
                        session_id=session_id or None,
                    )
                finally:
                    db.close()
            except Exception:
                _log.exception("persist session result failed")
                updated = None
            mbti_dialog = bool(
                binding
                and binding.active_test_id == "mbti"
                and binding.mbti_delivery_mode == "dialog"
            )
            self._store.clear_engine(chat_id)
            if binding:
                binding.context = "idle"
                binding.active_test_id = None
                binding.active_step_key = None
                binding.active_assignment_id = None
                binding.mbti_delivery_mode = None
            self._clear_runtime_db(chat_id)
            report = transition.report_text
            if transition.user_ack:
                report = f"{transition.user_ack}\n\n{report}"

            menu_ctx = None
            if updated is not None:
                try:
                    from app.services.psych_test_assignments import assignment_menu_context

                    db = SessionLocal()
                    try:
                        menu_ctx = assignment_menu_context(
                            db,
                            client_id=client_id,
                            employee_id=employee_id,
                        )
                    finally:
                        db.close()
                except Exception:
                    _log.debug("completion menu context failed", exc_info=True)

            report += "\n\n" + build_completion_footer(
                engine,
                has_hr_assignment=updated is not None,
                assignment_complete=bool(menu_ctx and menu_ctx.get("is_complete")),
                mbti_dialog=mbti_dialog,
            )
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
            self._persist_runtime(chat_id)
            return

        if transition.status == SessionStatus.CANCELLED:
            session_id = engine.session.session_id
            self._store.clear_engine(chat_id)
            self._clear_runtime_db(chat_id, session_id=session_id, cancelled=True)
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
        self._persist_runtime(chat_id)

    def handle_text(self, chat_id: str, text: str, *, is_command: bool = False) -> None:
        stripped = text.strip()
        lower = stripped.lower()

        if is_command or lower.startswith("/"):
            parts = lower.split()
            cmd = parts[0].split("@")[0]
            if cmd in ("/start", "/test"):
                if len(parts) < 2:
                    self._send_welcome(chat_id)
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
                self._send(chat_id, _psych_help_text())
                return

        engine = self._ensure_runtime_loaded(chat_id)
        if engine is None:
            self._send_welcome(chat_id)
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

        menu_action = parse_menu_callback(callback_data)
        if menu_action is not None:
            self._handle_menu_action(chat_id, menu_action)
            return

        engine = self._ensure_runtime_loaded(chat_id)
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
        engine = self._ensure_runtime_loaded(chat_id)
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
