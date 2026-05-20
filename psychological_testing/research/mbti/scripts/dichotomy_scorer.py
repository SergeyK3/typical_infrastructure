"""MBTI dichotomy scoring (research — re-exports production ``shared_engine``).

Phase 0 scripts import from here; canonical implementation lives in
``psychological_testing.shared_engine.dichotomy_scorer``.
"""

from psychological_testing.shared_engine.dichotomy_scorer import (
    AXIS_ORDER,
    AXIS_POLES,
    VALID_TYPE_CODES,
    Answer,
    AxisDetail,
    AxisId,
    DichotomyResult,
    Pole,
    calculate_type_from_answers,
    validate_type_code,
)

__all__ = [
    "AXIS_ORDER",
    "AXIS_POLES",
    "VALID_TYPE_CODES",
    "Answer",
    "AxisDetail",
    "AxisId",
    "DichotomyResult",
    "Pole",
    "calculate_type_from_answers",
    "validate_type_code",
]

if __name__ == "__main__":
    sample: list[Answer] = [
        ("E/I", "I"),
        ("S/N", "N"),
        ("T/F", "T"),
        ("J/P", "J"),
        ("E/I", "I"),
        ("S/N", "N"),
        ("T/F", "T"),
        ("J/P", "J"),
    ]
    result = calculate_type_from_answers(sample)
    print(result.type_code)
    for axis_id, detail in result.axes.items():
        print(f"  {axis_id}: {detail.dominant} (level {detail.level}) counts={detail.counts}")
