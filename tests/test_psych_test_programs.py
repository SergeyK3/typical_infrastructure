"""Program unlock rules for psychological testing assignments."""

from __future__ import annotations

from psychological_testing.domain.test_programs import (
    STANDARD_HR_V1,
    allowed_test_ids,
    completed_set,
    is_step_unlocked,
    next_recommended_test,
)


def test_standard_hr_v1_sequence():
    done = completed_set([])
    assert allowed_test_ids(STANDARD_HR_V1, done) == ["mbti"]
    assert next_recommended_test(STANDARD_HR_V1, done) == "mbti"

    done = completed_set(["mbti"])
    assert allowed_test_ids(STANDARD_HR_V1, done) == ["soft_skills"]

    done = completed_set(["mbti", "soft_skills"])
    allowed = allowed_test_ids(STANDARD_HR_V1, done)
    assert set(allowed) == {"paei", "hexaco", "disc"}

    done = completed_set(["mbti", "soft_skills", "paei", "hexaco", "disc"])
    assert allowed_test_ids(STANDARD_HR_V1, done) == []
    assert next_recommended_test(STANDARD_HR_V1, done) is None


def test_parallel_bundle_unlock_after_soft_skills_only():
    step_paei = STANDARD_HR_V1.step_for("paei")
    assert step_paei is not None
    assert not is_step_unlocked(step_paei, completed_set(["mbti"]))
    assert is_step_unlocked(step_paei, completed_set(["mbti", "soft_skills"]))
