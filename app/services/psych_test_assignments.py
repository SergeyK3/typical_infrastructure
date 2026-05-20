"""Psychological testing assignments (Phase 4a): DB + program unlock + Telegram notify."""

from __future__ import annotations

import json
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.business_days import default_assignment_due_at
from app.models import Employee, PtTestAssignment
from app.utils import new_id32
from psychological_testing.adapters.telegram_outbound import get_telegram_outbound
from psychological_testing.integration.session_repository import (
    latest_telegram_chat_for_employee,
)
from psychological_testing.domain.test_programs import (
    DEFAULT_PROGRAM_ID,
    allowed_test_ids,
    completed_set,
    get_program,
    list_programs,
    next_recommended_test,
    program_progress,
)

ACTIVE_STATUSES = frozenset({"scheduled", "notified", "in_progress"})
TERMINAL_STATUSES = frozenset({"completed", "cancelled"})


class NotifyTelegramError(Exception):
    """Structured notify failure for API layer."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        stored_telegram_id: str | None = None,
        session_telegram_chat_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.stored_telegram_id = stored_telegram_id
        self.session_telegram_chat_id = session_telegram_chat_id


def normalize_telegram_chat_id(raw: str) -> str:
    """Strip whitespace; keep numeric chat_id or @username as entered."""
    return str(raw or "").strip()


def _ensure_row_due_at(db: Session, row: PtTestAssignment) -> bool:
    """Fill missing due_at for active assignments (legacy rows). Returns True if updated."""
    if row.due_at is not None or row.status in TERMINAL_STATUSES:
        return False
    row.due_at = default_assignment_due_at()
    db.add(row)
    return True


def load_completed_tests(raw: str | None) -> list[str]:
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


def _dump_completed(test_ids: list[str]) -> str:
    return json.dumps(sorted(set(test_ids)), ensure_ascii=False)


def assignment_to_dict(
    row: PtTestAssignment,
    *,
    employee_name: str | None = None,
    employee_telegram_id: str | None = None,
) -> dict:
    done = completed_set(load_completed_tests(row.completed_tests_json))
    prog = get_program(row.program_id)
    progress = program_progress(prog, done)
    return {
        "id": row.id,
        "client_id": row.client_id,
        "employee_id": row.employee_id,
        "employee_display_name": employee_name,
        "employee_telegram_id": employee_telegram_id,
        "program_id": row.program_id,
        "program_title_ru": prog.title_ru,
        "status": row.status,
        "completed_tests": sorted(done),
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "due_date": row.due_at.date().isoformat() if row.due_at else None,
        "notified_at": row.notified_at.isoformat() if row.notified_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        **progress,
    }


def get_active_assignment(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
) -> PtTestAssignment | None:
    stmt = (
        select(PtTestAssignment)
        .where(
            PtTestAssignment.client_id == client_id,
            PtTestAssignment.employee_id == employee_id,
            PtTestAssignment.status.in_(tuple(ACTIVE_STATUSES)),
        )
        .order_by(PtTestAssignment.updated_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def create_assignment(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
    program_id: str = DEFAULT_PROGRAM_ID,
    due_at: datetime | None = None,
) -> PtTestAssignment:
    get_program(program_id)
    emp = db.get(Employee, employee_id)
    if not emp or emp.client_id != client_id:
        raise ValueError("employee_not_found")
    existing = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
    if existing:
        raise ValueError("active_assignment_exists")
    if due_at is None:
        due_at = default_assignment_due_at()
    row = PtTestAssignment(
        id=new_id32(),
        client_id=client_id,
        employee_id=employee_id,
        program_id=program_id,
        status="scheduled",
        completed_tests_json="[]",
        due_at=due_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_assignments(
    db: Session,
    *,
    client_id: str,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    stmt = select(PtTestAssignment).where(PtTestAssignment.client_id == client_id)
    total = len(db.scalars(stmt).all())
    rows = (
        db.scalars(
            stmt.order_by(PtTestAssignment.updated_at.desc()).offset(offset).limit(limit)
        ).all()
    )
    out: list[dict] = []
    touched = False
    for row in rows:
        if _ensure_row_due_at(db, row):
            touched = True
        emp = db.get(Employee, row.employee_id)
        name = None
        if emp:
            name = " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))
        tg = normalize_telegram_chat_id(str(emp.telegram_id or "")) if emp else None
        out.append(
            assignment_to_dict(row, employee_name=name, employee_telegram_id=tg or None)
        )
    if touched:
        db.commit()
    return out, total


def check_may_start_test(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
    test_id: str,
) -> tuple[bool, str | None, PtTestAssignment | None]:
    """
    Returns (allowed, user_message_ru, assignment).
    No active assignment → allow (legacy free /start).
    """
    assignment = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
    if assignment is None:
        return True, None, None
    prog = get_program(assignment.program_id)
    if test_id not in prog.all_test_ids():
        return (
            False,
            f"Тест «{test_id}» не входит в назначенную программу «{prog.title_ru}».",
            assignment,
        )
    done = completed_set(load_completed_tests(assignment.completed_tests_json))
    if test_id in done:
        nxt = next_recommended_test(prog, done)
        hint = f" Следующий шаг: /start {nxt}." if nxt else " Программа завершена."
        return False, f"Тест «{test_id}» уже пройден по назначению HR.{hint}", assignment
    allowed = allowed_test_ids(prog, done)
    if test_id not in allowed:
        if allowed:
            opts = ", ".join(f"/start {t}" for t in allowed)
            return (
                False,
                f"Сначала завершите предыдущие шаги программы HR. Сейчас доступно: {opts}.",
                assignment,
            )
        return False, "Ожидайте следующего шага программы HR или обратитесь к HR.", assignment
    return True, None, assignment


def mark_test_started(db: Session, assignment: PtTestAssignment) -> None:
    if assignment.status in TERMINAL_STATUSES:
        return
    if assignment.status != "in_progress":
        assignment.status = "in_progress"
        db.add(assignment)
        db.commit()


def record_test_completed(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
    test_id: str,
) -> PtTestAssignment | None:
    assignment = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
    if assignment is None:
        return None
    done = completed_set(load_completed_tests(assignment.completed_tests_json))
    if test_id not in done:
        done.add(test_id)
        assignment.completed_tests_json = _dump_completed(sorted(done))
    prog = get_program(assignment.program_id)
    if program_progress(prog, done)["is_complete"]:
        assignment.status = "completed"
    elif assignment.status == "notified":
        assignment.status = "in_progress"
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def build_notify_message(assignment: PtTestAssignment, employee: Employee) -> str:
    prog = get_program(assignment.program_id)
    done = completed_set(load_completed_tests(assignment.completed_tests_json))
    nxt = next_recommended_test(prog, done) or "mbti"
    name = employee.first_name or employee.last_name or "коллега"
    due = ""
    if assignment.due_at:
        due = f"\nДедлайн: {assignment.due_at.strftime('%d.%m.%Y')}."
    return (
        f"Здравствуйте, {name}!\n\n"
        f"Вам назначено психологическое тестирование ({prog.title_ru}).\n"
        f"Первый доступный шаг: {nxt.upper()} — отправьте /start {nxt} когда будете готовы."
        f"{due}\n\n"
        "Отмена текущей сессии: /cancel"
    )


def _telegram_bot_token() -> str:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        raise ValueError("telegram_bot_token_missing")
    return token


def update_assignment_due_at(
    db: Session,
    assignment_id: str,
    *,
    due_at: datetime | None,
) -> dict:
    row = db.get(PtTestAssignment, assignment_id)
    if not row:
        raise ValueError("assignment_not_found")
    if row.status in TERMINAL_STATUSES:
        raise ValueError("assignment_terminal")
    row.due_at = due_at
    db.add(row)
    db.commit()
    db.refresh(row)
    emp = db.get(Employee, row.employee_id)
    name = None
    if emp:
        name = " ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name]))
    return assignment_to_dict(row, employee_name=name)


def notify_assignment(db: Session, assignment_id: str) -> dict:
    row = db.get(PtTestAssignment, assignment_id)
    if not row:
        raise ValueError("assignment_not_found")
    if row.status in TERMINAL_STATUSES:
        raise ValueError("assignment_terminal")
    emp = db.get(Employee, row.employee_id)
    if not emp:
        raise ValueError("employee_not_found")
    chat_id = normalize_telegram_chat_id(str(emp.telegram_id or ""))
    if not chat_id:
        raise ValueError("employee_no_telegram")
    session_chat = latest_telegram_chat_for_employee(row.employee_id)
    text = build_notify_message(row, emp)
    outbound = get_telegram_outbound()
    result = outbound.send_message(
        token=_telegram_bot_token(),
        chat_id=chat_id,
        text=text,
        reply_markup=None,
    )
    if not result.ok:
        desc = (result.description or "telegram_send_failed").lower()
        if "chat not found" in desc:
            msg = (
                "Telegram не нашёл чат. Проверьте, что сотрудник писал именно этому боту (/start), "
                f"и что в карточке указан числовой chat_id, а не @ник. "
                f"Сейчас в карточке: «{chat_id}»."
            )
            if session_chat and session_chat != chat_id:
                msg += (
                    f" По завершённым тестам в JSON для этого сотрудника записан chat_id {session_chat} "
                    "— возможно, в карточке указан другой идентификатор."
                )
            elif session_chat:
                msg += f" В JSON сессий chat_id {session_chat} совпадает с карточкой — возможно, другой TELEGRAM_BOT_TOKEN у API и у worker."
            raise NotifyTelegramError(
                "telegram_chat_not_found",
                msg,
                stored_telegram_id=chat_id,
                session_telegram_chat_id=session_chat,
            )
        raise ValueError("telegram_send_failed")
    row.notified_at = datetime.utcnow()
    if row.status == "scheduled":
        row.status = "notified"
    db.add(row)
    db.commit()
    db.refresh(row)
    return assignment_to_dict(
        row,
        employee_name=" ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name])),
    )


def programs_payload() -> list[dict]:
    return [
        {
            "program_id": p.program_id,
            "title_ru": p.title_ru,
            "steps": [
                {
                    "test_id": s.test_id,
                    "unlock_after": list(s.unlock_after),
                    "parallel_group": s.parallel_group,
                    "label_ru": s.label_ru or s.test_id,
                }
                for s in p.steps
            ],
        }
        for p in list_programs()
    ]
