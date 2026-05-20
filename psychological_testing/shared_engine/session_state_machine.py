"""Session lifecycle: questioning → scoring → interpretation → report."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from psychological_testing.domain.entities import (
    SessionStatus,
    StructuredAnswer,
    TestDefinition,
    TestSession,
)
from psychological_testing.shared_engine.interpretation_engine import InterpretationResult, interpret
from psychological_testing.shared_engine.item_bank_loader import (
    DimensionBankItem,
    ForcedChoiceItem,
    LikertBankItem,
    load_items_for_definition,
    load_likert_csv_items,
    load_paei_items,
    load_soft_skills_items,
)
from psychological_testing.shared_engine.question_selector import SelectableItem, select_from_definition
from psychological_testing.shared_engine.report_builder import (
    build_text_report,
    format_likert_sum_report,
    format_paei_report,
    format_soft_skills_report,
    DISC_SCALE_NAMES,
    HEXACO_SCALE_NAMES,
)
from psychological_testing.shared_engine.response_collector import (
    CONFIDENCE_THRESHOLD,
    collect_button_response,
    collect_text_response,
    collect_voice_response,
    reprompt_message_for,
)
from psychological_testing.shared_engine.scoring_pipeline import score
from psychological_testing.shared_engine.voice_pipeline import VoicePipeline

VOICE_HINT_RU = "🎤 Можно ответить голосом или нажмите кнопку ниже."

SOFT_SKILLS_SCALE_LINES = (
    "1 — совсем не согласен",
    "2 — скорее не согласен",
    "3 — затрудняюсь ответить / нейтрально",
    "4 — скорее согласен",
    "5 — полностью согласен",
)

LIKERT_AGREEMENT_PROMPT = "Насколько вы согласны с этим утверждением?"


def _likert_scale_label(test_id: str, scale: str) -> str:
    if test_id == "disc":
        return DISC_SCALE_NAMES.get(scale, scale)
    if test_id == "hexaco":
        return HEXACO_SCALE_NAMES.get(scale, scale)
    return scale


def format_likert_question_message(
    item: LikertBankItem,
    *,
    test_id: str,
    display_name: str,
    index: int,
    total: int,
    voice_hint: bool = True,
) -> str:
    if test_id == "hexaco":
        header = f"[{index}/{total}] {display_name}"
    else:
        scale_label = _likert_scale_label(test_id, item.scale)
        header = f"[{index}/{total}] {display_name} — {item.scale} ({scale_label})"
    lines = [
        header,
        "",
        item.text,
        "",
        LIKERT_AGREEMENT_PROMPT,
        "",
        *SOFT_SKILLS_SCALE_LINES,
    ]
    if voice_hint:
        lines.extend(["", "🎤 Можно ответить голосом («два», «три», «четыре»…) или нажмите кнопку 1–5."])
    return "\n".join(lines)


@dataclass(frozen=True)
class SessionTransition:
    """Result of a state transition for adapters (Telegram, API)."""

    status: SessionStatus
    session: TestSession
    current_item: Any | None = None
    reprompt_message: str | None = None
    report_text: str | None = None
    progress: tuple[int, int] | None = None
    # mbti_dialog: Akma question text (bot → user); user replies via voice
    akma_question: str | None = None
    user_ack: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_question_message(
    item: SelectableItem,
    *,
    index: int,
    total: int,
    voice_hint: bool = True,
) -> str:
    """Telegram-style MBTI question body."""
    lines = [
        f"[{index}/{total}] Ось: {item.axis}",
        "",
        item.text,
        "",
        f"A) {item.option_a_text}",
        f"B) {item.option_b_text}",
    ]
    if voice_hint:
        lines.extend(["", VOICE_HINT_RU])
    return "\n".join(lines)


def format_soft_skills_question_message(
    item: DimensionBankItem,
    *,
    index: int,
    total: int,
    voice_hint: bool = True,
) -> str:
    lines = [
        f"[{index}/{total}] Soft Skills — {item.skill}",
        "",
        item.text,
        "",
        "Насколько вы согласны с этим утверждением?",
        "",
        *SOFT_SKILLS_SCALE_LINES,
    ]
    if voice_hint:
        lines.extend(["", "🎤 Можно ответить голосом («два», «три», «четыре»…) или нажмите кнопку 1–5."])
    return "\n".join(lines)


def format_paei_question_message(
    item: ForcedChoiceItem,
    *,
    index: int,
    total: int,
    voice_hint: bool = True,
) -> str:
    """Telegram-style PAEI forced-choice question."""
    lines = [f"[{index}/{total}] PAEI (Адизес)", "", item.text, ""]
    for code in ("P", "A", "E", "I"):
        if code in item.options:
            lines.append(f"{code}) {item.options[code]}")
    if voice_hint:
        lines.extend(["", "🎤 Можно ответить голосом (P, A, E или I) или нажмите кнопку ниже."])
    return "\n".join(lines)


class SessionEngine:
    """Drive a single test session without Telegram (button path first)."""

    def __init__(
        self,
        definition: TestDefinition,
        session: TestSession,
        *,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        voice_pipeline: VoicePipeline | None = None,
    ) -> None:
        self._definition = definition
        self._session = session
        self._confidence_threshold = confidence_threshold
        self._voice_pipeline = voice_pipeline or VoicePipeline()

    @classmethod
    def start(
        cls,
        definition: TestDefinition,
        *,
        client_id: str,
        employee_id: str,
        session_id: str | None = None,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        voice_pipeline: VoicePipeline | None = None,
    ) -> SessionEngine:
        if not definition.item_bank:
            raise ValueError(f"test {definition.test_id} has no item_bank")

        if definition.scoring_type == "dichotomy_weighted_choice":
            raw_items = load_items_for_definition(definition.item_bank)
            items = select_from_definition(raw_items, definition.selection)
        elif definition.scoring_type == "forced_choice_count":
            items = load_paei_items(definition.item_bank)
        elif definition.scoring_type == "likert_per_dimension":
            items = load_soft_skills_items(definition.item_bank)
        elif definition.scoring_type == "likert_sum":
            items = load_likert_csv_items(definition.item_bank)
        else:
            raise NotImplementedError(
                f"Session engine does not support scoring_type={definition.scoring_type!r}"
            )

        session = TestSession(
            session_id=session_id or str(uuid.uuid4()),
            client_id=client_id,
            employee_id=employee_id,
            test_id=definition.test_id,
            test_version=definition.version,
            status=SessionStatus.QUESTIONING,
            started_at=_utc_now(),
            items=items,
        )
        return cls(
            definition,
            session,
            confidence_threshold=confidence_threshold,
            voice_pipeline=voice_pipeline,
        )

    @property
    def session(self) -> TestSession:
        return self._session

    @property
    def definition(self) -> TestDefinition:
        return self._definition

    def _progress(self) -> tuple[int, int]:
        total = len(self._session.items)
        current = min(self._session.current_item_index + 1, total) if total else 0
        return current, total

    def current_item(self) -> Any | None:
        if self._session.status not in (SessionStatus.QUESTIONING, SessionStatus.REPROMPT):
            return None
        if self._session.current_item_index >= len(self._session.items):
            return None
        return self._session.items[self._session.current_item_index]

    def _transition(
        self,
        *,
        current_item: Any | None = None,
        reprompt_message: str | None = None,
        report_text: str | None = None,
    ) -> SessionTransition:
        return SessionTransition(
            status=self._session.status,
            session=self._session,
            current_item=current_item,
            reprompt_message=reprompt_message,
            report_text=report_text,
            progress=self._progress() if self._session.status == SessionStatus.QUESTIONING else None,
        )

    def _accept_answer(self, answer: StructuredAnswer) -> SessionTransition:
        self._session.responses.append(answer)
        self._session.current_item_index += 1
        self._session.status = SessionStatus.QUESTIONING
        self._session.reprompt_message = None

        if self._session.current_item_index >= len(self._session.items):
            return self._finish_scoring()
        item = self.current_item()
        assert item is not None
        return self._transition(current_item=item)

    def _reprompt(self) -> SessionTransition:
        self._session.status = SessionStatus.REPROMPT
        msg = reprompt_message_for(self._definition.test_id)
        self._session.reprompt_message = msg
        item = self.current_item()
        return self._transition(current_item=item, reprompt_message=msg)

    def _finish_scoring(self) -> SessionTransition:
        self._session.status = SessionStatus.SCORING
        if self._definition.scoring_type == "dichotomy_weighted_choice":
            scoring_answers = [
                (answer.axis or item.axis, answer.resolved_value)
                for item, answer in zip(self._session.items, self._session.responses, strict=True)
            ]
        elif self._definition.scoring_type == "likert_per_dimension":
            scoring_answers = [
                (answer.item_id, int(answer.resolved_value))
                for answer in self._session.responses
            ]
        elif self._definition.scoring_type == "likert_sum":
            scoring_answers = [
                (answer.item_id, int(answer.resolved_value))
                for answer in self._session.responses
            ]
        else:
            scoring_answers = [
                (answer.item_id, str(answer.resolved_value))
                for answer in self._session.responses
            ]
        self._session.score_result = score(self._definition, scoring_answers)

        self._session.status = SessionStatus.INTERPRETATION
        if self._definition.scoring_type == "dichotomy_weighted_choice":
            self._session.interpretation = interpret(self._definition, self._session.score_result)
            report_text = build_text_report(self._session.interpretation)
        elif self._definition.scoring_type == "likert_per_dimension":
            self._session.interpretation = None
            report_text = format_soft_skills_report(self._session.score_result)
        elif self._definition.scoring_type == "likert_sum":
            self._session.interpretation = None
            report_text = format_likert_sum_report(
                self._session.score_result,
                test_id=self._definition.test_id,
            )
        else:
            self._session.interpretation = None
            report_text = format_paei_report(self._session.score_result)

        self._session.status = SessionStatus.REPORT
        self._session.status = SessionStatus.DONE
        return self._transition(report_text=report_text)

    def submit_button(self, callback_data: str) -> SessionTransition:
        if self._session.status == SessionStatus.CANCELLED:
            return self._transition()
        if self._session.status == SessionStatus.DONE:
            return self._transition(report_text=self._done_report_text())

        item = self.current_item()
        if item is None:
            return self._transition()

        answer = collect_button_response(self._definition, item, callback_data)
        return self._accept_answer(answer)

    def _done_report_text(self) -> str | None:
        if self._session.score_result is None:
            return None
        if self._session.interpretation is not None:
            return build_text_report(self._session.interpretation)
        if self._definition.scoring_type == "likert_per_dimension":
            return format_soft_skills_report(self._session.score_result)
        if self._definition.scoring_type == "likert_sum":
            return format_likert_sum_report(
                self._session.score_result,
                test_id=self._definition.test_id,
            )
        return format_paei_report(self._session.score_result)

    def submit_text(self, text: str) -> SessionTransition:
        if self._session.status in (SessionStatus.CANCELLED, SessionStatus.DONE):
            return self._transition(report_text=self._done_report_text())

        item = self.current_item()
        if item is None:
            return self._transition()

        answer = collect_text_response(self._definition, item, text, input_channel="text")
        if answer is None or answer.confidence < self._confidence_threshold:
            return self._reprompt()
        return self._accept_answer(answer)

    def submit_voice(self, audio: bytes, *, hint: str | None = None) -> SessionTransition:
        if self._session.status in (SessionStatus.CANCELLED, SessionStatus.DONE):
            return self._transition(report_text=self._done_report_text())

        item = self.current_item()
        if item is None:
            return self._transition()

        answer, transcript = collect_voice_response(
            self._definition,
            item,
            audio,
            pipeline=self._voice_pipeline,
            hint=hint,
        )
        if transcript:
            self._session.raw_transcripts.append(transcript)
        if answer is None or answer.confidence < self._confidence_threshold:
            return self._reprompt()
        return self._accept_answer(answer)

    def cancel(self) -> SessionTransition:
        self._session.status = SessionStatus.CANCELLED
        return self._transition()

    def current_question_message(self, *, voice_hint: bool = True) -> str | None:
        item = self.current_item()
        if item is None:
            return None
        idx, total = self._progress()
        if self._definition.test_id == "paei":
            return format_paei_question_message(
                item, index=idx, total=total, voice_hint=voice_hint
            )
        if self._definition.test_id == "soft_skills":
            return format_soft_skills_question_message(
                item, index=idx, total=total, voice_hint=voice_hint
            )
        if self._definition.scoring_type == "likert_sum":
            assert isinstance(item, LikertBankItem)
            return format_likert_question_message(
                item,
                test_id=self._definition.test_id,
                display_name=self._definition.display_name,
                index=idx,
                total=total,
                voice_hint=voice_hint,
            )
        return format_question_message(item, index=idx, total=total, voice_hint=voice_hint)
