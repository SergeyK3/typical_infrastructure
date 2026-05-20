"""HR test programs: step order and unlock rules (Phase 4a)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgramStep:
    test_id: str
    unlock_after: tuple[str, ...] = ()
    parallel_group: str | None = None
    label_ru: str | None = None


@dataclass(frozen=True)
class TestProgram:
    program_id: str
    title_ru: str
    steps: tuple[ProgramStep, ...]

    def step_for(self, test_id: str) -> ProgramStep | None:
        for step in self.steps:
            if step.test_id == test_id:
                return step
        return None

    def all_test_ids(self) -> frozenset[str]:
        return frozenset(s.test_id for s in self.steps)


STANDARD_HR_V1 = TestProgram(
    program_id="standard_hr_v1",
    title_ru="Стандартная программа HR",
    steps=(
        ProgramStep("mbti", label_ru="MBTI"),
        ProgramStep("soft_skills", unlock_after=("mbti",), label_ru="Soft Skills"),
        ProgramStep(
            "paei",
            unlock_after=("soft_skills",),
            parallel_group="personality_bundle",
            label_ru="PAEI (Adizes)",
        ),
        ProgramStep(
            "hexaco",
            unlock_after=("soft_skills",),
            parallel_group="personality_bundle",
            label_ru="HEXACO",
        ),
        ProgramStep(
            "disc",
            unlock_after=("soft_skills",),
            parallel_group="personality_bundle",
            label_ru="DISC",
        ),
    ),
)

PROGRAMS: dict[str, TestProgram] = {
    STANDARD_HR_V1.program_id: STANDARD_HR_V1,
}

DEFAULT_PROGRAM_ID = STANDARD_HR_V1.program_id


def get_program(program_id: str) -> TestProgram:
    prog = PROGRAMS.get(program_id)
    if prog is None:
        raise KeyError(f"Unknown program_id: {program_id}")
    return prog


def list_programs() -> list[TestProgram]:
    return list(PROGRAMS.values())


def completed_set(completed_tests: list[str] | set[str]) -> set[str]:
    return {str(t).strip() for t in completed_tests if str(t).strip()}


def is_step_unlocked(step: ProgramStep, done: set[str]) -> bool:
    return all(req in done for req in step.unlock_after)


def allowed_test_ids(program: TestProgram, done: set[str]) -> list[str]:
    """Tests the employee may start now (parallel steps all listed)."""
    out: list[str] = []
    for step in program.steps:
        if step.test_id in done:
            continue
        if is_step_unlocked(step, done):
            out.append(step.test_id)
    return out


def next_recommended_test(program: TestProgram, done: set[str]) -> str | None:
    allowed = allowed_test_ids(program, done)
    if not allowed:
        return None
    for step in program.steps:
        if step.test_id in allowed:
            return step.test_id
    return allowed[0]


def program_progress(program: TestProgram, done: set[str]) -> dict[str, object]:
    total = len(program.steps)
    completed_count = sum(1 for s in program.steps if s.test_id in done)
    return {
        "program_id": program.program_id,
        "title_ru": program.title_ru,
        "total_steps": total,
        "completed_steps": completed_count,
        "is_complete": completed_count >= total,
        "allowed_test_ids": allowed_test_ids(program, done),
        "next_test_id": next_recommended_test(program, done),
    }
