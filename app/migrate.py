r"""Simple schema migrations for MVP (run on startup)."""

from __future__ import annotations

import os

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


def migrate_employee_consent_records() -> None:
    """Таблица единого согласия ПДн на сотрудника + backfill из Part1 и examination."""
    if _table_exists("employee_consent_records"):
        _backfill_employee_consent_records()
        return
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE employee_consent_records (
                    id VARCHAR(32) NOT NULL PRIMARY KEY,
                    client_id VARCHAR(32) NOT NULL,
                    employee_id VARCHAR(32) NOT NULL,
                    consent_type VARCHAR(32) NOT NULL DEFAULT 'pd_processing',
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    document_version VARCHAR(16) NULL,
                    accepted_at DATETIME NULL,
                    declined_at DATETIME NULL,
                    source VARCHAR(32) NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX ix_employee_consent_client_emp_type "
                "ON employee_consent_records (client_id, employee_id, consent_type)"
            )
        )
        conn.commit()
    _backfill_employee_consent_records()


def _backfill_employee_consent_records() -> None:
    """Перенос принятых согласий из Part1 и examination (идемпотентно)."""
    from datetime import datetime

    from app.utils import new_id32

    doc_ver = (os.getenv("TELEGRAM_PD_CONSENT_DOCUMENT_VERSION") or "1.0").strip() or "1.0"
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    def _insert_ignore(client_id: str, employee_id: str, source: str) -> None:
        if not client_id or not employee_id:
            return
        with engine.connect() as conn:
            exists = conn.execute(
                text(
                    """
                    SELECT 1 FROM employee_consent_records
                    WHERE client_id = :c AND employee_id = :e AND consent_type = 'pd_processing'
                    LIMIT 1
                    """
                ),
                {"c": client_id, "e": employee_id},
            ).fetchone()
            if exists:
                return
            conn.execute(
                text(
                    """
                    INSERT INTO employee_consent_records (
                        id, client_id, employee_id, consent_type, status,
                        document_version, accepted_at, declined_at, source,
                        created_at, updated_at
                    ) VALUES (
                        :id, :c, :e, 'pd_processing', 'accepted',
                        :ver, :now, NULL, :src, :now, :now
                    )
                    """
                ),
                {
                    "id": new_id32(),
                    "c": client_id,
                    "e": employee_id,
                    "ver": doc_ver,
                    "now": now,
                    "src": source,
                },
            )
            conn.commit()

    if _table_exists("sa_assessment_sessions"):
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT client_id, employee_id
                    FROM sa_assessment_sessions
                    WHERE docs_survey_pd_consent_status = 'accepted'
                      AND client_id IS NOT NULL AND client_id != ''
                      AND employee_id IS NOT NULL AND employee_id != ''
                    """
                )
            ).fetchall()
        for r in rows:
            _insert_ignore(str(r[0]), str(r[1]), "migrated_part1")

    if _table_exists("sa_examination_sessions"):
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT DISTINCT client_id, employee_id
                    FROM sa_examination_sessions
                    WHERE consent_status = 'accepted'
                      AND client_id IS NOT NULL AND client_id != ''
                      AND employee_id IS NOT NULL AND employee_id != ''
                    """
                )
            ).fetchall()
        for r in rows:
            _insert_ignore(str(r[0]), str(r[1]), "migrated_examination")


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


def migrate_pt_test_programs_and_assignment_steps() -> None:
    """Глобальные шаблоны программ + снимок/step_keys на назначении."""
    import json
    from datetime import datetime

    from psychological_testing.domain.test_programs import (
        PROGRAM_TEMPLATE_SEEDS,
        completed_set,
        dumps_steps_json,
        get_program,
        legacy_released_step_keys_from_snapshot,
        legacy_test_ids_to_step_keys,
    )

    from app.utils import new_id32

    if not _table_exists("pt_test_programs"):
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE pt_test_programs (
                        id VARCHAR(32) NOT NULL PRIMARY KEY,
                        code VARCHAR(64) NOT NULL,
                        title_ru VARCHAR(256) NOT NULL,
                        steps_json TEXT NOT NULL DEFAULT '[]',
                        is_active INTEGER NOT NULL DEFAULT 1,
                        notes VARCHAR(512) NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_pt_test_programs_code "
                    "ON pt_test_programs (code)"
                )
            )
            conn.commit()

    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")
    for code, title_ru, steps, notes in PROGRAM_TEMPLATE_SEEDS:
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pt_test_programs WHERE code = :c LIMIT 1"),
                {"c": code},
            ).fetchone()
            if exists:
                continue
            conn.execute(
                text(
                    """
                    INSERT INTO pt_test_programs (
                        id, code, title_ru, steps_json, is_active, notes,
                        created_at, updated_at
                    ) VALUES (
                        :id, :code, :title, :steps, 1, :notes, :now, :now
                    )
                    """
                ),
                {
                    "id": new_id32(),
                    "code": code,
                    "title": title_ru,
                    "steps": dumps_steps_json(steps),
                    "notes": notes,
                    "now": now,
                },
            )
            conn.commit()

    if not _table_exists("pt_test_assignments"):
        return

    new_cols = (
        ("steps_snapshot_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("completed_step_keys_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("released_step_keys_json", "TEXT NOT NULL DEFAULT '[]'"),
    )
    with engine.connect() as conn:
        for col, typ in new_cols:
            if not _column_exists("pt_test_assignments", col):
                conn.execute(text(f"ALTER TABLE pt_test_assignments ADD COLUMN {col} {typ}"))
        conn.commit()

    templates_by_code: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT code, steps_json FROM pt_test_programs")
        ).fetchall()
    for code, steps_raw in rows:
        try:
            steps = json.loads(steps_raw or "[]")
        except json.JSONDecodeError:
            steps = []
        if isinstance(steps, list):
            templates_by_code[str(code)] = steps

    with engine.connect() as conn:
        assign_rows = conn.execute(
            text(
                """
                SELECT id, program_id, completed_tests_json, released_tests_json,
                       steps_snapshot_json
                FROM pt_test_assignments
                """
            )
        ).fetchall()

    for row in assign_rows:
        aid, program_id, completed_raw, released_raw, snapshot_raw = row
        snapshot_raw = snapshot_raw or "[]"
        if snapshot_raw not in ("", "[]"):
            continue

        steps = templates_by_code.get(str(program_id))
        if not steps:
            try:
                steps = get_program(str(program_id)).to_steps_json()
            except KeyError:
                continue

        done_tests = completed_set(_load_json_string_list(completed_raw))
        released_tests = completed_set(_load_json_string_list(released_raw))
        completed_keys = legacy_test_ids_to_step_keys(steps, done_tests)
        released_keys = legacy_released_step_keys_from_snapshot(
            steps,
            done_tests,
            explicit_released_test_ids=released_tests if released_tests else None,
        )

        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    UPDATE pt_test_assignments
                    SET steps_snapshot_json = :snap,
                        completed_step_keys_json = :done,
                        released_step_keys_json = :rel
                    WHERE id = :id
                    """
                ),
                {
                    "id": aid,
                    "snap": dumps_steps_json(steps),
                    "done": json.dumps(sorted(completed_keys), ensure_ascii=False),
                    "rel": json.dumps(sorted(set(released_keys)), ensure_ascii=False),
                },
            )
            conn.commit()


def _load_json_string_list(raw: str | None) -> list[str]:
    import json

    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict):
        return [str(k) for k in data.keys()]
    return []


def migrate_pt_assignment_test_id() -> None:
    """Один test_id на назначение (без шаблонов программ)."""
    import json

    if not _table_exists("pt_test_assignments"):
        return
    if not _column_exists("pt_test_assignments", "test_id"):
        with engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE pt_test_assignments ADD COLUMN test_id VARCHAR(64) NULL")
            )
            conn.commit()

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, program_id, released_tests_json, released_step_keys_json,
                       steps_snapshot_json
                FROM pt_test_assignments
                WHERE test_id IS NULL OR test_id = ''
                """
            )
        ).fetchall()

    for row_id, program_id, released_tests_raw, released_keys_raw, snapshot_raw in rows:
        tid = None
        try:
            released_tests = json.loads(released_tests_raw or "[]")
            if isinstance(released_tests, list) and released_tests:
                tid = str(released_tests[0]).strip() or None
        except json.JSONDecodeError:
            pass
        if not tid:
            try:
                snapshot = json.loads(snapshot_raw or "[]")
                released_keys = json.loads(released_keys_raw or "[]")
                if isinstance(snapshot, list) and isinstance(released_keys, list) and released_keys:
                    key = str(released_keys[0])
                    for step in snapshot:
                        if isinstance(step, dict) and str(step.get("step_key")) == key:
                            tid = str(step.get("test_id") or "").strip() or None
                            break
                if not tid and isinstance(snapshot, list) and snapshot:
                    first = snapshot[0]
                    if isinstance(first, dict):
                        tid = str(first.get("test_id") or "").strip() or None
            except json.JSONDecodeError:
                pass
        if not tid and program_id and program_id not in ("standard_hr_v1", "flex_team_v1"):
            tid = str(program_id).strip() or None
        if not tid:
            tid = "mbti"
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE pt_test_assignments SET test_id = :t WHERE id = :id"),
                {"t": tid, "id": row_id},
            )
            conn.commit()


def migrate_pt_assignment_completion_history() -> None:
    """completed_at + session_id для истории прохождения тестов."""
    if not _table_exists("pt_test_assignments"):
        return
    with engine.connect() as conn:
        if not _column_exists("pt_test_assignments", "completed_at"):
            conn.execute(
                text("ALTER TABLE pt_test_assignments ADD COLUMN completed_at DATETIME NULL")
            )
        if not _column_exists("pt_test_assignments", "session_id"):
            conn.execute(
                text("ALTER TABLE pt_test_assignments ADD COLUMN session_id VARCHAR(64) NULL")
            )
        if not _column_exists("pt_test_assignments", "due_reminder_sent_at"):
            conn.execute(
                text(
                    "ALTER TABLE pt_test_assignments ADD COLUMN due_reminder_sent_at DATETIME NULL"
                )
            )
        conn.commit()


def migrate_pt_sessions_and_telegram() -> None:
    """Phase 4: pt_test_sessions, telegram bindings, process context."""
    with engine.connect() as conn:
        if not _table_exists("pt_test_sessions"):
            conn.execute(
                text(
                    """
                    CREATE TABLE pt_test_sessions (
                        id VARCHAR(64) PRIMARY KEY,
                        client_id VARCHAR(32) NOT NULL,
                        employee_id VARCHAR(32) NOT NULL,
                        test_id VARCHAR(64) NOT NULL,
                        test_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
                        status VARCHAR(32) NOT NULL DEFAULT 'questioning',
                        assignment_id VARCHAR(32) NULL,
                        telegram_chat_id VARCHAR(32) NULL,
                        delivery_mode VARCHAR(32) NOT NULL DEFAULT 'structured',
                        step_key VARCHAR(64) NULL,
                        started_at DATETIME NULL,
                        completed_at DATETIME NULL,
                        payload_json TEXT NOT NULL DEFAULT '{}',
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pt_sessions_client_employee "
                    "ON pt_test_sessions (client_id, employee_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pt_sessions_telegram_chat "
                    "ON pt_test_sessions (telegram_chat_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pt_sessions_status ON pt_test_sessions (status)"
                )
            )
        if not _table_exists("pt_telegram_bindings"):
            conn.execute(
                text(
                    """
                    CREATE TABLE pt_telegram_bindings (
                        id VARCHAR(36) PRIMARY KEY,
                        telegram_chat_id VARCHAR(32) NOT NULL,
                        client_id VARCHAR(32) NOT NULL,
                        employee_id VARCHAR(32) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_pt_tg_chat "
                    "ON pt_telegram_bindings (telegram_chat_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pt_tg_bindings_chat "
                    "ON pt_telegram_bindings (telegram_chat_id)"
                )
            )
        if not _table_exists("pt_telegram_process_context"):
            conn.execute(
                text(
                    """
                    CREATE TABLE pt_telegram_process_context (
                        id VARCHAR(36) PRIMARY KEY,
                        telegram_chat_id VARCHAR(32) NOT NULL,
                        client_id VARCHAR(32) NULL,
                        employee_id VARCHAR(32) NULL,
                        active_flow VARCHAR(32) NOT NULL DEFAULT 'idle',
                        active_session_id VARCHAR(64) NULL,
                        active_test_id VARCHAR(64) NULL,
                        active_step_key VARCHAR(64) NULL,
                        active_assignment_id VARCHAR(32) NULL,
                        mbti_delivery_mode VARCHAR(32) NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_pt_tg_process_chat "
                    "ON pt_telegram_process_context (telegram_chat_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pt_tg_process_chat "
                    "ON pt_telegram_process_context (telegram_chat_id)"
                )
            )
        conn.commit()


def migrate_enterprise_template_metadata() -> None:
    """Расширение enterprise_templates: status, author, comment, archived_at, cloned_from_id."""
    if not _table_exists("enterprise_templates"):
        return
    cols = [
        ("status", "TEXT NOT NULL DEFAULT 'active'"),
        ("author", "TEXT NULL"),
        ("comment", "TEXT NULL"),
        ("archived_at", "TEXT NULL"),
        ("cloned_from_id", "TEXT NULL"),
    ]
    with engine.connect() as conn:
        for col, typ in cols:
            if _column_exists("enterprise_templates", col):
                continue
            conn.execute(text(f"ALTER TABLE enterprise_templates ADD COLUMN {col} {typ}"))
            conn.commit()


def migrate_position_regulations_template_scope() -> None:
    """Убрать глобальный UNIQUE(regulation_code); уникальность в рамках template_code."""
    if not _table_exists("position_regulations"):
        return
    if not _column_exists("position_regulations", "template_code"):
        return
    with engine.connect() as conn:
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='position_regulations'")
        ).scalar()
        if not ddl or "UNIQUE (regulation_code)" not in ddl.replace("\n", " "):
            # Уже пересобрано или схема без устаревшего ограничения
            idx = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='position_regulations' AND sql LIKE '%template_code%regulation_code%'"
                )
            ).fetchone()
            if idx:
                return
        conn.execute(
            text(
                """
                CREATE TABLE position_regulations_new (
                    id VARCHAR(32) NOT NULL,
                    template_code VARCHAR(64) NOT NULL DEFAULT 'default',
                    regulation_code VARCHAR(64) NOT NULL,
                    position_code VARCHAR(64) NOT NULL,
                    dept_type_code VARCHAR(32) NOT NULL,
                    regulation_name VARCHAR(256) NOT NULL,
                    goal_summary VARCHAR(512),
                    ckp_short VARCHAR(512),
                    ckp_full TEXT,
                    google_doc_url VARCHAR(512),
                    instructions_folder_url VARCHAR(512),
                    version_no VARCHAR(16) NOT NULL,
                    status VARCHAR(16) NOT NULL,
                    effective_from DATE,
                    effective_to DATE,
                    is_current BOOLEAN NOT NULL,
                    owner_unit_code VARCHAR(64),
                    notes VARCHAR(512),
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO position_regulations_new (
                    id, template_code, regulation_code, position_code, dept_type_code,
                    regulation_name, goal_summary, ckp_short, ckp_full,
                    google_doc_url, instructions_folder_url, version_no, status,
                    effective_from, effective_to, is_current, owner_unit_code,
                    notes, created_at, updated_at
                )
                SELECT
                    id, template_code, regulation_code, position_code, dept_type_code,
                    regulation_name, goal_summary, ckp_short, ckp_full,
                    google_doc_url, instructions_folder_url, version_no, status,
                    effective_from, effective_to, is_current, owner_unit_code,
                    notes, created_at, updated_at
                FROM position_regulations
                """
            )
        )
        conn.execute(text("DROP TABLE position_regulations"))
        conn.execute(text("ALTER TABLE position_regulations_new RENAME TO position_regulations"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_position_regulations_tpl_code "
                "ON position_regulations (template_code, regulation_code)"
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_position_regulations_unique "
                "ON position_regulations (template_code, position_code, dept_type_code, version_no)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_position_regulations_current "
                "ON position_regulations (template_code, position_code, dept_type_code, is_current)"
            )
        )
        conn.commit()


def migrate_template_code_bundle() -> None:
    """Добавить template_code к bundle-справочникам и пересобрать PK где нужно."""
    if not _table_exists("position_catalog"):
        return

    def _rebuild_position_catalog() -> None:
        if _column_exists("position_catalog", "template_code"):
            return
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE position_catalog_new (
                        template_code VARCHAR(64) NOT NULL DEFAULT 'default',
                        position_code VARCHAR(64) NOT NULL,
                        position_name_ru VARCHAR(256) NOT NULL,
                        position_name_en VARCHAR(256) NULL,
                        function_code VARCHAR(32) NOT NULL,
                        position_level VARCHAR(16) NOT NULL DEFAULT 'SPEC',
                        is_managerial INTEGER NOT NULL DEFAULT 0,
                        position_family VARCHAR(64) NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        default_regulation_code VARCHAR(64) NULL,
                        notes VARCHAR(512) NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (template_code, position_code)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO position_catalog_new (
                        template_code, position_code, position_name_ru, position_name_en,
                        function_code, position_level, is_managerial, position_family,
                        is_active, default_regulation_code, notes, created_at, updated_at
                    )
                    SELECT 'default', position_code, position_name_ru, position_name_en,
                           function_code, position_level, is_managerial, position_family,
                           is_active, default_regulation_code, notes, created_at, updated_at
                    FROM position_catalog
                    """
                )
            )
            conn.execute(text("DROP TABLE position_catalog"))
            conn.execute(text("ALTER TABLE position_catalog_new RENAME TO position_catalog"))
            conn.commit()

    def _rebuild_position_dept_types() -> None:
        if _column_exists("position_dept_types", "template_code"):
            return
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE position_dept_types_new (
                        template_code VARCHAR(64) NOT NULL DEFAULT 'default',
                        position_code VARCHAR(64) NOT NULL,
                        dept_type_code VARCHAR(32) NOT NULL,
                        is_primary INTEGER NOT NULL DEFAULT 1,
                        PRIMARY KEY (template_code, position_code, dept_type_code)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO position_dept_types_new (template_code, position_code, dept_type_code, is_primary)
                    SELECT 'default', position_code, dept_type_code, is_primary FROM position_dept_types
                    """
                )
            )
            conn.execute(text("DROP TABLE position_dept_types"))
            conn.execute(text("ALTER TABLE position_dept_types_new RENAME TO position_dept_types"))
            conn.commit()

    def _rebuild_kpi_templates() -> None:
        if not _table_exists("kpi_templates"):
            return
        if _column_exists("kpi_templates", "template_code"):
            return
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE kpi_templates_new (
                        template_code VARCHAR(64) NOT NULL DEFAULT 'default',
                        kpi_code VARCHAR(64) NOT NULL,
                        kpi_name VARCHAR(256) NOT NULL,
                        unit VARCHAR(32) NOT NULL DEFAULT '%',
                        period_type VARCHAR(16) NOT NULL DEFAULT 'month',
                        formula_or_rule VARCHAR(512) NULL,
                        default_target REAL NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        position_code VARCHAR(64) NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        PRIMARY KEY (template_code, kpi_code)
                    )
                    """
                )
            )
            cols = "kpi_code, kpi_name, unit, period_type, formula_or_rule, default_target, is_active, created_at, updated_at"
            if _column_exists("kpi_templates", "position_code"):
                cols += ", position_code"
                sel = (
                    "'default', kpi_code, kpi_name, unit, period_type, formula_or_rule, "
                    "default_target, is_active, created_at, updated_at, position_code"
                )
            else:
                sel = (
                    "'default', kpi_code, kpi_name, unit, period_type, formula_or_rule, "
                    "default_target, is_active, created_at, updated_at"
                )
            conn.execute(
                text(
                    f"INSERT INTO kpi_templates_new (template_code, {cols}) "
                    f"SELECT {sel} FROM kpi_templates"
                )
            )
            conn.execute(text("DROP TABLE kpi_templates"))
            conn.execute(text("ALTER TABLE kpi_templates_new RENAME TO kpi_templates"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_kpi_templates_position_code "
                    "ON kpi_templates (position_code)"
                )
            )
            conn.commit()

    def _add_template_code_column(table: str) -> None:
        if not _table_exists(table):
            return
        if _column_exists(table, "template_code"):
            return
        with engine.connect() as conn:
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN template_code VARCHAR(64) NOT NULL DEFAULT 'default'")
            )
            conn.execute(text(f"UPDATE {table} SET template_code = 'default' WHERE template_code IS NULL OR template_code = ''"))
            conn.commit()

    _rebuild_position_catalog()
    _rebuild_position_dept_types()
    _rebuild_kpi_templates()
    _add_template_code_column("position_regulations")
    _add_template_code_column("regulation_kpis")
    _add_template_code_column("regulation_instructions")
    _add_template_code_column("sa_competency_catalog_versions")
    _add_template_code_column("sa_competency_skill_definitions")

    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE sa_competency_catalog_versions SET template_code = 'default' "
                "WHERE client_id IS NULL AND (template_code IS NULL OR template_code = '')"
            )
        )
        conn.execute(
            text(
                "UPDATE sa_competency_skill_definitions SET template_code = 'default' "
                "WHERE client_id IS NULL AND (template_code IS NULL OR template_code = '')"
            )
        )
        conn.commit()


def migrate_competency_skill_definitions_template_scope() -> None:
    """Убрать глобальный UNIQUE(skill_code); уникальность в рамках template_code."""
    if not _table_exists("sa_competency_skill_definitions"):
        return
    if not _column_exists("sa_competency_skill_definitions", "template_code"):
        return
    with engine.connect() as conn:
        ddl = conn.execute(
            text(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                "AND name='sa_competency_skill_definitions'"
            )
        ).scalar()
        if not ddl:
            return
        ddl_norm = ddl.replace("\n", " ")
        if "UNIQUE (skill_code)" not in ddl_norm and "UNIQUE (template_code, skill_code)" in ddl_norm:
            return
        if "uq_sa_csd_tpl_skill_code" in ddl_norm:
            return
        idx = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='sa_competency_skill_definitions' "
                "AND sql LIKE '%template_code%skill_code%'"
            )
        ).fetchone()
        if idx and "UNIQUE (skill_code)" not in ddl_norm:
            return
        conn.execute(
            text(
                """
                CREATE TABLE sa_competency_skill_definitions_new (
                    id VARCHAR(36) NOT NULL,
                    client_id VARCHAR(32),
                    template_code VARCHAR(64) NOT NULL DEFAULT 'default',
                    skill_code VARCHAR(64) NOT NULL,
                    title_ru VARCHAR(512) NOT NULL,
                    description TEXT,
                    is_active BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_sa_csd_tpl_skill_code UNIQUE (template_code, skill_code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO sa_competency_skill_definitions_new (
                    id, client_id, template_code, skill_code, title_ru,
                    description, is_active, created_at, updated_at
                )
                SELECT
                    id, client_id, template_code, skill_code, title_ru,
                    description, is_active, created_at, updated_at
                FROM sa_competency_skill_definitions
                """
            )
        )
        conn.execute(text("DROP TABLE sa_competency_skill_definitions"))
        conn.execute(
            text("ALTER TABLE sa_competency_skill_definitions_new RENAME TO sa_competency_skill_definitions")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_sa_competency_skill_definitions_skill_code "
                "ON sa_competency_skill_definitions (skill_code)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_sa_competency_skill_definitions_client_id "
                "ON sa_competency_skill_definitions (client_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_sa_competency_skill_definitions_is_active "
                "ON sa_competency_skill_definitions (is_active)"
            )
        )
        conn.commit()


def migrate_template_org_units_log_group() -> None:
    """Логическая группа (log_group) для отделений и секций типового шаблона оргструктуры."""
    if not _table_exists("template_org_units"):
        return
    if _column_exists("template_org_units", "log_group"):
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE template_org_units ADD COLUMN log_group VARCHAR(64) NULL")
        )
        conn.commit()


def migrate_position_catalog_sort_order() -> None:
    """Индекс сортировки для типовых должностей в глобальном каталоге."""
    if not _table_exists("position_catalog"):
        return
    if _column_exists("position_catalog", "sort_order"):
        return
    with engine.connect() as conn:
        conn.execute(
            text("ALTER TABLE position_catalog ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
        )
        conn.commit()


def migrate_org_unit_name_casing() -> None:
    """Привести названия отделений (UPPER) и секций (Sentence case) в оргструктурах."""
    from app.db import SessionLocal
    from app.models import OrgUnit, TemplateOrgUnitRow
    from app.org_unit_ops import format_org_unit_name
    from sqlalchemy import select

    if not _table_exists("org_units") and not _table_exists("template_org_units"):
        return
    db = SessionLocal()
    try:
        if _table_exists("template_org_units"):
            for row in db.scalars(select(TemplateOrgUnitRow)).all():
                formatted = format_org_unit_name(row.name, row.unit_type)
                if formatted != row.name:
                    row.name = formatted
        if _table_exists("org_units"):
            for row in db.scalars(select(OrgUnit)).all():
                formatted = format_org_unit_name(row.name, row.unit_type)
                if formatted != row.name:
                    row.name = formatted
        db.commit()
    finally:
        db.close()


def migrate_normalize_position_dept_links() -> None:
    """Одна primary-связь должность↔отделение в каждом шаблоне (убирает дубли вроде MAIN_NURSE×6)."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import EnterpriseTemplate
    from app.position_deploy import normalize_template_position_dept_links

    db = SessionLocal()
    try:
        codes = db.scalars(
            select(EnterpriseTemplate.code).where(EnterpriseTemplate.is_active == True)
        ).all()
        for code in codes:
            normalize_template_position_dept_links(db, code)
        db.commit()
    finally:
        db.close()


def run_migrations() -> None:
    migrate_created_entities()
    migrate_positions_catalog_fields()
    migrate_position_regulations_instructions_folder()
    migrate_org_units_catalog_detached()
    migrate_enterprise_template_metadata()
    migrate_kpi_templates_position_code()
    migrate_positions_is_detached()
    migrate_employees_telegram_id()
    migrate_employee_consent_records()
    migrate_pt_assignment_released_tests()
    migrate_pt_test_programs_and_assignment_steps()
    migrate_pt_assignment_test_id()
    migrate_pt_assignment_completion_history()
    migrate_pt_sessions_and_telegram()
    migrate_template_code_bundle()
    migrate_position_regulations_template_scope()
    migrate_competency_skill_definitions_template_scope()
    migrate_template_org_units_log_group()
    migrate_position_catalog_sort_order()
    migrate_org_unit_name_casing()
    migrate_normalize_position_dept_links()
