# PROJ-PERSON — Stage 1 Implementation Record

| Поле | Значение |
|------|----------|
| **Stage** | 1 — Person без потребителей |
| **Дата** | 2026-06-30 |
| **Assessment** | [PROJ-PERSON-assessment.md](./PROJ-PERSON-assessment.md) |

## Delivered

- SQLAlchemy model `Person` in `app/models.py`
- SQLite table `persons` via `create_all` and idempotent `migrate_persons()` in `app/migrate.py`
- Tests in `tests/test_person_foundation.py`

## Explicitly out of scope (Stage 1)

- `Employee.person_id`, backfill, NOT NULL on link
- `/api/persons`, UI changes, field migration from Employee
- Auth, Account, Telegram, HR modules
- Accepted ADR, Glossary, Roadmap changes

## Next stage

Stage 2: nullable `Employee.person_id`, atomic Person+Employee create, backfill (after physical model / migration policy confirmed per assessment).
