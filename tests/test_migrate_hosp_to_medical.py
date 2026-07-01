"""Idempotent migration: legacy template_code=hosp → medical."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import text

from app.migrate import migrate_hosp_template_code_to_medical


def _position_catalog_row(template_code: str, position_code: str) -> dict:
    now = datetime.utcnow().isoformat(sep=" ")
    return {
        "template_code": template_code,
        "position_code": position_code,
        "position_name_ru": f"Должность {position_code}",
        "function_code": "ADM",
        "position_level": "SPEC",
        "is_managerial": 0,
        "is_active": 1,
        "sort_order": 0,
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture
def legacy_hosp_medical_db():
    import app.models  # noqa: F401
    from app.db import Base, engine

    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        now = datetime.utcnow().isoformat(sep=" ")
        conn.execute(
            text(
                """
                INSERT INTO enterprise_templates
                    (id, code, name, version, is_active, status, created_at, updated_at)
                VALUES
                    ('tpl_hosp', 'hosp', 'Legacy hosp', '1', 1, 'active', :now, :now),
                    ('tpl_med', 'medical', 'Медицинская организация', '1', 1, 'active', :now, :now)
                """
            ),
            {"now": now},
        )
        row = _position_catalog_row("hosp", "X")
        conn.execute(
            text(
                """
                INSERT INTO position_catalog (
                    template_code, position_code, position_name_ru, function_code,
                    position_level, is_managerial, is_active, sort_order, created_at, updated_at
                ) VALUES (
                    :template_code, :position_code, :position_name_ru, :function_code,
                    :position_level, :is_managerial, :is_active, :sort_order, :created_at, :updated_at
                )
                """
            ),
            row,
        )
        row = _position_catalog_row("medical", "X")
        conn.execute(
            text(
                """
                INSERT INTO position_catalog (
                    template_code, position_code, position_name_ru, function_code,
                    position_level, is_managerial, is_active, sort_order, created_at, updated_at
                ) VALUES (
                    :template_code, :position_code, :position_name_ru, :function_code,
                    :position_level, :is_managerial, :is_active, :sort_order, :created_at, :updated_at
                )
                """
            ),
            row,
        )
        conn.commit()
    yield engine


def test_migrate_hosp_to_medical_skips_duplicate_position_codes(legacy_hosp_medical_db):
    migrate_hosp_template_code_to_medical()
    migrate_hosp_template_code_to_medical()

    with legacy_hosp_medical_db.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT template_code, position_code
                FROM position_catalog
                WHERE position_code = 'X'
                ORDER BY template_code
                """
            )
        ).fetchall()

    assert rows == [("medical", "X")]

    with legacy_hosp_medical_db.connect() as conn:
        hosp_count = conn.execute(
            text("SELECT COUNT(*) FROM position_catalog WHERE template_code = 'hosp'")
        ).scalar()
    assert hosp_count == 0
