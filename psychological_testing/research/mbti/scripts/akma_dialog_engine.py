"""Telegram-compatible session driver for MBTI dialog (Akma) delivery mode."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from dataclasses import replace

from psychological_testing.domain.entities import SessionStatus, TestDefinition, TestSession
from psychological_testing.domain.mbti_delivery import (
    DIALOG_VOICE_HINT_RU,
    dialog_voice_reprompt,
    participant_greeting_name,
)
from psychological_testing.research.mbti.scripts.akma_dialog import (
    AkmaDialogState,
    UserProfile,
    begin_dialog,
    process_user_message,
)
from psychological_testing.services.llm_service import (
    LlmClient,
    default_llm_model,
    get_llm_client,
)
from psychological_testing.shared_engine.session_state_machine import SessionTransition
from psychological_testing.shared_engine.voice_pipeline import VoicePipeline


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _max_questions_from_env(default: int = 12) -> int:
    raw = os.getenv("PSYCH_TESTING_MBTI_DIALOG_MAX_QUESTIONS", "").strip()
    if raw.isdigit():
        return max(4, min(44, int(raw)))
    return default


class AkmaDialogEngine:
    """Backup MBTI delivery: conversational Akma + LLM evaluator (research)."""

    def __init__(
        self,
        definition: TestDefinition,
        session: TestSession,
        akma_state: AkmaDialogState,
        *,
        llm: LlmClient | None = None,
        voice_pipeline: VoicePipeline | None = None,
        opening_message: str | None = None,
    ) -> None:
        self._definition = definition
        self._session = session
        self._akma = akma_state
        self._llm = llm or get_llm_client()
        self._voice_pipeline = voice_pipeline or VoicePipeline()
        self._opening_message = opening_message

    @classmethod
    def start(
        cls,
        definition: TestDefinition,
        *,
        client_id: str,
        employee_id: str,
        session_id: str | None = None,
        user: UserProfile | None = None,
        llm: LlmClient | None = None,
        voice_pipeline: VoicePipeline | None = None,
    ) -> AkmaDialogEngine:
        if user is not None:
            profile = user
        else:
            greeting = participant_greeting_name(employee_id)
            profile = UserProfile(name=greeting or "Участник")
        max_q = _max_questions_from_env()
        akma_state, zero_q = begin_dialog(profile, max_questions=max_q)
        session = TestSession(
            session_id=session_id or str(uuid.uuid4()),
            client_id=client_id,
            employee_id=employee_id,
            test_id=definition.test_id,
            test_version=definition.version,
            status=SessionStatus.QUESTIONING,
            started_at=_utc_now(),
            items=[],
        )
        return cls(
            definition,
            session,
            akma_state,
            llm=llm,
            voice_pipeline=voice_pipeline,
            opening_message=zero_q,
        )

    @property
    def session(self) -> TestSession:
        return self._session

    @property
    def definition(self) -> TestDefinition:
        return self._definition

    @property
    def akma_state(self) -> AkmaDialogState:
        return self._akma

    @property
    def delivery_mode(self) -> str:
        return "dialog"

    def current_item(self) -> None:
        return None

    def current_question_message(self, *, voice_hint: bool = True) -> str | None:
        if not self._akma.is_active:
            return None
        if self._opening_message:
            msg = self._opening_message
            self._opening_message = None
            lines = [msg]
            if voice_hint:
                lines.extend(["", DIALOG_VOICE_HINT_RU])
            return "\n".join(lines)
        question = self._akma.last_akma_question
        if not question:
            return None
        if voice_hint:
            return f"{question}\n\n{DIALOG_VOICE_HINT_RU}"
        return question

    def cancel(self) -> None:
        self._akma.is_active = False
        self._session.status = SessionStatus.CANCELLED

    def _transition(
        self,
        *,
        reprompt_message: str | None = None,
        report_text: str | None = None,
        akma_question: str | None = None,
        user_ack: str | None = None,
    ) -> SessionTransition:
        if report_text:
            self._session.status = SessionStatus.DONE
            return SessionTransition(
                status=self._session.status,
                session=self._session,
                report_text=report_text,
                user_ack=user_ack,
            )
        return SessionTransition(
            status=self._session.status,
            session=self._session,
            current_item=None,
            reprompt_message=reprompt_message,
            akma_question=akma_question,
            user_ack=user_ack,
            progress=(self._akma.num, self._akma.max_questions),
        )

    def submit_text(self, text: str) -> SessionTransition:
        if not self._akma.is_active:
            return self._transition(reprompt_message="Сессия завершена. /start mbti")

        result = process_user_message(
            self._akma,
            text,
            llm_chat=self._llm.chat,
            model_akma=default_llm_model("akma"),
            model_eval=default_llm_model("eval"),
            model_report=default_llm_model("report"),
        )
        self._akma = result.state

        if result.report_text:
            return self._transition(report_text=result.report_text)

        # Score lines ("Оценка: E | Счёт EI: …") stay in eval_note for tests/protocol only.
        notes: list[str] = []
        if result.eval_note and result.eval_note.startswith("Нужно уточнение"):
            notes.append(result.eval_note)
        if result.skipped_axis:
            notes.append(f"Ось {result.skipped_axis}: достаточно данных, переходим дальше.")
        return self._transition(
            reprompt_message="\n".join(notes) if notes else None,
            akma_question=result.assistant_message,
        )

    def submit_button(self, _value: str) -> SessionTransition:
        return self._transition(
            reprompt_message=(
                "В диалоге с Акма ответ — только голосом. "
                f"{DIALOG_VOICE_HINT_RU}"
            ),
            akma_question=self._akma.last_akma_question or None,
        )

    def submit_voice(self, audio: bytes, *, hint: str | None = None) -> SessionTransition:
        if not audio:
            raise ValueError("empty_audio")
        try:
            transcript = self._voice_pipeline.transcribe(audio, hint=hint).strip()
        except ValueError as e:
            if str(e) in ("empty_audio", "empty_transcript"):
                return self._transition(
                    reprompt_message=dialog_voice_reprompt(empty=True),
                    akma_question=self._akma.last_akma_question or None,
                )
            raise
        if not transcript:
            return self._transition(
                reprompt_message=dialog_voice_reprompt(empty=True),
                akma_question=self._akma.last_akma_question or None,
            )

        self._session.raw_transcripts.append(transcript)
        transition = self.submit_text(transcript)
        ack = f"🎤 Распознано: «{transcript[:240]}{'…' if len(transcript) > 240 else ''}»"
        return replace(transition, user_ack=ack)
