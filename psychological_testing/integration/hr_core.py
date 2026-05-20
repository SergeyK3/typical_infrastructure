"""
In-process HR bridge for psychological testing (mirror skill_assessment/integration/hr_core.py).

Master data: ``Employee.telegram_id`` in ``app.models``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy.orm import Session

_log = logging.getLogger(__name__)

__all__ = [
    "CORE_HR_AVAILABLE",
    "EmployeeSnapshot",
    "employee_display_label",
    "get_employee",
    "resolve_employee_by_telegram",
]

_core_get_employee: Any = None
CORE_HR_AVAILABLE: bool = False

try:
    from app.hr import get_employee as _core_get_employee  # type: ignore[import-untyped,import-not-found]

    CORE_HR_AVAILABLE = True
    _log.debug("psych_testing: app.hr.get_employee connected")
except ImportError:
    _log.info(
        "psych_testing: app.hr not found — HR bridge uses dev stubs "
        "(PSYCH_TESTING_DEV_CLIENT_ID / PSYCH_TESTING_DEV_EMPLOYEE_ID)."
    )


@dataclass(frozen=True)
class EmployeeSnapshot:
    id: str
    client_id: str
    display_name: str | None = None
    email: str | None = None
    telegram_chat_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None


def _telegram_chat_ids_equal(stored: str, incoming: str) -> bool:
    a = str(stored).strip()
    b = str(incoming).strip()
    if not a or not b:
        return False
    if a == b:
        return True
    try:
        return int(a) == int(b)
    except ValueError:
        return False


def _stub_employee(client_id: str, employee_id: str) -> EmployeeSnapshot:
    return EmployeeSnapshot(
        id=employee_id,
        client_id=client_id,
        display_name=None,
        email=None,
        telegram_chat_id=None,
    )


def _adapt_core_employee(obj: Any, client_id: str, employee_id: str) -> EmployeeSnapshot | None:
    if obj is None:
        return None
    if isinstance(obj, EmployeeSnapshot):
        return obj
    eid = str(getattr(obj, "id", None) or getattr(obj, "employee_id", None) or employee_id)
    cid = str(getattr(obj, "client_id", None) or client_id)
    display = (
        getattr(obj, "display_name", None)
        or getattr(obj, "full_name", None)
        or getattr(obj, "name", None)
    )
    if not (isinstance(display, str) and display.strip()):
        parts = [
            p
            for p in (
                getattr(obj, "last_name", None),
                getattr(obj, "first_name", None),
                getattr(obj, "middle_name", None),
            )
            if isinstance(p, str) and p.strip()
        ]
        display = " ".join(parts) if parts else None
    tg = (
        getattr(obj, "telegram_chat_id", None)
        or getattr(obj, "telegram_id", None)
        or getattr(obj, "tg_id", None)
    )
    tg_s = str(tg).strip() if tg is not None else None
    return EmployeeSnapshot(
        id=eid,
        client_id=cid,
        display_name=display.strip() if isinstance(display, str) and display.strip() else None,
        email=getattr(obj, "email", None),
        telegram_chat_id=tg_s or None,
        first_name=getattr(obj, "first_name", None),
        last_name=getattr(obj, "last_name", None),
    )


def get_employee(db: Session, client_id: str, employee_id: str | None) -> EmployeeSnapshot | None:
    if not employee_id:
        return None
    if CORE_HR_AVAILABLE and _core_get_employee is not None:
        try:
            raw = _core_get_employee(db, client_id, employee_id)
            if raw is None:
                return None
            return _adapt_core_employee(raw, client_id, employee_id)
        except Exception:
            _log.exception("psych_testing: get_employee failed — stub fallback")
    return _stub_employee(client_id, employee_id)


def employee_display_label(snapshot: EmployeeSnapshot | None) -> str | None:
    if snapshot is None:
        return None
    if snapshot.display_name and snapshot.display_name.strip():
        return snapshot.display_name.strip()
    parts = [p for p in (snapshot.last_name, snapshot.first_name) if isinstance(p, str) and p.strip()]
    return " ".join(parts) if parts else snapshot.id


def resolve_employee_by_telegram(
    db: Session,
    telegram_chat_id: str,
    *,
    default_client_id: str,
    default_employee_id: str,
) -> EmployeeSnapshot:
    """
    Resolve ``Employee`` by ``telegram_id``; fallback to dev ids when not found.
    """
    tid = str(telegram_chat_id).strip()
    try:
        from app.models import Employee
        from sqlalchemy import select

        rows = db.scalars(
            select(Employee)
            .where(Employee.telegram_id.isnot(None))
            .order_by(Employee.updated_at.desc())
            .limit(500)
        ).all()
        matches = [r for r in rows if _telegram_chat_ids_equal(str(r.telegram_id or ""), tid)]
        if len(matches) == 1:
            emp = matches[0]
            snap = _adapt_core_employee(emp, str(emp.client_id), str(emp.id))
            if snap is not None:
                return replace(snap, telegram_chat_id=tid)
        if len(matches) > 1:
            _log.warning(
                "psych_testing: multiple employees for telegram chat_id=%s — using newest",
                tid,
            )
            emp = matches[0]
            snap = _adapt_core_employee(emp, str(emp.client_id), str(emp.id))
            if snap is not None:
                return replace(snap, telegram_chat_id=tid)
    except ImportError:
        _log.debug("psych_testing: app.models.Employee unavailable for telegram resolve")
    except Exception:
        _log.exception("psych_testing: resolve_employee_by_telegram failed — dev fallback")

    return EmployeeSnapshot(
        id=default_employee_id,
        client_id=default_client_id,
        display_name=None,
        telegram_chat_id=tid,
    )
