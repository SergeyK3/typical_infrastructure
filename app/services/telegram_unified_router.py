"""
Единая маршрутизация Telegram для одного бота (один TELEGRAM_BOT_TOKEN).

- psychological_testing/ — психологическое тестирование (назначение HR, /start mbti, pt: callbacks)
- skill_assessment/ — опрос по регламентам, Part1 ПДн, Part2 кейсы (dsp|, dsr|, examination)
"""

from __future__ import annotations

import logging
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from skill_assessment.domain.examination_entities import ExaminationPhase, ExaminationSessionStatus
from skill_assessment.infrastructure.db_models import ExaminationSessionRow
from skill_assessment.services.telegram_examination import _resolve_binding

_log = logging.getLogger(__name__)

# Фазы экзамена по регламентам, которые не считаются «идущим опросом» — при активном назначении психотестов
# сообщения уходят в psychological_testing.
_EXAM_PHASES_DEFERRABLE_TO_PSYCH = frozenset(
    {
        ExaminationPhase.CONSENT.value,
        ExaminationPhase.INTRO.value,
        ExaminationPhase.BLOCKED_NO_REGULATION.value,
        ExaminationPhase.BLOCKED_CONSENT.value,
        ExaminationPhase.INTERRUPTED_TIMEOUT.value,
    }
)


class TelegramRoute(str, Enum):
    PSYCH_TESTING = "psych_testing"
    SKILL_ASSESSMENT = "skill_assessment"


def _active_examination_row(db: Session, client_id: str, employee_id: str) -> ExaminationSessionRow | None:
    return db.scalars(
        select(ExaminationSessionRow)
        .where(
            ExaminationSessionRow.client_id == client_id,
            ExaminationSessionRow.employee_id == employee_id,
            ExaminationSessionRow.status.in_(
                (
                    ExaminationSessionStatus.SCHEDULED.value,
                    ExaminationSessionStatus.IN_PROGRESS.value,
                )
            ),
        )
        .order_by(ExaminationSessionRow.created_at.desc())
        .limit(1)
    ).first()


def _has_active_psych_assignment(db: Session, client_id: str, employee_id: str) -> bool:
    try:
        from app.services.psych_test_assignments import get_active_assignment

        return get_active_assignment(db, client_id=client_id, employee_id=employee_id) is not None
    except Exception:
        _log.debug("psych assignment lookup failed", exc_info=True)
        return False


def _psych_engine_active(chat_id: str) -> bool:
    try:
        from psychological_testing.integration.session_store import get_session_store

        return get_session_store().get_engine(str(chat_id).strip()) is not None
    except Exception:
        return False


def decide_telegram_route(
    db: Session,
    telegram_chat_id: str,
    *,
    callback_data: str | None = None,
) -> TelegramRoute:
    """
    Куда направить входящее событие (сообщение или callback).

    Приоритет:
    1. pt: → psychological_testing
    2. Активная сессия теста в памяти (MBTI и т.д.) → psych
    3. Активное назначение психотестов + экзамен по регламентам ещё не в фазе questions → psych
    4. Иначе skill_assessment (регламенты, Part1, Part2)
    """
    tid = str(telegram_chat_id).strip()
    data = (callback_data or "").strip()
    if data.startswith("pt:"):
        return TelegramRoute.PSYCH_TESTING
    if _psych_engine_active(tid):
        return TelegramRoute.PSYCH_TESTING

    pair = _resolve_binding(db, tid)
    if pair is None:
        return TelegramRoute.SKILL_ASSESSMENT

    client_id, employee_id = pair
    if not _has_active_psych_assignment(db, client_id, employee_id):
        return TelegramRoute.SKILL_ASSESSMENT

    exam_row = _active_examination_row(db, client_id, employee_id)
    if exam_row is None:
        return TelegramRoute.PSYCH_TESTING

    phase = str(exam_row.phase or "")
    if phase in _EXAM_PHASES_DEFERRABLE_TO_PSYCH:
        return TelegramRoute.PSYCH_TESTING

    if phase == ExaminationPhase.QUESTIONS.value:
        return TelegramRoute.SKILL_ASSESSMENT

    # protocol / completed / unknown — не перехватываем психотестами
    return TelegramRoute.SKILL_ASSESSMENT
