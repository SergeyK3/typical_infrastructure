"""
Исходящие сообщения в Telegram Bot API.

Переключение: ``PSYCH_TESTING_TELEGRAM_OUTBOUND`` = ``mock`` | ``http``.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelegramOutboundResult:
    ok: bool
    http_status: int | None = None
    description: str | None = None


class FakeTelegramOutbound:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.callback_answers: list[dict[str, Any]] = []

    def send_message(
        self,
        *,
        token: str,
        chat_id: str,
        text: str,
        reply_markup: dict[str, Any] | None,
    ) -> TelegramOutboundResult:
        self.messages.append(
            {
                "token_set": bool(token and len(token) >= 10),
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )
        return TelegramOutboundResult(ok=True, http_status=200, description="fake_ok")

    def answer_callback_query(
        self,
        *,
        token: str,
        callback_query_id: str,
        text: str | None = None,
    ) -> TelegramOutboundResult:
        self.callback_answers.append(
            {
                "token_set": bool(token and len(token) >= 10),
                "callback_query_id": callback_query_id,
                "text": text,
            }
        )
        return TelegramOutboundResult(ok=True, http_status=200, description="fake_ok")

    def clear(self) -> None:
        self.messages.clear()
        self.callback_answers.clear()


_fake_singleton: FakeTelegramOutbound | None = None


def clear_fake_telegram_outbound() -> None:
    global _fake_singleton
    if _fake_singleton is not None:
        _fake_singleton.clear()


class HttpxTelegramOutbound:
    def _post(
        self,
        token: str,
        method: str,
        payload: dict[str, Any],
    ) -> TelegramOutboundResult:
        url = f"https://api.telegram.org/bot{token}/{method}"
        try:
            timeout_sec = float(
                (os.getenv("TELEGRAM_HTTP_TIMEOUT_SECONDS") or "45").strip() or "45"
            )
        except ValueError:
            timeout_sec = 45.0
        try:
            max_attempts = max(
                1, min(8, int((os.getenv("TELEGRAM_SEND_MAX_ATTEMPTS") or "3").strip() or "3"))
            )
        except ValueError:
            max_attempts = 3

        last_err: str | None = None
        last_status: int | None = None
        for attempt in range(max_attempts):
            try:
                r = httpx.post(url, json=payload, timeout=timeout_sec)
                data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                last_status = r.status_code
                if r.status_code in (429, 500, 502, 503, 504) and attempt + 1 < max_attempts:
                    wait = min(8.0, 1.5 * (2**attempt))
                    time.sleep(wait)
                    continue
                if not r.is_success:
                    detail = data.get("description") if isinstance(data, dict) else r.text[:300]
                    return TelegramOutboundResult(
                        ok=False, http_status=r.status_code, description=str(detail)
                    )
                if isinstance(data, dict) and data.get("ok"):
                    return TelegramOutboundResult(ok=True, http_status=r.status_code)
                return TelegramOutboundResult(
                    ok=False, http_status=r.status_code, description=str(data)[:400]
                )
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
                last_err = str(e)[:200]
                if attempt + 1 < max_attempts:
                    time.sleep(min(8.0, 1.5 * (2**attempt)))
                    continue
                return TelegramOutboundResult(ok=False, http_status=last_status, description=last_err)
        return TelegramOutboundResult(ok=False, http_status=last_status, description=last_err or "send_failed")

    def send_message(
        self,
        *,
        token: str,
        chat_id: str,
        text: str,
        reply_markup: dict[str, Any] | None,
    ) -> TelegramOutboundResult:
        chunk_size = 4000
        last: TelegramOutboundResult = TelegramOutboundResult(ok=False, description="empty_text")
        for i in range(0, max(len(text), 1), chunk_size):
            chunk = text[i : i + chunk_size]
            payload: dict[str, Any] = {"chat_id": chat_id, "text": chunk}
            if reply_markup is not None and i == 0:
                payload["reply_markup"] = reply_markup
            last = self._post(token, "sendMessage", payload)
            if not last.ok:
                return last
        return last

    def answer_callback_query(
        self,
        *,
        token: str,
        callback_query_id: str,
        text: str | None = None,
    ) -> TelegramOutboundResult:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text[:200]
        return self._post(token, "answerCallbackQuery", payload)


def get_telegram_outbound() -> FakeTelegramOutbound | HttpxTelegramOutbound:
    raw = os.getenv("PSYCH_TESTING_TELEGRAM_OUTBOUND", "").strip().lower()
    if raw == "mock":
        global _fake_singleton
        if _fake_singleton is None:
            _fake_singleton = FakeTelegramOutbound()
        return _fake_singleton
    return HttpxTelegramOutbound()
