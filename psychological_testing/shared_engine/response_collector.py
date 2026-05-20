"""Unified intake: button, text, and voice → ``StructuredAnswer``."""

from __future__ import annotations

from typing import Literal

from psychological_testing.domain.entities import InputChannel, StructuredAnswer, TestDefinition
from psychological_testing.shared_engine.answer_resolver import (
    PoleChoice,
    choice_to_pole,
    resolve_answer,
)
from psychological_testing.shared_engine.item_bank_loader import DimensionBankItem, ForcedChoiceItem
from psychological_testing.shared_engine.question_selector import SelectableItem

SessionItem = SelectableItem | ForcedChoiceItem | DimensionBankItem
from psychological_testing.shared_engine.voice_pipeline import VoicePipeline

CONFIDENCE_THRESHOLD = 0.7

REPROMPT_MBTI_RU = (
    "Не удалось распознать ответ. Выберите кнопку или повторите голосом: A или B"
)


def reprompt_message_for(test_id: str) -> str:
    if test_id == "mbti":
        return REPROMPT_MBTI_RU
    if test_id in ("soft_skills", "disc", "hexaco"):
        return "Не удалось распознать ответ. Выберите кнопку 1–5 или скажите число (от «один» до «пять»)."
    if test_id == "paei":
        return "Не удалось распознать ответ. Выберите кнопку или скажите: P, A, E или I."
    return "Не удалось распознать ответ. Повторите или выберите кнопку."


def _normalize_button_choice(callback_data: str) -> PoleChoice | None:
    token = callback_data.strip().upper()
    if token in {"A", "B"}:
        return token  # type: ignore[return-value]
    if ":" in token:
        _, choice = token.split(":", 1)
        choice = choice.strip().upper()
        if choice in {"A", "B"}:
            return choice  # type: ignore[return-value]
    return None


def _normalize_likert_callback(callback_data: str, *, min_val: int, max_val: int) -> int:
    token = callback_data.strip().lower()
    if token.startswith("soft_"):
        token = token.removeprefix("soft_")
    value = int(token)
    if value < min_val or value > max_val:
        raise ValueError(f"Likert score out of range: {value}")
    return value


def _normalize_paei_callback(callback_data: str) -> str:
    token = callback_data.strip().upper()
    if token in {"P", "A", "E", "I"}:
        return token
    if token.startswith("PAEI_"):
        choice = token.removeprefix("PAEI_")
        if choice in {"P", "A", "E", "I"}:
            return choice
    if ":" in token:
        _, choice = token.split(":", 1)
        choice = choice.strip().upper()
        if choice in {"P", "A", "E", "I"}:
            return choice
    raise ValueError(f"Invalid PAEI button callback: {callback_data!r}")


def collect_button_response(
    definition: TestDefinition,
    item: SessionItem,
    callback_data: str,
) -> StructuredAnswer:
    """Inline button → structured value (confidence 1.0)."""
    if definition.scoring_type in ("likert_sum", "likert_per_dimension"):
        min_v = int(definition.response_scale.get("min", 1))
        max_v = int(definition.response_scale.get("max", 5))
        score_val = _normalize_likert_callback(callback_data, min_val=min_v, max_val=max_v)
        return StructuredAnswer(
            item_id=item.id,
            input_channel="button",
            raw_input=callback_data,
            resolved_value=score_val,
            confidence=1.0,
            resolver_method="exact_button",
        )
    if definition.test_id == "paei":
        scale = _normalize_paei_callback(callback_data)
        return StructuredAnswer(
            item_id=item.id,
            input_channel="button",
            raw_input=callback_data,
            resolved_value=scale,
            confidence=1.0,
            resolver_method="exact_button",
        )
    if definition.test_id == "mbti":
        choice = _normalize_button_choice(callback_data)
        if choice is None:
            raise ValueError(f"Invalid MBTI button callback: {callback_data!r}")
        pole = choice_to_pole(choice, item.option_a_pole, item.option_b_pole)
        return StructuredAnswer(
            item_id=item.id,
            input_channel="button",
            raw_input=callback_data,
            resolved_value=pole,
            confidence=1.0,
            resolver_method="exact_button",
            axis=item.axis,
        )
    raise NotImplementedError(f"Button collector not implemented for {definition.test_id!r}")


def collect_text_response(
    definition: TestDefinition,
    item: SessionItem,
    text: str,
    *,
    input_channel: InputChannel = "text",
) -> StructuredAnswer | None:
    """Text or STT transcript → structured value; ``None`` if ambiguous."""
    if definition.scoring_type in ("likert_sum", "likert_per_dimension"):
        min_v = int(definition.response_scale.get("min", 1))
        max_v = int(definition.response_scale.get("max", 5))
        resolved = resolve_answer(
            definition.test_id,
            text,
            input_channel=input_channel,
            min_val=min_v,
            max_val=max_v,
        )
        if resolved is None:
            return None
        method = resolved.matched_rule
        if input_channel == "voice":
            method = f"voice_{method}"
        return StructuredAnswer(
            item_id=item.id,
            input_channel=input_channel,
            raw_input=text,
            resolved_value=resolved.value,
            confidence=resolved.confidence,
            resolver_method=method,
        )

    if definition.test_id == "paei":
        resolved = resolve_answer(definition.test_id, text, input_channel=input_channel)
        if resolved is None:
            return None
        method = resolved.matched_rule
        if input_channel == "voice":
            method = f"voice_{method}"
        return StructuredAnswer(
            item_id=item.id,
            input_channel=input_channel,
            raw_input=text,
            resolved_value=resolved.value,
            confidence=resolved.confidence,
            resolver_method=method,
        )

    resolved = resolve_answer(
        definition.test_id,
        text,
        option_a_pole=item.option_a_pole,
        option_b_pole=item.option_b_pole,
        input_channel=input_channel,
    )
    if resolved is None:
        return None
    method = resolved.matched_rule
    if input_channel == "voice":
        method = f"voice_{method}"
    return StructuredAnswer(
        item_id=item.id,
        input_channel=input_channel,
        raw_input=text,
        resolved_value=resolved.value,
        confidence=resolved.confidence,
        resolver_method=method,
        axis=item.axis,
    )


def collect_voice_response(
    definition: TestDefinition,
    item: SessionItem,
    audio: bytes,
    *,
    pipeline: VoicePipeline | None = None,
    hint: str | None = None,
) -> tuple[StructuredAnswer | None, str]:
    """Voice bytes → STT → resolver. Returns (answer, transcript)."""
    pipe = pipeline or VoicePipeline()
    transcript = pipe.transcribe(audio, hint=hint)
    answer = collect_text_response(
        definition,
        item,
        transcript,
        input_channel="voice",
    )
    return answer, transcript
