"""MBTI A/B answer resolver — re-exports production ``shared_engine.answer_resolver``."""

from __future__ import annotations

import argparse

from psychological_testing.shared_engine.answer_resolver import (
    PoleChoice,
    ResolvedAnswer,
    choice_to_pole,
    resolve_mbti_ab,
)

__all__ = [
    "PoleChoice",
    "ResolvedAnswer",
    "choice_to_pole",
    "resolve_mbti_ab",
]

# Backward-compatible alias for Phase 0 tests/CLI
resolve_mbti_answer = resolve_mbti_ab


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve MBTI voice/text to A or B")
    parser.add_argument("text", nargs="+", help="User utterance, e.g. вариант А")
    parser.add_argument("--pole-a", default="E", help="Pole for option A (demo)")
    parser.add_argument("--pole-b", default="I", help="Pole for option B (demo)")
    args = parser.parse_args()
    utterance = " ".join(args.text)
    result = resolve_mbti_ab(utterance)
    if result is None:
        print("ambiguous")
        raise SystemExit(1)
    pole = choice_to_pole(result.value, args.pole_a, args.pole_b)
    print(
        f"choice={result.value} pole={pole} "
        f"confidence={result.confidence} rule={result.matched_rule}"
    )


if __name__ == "__main__":
    main()
