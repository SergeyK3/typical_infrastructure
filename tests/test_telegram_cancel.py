"""Обработка /cancel в едином Telegram-боте."""

from __future__ import annotations

import pytest

from app.db import Base, SessionLocal, engine
from app.services.telegram_cancel import handle_cancel_command, is_cancel_command


@pytest.fixture
def db():
    import app.models  # noqa: F401
    import skill_assessment.infrastructure.db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_is_cancel_command() -> None:
    assert is_cancel_command("/cancel")
    assert is_cancel_command("/cancel@MyBot")
    assert not is_cancel_command("/start paei")


def test_cancel_dismisses_examination_consent(db, monkeypatch: pytest.MonkeyPatch) -> None:
    from skill_assessment.domain.examination_entities import (
        ExaminationPhase,
        ExaminationSessionStatus,
    )
    from skill_assessment.infrastructure.db_models import ExaminationSessionRow

    monkeypatch.setenv("TELEGRAM_DEV_CLIENT_ID", "c_cancel")
    monkeypatch.setenv("TELEGRAM_DEV_EMPLOYEE_ID", "e_cancel")

    row = ExaminationSessionRow(
        id="ex_cancel_01",
        client_id="c_cancel",
        employee_id="e_cancel",
        scenario_id="regulation_v1",
        status=ExaminationSessionStatus.SCHEDULED.value,
        phase=ExaminationPhase.CONSENT.value,
    )
    db.add(row)
    db.commit()

    from app.services.telegram_cancel import _dismiss_examination_consent_intro

    msg = _dismiss_examination_consent_intro(db, "c_cancel", "e_cancel")
    assert msg
    assert "регламентам отменён" in msg
    db.refresh(row)
    assert row.status == ExaminationSessionStatus.CANCELLED.value
