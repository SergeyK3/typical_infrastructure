"""Psychological testing assignments: один тест на назначение + Telegram notify."""

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
from psychological_testing.domain.test_registry import TestRegistry
from psychological_testing.integration.session_repository import (
    latest_telegram_chat_for_employee,
)

ACTIVE_STATUSES = frozenset({"scheduled", "notified", "in_progress"})
TERMINAL_STATUSES = frozenset({"completed", "cancelled", "superseded"})


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
    return str(raw or "").strip()


def _registry() -> TestRegistry:
    return TestRegistry()


def _known_test_ids() -> frozenset[str]:
    return frozenset(_registry().list_test_ids())


def _test_label(test_id: str) -> str:
    try:
        return _registry().get(test_id).display_name or test_id
    except KeyError:
        return test_id


def _assignment_test_id(row: PtTestAssignment) -> str | None:
    tid = str(row.test_id or "").strip()
    if tid:
        return tid
    released = json.loads(row.released_tests_json or "[]")
    if isinstance(released, list) and released:
        return str(released[0]).strip() or None
    return None


def _ensure_row_due_at(db: Session, row: PtTestAssignment) -> bool:
    if row.due_at is not None or row.status in TERMINAL_STATUSES:
        return False
    row.due_at = default_assignment_due_at()
    db.add(row)
    return True


def assignment_to_dict(
    row: PtTestAssignment,
    *,
    employee_name: str | None = None,
    employee_telegram_id: str | None = None,
    db: Session | None = None,
) -> dict:
    del db
    test_id = _assignment_test_id(row) or ""
    label = _test_label(test_id) if test_id else ""
    is_complete = row.status == "completed"
    return {
        "id": row.id,
        "client_id": row.client_id,
        "employee_id": row.employee_id,
        "employee_display_name": employee_name,
        "employee_telegram_id": employee_telegram_id,
        "test_id": test_id,
        "test_label_ru": label,
        "status": row.status,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "due_date": row.due_at.date().isoformat() if row.due_at else None,
        "notified_at": row.notified_at.isoformat() if row.notified_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "session_id": row.session_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "is_complete": is_complete,
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


def _supersede_active_assignments(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
) -> None:
    """Закрыть незавершённые активные назначения (история строк сохраняется)."""
    stmt = select(PtTestAssignment).where(
        PtTestAssignment.client_id == client_id,
        PtTestAssignment.employee_id == employee_id,
        PtTestAssignment.status.in_(tuple(ACTIVE_STATUSES)),
    )
    for row in db.scalars(stmt).all():
        row.status = "superseded"
        db.add(row)


def create_assignment(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
    test_id: str,
    due_at: datetime | None = None,
    replace_active: bool = False,
) -> PtTestAssignment:
    tid = str(test_id or "").strip()
    if not tid:
        raise ValueError("test_id_required")
    if tid not in _known_test_ids():
        raise ValueError(f"unknown_test_id:{tid}")
    emp = db.get(Employee, employee_id)
    if not emp or emp.client_id != client_id:
        raise ValueError("employee_not_found")
    existing = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
    if existing:
        existing_tid = _assignment_test_id(existing)
        if existing_tid == tid:
            if due_at is not None:
                existing.due_at = due_at
                db.add(existing)
                db.commit()
                db.refresh(existing)
            return existing
        if not replace_active:
            raise ValueError("active_assignment_exists")
        _supersede_active_assignments(db, client_id=client_id, employee_id=employee_id)
    if due_at is None:
        due_at = default_assignment_due_at()
    row = PtTestAssignment(
        id=new_id32(),
        client_id=client_id,
        employee_id=employee_id,
        test_id=tid,
        program_id=tid,
        status="scheduled",
        steps_snapshot_json="[]",
        completed_step_keys_json="[]",
        released_step_keys_json="[]",
        completed_tests_json="[]",
        released_tests_json=json.dumps([tid], ensure_ascii=False),
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
    employee_id: str | None = None,
    employee_ids: frozenset[str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    stmt = select(PtTestAssignment).where(PtTestAssignment.client_id == client_id)
    if employee_id:
        stmt = stmt.where(PtTestAssignment.employee_id == employee_id)
    if employee_ids is not None:
        if not employee_ids:
            return [], 0
        stmt = stmt.where(PtTestAssignment.employee_id.in_(sorted(employee_ids)))
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
            assignment_to_dict(
                row, employee_name=name, employee_telegram_id=tg or None, db=db
            )
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
    step_key: str | None = None,
) -> tuple[bool, str | None, PtTestAssignment | None]:
    del step_key
    assignment = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
    if assignment is None:
        return True, None, None
    assigned = _assignment_test_id(assignment)
    if not assigned:
        return True, None, assignment
    if assignment.status == "completed":
        return (
            False,
            "Назначение HR уже выполнено. Дождитесь нового назначения от отдела кадров.",
            assignment,
        )
    if test_id != assigned:
        label = _test_label(assigned)
        return (
            False,
            f"По назначению HR вам доступен тест «{label}». "
            f"Нажмите /start {assigned} или кнопку в меню.",
            assignment,
        )
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
    step_key: str | None = None,
    assignment_id: str | None = None,
    session_id: str | None = None,
) -> PtTestAssignment | None:
    del step_key
    row: PtTestAssignment | None = None
    if assignment_id:
        candidate = db.get(PtTestAssignment, assignment_id)
        if (
            candidate
            and candidate.client_id == client_id
            and candidate.employee_id == employee_id
        ):
            row = candidate
    if row is None:
        active = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
        if active and _assignment_test_id(active) == test_id:
            row = active
    if row is None:
        return None
    if row.status == "completed":
        return row
    row.completed_tests_json = json.dumps([test_id], ensure_ascii=False)
    row.status = "completed"
    row.completed_at = datetime.utcnow()
    if session_id:
        row.session_id = str(session_id).strip() or None
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


record_step_completed = record_test_completed


def _test_intro_blurb(test_id: str) -> str:
    from psychological_testing.shared_engine.report_sections.constants import (
        TEST_SECTION_INTROS,
    )

    return (TEST_SECTION_INTROS.get(test_id) or "").strip()


def build_notify_message(assignment: PtTestAssignment, employee: Employee, db: Session) -> str:
    from app.services.employee_consent import (
        PD_CONSENT_ACK_LINE,
        employee_greeting_first_patronymic,
        get_pd_consent,
        is_pd_consent_valid,
    )

    test_id = _assignment_test_id(assignment) or ""
    label = _test_label(test_id)
    name = employee_greeting_first_patronymic(employee.first_name, employee.middle_name)
    chunks = [
        f"Здравствуйте, {name}!",
        f"\n\nВам назначено психологическое тестирование: {label}.",
    ]
    blurb = _test_intro_blurb(test_id)
    if blurb:
        chunks.append(f"\n\n{blurb}")
    if assignment.due_at:
        chunks.append(f"\n\nДедлайн: {assignment.due_at.strftime('%d.%m.%Y')}.")
    snap = get_pd_consent(db, assignment.client_id, assignment.employee_id)
    if is_pd_consent_valid(snap):
        chunks.append(f"\n\n{PD_CONSENT_ACK_LINE}")
    return "".join(chunks)


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
    return assignment_to_dict(row, employee_name=name, db=db)


def build_psych_post_consent_followup(
    db: Session,
    client_id: str,
    employee_id: str,
) -> tuple[str, dict] | None:
    from psychological_testing.adapters.telegram_keyboards import welcome_menu_keyboard

    assignment = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
    if assignment is None:
        return None
    emp = db.get(Employee, employee_id)
    if not emp:
        return None
    ctx = assignment_menu_context(db, client_id=client_id, employee_id=employee_id)
    text = build_notify_message(assignment, emp, db)
    allowed = frozenset(ctx["allowed_test_ids"]) if ctx else None
    markup = welcome_menu_keyboard(allowed_test_ids=allowed)
    return text, markup


def build_psych_assignment_consent_intro(employee: Employee) -> str:
    from app.services.employee_consent import employee_greeting_first_patronymic

    name = employee_greeting_first_patronymic(employee.first_name, employee.middle_name)
    return (
        f"Здравствуйте, {name}!\n\n"
        "Вам назначено психологическое тестирование командных качеств."
    )


def _telegram_outbound_send_pd_consent_aware(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
    chat_id: str,
    primary_text: str,
    primary_reply_markup: dict | None = None,
    session_chat: str | None = None,
    consent_intro: str | None = None,
) -> None:
    from app.services.employee_consent import PdConsentGate, require_pd_consent_or_prompt

    gate = require_pd_consent_or_prompt(
        db, client_id, employee_id, intro=consent_intro
    )
    if gate.outcome == PdConsentGate.ALLOW:
        text = primary_text
        markup = primary_reply_markup
    elif gate.outcome == PdConsentGate.BLOCKED:
        text = gate.message or primary_text
        markup = None
    else:
        text = gate.message or primary_text
        markup = gate.reply_markup
    outbound = get_telegram_outbound()
    result = outbound.send_message(
        token=_telegram_bot_token(),
        chat_id=chat_id,
        text=text,
        reply_markup=markup,
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
                msg += (
                    f" В JSON сессий chat_id {session_chat} совпадает с карточкой — возможно, "
                    "другой TELEGRAM_BOT_TOKEN у API и у worker."
                )
            raise NotifyTelegramError(
                "telegram_chat_not_found",
                msg,
                stored_telegram_id=chat_id,
                session_telegram_chat_id=session_chat,
            )
        raise ValueError("telegram_send_failed")


def _resolve_assignment_for_notify(
    db: Session, assignment_id: str
) -> PtTestAssignment:
    """Строка для отправки Telegram: активная или восстановленная из истории."""
    clicked = db.get(PtTestAssignment, assignment_id)
    if not clicked:
        raise ValueError("assignment_not_found")

    active = get_active_assignment(
        db, client_id=clicked.client_id, employee_id=clicked.employee_id
    )
    if active is not None:
        return active

    if clicked.status not in TERMINAL_STATUSES:
        return clicked

    raise ValueError("assignment_no_active")


def notify_assignment(db: Session, assignment_id: str) -> dict:
    row = _resolve_assignment_for_notify(db, assignment_id)
    emp = db.get(Employee, row.employee_id)
    if not emp:
        raise ValueError("employee_not_found")
    chat_id = normalize_telegram_chat_id(str(emp.telegram_id or ""))
    if not chat_id:
        raise ValueError("employee_no_telegram")
    session_chat = latest_telegram_chat_for_employee(row.employee_id)
    from psychological_testing.adapters.telegram_keyboards import welcome_menu_keyboard

    ctx = assignment_menu_context(db, client_id=row.client_id, employee_id=row.employee_id)
    allowed = frozenset(ctx["allowed_test_ids"]) if ctx else None
    text = build_notify_message(row, emp, db)
    _telegram_outbound_send_pd_consent_aware(
        db,
        client_id=row.client_id,
        employee_id=row.employee_id,
        chat_id=chat_id,
        primary_text=text,
        primary_reply_markup=welcome_menu_keyboard(allowed_test_ids=allowed),
        session_chat=session_chat,
        consent_intro=build_psych_assignment_consent_intro(emp),
    )
    row.notified_at = datetime.utcnow()
    if row.status == "scheduled":
        row.status = "notified"
    db.add(row)
    db.commit()
    db.refresh(row)
    return assignment_to_dict(
        row,
        employee_name=" ".join(filter(None, [emp.last_name, emp.first_name, emp.middle_name])),
        db=db,
    )


def assignment_menu_context(
    db: Session,
    *,
    client_id: str,
    employee_id: str,
) -> dict[str, object] | None:
    assignment = get_active_assignment(db, client_id=client_id, employee_id=employee_id)
    if assignment is None:
        return None
    test_id = _assignment_test_id(assignment)
    if not test_id or assignment.status == "completed":
        return {
            "assignment_id": assignment.id,
            "test_id": test_id,
            "test_label_ru": _test_label(test_id) if test_id else "",
            "allowed_test_ids": [],
            "is_complete": True,
        }
    return {
        "assignment_id": assignment.id,
        "test_id": test_id,
        "test_label_ru": _test_label(test_id),
        "allowed_test_ids": [test_id],
        "is_complete": False,
    }
