"""Program unlock rules for psychological testing assignments (step_key engine)."""

from __future__ import annotations

from psychological_testing.domain.test_programs import (
    FLEX_TEAM_V1,
    STANDARD_HR_V1,
    allowed_step_keys,
    allowed_test_ids,
    completed_set,
    is_step_unlocked,
    next_recommended_step_key,
    pending_hr_release_step_keys,
)


def test_standard_hr_v1_sequence():
    done = completed_set([])
    assert allowed_step_keys(STANDARD_HR_V1, done) == ["mbti_1"]
    assert next_recommended_step_key(STANDARD_HR_V1, done) == "mbti_1"
    assert allowed_test_ids(STANDARD_HR_V1, done) == ["mbti"]

    done = completed_set(["mbti_1"])
    assert allowed_step_keys(STANDARD_HR_V1, done) == ["soft_skills_1"]
    assert allowed_test_ids(STANDARD_HR_V1, done) == ["soft_skills"]

    done = completed_set(["mbti_1", "soft_skills_1"])
    allowed = allowed_step_keys(STANDARD_HR_V1, done)
    assert set(allowed) == {"paei_1", "hexaco_1", "disc_1"}

    done = completed_set(["mbti_1", "soft_skills_1", "paei_1", "hexaco_1", "disc_1"])
    assert allowed_step_keys(STANDARD_HR_V1, done) == []
    assert next_recommended_step_key(STANDARD_HR_V1, done) is None


def test_parallel_bundle_unlock_after_soft_skills_only():
    step_paei = STANDARD_HR_V1.step_for_key("paei_1")
    assert step_paei is not None
    assert not is_step_unlocked(step_paei, completed_set(["mbti_1"]))
    assert is_step_unlocked(step_paei, completed_set(["mbti_1", "soft_skills_1"]))


def test_flex_team_repeat_soft_skills():
    done = completed_set([])
    released = completed_set(["soft_skills_1"])
    assert allowed_step_keys(FLEX_TEAM_V1, done, released_keys=released) == ["soft_skills_1"]

    done = completed_set(["soft_skills_1", "hexaco_1"])
    released = completed_set(["soft_skills_1", "hexaco_1", "soft_skills_2"])
    assert allowed_step_keys(FLEX_TEAM_V1, done, released_keys=released) == ["soft_skills_2"]
    assert allowed_test_ids(FLEX_TEAM_V1, done, released_keys=released) == ["soft_skills"]

    done = completed_set(["soft_skills_1", "hexaco_1", "soft_skills_2", "mbti_1"])
    released = completed_set(["soft_skills_1", "hexaco_1", "soft_skills_2", "mbti_1"])
    pending = pending_hr_release_step_keys(FLEX_TEAM_V1, done, released)
    assert set(pending) == {"paei_1", "disc_1"}


def test_hr_release_gate_standard_hr():
    done = completed_set(["mbti_1"])
    released = completed_set(["mbti_1"])
    assert allowed_step_keys(STANDARD_HR_V1, done, released_keys=released) == []
    assert pending_hr_release_step_keys(STANDARD_HR_V1, done, released) == ["soft_skills_1"]
