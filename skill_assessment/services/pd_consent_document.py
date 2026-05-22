"""Ссылка на текст согласия ПДн (общая для Part1 и опроса по регламентам)."""

from __future__ import annotations

import os


def _normalize_consent_url(url: str) -> str:
    """Ссылка на просмотр Google Docs (edit часто требует вход и выглядит «недействительной»)."""
    u = url.strip()
    if "docs.google.com/document/d/" in u and "/edit" in u:
        u = u.replace("/edit", "/view", 1)
    return u


def pd_consent_document_url() -> str | None:
    """
    URL текста согласия на обработку ПДн.

    Переменные (первая непустая):
    - TELEGRAM_PD_CONSENT_DOCUMENT_URL
    - DOCS_SURVEY_CONSENT_DOCUMENT_URL
    """
    for key in ("TELEGRAM_PD_CONSENT_DOCUMENT_URL", "DOCS_SURVEY_CONSENT_DOCUMENT_URL"):
        raw = (os.getenv(key) or "").strip()
        if raw:
            return _normalize_consent_url(raw)
    return None


def pd_consent_link_line() -> str:
    """Строка для вставки в Telegram-сообщение или пустая строка."""
    url = pd_consent_document_url()
    if not url:
        return ""
    return f"\n\nТекст согласия: {url}"
