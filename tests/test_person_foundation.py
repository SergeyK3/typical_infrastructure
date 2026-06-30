"""PROJ-PERSON Stage 1: Person foundation (model, schema, migration)."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text

from app.db import SessionLocal, engine
from app.migrate import migrate_persons
from app.models import Person
from app.utils import new_id32


@pytest.fixture
def person_db():
    import app.models  # noqa: F401
    from app.db import Base

    Base.metadata.create_all(bind=engine)
    migrate_persons()
    yield engine


def test_person_model_exists():
    assert Person.__tablename__ == "persons"
    mapper = inspect(Person)
    column_names = {c.key for c in mapper.columns}
    assert column_names == {
        "id",
        "client_id",
        "last_name",
        "first_name",
        "middle_name",
        "email",
        "phone",
        "telegram_id",
        "created_at",
        "updated_at",
    }


def test_persons_table_created(person_db):
    insp = inspect(person_db)
    assert insp.has_table("persons")
    cols = {c["name"]: c for c in insp.get_columns("persons")}
    assert cols["client_id"]["nullable"] is False
    assert cols["last_name"]["nullable"] is False
    assert cols["first_name"]["nullable"] is False
    assert cols["middle_name"]["nullable"] is True
    assert cols["email"]["nullable"] is True
    assert cols["phone"]["nullable"] is True
    assert cols["telegram_id"]["nullable"] is True


def test_person_required_fields_enforced(person_db):
    with person_db.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO persons (id, client_id, first_name, created_at, updated_at)
                    VALUES ('p_no_ln', 'c1', 'Ivan', datetime('now'), datetime('now'))
                    """
                )
            )
            conn.commit()
        conn.rollback()
        with pytest.raises(Exception):
            conn.execute(
                text(
                    """
                    INSERT INTO persons (id, client_id, last_name, created_at, updated_at)
                    VALUES ('p_no_fn', 'c1', 'Ivanov', datetime('now'), datetime('now'))
                    """
                )
            )
            conn.commit()


def test_person_nullable_fields_allow_null(person_db):
    db = SessionLocal()
    try:
        p = Person(
            id=new_id32(),
            client_id="c_nullable",
            last_name="Ivanov",
            first_name="Ivan",
            middle_name=None,
            email=None,
            phone=None,
            telegram_id=None,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        assert p.middle_name is None
        assert p.email is None
        assert p.phone is None
        assert p.telegram_id is None
    finally:
        db.close()


def test_migrate_persons_idempotent(person_db):
    migrate_persons()
    migrate_persons()
    with person_db.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='persons'")
        ).scalar()
    assert count == 1


def test_employees_table_unchanged_by_person_migration(person_db):
    insp = inspect(person_db)
    assert insp.has_table("employees")
    emp_cols = {c["name"] for c in insp.get_columns("employees")}
    assert "person_id" not in emp_cols


def test_person_migration_and_metadata_create_all_are_compatible():
    """migrate_persons → create_all (как legacy DB + startup) не конфликтуют."""
    import app.models  # noqa: F401
    from app.db import Base

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS persons"))
        conn.commit()

    migrate_persons()
    migrate_persons()
    migrate_persons()

    Base.metadata.create_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    insp = inspect(engine)
    assert insp.has_table("persons")
    assert insp.has_table("employees")
    persons_cols = {c["name"]: c for c in insp.get_columns("persons")}
    assert set(persons_cols) == {
        "id",
        "client_id",
        "last_name",
        "first_name",
        "middle_name",
        "email",
        "phone",
        "telegram_id",
        "created_at",
        "updated_at",
    }
    assert persons_cols["client_id"]["nullable"] is False
    assert persons_cols["last_name"]["nullable"] is False
    assert persons_cols["first_name"]["nullable"] is False
    assert persons_cols["middle_name"]["nullable"] is True
    emp_cols = {c["name"] for c in insp.get_columns("employees")}
    assert "person_id" not in emp_cols
