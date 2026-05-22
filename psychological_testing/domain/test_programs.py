"""HR test programs: step order and unlock rules (Phase 4a)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProgramStep:
    step_key: str
    test_id: str
    unlock_after: tuple[str, ...] = ()
    parallel_group: str | None = None
    label_ru: str | None = None


@dataclass(frozen=True)
class TestProgram:
    program_id: str
    title_ru: str
    steps: tuple[ProgramStep, ...]

    @classmethod
    def from_steps_json(
        cls,
        steps: list[dict[str, Any]],
        *,
        program_id: str,
        title_ru: str,
    ) -> TestProgram:
        parsed: list[ProgramStep] = []
        for raw in steps:
            parsed.append(
                ProgramStep(
                    step_key=str(raw["step_key"]),
                    test_id=str(raw["test_id"]),
                    unlock_after=tuple(str(u) for u in (raw.get("unlock_after") or [])),
                    parallel_group=raw.get("parallel_group"),
                    label_ru=raw.get("label_ru"),
                )
            )
        return cls(program_id=program_id, title_ru=title_ru, steps=tuple(parsed))

    def to_steps_json(self) -> list[dict[str, Any]]:
        return [
            {
                "step_key": s.step_key,
                "test_id": s.test_id,
                "label_ru": s.label_ru or s.test_id,
                "unlock_after": list(s.unlock_after),
                "parallel_group": s.parallel_group,
            }
            for s in self.steps
        ]

    def step_for_key(self, step_key: str) -> ProgramStep | None:
        for step in self.steps:
            if step.step_key == step_key:
                return step
        return None

    def step_for(self, test_id: str) -> ProgramStep | None:
        """First step with ``test_id`` (legacy; ambiguous when test repeats)."""
        for step in self.steps:
            if step.test_id == test_id:
                return step
        return None

    def all_test_ids(self) -> frozenset[str]:
        return frozenset(s.test_id for s in self.steps)

    def all_step_keys(self) -> frozenset[str]:
        return frozenset(s.step_key for s in self.steps)


STANDARD_HR_V1 = TestProgram(
    program_id="standard_hr_v1",
    title_ru="Стандартная программа HR",
    steps=(
        ProgramStep("mbti_1", "mbti", label_ru="MBTI"),
        ProgramStep(
            "soft_skills_1",
            "soft_skills",
            unlock_after=("mbti_1",),
            label_ru="Soft Skills",
        ),
        ProgramStep(
            "paei_1",
            "paei",
            unlock_after=("soft_skills_1",),
            parallel_group="personality_bundle",
            label_ru="PAEI (Adizes)",
        ),
        ProgramStep(
            "hexaco_1",
            "hexaco",
            unlock_after=("soft_skills_1",),
            parallel_group="personality_bundle",
            label_ru="HEXACO",
        ),
        ProgramStep(
            "disc_1",
            "disc",
            unlock_after=("soft_skills_1",),
            parallel_group="personality_bundle",
            label_ru="DISC",
        ),
    ),
)

PROGRAMS: dict[str, TestProgram] = {
    STANDARD_HR_V1.program_id: STANDARD_HR_V1,
}

DEFAULT_PROGRAM_ID = STANDARD_HR_V1.program_id

STANDARD_HR_V1_STEPS_JSON = STANDARD_HR_V1.to_steps_json()

FLEX_TEAM_V1_CODE = "flex_team_v1"
FLEX_TEAM_V1 = TestProgram.from_steps_json(
    [
        {
            "step_key": "soft_skills_1",
            "test_id": "soft_skills",
            "label_ru": "Soft Skills (1-й этап)",
            "unlock_after": [],
            "parallel_group": None,
        },
        {
            "step_key": "hexaco_1",
            "test_id": "hexaco",
            "label_ru": "HEXACO",
            "unlock_after": ["soft_skills_1"],
            "parallel_group": None,
        },
        {
            "step_key": "soft_skills_2",
            "test_id": "soft_skills",
            "label_ru": "Soft Skills (2-й этап)",
            "unlock_after": ["hexaco_1"],
            "parallel_group": None,
        },
        {
            "step_key": "mbti_1",
            "test_id": "mbti",
            "label_ru": "MBTI",
            "unlock_after": ["soft_skills_2"],
            "parallel_group": None,
        },
        {
            "step_key": "paei_1",
            "test_id": "paei",
            "label_ru": "PAEI (Adizes)",
            "unlock_after": ["mbti_1"],
            "parallel_group": "wave_final",
        },
        {
            "step_key": "disc_1",
            "test_id": "disc",
            "label_ru": "DISC",
            "unlock_after": ["mbti_1"],
            "parallel_group": "wave_final",
        },
    ],
    program_id=FLEX_TEAM_V1_CODE,
    title_ru="Гибкая программа (Soft Skills ×2, HEXACO, MBTI, PAEI+DISC)",
)
FLEX_TEAM_V1_STEPS_JSON = FLEX_TEAM_V1.to_steps_json()

PROGRAM_TEMPLATE_SEEDS: tuple[tuple[str, str, list[dict[str, Any]], str | None], ...] = (
    (STANDARD_HR_V1.program_id, STANDARD_HR_V1.title_ru, STANDARD_HR_V1_STEPS_JSON, None),
    (
        FLEX_TEAM_V1_CODE,
        FLEX_TEAM_V1.title_ru,
        FLEX_TEAM_V1_STEPS_JSON,
        "Пример повторов test_id и параллельной финальной волны",
    ),
)


def program_to_steps_json(program: TestProgram) -> list[dict[str, Any]]:
    """Alias for ``TestProgram.to_steps_json`` (seed / migration)."""
    return program.to_steps_json()


def legacy_test_ids_to_step_keys(steps: list[dict[str, Any]], test_ids: set[str]) -> list[str]:
    """Map legacy completed/released test_id sets to step_key (1:1 per test_id in snapshot)."""
    key_by_test = {str(s["test_id"]): str(s["step_key"]) for s in steps}
    return sorted(key_by_test[t] for t in test_ids if t in key_by_test)


def legacy_released_step_keys_from_snapshot(
    steps: list[dict[str, Any]],
    done_test_ids: set[str],
    *,
    explicit_released_test_ids: set[str] | None = None,
) -> list[str]:
    """Backfill released_step_keys from legacy test_id columns (empty released = auto-unlock)."""
    done_keys = set(legacy_test_ids_to_step_keys(steps, done_test_ids))
    if explicit_released_test_ids:
        return sorted(
            set(legacy_test_ids_to_step_keys(steps, explicit_released_test_ids))
        )
    keys = set(done_keys)
    for step in steps:
        step_key = str(step["step_key"])
        if step_key in done_keys:
            continue
        unlock = [str(u) for u in (step.get("unlock_after") or [])]
        if all(u in done_keys for u in unlock):
            keys.add(step_key)
    return sorted(keys)


def dumps_steps_json(steps: list[dict[str, Any]]) -> str:
    return json.dumps(steps, ensure_ascii=False)


def parse_steps_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw or raw == "[]":
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def get_program(program_id: str) -> TestProgram:
    prog = PROGRAMS.get(program_id)
    if prog is None:
        raise KeyError(f"Unknown program_id: {program_id}")
    return prog


def list_programs() -> list[TestProgram]:
    return list(PROGRAMS.values())


def completed_set(completed: list[str] | set[str]) -> set[str]:
    return {str(t).strip() for t in completed if str(t).strip()}


def is_step_unlocked(step: ProgramStep, done_keys: set[str]) -> bool:
    return all(req in done_keys for req in step.unlock_after)


def allowed_step_keys(
    program: TestProgram,
    done_keys: set[str],
    *,
    released_keys: set[str] | None = None,
) -> list[str]:
    """Steps the employee may start now (parallel steps all listed).

    ``released_keys=None`` — без HR-гейтинга (legacy / свободный режим).
    """
    out: list[str] = []
    for step in program.steps:
        if step.step_key in done_keys:
            continue
        if not is_step_unlocked(step, done_keys):
            continue
        if released_keys is not None and step.step_key not in released_keys:
            continue
        out.append(step.step_key)
    return out


def pending_hr_release_step_keys(
    program: TestProgram,
    done_keys: set[str],
    released_keys: set[str],
) -> list[str]:
    """Steps with satisfied prerequisites, но HR ещё не открыл доступ."""
    out: list[str] = []
    for step in program.steps:
        if step.step_key in done_keys or step.step_key in released_keys:
            continue
        if is_step_unlocked(step, done_keys):
            out.append(step.step_key)
    return out


def next_recommended_step_key(
    program: TestProgram,
    done_keys: set[str],
    *,
    released_keys: set[str] | None = None,
) -> str | None:
    allowed = allowed_step_keys(program, done_keys, released_keys=released_keys)
    if not allowed:
        return None
    for step in program.steps:
        if step.step_key in allowed:
            return step.step_key
    return allowed[0]


def step_summary(program: TestProgram, step_key: str) -> dict[str, str]:
    step = program.step_for_key(step_key)
    if step is None:
        return {"step_key": step_key, "test_id": step_key, "label_ru": step_key}
    return {
        "step_key": step.step_key,
        "test_id": step.test_id,
        "label_ru": step.label_ru or step.test_id,
    }


def step_keys_to_test_ids(program: TestProgram, step_keys: list[str]) -> list[str]:
    out: list[str] = []
    for key in step_keys:
        step = program.step_for_key(key)
        if step is not None:
            out.append(step.test_id)
    return out


def allowed_test_ids(
    program: TestProgram,
    done_keys: set[str],
    *,
    released_keys: set[str] | None = None,
) -> list[str]:
    """Derived test_id list for Telegram/API backward compatibility."""
    return step_keys_to_test_ids(
        program, allowed_step_keys(program, done_keys, released_keys=released_keys)
    )


def pending_hr_release_test_ids(
    program: TestProgram,
    done_keys: set[str],
    released_keys: set[str],
) -> list[str]:
    return step_keys_to_test_ids(
        program, pending_hr_release_step_keys(program, done_keys, released_keys)
    )


def next_recommended_test(
    program: TestProgram,
    done_keys: set[str],
    *,
    released_keys: set[str] | None = None,
) -> str | None:
    key = next_recommended_step_key(program, done_keys, released_keys=released_keys)
    if key is None:
        return None
    step = program.step_for_key(key)
    return step.test_id if step else None


def resolve_step_key_for_test(
    program: TestProgram,
    test_id: str,
    done_keys: set[str],
    *,
    released_keys: set[str] | None = None,
    step_key: str | None = None,
) -> str | None:
    if step_key:
        step = program.step_for_key(step_key)
        if step is None or step.test_id != test_id:
            return None
        if step_key in done_keys:
            return None
        allowed = allowed_step_keys(program, done_keys, released_keys=released_keys)
        return step_key if step_key in allowed else None
    allowed = allowed_step_keys(program, done_keys, released_keys=released_keys)
    matches = [k for k in allowed if program.step_for_key(k) and program.step_for_key(k).test_id == test_id]
    if len(matches) == 1:
        return matches[0]
    return None


def program_progress(
    program: TestProgram,
    done_keys: set[str],
    *,
    released_keys: set[str] | None = None,
) -> dict[str, object]:
    total = len(program.steps)
    completed_count = sum(1 for s in program.steps if s.step_key in done_keys)
    rel = released_keys if released_keys is not None else None
    allowed_keys = allowed_step_keys(program, done_keys, released_keys=rel)
    pending_keys = (
        pending_hr_release_step_keys(program, done_keys, released_keys)
        if released_keys is not None
        else []
    )
    next_key = next_recommended_step_key(program, done_keys, released_keys=rel)
    next_step = program.step_for_key(next_key) if next_key else None
    completed_test_ids = sorted(
        {s.test_id for s in program.steps if s.step_key in done_keys}
    )
    released_test_ids = (
        sorted({program.step_for_key(k).test_id for k in released_keys if program.step_for_key(k)})
        if released_keys is not None
        else None
    )
    return {
        "program_id": program.program_id,
        "title_ru": program.title_ru,
        "total_steps": total,
        "completed_step_count": completed_count,
        "is_complete": completed_count >= total,
        "allowed_step_keys": allowed_keys,
        "allowed_test_ids": step_keys_to_test_ids(program, allowed_keys),
        "next_step_key": next_key,
        "next_test_id": next_step.test_id if next_step else None,
        "released_step_keys": sorted(released_keys) if released_keys is not None else None,
        "released_test_ids": released_test_ids,
        "pending_hr_release_step_keys": pending_keys,
        "pending_hr_release_test_ids": step_keys_to_test_ids(program, pending_keys),
        "pending_hr_release_steps": [step_summary(program, k) for k in pending_keys],
        "needs_hr_release": bool(pending_keys),
        "completed_step_keys": sorted(done_keys),
        "completed_tests": completed_test_ids,
    }
