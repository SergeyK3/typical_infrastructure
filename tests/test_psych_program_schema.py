"""Schema: pt_test_programs templates and assignment step snapshot backfill."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from app.db import engine
from app.migrate import migrate_pt_test_programs_and_assignment_steps
from app.utils import new_id32
from psychological_testing.domain.test_programs import (
    FLEX_TEAM_V1_CODE,
    STANDARD_HR_V1_STEPS_JSON,
    legacy_test_ids_to_step_keys,
)


@pytest.fixture
def psych_schema_db():
    """Minimal DB with pt tables for migration tests."""
    import app.models  # noqa: F401
    from app.db import Base

    Base.metadata.create_all(bind=engine)
    migrate_pt_test_programs_and_assignment_steps()
    yield engine
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM pt_test_assignments"))
        conn.execute(text("DELETE FROM pt_test_programs"))
        conn.commit()


def test_program_templates_seeded(psych_schema_db):
    with psych_schema_db.connect() as conn:
        rows = conn.execute(
            text("SELECT code, steps_json FROM pt_test_programs ORDER BY code")
        ).fetchall()
    codes = [r[0] for r in rows]
    assert "standard_hr_v1" in codes
    assert FLEX_TEAM_V1_CODE in codes

    std_steps = json.loads(next(r[1] for r in rows if r[0] == "standard_hr_v1"))
    assert [s["step_key"] for s in std_steps] == [
        "mbti_1",
        "soft_skills_1",
        "paei_1",
        "hexaco_1",
        "disc_1",
    ]
    assert std_steps[1]["unlock_after"] == ["mbti_1"]

    flex_steps = json.loads(next(r[1] for r in rows if r[0] == FLEX_TEAM_V1_CODE))
    assert flex_steps[0]["step_key"] == "soft_skills_1"
    assert flex_steps[2]["test_id"] == "soft_skills"
    assert flex_steps[2]["step_key"] == "soft_skills_2"
    wave = [s for s in flex_steps if s.get("parallel_group") == "wave_final"]
    assert {s["step_key"] for s in wave} == {"paei_1", "disc_1"}


def test_legacy_test_ids_to_step_keys():
    keys = legacy_test_ids_to_step_keys(STANDARD_HR_V1_STEPS_JSON, {"mbti", "soft_skills"})
    assert keys == ["mbti_1", "soft_skills_1"]


def test_assignment_backfill_from_legacy_fields(psych_schema_db):
    aid = new_id32()
    with psych_schema_db.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO pt_test_assignments (
                    id, client_id, employee_id, program_id, status,
                    completed_tests_json, released_tests_json,
                    steps_snapshot_json, completed_step_keys_json, released_step_keys_json,
                    created_at, updated_at
                ) VALUES (
                    :id, 'c1', 'e1', 'standard_hr_v1', 'in_progress',
                    '["mbti"]', '["mbti", "soft_skills"]',
                    '[]', '[]', '[]',
                    datetime('now'), datetime('now')
                )
                """
            ),
            {"id": aid},
        )
        conn.commit()

    migrate_pt_test_programs_and_assignment_steps()

    with psych_schema_db.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT steps_snapshot_json, completed_step_keys_json, released_step_keys_json
                FROM pt_test_assignments WHERE id = :id
                """
            ),
            {"id": aid},
        ).fetchone()

    snap = json.loads(row[0])
    assert len(snap) == 5
    assert json.loads(row[1]) == ["mbti_1"]
    assert json.loads(row[2]) == ["mbti_1", "soft_skills_1"]
