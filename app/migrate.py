r"""Simple schema migrations for MVP (run on startup)."""

from __future__ import annotations

from sqlalchemy import text

from app.db import engine


def _column_exists(table: str, column: str) -> bool:
    with engine.connect() as conn:
        r = conn.execute(text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in r.fetchall())


def _table_exists(table: str) -> bool:
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table},
        )
        return r.fetchone() is not None


def migrate_created_entities() -> None:
    """Add created_entities column to onboarding_runs if missing."""
    if _column_exists("onboarding_runs", "created_entities"):
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE onboarding_runs ADD COLUMN created_entities TEXT NULL"))
        conn.commit()


def migrate_positions_catalog_fields() -> None:
    """Add position catalog fields to positions table."""
    cols = [
        ("position_catalog_code", "TEXT NULL"),
        ("function_code", "TEXT NULL"),
        ("position_level", "TEXT NULL"),
        ("is_managerial", "INTEGER NULL"),
    ]
    if not _table_exists("positions"):
        return
    with engine.connect() as conn:
        for col, typ in cols:
            if _column_exists("positions", col):
                continue
            conn.execute(text(f"ALTER TABLE positions ADD COLUMN {col} {typ}"))
        conn.commit()


def migrate_position_regulations_instructions_folder() -> None:
    """Add instructions_folder_url to position_regulations."""
    if not _table_exists("position_regulations"):
        return
    if _column_exists("position_regulations", "instructions_folder_url"):
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE position_regulations ADD COLUMN instructions_folder_url VARCHAR(512) NULL")
        )
        conn.commit()


def migrate_org_units_catalog_detached() -> None:
    """Происхождение из типового шаблона + флаг отсутствия авто-синхронизации со шаблоном."""
    if not _table_exists("org_units"):
        return
    with engine.connect() as conn:
        if not _column_exists("org_units", "catalog_source_code"):
            conn.execute(text("ALTER TABLE org_units ADD COLUMN catalog_source_code VARCHAR(64) NULL"))
        if not _column_exists("org_units", "is_detached"):
            conn.execute(
                text("ALTER TABLE org_units ADD COLUMN is_detached INTEGER NOT NULL DEFAULT 1")
            )
        conn.commit()


def migrate_kpi_templates_position_code() -> None:
    """Связь шаблона KPI с типовой должностью (фильтр по отделению через position_dept_types)."""
    if not _table_exists("kpi_templates"):
        return
    if _column_exists("kpi_templates", "position_code"):
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE kpi_templates ADD COLUMN position_code VARCHAR(64) NULL"))
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_kpi_templates_position_code ON kpi_templates (position_code)")
        )
        conn.commit()


def migrate_positions_is_detached() -> None:
    """Флаг: штатная позиция не синхронизируется с глобальным position_catalog автоматически."""
    if not _table_exists("positions"):
        return
    if _column_exists("positions", "is_detached"):
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE positions ADD COLUMN is_detached INTEGER NOT NULL DEFAULT 1"))
        conn.commit()


def migrate_employees_telegram_id() -> None:
    if not _table_exists("employees"):
        return
    if _column_exists("employees", "telegram_id"):
        return
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE employees ADD COLUMN telegram_id VARCHAR(128) NULL"))
        conn.commit()


def migrate_pt_assignment_released_tests() -> None:
    """HR-дозированная выдача: какие тесты открыты для сотрудника."""
    if not _table_exists("pt_test_assignments"):
        return
    if _column_exists("pt_test_assignments", "released_tests_json"):
        return
    with engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE pt_test_assignments "
                "ADD COLUMN released_tests_json TEXT NOT NULL DEFAULT '[]'"
            )
        )
        conn.commit()


def run_migrations() -> None:
    migrate_created_entities()
    migrate_positions_catalog_fields()
    migrate_position_regulations_instructions_folder()
    migrate_org_units_catalog_detached()
    migrate_kpi_templates_position_code()
    migrate_positions_is_detached()
    migrate_employees_telegram_id()
    migrate_pt_assignment_released_tests()
