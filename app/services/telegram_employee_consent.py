"""Telegram gate: единое согласие ПДн до psych / Part1 / examination."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.services.employee_consent import (
    PREFIX_EPC,
    MSG_DECLINE_WARNING,
    MSG_DECLINED_BLOCKED,
    MSG_UNCLEAR_CONSENT,
    PdConsentGate,
    build_pd_consent_keyboard,
    build_pd_consent_prompt,
    get_pd_consent,
    handle_pd_consent_no,
    is_pd_consent_blocked,
    is_pd_consent_valid,
    needs_pd_consent_prompt,
    parse_pd_consent_yes_no,
    record_pd_consent_yes,
    require_pd_consent_or_prompt,
)
from skill_assessment.services.telegram_examination import _resolve_binding

_log = logging.getLogger(__name__)


class GateResult(str, Enum):
    ALLOW = "allow"
    HANDLED = "handled"
    BLOCKED = "blocked"


@dataclass
class ConsentTurnResult:
    """Исходящие сообщения после обработки callback или текста."""

    outgoing: list[tuple[str, dict[str, Any] | None]]
    popup_text: str | None = None


def _binding_for_chat(db: Session, chat_id: str) -> tuple[str, str] | None:
    """Привязка chat_id → client_id + employee_id (экзамен, Part1, карточка HR)."""
    tid = str(chat_id).strip()
    pair = _resolve_binding(db, tid)
    if pair is not None:
        return pair
    try:
        from sqlalchemy import select

        from app.models import Employee
        from skill_assessment.services.telegram_docs_survey import _telegram_chat_ids_equal

        rows = db.scalars(
            select(Employee).where(Employee.telegram_id.isnot(None)).limit(500)
        ).all()
        for emp in rows:
            if _telegram_chat_ids_equal(str(emp.telegram_id or ""), tid):
                return emp.client_id, emp.id
    except Exception:
        _log.debug("consent: resolve employee by telegram_id failed", exc_info=True)
    return None


def _employee_matches(binding_eid: str, target_eid: str) -> bool:
    return (binding_eid or "").strip().lower() == (target_eid or "").strip().lower()


def _resolve_for_epc_action(
    db: Session, chat_id: str, callback_employee_id: str
) -> tuple[str, str] | None:
    """client_id + employee_id для epc|y/n: привязка чата или сотрудник из callback_data."""
    tid = str(chat_id).strip()
    eid = (callback_employee_id or "").strip()
    pair = _binding_for_chat(db, tid)
    if pair is not None and _employee_matches(pair[1], eid):
        return pair
    if not eid:
        return pair
    try:
        from app.models import Employee
        from skill_assessment.services.telegram_docs_survey import _telegram_chat_ids_equal

        emp = db.get(Employee, eid)
        if emp is None:
            return pair
        if _telegram_chat_ids_equal(str(emp.telegram_id or ""), tid):
            return emp.client_id, emp.id
    except Exception:
        _log.debug("consent: resolve epc employee_id failed", exc_info=True)
    return pair


def _consent_yes_turn_result(
    db: Session, client_id: str, employee_id: str
) -> ConsentTurnResult:
    """После «Да»: переход к психотестированию (меню) или краткая подсказка /start."""
    try:
        from app.services.psych_test_assignments import build_psych_post_consent_followup

        follow = build_psych_post_consent_followup(db, client_id, employee_id)
        if follow:
            text, kb = follow
            return ConsentTurnResult(
                outgoing=[(text, kb)],
                popup_text="Согласие принято.",
            )
    except Exception:
        _log.debug("consent: psych post-consent followup failed", exc_info=True)
    return ConsentTurnResult(
        outgoing=[
            (
                "Согласие принято.\n\n"
                "Для психологического тестирования отправьте /start или выберите тест в меню.",
                None,
            )
        ],
        popup_text="Согласие принято.",
    )


def _notify_hr_declined(db: Session, client_id: str, employee_id: str) -> None:
    """Уведомление HR о подтверждённом отказе (без привязки к сессии Part1)."""
    try:
        from skill_assessment.services.docs_survey_hr_notify import send_telegram_text_to_chat
        from skill_assessment.integration.hr_core import employee_display_label, get_employee
    except Exception:
        _log.exception("employee_consent: HR notify import failed")
        return

    import os

    hr_chat = (os.getenv("TELEGRAM_DOCS_SURVEY_HR_NOTIFY_CHAT_ID") or "").strip()
    if not hr_chat:
        _log.warning("employee_consent: TELEGRAM_DOCS_SURVEY_HR_NOTIFY_CHAT_ID не задан")
        return
    emp = get_employee(db, client_id, employee_id)
    who = employee_display_label(emp) or employee_id
    pos = (emp.position_label.strip() if emp and emp.position_label else None) or "—"
    body = (
        "Сотрудник подтвердил отказ от согласия на обработку персональных данных "
        "(единый слой ПДн, Telegram).\n\n"
        f"Сотрудник: {who}\n"
        f"Должность: {pos}\n"
        f"client_id: {client_id}\n"
        f"employee_id: {employee_id}\n\n"
        "Сообщение сформировано автоматически."
    )
    send_telegram_text_to_chat(hr_chat, body)


def handle_consent_callback(
    db: Session,
    chat_id: str,
    callback_data: str,
) -> ConsentTurnResult | None:
    """Inline «Да»/«Нет». Префикс ``epc|y|{employee_id}`` / ``epc|n|{employee_id}``."""
    raw = (callback_data or "").strip()
    if not raw.startswith(f"{PREFIX_EPC}|"):
        return None
    parts = raw.split("|", 2)
    if len(parts) != 3:
        return None
    _, action, eid = parts
    pair = _resolve_for_epc_action(db, chat_id, eid)
    if pair is None:
        return ConsentTurnResult(
            outgoing=[("Не удалось определить сотрудника. Обратитесь в HR.", None)],
            popup_text="Нет привязки",
        )
    client_id, employee_id = pair

    snap = get_pd_consent(db, client_id, employee_id)
    if is_pd_consent_blocked(snap):
        return ConsentTurnResult(outgoing=[(MSG_DECLINED_BLOCKED, None)])

    if action == "y":
        record_pd_consent_yes(db, client_id, employee_id)
        db.commit()
        return _consent_yes_turn_result(db, client_id, employee_id)

    if action != "n":
        return None

    result = handle_pd_consent_no(db, client_id, employee_id)
    if result.is_final_decline:
        _notify_hr_declined(db, client_id, employee_id)
        db.commit()
        return ConsentTurnResult(outgoing=[(MSG_DECLINED_BLOCKED, None)])
    db.commit()
    kb = build_pd_consent_keyboard(employee_id)
    warn = result.warning_message or MSG_DECLINE_WARNING
    return ConsentTurnResult(outgoing=[(warn, kb)])


def handle_consent_message(
    db: Session,
    chat_id: str,
    text: str | None,
) -> ConsentTurnResult | None:
    """Текстовые «да»/«нет», пока согласие pending или decline_pending."""
    from app.services.telegram_cancel import is_cancel_command

    if is_cancel_command(text):
        return None

    pair = _binding_for_chat(db, chat_id)
    if pair is None:
        return None
    client_id, employee_id = pair
    snap = get_pd_consent(db, client_id, employee_id)
    if is_pd_consent_blocked(snap):
        return ConsentTurnResult(outgoing=[(MSG_DECLINED_BLOCKED, None)])
    if is_pd_consent_valid(snap):
        return None
    if not needs_pd_consent_prompt(snap):
        return None

    yn = parse_pd_consent_yes_no((text or "").strip())
    if yn is None:
        if (text or "").strip():
            return ConsentTurnResult(
                outgoing=[
                    (MSG_UNCLEAR_CONSENT, build_pd_consent_keyboard(employee_id)),
                ]
            )
        return None

    if yn:
        record_pd_consent_yes(db, client_id, employee_id)
        db.commit()
        return _consent_yes_turn_result(db, client_id, employee_id)

    result = handle_pd_consent_no(db, client_id, employee_id)
    if result.is_final_decline:
        _notify_hr_declined(db, client_id, employee_id)
        db.commit()
        return ConsentTurnResult(outgoing=[(MSG_DECLINED_BLOCKED, None)])
    db.commit()
    kb = build_pd_consent_keyboard(employee_id)
    warn = result.warning_message or MSG_DECLINE_WARNING
    return ConsentTurnResult(outgoing=[(warn, kb)])


def consent_gate(db: Session, chat_id: str) -> tuple[GateResult, list[tuple[str, dict[str, Any] | None]]]:
    """
    Проверка перед маршрутизацией сценариев.
    Возвращает (allow | handled | blocked, исходящие сообщения).
    """
    pair = _binding_for_chat(db, chat_id)
    if pair is None:
        return GateResult.ALLOW, []
    client_id, employee_id = pair
    gate = require_pd_consent_or_prompt(db, client_id, employee_id)
    if gate.outcome == PdConsentGate.ALLOW:
        return GateResult.ALLOW, []
    if gate.outcome == PdConsentGate.BLOCKED:
        return GateResult.BLOCKED, [(gate.message or MSG_DECLINED_BLOCKED, gate.reply_markup)]
    return GateResult.HANDLED, [(gate.message or build_pd_consent_prompt(), gate.reply_markup)]
