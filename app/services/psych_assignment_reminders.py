"""Deadline reminders for psych test assignments (Telegram)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, PtTestAssignment

_log = logging.getLogger(__name__)


def _test_label(test_id: str) -> str:
    tid = str(test_id or "").strip()
    if not tid:
        return "тест"
    try:
        from psychological_testing.domain.test_registry import TestRegistry

        return TestRegistry().get(tid).display_name or tid
    except KeyError:
        return tid


def reminders_enabled() -> bool:
    return os.getenv("PSYCH_TESTING_REMINDERS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "",
    )


def reminder_hours_before() -> int:
    raw = os.getenv("PSYCH_TESTING_REMINDER_HOURS_BEFORE", "24").strip()
    try:
        return max(1, min(168, int(raw)))
    except ValueError:
        return 24


def _telegram_token() -> str | None:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
    return token or None


def _send_telegram(chat_id: str, text: str) -> bool:
    token = _telegram_token()
    if not token:
        _log.warning("psych reminder: TELEGRAM_BOT_TOKEN missing")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=20.0,
        )
        data = r.json()
        if r.status_code >= 400 or not data.get("ok"):
            _log.warning("psych reminder send failed chat=%s: %s", chat_id, data)
            return False
        return True
    except Exception:
        _log.exception("psych reminder send error chat=%s", chat_id)
        return False


def process_assignment_due_reminders_once(db: Session) -> int:
    """
    Отправить напоминание о дедлайне один раз на назначение.

    Условия: status in (scheduled, in_progress), notified_at задан, due_at близко/просрочен,
    due_reminder_sent_at пуст.
    """
    if not reminders_enabled():
        return 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window = now + timedelta(hours=reminder_hours_before())
    rows = db.scalars(
        select(PtTestAssignment).where(
            PtTestAssignment.status.in_(("scheduled", "in_progress")),
            PtTestAssignment.notified_at.is_not(None),
            PtTestAssignment.due_at.is_not(None),
            PtTestAssignment.due_reminder_sent_at.is_(None),
            PtTestAssignment.due_at <= window,
        )
    ).all()
    sent = 0
    for row in rows:
        emp = db.get(Employee, row.employee_id)
        if not emp or not emp.telegram_id:
            continue
        label = _test_label(str(row.test_id or ""))
        due = row.due_at.strftime("%d.%m.%Y") if row.due_at else "—"
        if row.due_at and row.due_at < now:
            text = (
                f"Напоминание: срок прохождения теста «{label}» истёк ({due}).\n"
                "Пройдите тест в Telegram или свяжитесь с HR."
            )
        else:
            text = (
                f"Напоминание: до дедлайна теста «{label}» осталось менее "
                f"{reminder_hours_before()} ч (срок: {due})."
            )
        if _send_telegram(str(emp.telegram_id).strip(), text):
            row.due_reminder_sent_at = now
            db.add(row)
            sent += 1
    if sent:
        db.commit()
    return sent


async def run_psych_assignment_reminder_loop() -> None:
    """Фоновый цикл напоминаний (вызывается из telegram worker)."""
    import asyncio

    interval = int(os.getenv("PSYCH_TESTING_REMINDER_POLL_SEC", "300") or "300")
    interval = max(60, min(interval, 3600))
    while True:
        try:
            from app.db import SessionLocal

            db = SessionLocal()
            try:
                count = await asyncio.to_thread(process_assignment_due_reminders_once, db)
                if count:
                    _log.info("psych reminders sent: %s", count)
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("psych reminder loop error")
        await asyncio.sleep(interval)
