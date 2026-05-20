"""MBTI answer resolver — voice/text heuristics."""

from __future__ import annotations

import pytest

from psychological_testing.research.scripts.answer_resolver_mbti import (
    choice_to_pole,
    resolve_mbti_answer,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("А", "A"),
        ("вариант первый", "A"),
        ("Б", "B"),
        ("вариант Б", "B"),
        ("b", "B"),
    ],
)
def test_resolve_mbti_answer(text: str, expected: str) -> None:
    result = resolve_mbti_answer(text)
    assert result is not None
    assert result.choice == expected


def test_choice_to_pole() -> None:
    assert choice_to_pole("A", "E", "I") == "E"
    assert choice_to_pole("B", "E", "I") == "I"


def test_ambiguous_returns_none() -> None:
    assert resolve_mbti_answer("не знаю") is None
    assert resolve_mbti_answer("а или б") is None
