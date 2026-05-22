"""Маршрутизация одного Telegram-бота: psych vs skill_assessment."""

from app.db import SessionLocal
from app.services.telegram_unified_router import TelegramRoute, decide_telegram_route


def test_route_psych_when_callback_pt_prefix():
    db = SessionLocal()
    try:
        assert (
            decide_telegram_route(db, "300398364", callback_data="pt:s1:q1:A")
            == TelegramRoute.PSYCH_TESTING
        )
    finally:
        db.close()
