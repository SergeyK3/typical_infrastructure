"""Единый слой согласия ПДн на сотрудника (client_id + employee_id)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmployeeConsentRecord, utcnow
from app.utils import new_id32
from skill_assessment.services.pd_consent_document import (
    pd_consent_document_url,
    pd_consent_link_line,
)

CONSENT_TYPE_PD = "pd_processing"
PREFIX_EPC = "epc"

STATUS_PENDING = "pending"
STATUS_DECLINE_PENDING = "decline_pending"
STATUS_ACCEPTED = "accepted"
STATUS_DECLINED = "declined"
STATUS_REVOKED = "revoked"


@dataclass(frozen=True)
class ConsentSnapshot:
    client_id: str
    employee_id: str
    status: str
    document_version: str | None
    accepted_at: datetime | None
    declined_at: datetime | None
    source: str | None

    @property
    def has_record(self) -> bool:
        return bool(self.client_id and self.employee_id and self.status)


def pd_consent_document_version() -> str:
    return (os.getenv("TELEGRAM_PD_CONSENT_DOCUMENT_VERSION") or "1.0").strip() or "1.0"


def get_pd_consent(db: Session, client_id: str, employee_id: str) -> ConsentSnapshot:
    cid = (client_id or "").strip()
    eid = (employee_id or "").strip()
    if not cid or not eid:
        return ConsentSnapshot(cid, eid, STATUS_PENDING, None, None, None, None)
    row = db.scalar(
        select(EmployeeConsentRecord).where(
            EmployeeConsentRecord.client_id == cid,
            EmployeeConsentRecord.employee_id == eid,
            EmployeeConsentRecord.consent_type == CONSENT_TYPE_PD,
        )
    )
    if row is None:
        return ConsentSnapshot(cid, eid, STATUS_PENDING, None, None, None, None)
    return ConsentSnapshot(
        cid,
        eid,
        row.status or STATUS_PENDING,
        row.document_version,
        row.accepted_at,
        row.declined_at,
        row.source,
    )


def is_pd_consent_valid(snapshot: ConsentSnapshot) -> bool:
    if snapshot.status != STATUS_ACCEPTED:
        return False
    current = pd_consent_document_version()
    stored = (snapshot.document_version or "").strip()
    return stored == current


def is_pd_consent_blocked(snapshot: ConsentSnapshot) -> bool:
    return snapshot.status == STATUS_DECLINED


def _get_or_create_row(db: Session, client_id: str, employee_id: str) -> EmployeeConsentRecord:
    row = db.scalar(
        select(EmployeeConsentRecord).where(
            EmployeeConsentRecord.client_id == client_id,
            EmployeeConsentRecord.employee_id == employee_id,
            EmployeeConsentRecord.consent_type == CONSENT_TYPE_PD,
        )
    )
    if row is not None:
        return row
    now = utcnow()
    row = EmployeeConsentRecord(
        id=new_id32(),
        client_id=client_id,
        employee_id=employee_id,
        consent_type=CONSENT_TYPE_PD,
        status=STATUS_PENDING,
        document_version=None,
        accepted_at=None,
        declined_at=None,
        source="telegram",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    return row


def record_pd_consent_yes(
    db: Session,
    client_id: str,
    employee_id: str,
    *,
    source: str = "telegram",
) -> ConsentSnapshot:
    cid = (client_id or "").strip()
    eid = (employee_id or "").strip()
    now = utcnow()
    ver = pd_consent_document_version()
    row = _get_or_create_row(db, cid, eid)
    row.status = STATUS_ACCEPTED
    row.document_version = ver
    row.accepted_at = now
    row.declined_at = None
    row.source = source
    row.updated_at = now
    db.flush()
    return get_pd_consent(db, cid, eid)


@dataclass(frozen=True)
class PdConsentNoResult:
    """Результат обработки «Нет»: предупреждение или финальный отказ."""

    status: str
    is_final_decline: bool
    warning_message: str | None = None


def handle_pd_consent_no(
    db: Session,
    client_id: str,
    employee_id: str,
) -> PdConsentNoResult:
    """
    Двухшаговый отказ:
    - pending / нет записи → decline_pending + предупреждение;
    - decline_pending → declined;
    - accepted → снова decline_pending (повторный отказ после согласия).
    """
    cid = (client_id or "").strip()
    eid = (employee_id or "").strip()
    snap = get_pd_consent(db, cid, eid)
    now = utcnow()

    if snap.status == STATUS_DECLINED:
        return PdConsentNoResult(STATUS_DECLINED, is_final_decline=True)

    if snap.status == STATUS_DECLINE_PENDING:
        row = _get_or_create_row(db, cid, eid)
        row.status = STATUS_DECLINED
        row.declined_at = now
        row.updated_at = now
        db.flush()
        return PdConsentNoResult(STATUS_DECLINED, is_final_decline=True)

    row = _get_or_create_row(db, cid, eid)
    row.status = STATUS_DECLINE_PENDING
    row.document_version = pd_consent_document_version()
    row.updated_at = now
    db.flush()
    return PdConsentNoResult(
        STATUS_DECLINE_PENDING,
        is_final_decline=False,
        warning_message=MSG_DECLINE_WARNING,
    )


def hr_release_pd_consent_block(db: Session, client_id: str, employee_id: str) -> ConsentSnapshot:
    """Сброс блокировки HR: снова можно запросить согласие."""
    cid = (client_id or "").strip()
    eid = (employee_id or "").strip()
    row = db.scalar(
        select(EmployeeConsentRecord).where(
            EmployeeConsentRecord.client_id == cid,
            EmployeeConsentRecord.employee_id == eid,
            EmployeeConsentRecord.consent_type == CONSENT_TYPE_PD,
        )
    )
    now = utcnow()
    if row is None:
        return ConsentSnapshot(cid, eid, STATUS_PENDING, None, None, None, None)
    row.status = STATUS_PENDING
    row.document_version = None
    row.accepted_at = None
    row.declined_at = None
    row.source = "hr_manual"
    row.updated_at = now
    db.flush()
    return get_pd_consent(db, cid, eid)


PD_CONSENT_EXPLANATION = (
    "Для участия в опросах, тестировании и других этапах оценки необходимо принять условия "
    "обработки персональных данных."
)

PD_CONSENT_ACK_LINE = "Согласие на обработку персональных данных принято ранее."


def employee_greeting_first_patronymic(
    first_name: str | None,
    middle_name: str | None,
    *,
    fallback: str = "коллега",
) -> str:
    """«Имя Отчество» для приветствия в Telegram."""
    parts = [str(first_name or "").strip(), str(middle_name or "").strip()]
    name = " ".join(p for p in parts if p)
    return name or fallback


def build_pd_consent_prompt(*, intro: str | None = None) -> str:
    """
    Текст запроса ПДн. ``intro`` — опциональный блок сверху (приветствие + контекст сценария).
    """
    chunks: list[str] = []
    if intro and intro.strip():
        chunks.append(intro.strip())
    chunks.append(PD_CONSENT_EXPLANATION)
    link = pd_consent_link_line()
    if link:
        chunks.append(link.strip())
    chunks.append("Нажмите «Да» или «Нет»:")
    return "\n\n".join(chunks)


MSG_DECLINE_WARNING = (
    "Без согласия вы не будете допущены к другим этапам (опросы, тестирование, проверка "
    "по регламентам и т.д.).\n\n"
    "Подтвердите отказ, нажав «Нет» ещё раз, или нажмите «Да», чтобы принять согласие."
)

MSG_DECLINED_BLOCKED = (
    "Отказ от согласия на обработку персональных данных зафиксирован. "
    "Участие в этапах оценки недоступно до снятия блокировки в отделе кадров."
)

MSG_UNCLEAR_CONSENT = (
    "Не понял ответ. Нажмите кнопки «Да» или «Нет» под сообщением "
    "или напишите «да» / «нет»."
)


def build_pd_consent_keyboard(employee_id: str) -> dict[str, Any]:
    eid = (employee_id or "").strip()
    cb_y = f"{PREFIX_EPC}|y|{eid}"
    cb_n = f"{PREFIX_EPC}|n|{eid}"
    for cb in (cb_y, cb_n):
        if len(cb.encode("utf-8")) > 64:
            raise ValueError("callback_data exceeds Telegram 64-byte limit")
    return {
        "inline_keyboard": [
            [{"text": "Да", "callback_data": cb_y}],
            [{"text": "Нет", "callback_data": cb_n}],
        ]
    }


def parse_pd_consent_yes_no(text: str) -> bool | None:
    """Да/нет для единого согласия (без «готов»)."""
    t = text.strip().lower()
    if not t:
        return None
    if t in ("да", "yes", "ok", "ага", "+", "согласен", "согласна", "принимаю", "принимаю согласие"):
        return True
    if t in ("нет", "no", "отказ", "отказываюсь", "-", "не согласен", "не согласна"):
        return False
    if re.match(r"^да[\s!.]*$", t) or (t.startswith("да ") and len(t) < 80):
        return True
    if re.match(r"^нет[\s!.]*$", t) or (t.startswith("нет ") and len(t) < 80):
        return False
    return None


def needs_pd_consent_prompt(snapshot: ConsentSnapshot) -> bool:
    """Нужно показать запрос согласия (нет valid consent и не заблокирован окончательно)."""
    if is_pd_consent_blocked(snapshot):
        return False
    return not is_pd_consent_valid(snapshot)


class PdConsentGate(str, Enum):
    """Исход проверки перед любым сценарием (psych, Part1, examination)."""

    ALLOW = "allow"
    BLOCKED = "blocked"
    PROMPT = "prompt"


@dataclass(frozen=True)
class PdConsentGateResult:
    outcome: PdConsentGate
    message: str | None = None
    reply_markup: dict[str, Any] | None = None


def require_pd_consent_or_prompt(
    db: Session,
    client_id: str,
    employee_id: str,
    *,
    intro: str | None = None,
) -> PdConsentGateResult:
    """
    Единая точка для сценариев: можно продолжать, показать запрос ПДн или сообщить о блоке.

    Сценарии только отправляют ``message`` / ``reply_markup`` и не дублируют логику статусов.
    """
    cid = (client_id or "").strip()
    eid = (employee_id or "").strip()
    snap = get_pd_consent(db, cid, eid)
    if is_pd_consent_blocked(snap):
        return PdConsentGateResult(PdConsentGate.BLOCKED, MSG_DECLINED_BLOCKED, None)
    if is_pd_consent_valid(snap):
        return PdConsentGateResult(PdConsentGate.ALLOW, None, None)
    if snap.status == STATUS_DECLINE_PENDING:
        # После первого «Нет» — только предупреждение, без повтора всего текста согласия.
        return PdConsentGateResult(
            PdConsentGate.PROMPT,
            MSG_DECLINE_WARNING,
            build_pd_consent_keyboard(eid),
        )
    return PdConsentGateResult(
        PdConsentGate.PROMPT,
        build_pd_consent_prompt(intro=intro),
        build_pd_consent_keyboard(eid),
    )


# Re-export URL helpers for callers migrating to this module
__all__ = [
    "CONSENT_TYPE_PD",
    "PREFIX_EPC",
    "ConsentSnapshot",
    "PdConsentGate",
    "PdConsentGateResult",
    "PdConsentNoResult",
    "build_pd_consent_keyboard",
    "build_pd_consent_prompt",
    "employee_greeting_first_patronymic",
    "PD_CONSENT_ACK_LINE",
    "PD_CONSENT_EXPLANATION",
    "get_pd_consent",
    "handle_pd_consent_no",
    "hr_release_pd_consent_block",
    "is_pd_consent_blocked",
    "is_pd_consent_valid",
    "needs_pd_consent_prompt",
    "parse_pd_consent_yes_no",
    "pd_consent_document_url",
    "pd_consent_document_version",
    "pd_consent_link_line",
    "record_pd_consent_yes",
    "require_pd_consent_or_prompt",
]
