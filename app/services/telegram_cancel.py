"""Единая обработка /cancel для одного Telegram-бота."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


def is_cancel_command(text: str | None) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    cmd = raw.split()[0].split("@")[0].lower()
    return cmd == "/cancel"


def _dismiss_examination_consent_intro(
    db: Session, client_id: str, employee_id: str
) -> str | None:
    from skill_assessment.domain.examination_entities import (
        ExaminationPhase,
        ExaminationSessionStatus,
    )
    from skill_assessment.infrastructure.db_models import ExaminationSessionRow
    from sqlalchemy import select

    row = db.scalars(
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
    if row is None:
        return None
    phase = str(row.phase or "")
    if phase not in (ExaminationPhase.CONSENT.value, ExaminationPhase.INTRO.value):
        return None
    row.status = ExaminationSessionStatus.CANCELLED.value
    row.phase = ExaminationPhase.COMPLETED.value
    db.add(row)
    db.commit()
    return (
        "Шаг опроса по внутренним регламентам отменён.\n\n"
        "Для психологического тестирования откройте сообщение от HR и нажмите «Пройти»."
    )


def handle_cancel_command(
    db: Session,
    chat_id: str,
    *,
    telegram_token: str | None = None,
) -> list[tuple[str, dict[str, Any] | None]]:
    """
    Сообщения для отправки в чат.

    Пустой список — ответ уже отправил psych-адаптер (активная сессия теста).
    """
    cid = str(chat_id).strip()

    try:
        from psychological_testing.integration.session_store import get_session_store

        store = get_session_store()
        if store.get_engine(cid):
            if telegram_token:
                try:
                    from skill_assessment.integration.telegram_poller import (
                        _get_psych_telegram_adapter,
                    )

                    _get_psych_telegram_adapter(telegram_token).cancel_session(cid)
                except Exception:
                    from psychological_testing.adapters.telegram_outbound import (
                        get_telegram_outbound,
                    )

                    engine = store.get_engine(cid)
                    if engine is not None:
                        engine.cancel()
                    store.clear_engine(cid)
                    binding = store.get_binding(cid)
                    if binding:
                        binding.context = "idle"
                        binding.active_test_id = None
                        binding.active_step_key = None
                        binding.active_assignment_id = None
                        binding.mbti_delivery_mode = None
                    get_telegram_outbound().send_message(
                        token=telegram_token,
                        chat_id=cid,
                        text="Сессия отменена.",
                    )
            return []
    except Exception:
        pass

    pair = None
    try:
        from skill_assessment.services.telegram_examination import _resolve_binding

        pair = _resolve_binding(db, cid)
    except Exception:
        pair = None

    if pair:
        client_id, employee_id = pair
        exam_msg = _dismiss_examination_consent_intro(db, client_id, employee_id)
        if exam_msg:
            return [(exam_msg, None)]

        try:
            from skill_assessment.domain.examination_entities import ExaminationPhase
            from skill_assessment.services.telegram_unified_router import _active_examination_row

            exam_row = _active_examination_row(db, client_id, employee_id)
            if exam_row is not None and str(exam_row.phase or "") == ExaminationPhase.BLOCKED_CONSENT.value:
                return [
                    (
                        "Согласие заблокировано до действий HR. После снятия блока напишите в этот чат — "
                        "бот предложит шаги снова.",
                        None,
                    )
                ]
        except Exception:
            pass

        try:
            from app.services.employee_consent import (
                get_pd_consent,
                needs_pd_consent_prompt,
            )

            snap = get_pd_consent(db, client_id, employee_id)
            if needs_pd_consent_prompt(snap):
                return [
                    (
                        "Запрос согласия отложён. Подтвердите его кнопками «Да»/«Нет» "
                        "в сообщении от HR, когда будете готовы.",
                        None,
                    )
                ]
        except Exception:
            pass

        try:
            from app.services.psych_test_assignments import get_active_assignment

            if get_active_assignment(db, client_id=client_id, employee_id=employee_id):
                return [
                    (
                        "Активного теста нет. Откройте сообщение от HR и нажмите «Пройти».",
                        None,
                    )
                ]
        except Exception:
            pass

    return [("Нечего отменять.", None)]
