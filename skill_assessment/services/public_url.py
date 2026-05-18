# route: (urls) | file: skill_assessment/services/public_url.py
"""Базовый URL для ссылок в Telegram: на телефоне недоступны localhost и 127.0.0.1."""

from __future__ import annotations

import os

DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:8000"


def _normalized_base_url(value: str | None) -> str | None:
    base = (value or "").strip().rstrip("/")
    return base or None


def skill_assessment_public_base_url_for_device_links() -> str | None:
    """
    Возвращает ``SKILL_ASSESSMENT_PUBLIC_BASE_URL``, если он задан и не указывает на локальную машину.

    Для ссылок в SMS/Telegram на телефоне нужен реальный хост (например HTTPS из ngrok).
    """
    base = _normalized_base_url(os.getenv("SKILL_ASSESSMENT_PUBLIC_BASE_URL"))
    if not base:
        return None
    low = base.lower()
    if "127.0.0.1" in low or "localhost" in low or "0.0.0.0" in low:
        return None
    return base


def skill_assessment_hr_base_url_for_browser_links() -> str:
    """
    Базовый URL для ссылок, которые HR открывает в браузере рядом с локальным API.

    Не используем ``SKILL_ASSESSMENT_PUBLIC_BASE_URL`` как fallback: в разработке там часто
    остаётся устаревший tunnel URL, который открывается как ``503 Tunnel Unavailable``.
    Если HR должен открывать ссылки извне, задайте ``SKILL_ASSESSMENT_HR_BASE_URL`` явно.
    """
    return (
        _normalized_base_url(os.getenv("SKILL_ASSESSMENT_HR_BASE_URL"))
        or _normalized_base_url(os.getenv("SKILL_ASSESSMENT_INTERNAL_BASE_URL"))
        or DEFAULT_LOCAL_BASE_URL
    )
