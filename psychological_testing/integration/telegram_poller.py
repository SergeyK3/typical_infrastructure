"""
Long polling for psychological testing Telegram bot.

Enable: ``PSYCH_TESTING_ENABLE_POLLING=1`` and ``TELEGRAM_BOT_TOKEN`` in package ``.env``.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from psychological_testing.integration.telegram_adapter import PsychTestingTelegramAdapter

_log = logging.getLogger("psychological_testing.telegram")


def _api_base(token: str) -> str:
    return f"https://api.telegram.org/bot{token}"


def _chat_id_from_message(message: dict[str, Any]) -> str | None:
    chat = message.get("chat") or {}
    cid = chat.get("id")
    return str(cid) if cid is not None else None


def _callback_chat_id(cq: dict[str, Any]) -> str | None:
    msg = cq.get("message") or {}
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    if cid is not None:
        return str(cid)
    from_user = cq.get("from") or {}
    uid = from_user.get("id")
    return str(uid) if uid is not None else None


async def _download_voice(
    client: httpx.AsyncClient, token: str, file_id: str
) -> bytes:
    r = await client.get(f"{_api_base(token)}/getFile", params={"file_id": file_id})
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"getFile: {data}")
    fp = (data.get("result") or {}).get("file_path") or ""
    if not fp:
        raise RuntimeError("getFile: no file_path")
    url = f"https://api.telegram.org/file/bot{token}/{fp}"
    r2 = await client.get(url)
    r2.raise_for_status()
    return r2.content


async def _delete_webhook(client: httpx.AsyncClient, token: str) -> None:
    r = await client.post(
        f"{_api_base(token)}/deleteWebhook",
        json={"drop_pending_updates": True},
    )
    data = r.json()
    if not data.get("ok"):
        _log.warning("deleteWebhook: %s", data)


async def run_long_polling(token: str, adapter: PsychTestingTelegramAdapter | None = None) -> None:
    """Poll ``getUpdates`` until cancelled."""
    handler = adapter or PsychTestingTelegramAdapter(token=token)
    offset: int | None = None
    timeout = int(os.getenv("PSYCH_TESTING_POLL_TIMEOUT", "30") or "30")

    async with httpx.AsyncClient(timeout=timeout + 10) as client:
        await _delete_webhook(client, token)
        _log.info("psych_testing telegram: long polling started")

        while True:
            params: dict[str, Any] = {"timeout": timeout}
            if offset is not None:
                params["offset"] = offset
            try:
                r = await client.get(f"{_api_base(token)}/getUpdates", params=params)
                data = r.json()
            except Exception:
                _log.exception("getUpdates failed")
                await asyncio.sleep(2.0)
                continue

            if not data.get("ok"):
                err = data.get("error_code") if isinstance(data, dict) else None
                if err == 409:
                    _log.warning(
                        "getUpdates 409 — другой процесс уже polling этого бота; "
                        "остановите лишние telegram_worker / skill_assessment polling"
                    )
                    await asyncio.sleep(15.0)
                else:
                    _log.warning("getUpdates not ok: %s", data)
                    await asyncio.sleep(2.0)
                continue

            for update in data.get("result") or []:
                uid = update.get("update_id")
                if uid is not None:
                    offset = int(uid) + 1
                await _dispatch_update(client, token, handler, update)

            await asyncio.sleep(0.05)


async def _dispatch_update(
    client: httpx.AsyncClient,
    token: str,
    adapter: PsychTestingTelegramAdapter,
    update: dict[str, Any],
) -> None:
    if "callback_query" in update:
        cq = update["callback_query"]
        chat_id = _callback_chat_id(cq)
        if not chat_id:
            return
        qid = str(cq.get("id", ""))
        data = str(cq.get("data") or "")
        adapter.handle_callback(chat_id, qid, data)
        return

    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = _chat_id_from_message(message)
    if not chat_id:
        return

    if "voice" in message:
        file_id = message["voice"].get("file_id")
        if file_id:
            try:
                audio = await _download_voice(client, token, file_id)
                adapter.handle_voice(chat_id, audio)
            except Exception:
                _log.exception("voice download failed")
                adapter._send(
                    chat_id,
                    "Не удалось загрузить голосовое. Повторите или нажмите кнопку.",
                )
        return

    if "audio" in message:
        file_id = message["audio"].get("file_id")
        if file_id:
            try:
                audio = await _download_voice(client, token, file_id)
                adapter.handle_voice(chat_id, audio)
            except Exception:
                _log.exception("audio download/transcribe")
        return

    text = message.get("text") or ""
    is_command = text.strip().startswith("/")
    _log.info("incoming chat_id=%s text=%r", chat_id, text[:80])
    try:
        adapter.handle_text(chat_id, text, is_command=is_command)
    except Exception:
        _log.exception("handle_text failed chat_id=%s", chat_id)
        adapter._send(chat_id, "Ошибка обработки. Попробуйте /start mbti или /help.")
