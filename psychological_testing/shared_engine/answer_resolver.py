"""Resolve voice/text/button input to structured values (no LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

PoleChoice = Literal["A", "B"]
PaeiChoice = Literal["P", "A", "E", "I"]

_PAEI_EXACT: dict[str, tuple[str, ...]] = {
    "P": ("p", "п", "производитель"),
    "A": ("a", "а", "администратор"),
    "E": ("e", "е", "предприниматель", "энтузиаст"),
    "I": ("i", "и", "интегратор"),
}

_PATTERN_A = re.compile(
    r"(?:^|\b)(?:а|a|вариант\s*а|первый|первая|один|1)(?:\b|$)",
    re.IGNORECASE,
)
_PATTERN_B = re.compile(
    r"(?:^|\b)(?:б|b|вариант\s*б|второй|вторая|два|2)(?:\b|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResolvedAnswer:
    """Structured resolver output before scoring."""

    value: Any
    confidence: float
    matched_rule: str
    input_channel: str = "text"

    @property
    def choice(self) -> PoleChoice:
        """A/B choice when ``value`` is ``'A'`` or ``'B'`` (MBTI resolver)."""
        if self.value not in ("A", "B"):
            raise AttributeError("choice is only defined for A/B resolution")
        return self.value  # type: ignore[return-value]


def resolve_mbti_ab(text: str) -> ResolvedAnswer | None:
    """Map free-text or button label to A or B."""
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return None

    if normalized in {"a", "а", "1"}:
        return ResolvedAnswer("A", 1.0, "exact_a")
    if normalized in {"b", "б", "2"}:
        return ResolvedAnswer("B", 1.0, "exact_b")

    has_a = bool(_PATTERN_A.search(normalized))
    has_b = bool(_PATTERN_B.search(normalized))

    if has_a and not has_b:
        return ResolvedAnswer("A", 0.85, "pattern_a")
    if has_b and not has_a:
        return ResolvedAnswer("B", 0.85, "pattern_b")
    return None


def choice_to_pole(choice: PoleChoice, option_a_pole: str, option_b_pole: str) -> str:
    return option_a_pole if choice == "A" else option_b_pole


_LIKERT_WORDS: dict[str, int] = {
    "1": 1,
    "один": 1,
    "первый": 1,
    "первая": 1,
    "2": 2,
    "два": 2,
    "второй": 2,
    "вторая": 2,
    "3": 3,
    "три": 3,
    "третий": 3,
    "третья": 3,
    "4": 4,
    "четыре": 4,
    "четвертый": 4,
    "четвёртый": 4,
    "5": 5,
    "пять": 5,
    "пятый": 5,
    "пятая": 5,
}


def resolve_likert_value(
    text: str,
    *,
    min_val: int = 1,
    max_val: int = 5,
) -> ResolvedAnswer | None:
    """Map voice/text to Likert integer in ``[min_val, max_val]``."""
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return None
    if normalized.isdigit():
        value = int(normalized)
        if min_val <= value <= max_val:
            return ResolvedAnswer(value, 1.0, "exact_digit")
        return None
    if normalized in _LIKERT_WORDS:
        value = _LIKERT_WORDS[normalized]
        if min_val <= value <= max_val:
            return ResolvedAnswer(value, 0.9, "spoken_digit")
    return None


def resolve_paei_choice(text: str) -> ResolvedAnswer | None:
    """Map free-text or button label to P, A, E, or I."""
    normalized = " ".join(text.strip().lower().split())
    if not normalized:
        return None
    token = normalized.upper()
    if token in {"P", "A", "E", "I"}:
        return ResolvedAnswer(token, 1.0, "exact_scale")
    for scale, variants in _PAEI_EXACT.items():
        if normalized in variants:
            return ResolvedAnswer(scale, 0.9, f"keyword_{scale}")
    return None


def resolve_answer(
    test_id: str,
    text: str,
    *,
    option_a_pole: str = "",
    option_b_pole: str = "",
    input_channel: str = "text",
    min_val: int = 1,
    max_val: int = 5,
) -> ResolvedAnswer | None:
    """Dispatch resolver by test plugin."""
    if test_id in ("soft_skills", "disc", "hexaco"):
        resolved = resolve_likert_value(text, min_val=min_val, max_val=max_val)
        if resolved is None:
            return None
        return ResolvedAnswer(
            value=resolved.value,
            confidence=resolved.confidence,
            matched_rule=resolved.matched_rule,
            input_channel=input_channel,
        )
    if test_id == "paei":
        resolved = resolve_paei_choice(text)
        if resolved is None:
            return None
        return ResolvedAnswer(
            value=resolved.value,
            confidence=resolved.confidence,
            matched_rule=resolved.matched_rule,
            input_channel=input_channel,
        )
    if test_id == "mbti":
        ab = resolve_mbti_ab(text)
        if ab is None:
            return None
        pole = choice_to_pole(ab.value, option_a_pole, option_b_pole)
        return ResolvedAnswer(
            value=pole,
            confidence=ab.confidence,
            matched_rule=ab.matched_rule,
            input_channel=input_channel,
        )
    raise NotImplementedError(f"No answer resolver for test_id={test_id!r}")
