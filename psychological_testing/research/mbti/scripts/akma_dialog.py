"""
Akma dialog MBTI — prompts and pure state machine (from ``testing_v2_akma_dialog.ipynb``).

Research / backup delivery mode. Not used for production ``dichotomy_scorer`` path.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

AXES: tuple[str, ...] = ("EI", "SN", "TF", "JP")

AkmaPhase = Literal["zero", "questioning", "done"]


@dataclass(frozen=True)
class UserProfile:
    name: str = "Участник"
    age: int = 30
    gender: str = "не указан"
    post: str = "сотрудник"
    activity: str = "согласно должностной инструкции"


@dataclass
class AkmaDialogState:
    user: UserProfile
    max_questions: int = 12
    hist_akma: list[dict[str, str]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {"EI": 0, "SN": 0, "TF": 0, "JP": 0})
    axis_index: int = 0
    num: int = 0
    phase: AkmaPhase = "zero"
    is_active: bool = True
    errors_count: int = 0
    last_akma_question: str = ""
    type_code: str | None = None
    llm_calls: int = 0

    def current_axis(self) -> str:
        return AXES[self.axis_index % len(AXES)]


def get_akma_system_prompt(
    *,
    size_query: int = 150,
    name: str = "Пётр",
    age: int = 30,
    gender: str = "мужской",
    post: str = "директор",
    activity: str = "согласно должностной инструкции",
) -> tuple[str, str]:
    public_name = name.strip() if name and name.strip() not in ("Участник",) else ""
    if public_name:
        zero_question = (
            f"Здравствуйте, {public_name}! Я Акма — нейро-психолог. "
            f"Расскажите, пожалуйста, чем вы занимаетесь на работе, "
            f"что входит в ваши обязанности и за что вы отвечаете?"
        )
    else:
        zero_question = (
            "Здравствуйте! Я Акма — нейро-психолог. "
            "Расскажите, пожалуйста, чем вы занимаетесь на работе, "
            "что входит в ваши обязанности и за что вы отвечаете?"
        )
    gender_clean = gender.strip().lower()
    if gender_clean in ("мужчина", "мужской", "male", "man") or gender_clean.startswith("м"):
        style = (
            "романтична, проявляешь лёгкий интеллектуальный флирт, "
            "с интересом к деталям его ответов"
        )
    else:
        style = "умна, добра, интелектуальная и внимательна к эмоциям и нюансам"

    akma_system_prompt = f"""Ты — женщина Акма, ведущий психолог и акмеолог. Ты {style}. Ты лучше всех в связанной беседе задаешь вопросы для определения предпочтения по заданной оси MBTI.
Пользователь: {name}, {age} лет, пол -{gender}, занимает должность – {post} и выполняет работы {activity}
Задача: Веди связный диалог с Пользователь по его должности и выполняемой работе, задавая вопросы для определения его предпочтения по заданной оси MBTI.
Правила:
    Всегда **реагируй на последний ответ** Пользователь - покажи коротко, что ты его услышала, процитируй или эмоция.
    На все вопросы Пользователь отвечай - "это не относится к данной беседе".
    Если Пользователь не отвечает или непонятно отвечает на твои вопросы, попроси его более конкретно отвечать на вопросы т.к. это все же тест, иначе тест будет прерван.
    Затем **плавно перейди** к новому вопросу для определения его тпредпочтения MBTI по указанной оси.
    Запрещено повторять или переформулировать вопросы, которые уже есть в истории диалога или "role":"assistant".
    Ответ — строго только на русском языке {int(0.5 * size_query)} – {size_query} токенов.
    Запрещено в ответе выдавать </think>, тесты, смайлы, эмодзи, кавычки, *, термины MBTI («экстраверсия», «интуиция» и т.д.) и какую-либо разметку."""
    return zero_question, akma_system_prompt


def get_akma_local_prompt(axis: str) -> str:
    return (
        f'Обязательно но кратко отреагируй(поцетируй, эмоция) на последний Ответ Пользователь '
        f'и задай один новый вопрос для определения его предпочтения по оси "{axis}" по MBTI, '
        f"обязательно связав его с предыдущими ответами пользователя"
    )


def get_analis_messages(akma_question: str, user_resp: str, axis: str) -> list[dict[str, str]]:
    system_content = "Ты профессиональный акмеолог-психолог по определению предпочтения по оси теста MBTI."
    user_content = f"""На ВОПРОС: "{akma_question}".
 Пользователь дал ОТВЕТ: "{user_resp}".
Определи точно по ОТВЕТ Пользователь на ВОПРОС его предпочтение "{axis[0]}" или "{axis[1]}" по оси "{axis}" MBTI.
Если ОТВЕТ не является ответом на ВОПРОС верни "x".
Если ВОПРОС или ОТВЕТ не понятен верни "x".
Если не уверен в его предпочтении или не можешь точно определить его предпочтение, верни "x".
Ответь только JSON-объектом с ключом "choice", где значение только 1 буква "{axis[0]}", "{axis[1]}" или "x", без дополнительного текста.
Пример правильного ответа: {{"choice": "x"}}"""
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def get_final_report_messages(basic_type: str, *, size_query: int = 150) -> list[dict[str, str]]:
    system_content = "Ты профессиональный акмеолог-психолог и лучше всех характеризуешь по тесту MBTI."
    user_content = f"""Ответь строго только на русском языке меньше {int(1.5 * size_query)} токенов.
Запрещено в ответе выдавать </think>, тесты, смайлы, эмодзи, *, Markdown и какую-либо разметку.
По результатам теста MBTI выявлен тип личности: {basic_type}. Перечисли для типа {basic_type} не более трех:
cильные стороны -
cлабые стороны -
рекомендации для развития и обучения -
подходяшие профессии и должности -"""
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def type_code_from_counters(counters: dict[str, int]) -> str:
    return "".join(ax[0] if counters.get(ax, 0) >= 0 else ax[1] for ax in AXES)


def parse_eval_choice(raw: str, axis: str) -> str:
    text = raw.strip()
    try:
        data = json.loads(text)
        choice = str(data.get("choice", "x")).upper()
    except json.JSONDecodeError:
        match = re.search(r'"choice"\s*:\s*"([A-Za-z])"', text)
        choice = match.group(1).upper() if match else "X"
    if choice in (axis[0], axis[1]):
        return choice
    return "x"


def axis_threshold(max_questions: int) -> int:
    return max(1, max_questions // 8)


def begin_dialog(user: UserProfile, *, max_questions: int = 12) -> tuple[AkmaDialogState, str]:
    zero_q, akma_sys = get_akma_system_prompt(
        name=user.name,
        age=user.age,
        gender=user.gender,
        post=user.post,
        activity=user.activity,
    )
    state = AkmaDialogState(user=user, max_questions=max_questions, last_akma_question=zero_q)
    state.hist_akma = [
        {"role": "system", "content": akma_sys},
        {"role": "assistant", "content": zero_q},
    ]
    return state, zero_q


def _append_user(state: AkmaDialogState, user_text: str) -> None:
    state.hist_akma.append({"role": "user", "content": f"Ответ Пользователь: {user_text}"})


def _apply_eval(state: AkmaDialogState, choice: str, axis: str) -> None:
    if choice == axis[0]:
        state.counters[axis] += 1
    else:
        state.counters[axis] -= 1
    state.num += 1
    state.axis_index = (state.axis_index + 1) % len(AXES)


def _maybe_skip_axis(state: AkmaDialogState) -> str:
    axis = state.current_axis()
    threshold = axis_threshold(state.max_questions)
    if abs(state.counters[axis]) > threshold:
        state.num += 1
        state.axis_index = (state.axis_index + 1) % len(AXES)
        return axis
    return ""


@dataclass(frozen=True)
class AkmaStepResult:
    state: AkmaDialogState
    assistant_message: str | None = None
    report_text: str | None = None
    eval_note: str | None = None
    skipped_axis: str | None = None


def process_user_message(
    state: AkmaDialogState,
    user_text: str,
    *,
    llm_chat: Any,
    model_akma: str,
    model_eval: str,
    model_report: str,
    temp_akma: float = 0.3,
) -> AkmaStepResult:
    """Advance dialog by one user turn. ``llm_chat(model, messages, temperature=...) -> str``."""
    if not state.is_active:
        return AkmaStepResult(state=state)

    text = user_text.strip()
    if not text:
        return AkmaStepResult(state=state, assistant_message="Пожалуйста, напишите ответ текстом.")

    eval_note: str | None = None

    if state.phase == "zero":
        _append_user(state, text)
        state.phase = "questioning"
    else:
        axis = state.current_axis()
        eval_messages = get_analis_messages(state.last_akma_question, text, axis)
        raw_eval = llm_chat(model_eval, eval_messages, temperature=0.0)
        state.llm_calls += 1
        choice = parse_eval_choice(raw_eval, axis)

        if choice in axis:
            _apply_eval(state, choice, axis)
            _append_user(state, text)
            eval_note = f"Оценка: {choice} | Счёт {axis}: {state.counters[axis]}"
        else:
            state.errors_count += 1
            eval_note = "Нужно уточнение — ответ не удалось однозначно отнести к полюсу."

        if state.num >= state.max_questions:
            return _finish(state, llm_chat=llm_chat, model_report=model_report, eval_note=eval_note)

        skipped = _maybe_skip_axis(state)
        if skipped:
            return _ask_next(
                state,
                llm_chat=llm_chat,
                model_akma=model_akma,
                temp_akma=temp_akma,
                eval_note=eval_note,
                skipped_axis=skipped,
            )

        if choice not in axis:
            return _ask_next(
                state,
                llm_chat=llm_chat,
                model_akma=model_akma,
                temp_akma=temp_akma,
                eval_note=eval_note,
            )

    return _ask_next(
        state,
        llm_chat=llm_chat,
        model_akma=model_akma,
        temp_akma=temp_akma,
        eval_note=eval_note,
    )


def _ask_next(
    state: AkmaDialogState,
    *,
    llm_chat: Any,
    model_akma: str,
    temp_akma: float,
    eval_note: str | None = None,
    skipped_axis: str | None = None,
) -> AkmaStepResult:
    axis = state.current_axis()
    local_p = get_akma_local_prompt(axis)
    messages = state.hist_akma + [{"role": "user", "content": local_p}]
    next_q = llm_chat(model_akma, messages, temperature=temp_akma)
    state.llm_calls += 1
    state.hist_akma.append({"role": "assistant", "content": next_q})
    state.last_akma_question = next_q
    return AkmaStepResult(
        state=state,
        assistant_message=next_q,
        eval_note=eval_note,
        skipped_axis=skipped_axis,
    )


def _finish(
    state: AkmaDialogState,
    *,
    llm_chat: Any,
    model_report: str,
    eval_note: str | None = None,
) -> AkmaStepResult:
    state.is_active = False
    state.phase = "done"
    type_code = type_code_from_counters(state.counters)
    state.type_code = type_code
    report_messages = get_final_report_messages(type_code)
    interpretation = llm_chat(model_report, report_messages, temperature=0.2)
    state.llm_calls += 1
    report = (
        f"=== MBTI (диалог с Акма) ===\n\n"
        f"Ваш тип: {type_code}\n"
        f"Счётчики осей: {state.counters}\n"
        f"LLM-вызовов в сессии: {state.llm_calls}\n\n"
        f"{interpretation}\n\n"
        f"— Режим dialog (research). Для сравнения: /start mbti_structured"
    )
    return AkmaStepResult(state=state, report_text=report, eval_note=eval_note)
