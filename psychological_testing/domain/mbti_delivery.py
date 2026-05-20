"""Resolve MBTI delivery mode (structured vs dialog) for Telegram and API."""

from __future__ import annotations

import os
import re
from typing import Literal

_DEV_EMPLOYEE_IDS = frozenset({"dev-employee", "dev-client", "dev", "employee", "участник"})
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

MbtiDeliveryMode = Literal["structured", "dialog"]

_VALID_MODES: frozenset[str] = frozenset({"structured", "dialog"})
_DEFAULT_MODE: MbtiDeliveryMode = "structured"

DIALOG_VOICE_HINT_RU = (
    "🎤 Ваш ответ — голосовым сообщением (кнопка микрофона в Telegram)."
)
DIALOG_AKMA_CHANNEL_NOTE = "Акма задаёт вопросы текстом в чате."
DIALOG_VOICE_STT_SETUP = (
    "Для голосовых ответов в mbti_dialog включите STT:\n"
    "PSYCH_TESTING_STT_PROVIDER=openai и PSYCH_TESTING_OPENAI_API_KEY (или OPENAI_API_KEY)."
)


def mbti_delivery_mode_from_env() -> MbtiDeliveryMode:
    """``PSYCH_TESTING_MBTI_DELIVERY_MODE``: ``structured`` (default) | ``dialog``."""
    raw = os.getenv("PSYCH_TESTING_MBTI_DELIVERY_MODE", _DEFAULT_MODE).strip().lower()
    if raw in _VALID_MODES:
        return raw  # type: ignore[return-value]
    return _DEFAULT_MODE


def _normalize_start_arg(start_arg: str) -> str:
    """Strip ``@BotName`` suffix from Telegram command arguments."""
    return start_arg.strip().lower().split("@", 1)[0]


def resolve_mbti_start_arg(start_arg: str) -> tuple[str, MbtiDeliveryMode]:
    """
    Map ``/start`` argument to ``(test_id, delivery_mode)``.

    Explicit overrides:
      - ``mbti_structured`` → structured
      - ``mbti_dialog`` / ``mbti_akma`` → dialog
      - ``mbti`` → env default (``PSYCH_TESTING_MBTI_DELIVERY_MODE``)
    """
    key = _normalize_start_arg(start_arg)
    if key in ("mbti_structured", "mbti-structured"):
        return "mbti", "structured"
    if key in ("mbti_dialog", "mbti-dialog", "mbti_akma", "mbti-akma"):
        return "mbti", "dialog"
    if key == "mbti":
        return "mbti", mbti_delivery_mode_from_env()
    return key, _DEFAULT_MODE  # type: ignore[return-value]


def mbti_dialog_requires_ai() -> bool:
    """Dialog mode needs LLM; check ``PSYCH_TESTING_AI_ENABLED``."""
    raw = os.getenv("PSYCH_TESTING_AI_ENABLED", "").strip().lower()
    return raw in ("1", "true", "yes")


def mbti_dialog_voice_primary() -> bool:
    """Dialog UX: voice-first answers (default on)."""
    raw = os.getenv("PSYCH_TESTING_MBTI_DIALOG_VOICE_PRIMARY", "1").strip().lower()
    return raw not in ("0", "false", "no")


def dialog_accepts_text() -> bool:
    """
    Text answers in mbti_dialog.

    Allowed when STT is mock (dev/tests) or ``PSYCH_TESTING_MBTI_DIALOG_ALLOW_TEXT=1``.
    With live Whisper + voice_primary, only voice is accepted.
    """
    allow = os.getenv("PSYCH_TESTING_MBTI_DIALOG_ALLOW_TEXT", "").strip().lower()
    if allow in ("1", "true", "yes"):
        return True
    from psychological_testing.services.stt_service import stt_provider

    if stt_provider() == "mock":
        return True
    return not mbti_dialog_voice_primary()


def dialog_stt_live() -> bool:
    """True when Whisper (or explicit openai provider) is active, not env mock."""
    from psychological_testing.services.stt_service import stt_provider

    return stt_provider() == "openai"


def dialog_voice_reprompt(*, empty: bool = False) -> str:
    if empty:
        base = "Не удалось распознать голос. Повторите короче и чётче."
    else:
        base = "Ответ не принят."
    if dialog_stt_live():
        return f"{base}\n\n{DIALOG_VOICE_HINT_RU}"
    return f"{base}\n\n{DIALOG_VOICE_STT_SETUP}\n\n(Dev: пока STT=mock — можно ответить текстом.)"


def participant_greeting_name(
    employee_id: str,
    *,
    hr_display_name: str | None = None,
) -> str | None:
    """
    Имя для приветствия в чате.

    Сейчас: dev-заглушки и UUID без имени → ``None`` (без «Здравствуйте, dev-employee!»).
    После ``hr_core``: передать ``hr_display_name`` из карточки Employee.
    """
    if hr_display_name and hr_display_name.strip():
        return hr_display_name.strip()
    eid = (employee_id or "").strip()
    if not eid:
        return None
    low = eid.lower()
    if low in _DEV_EMPLOYEE_IDS or low.startswith("dev-"):
        return None
    if _UUID_RE.match(eid):
        return None
    return eid
