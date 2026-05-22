# route: (telegram dev polling) | file: skill_assessment/integration/telegram_poller.py
"""
Long polling для Bot API (удобно в разработке без HTTPS webhook).

Включение: TELEGRAM_ENABLE_POLLING=1 и TELEGRAM_BOT_TOKEN в .env (корень репозитория).
Один токен — один процесс ``python -m skill_assessment.telegram_worker``:

- ``psychological_testing/`` — психологическое тестирование (назначение HR, /start mbti, callback ``pt:``)
- ``skill_assessment/`` — опрос по регламентам, Part1 ПДн (``dsp|``), Part2

Отдельный ``python -m psychological_testing.telegram_worker`` не нужен, если крутится этот воркер
(иначе Telegram 409 — два getUpdates на один токен).
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException

from app.services.telegram_cancel import is_cancel_command
from skill_assessment.services import stt_service as stt_svc
from skill_assessment.services.llm_post_stt_blacklist import assert_user_text_allowed_after_stt

_log = logging.getLogger("skill_assessment.telegram")


def _callback_query_chat_id(cq: dict[str, Any]) -> int | None:
    """
    Chat id для callback: обычно ``message.chat.id``.
    Если ``message`` пуст (редко, «старое» сообщение), в личке совпадает с ``from.id``.
    """
    msg = cq.get("message") or {}
    chat = msg.get("chat") or {}
    cid = chat.get("id")
    if cid is not None:
        try:
            return int(cid)
        except (TypeError, ValueError):
            pass
    from_user = cq.get("from")
    if isinstance(from_user, dict) and from_user.get("id") is not None:
        try:
            return int(from_user["id"])
        except (TypeError, ValueError):
            pass
    return None


def _api_base(token: str) -> str:
    return f"https://api.telegram.org/bot{token}"


def _run_exam_gate_turn(
    chat_id: int, text: str | None, is_start_command: bool
) -> list[tuple[str, dict[str, Any] | None]]:
    from app.db import SessionLocal

    from skill_assessment.services.telegram_docs_survey_exam_gate import handle_exam_gate_message

    db = SessionLocal()
    try:
        return handle_exam_gate_message(db, str(chat_id), text, is_start_command)
    finally:
        db.close()


def _run_docs_survey_pd_consent_turn(
    chat_id: int, text: str | None, is_start_command: bool
) -> list[tuple[str, dict[str, Any] | None]]:
    from app.db import SessionLocal

    from skill_assessment.services.telegram_docs_survey_consent import handle_docs_survey_pd_consent_message

    db = SessionLocal()
    try:
        return handle_docs_survey_pd_consent_message(db, str(chat_id), text, is_start_command)
    finally:
        db.close()


_psych_adapter_singleton = None


def _get_psych_telegram_adapter(token: str):
    global _psych_adapter_singleton
    if _psych_adapter_singleton is None:
        from psychological_testing.integration.telegram_adapter import PsychTestingTelegramAdapter

        _psych_adapter_singleton = PsychTestingTelegramAdapter(token=token)
    return _psych_adapter_singleton


def _run_psych_telegram_turn(
    token: str,
    chat_id: int,
    text: str | None,
    is_start_command: bool,
    *,
    voice_bytes: bytes | None = None,
    callback_data: str | None = None,
    callback_query_id: str | None = None,
) -> bool:
    """Обработка в psychological_testing. True — событие обработано."""
    from app.db import SessionLocal
    from app.services.telegram_unified_router import TelegramRoute, decide_telegram_route

    db = SessionLocal()
    try:
        route = decide_telegram_route(db, str(chat_id), callback_data=callback_data)
    finally:
        db.close()
    if route != TelegramRoute.PSYCH_TESTING:
        return False

    adapter = _get_psych_telegram_adapter(token)
    cid = str(chat_id)
    if callback_data and callback_query_id:
        adapter.handle_callback(cid, callback_query_id, callback_data)
        return True
    if voice_bytes:
        adapter.handle_voice(cid, voice_bytes)
        return True
    adapter.handle_text(cid, text or "", is_command=is_start_command)
    return True


def _run_cancel_command_turn(
    chat_id: int, *, telegram_token: str
) -> list[tuple[str, dict[str, Any] | None]]:
    from app.db import SessionLocal

    from app.services.telegram_cancel import handle_cancel_command

    db = SessionLocal()
    try:
        return handle_cancel_command(db, str(chat_id), telegram_token=telegram_token)
    finally:
        db.close()


def _run_dialog_dispatch_turn(
    chat_id: int, text: str | None, is_start_command: bool
) -> list[str]:
    from app.db import SessionLocal

    from skill_assessment.services.telegram_dispatcher import dispatch_dialog_message

    db = SessionLocal()
    try:
        return dispatch_dialog_message(db, str(chat_id), text, is_start_command)
    finally:
        db.close()


def _stt_blacklist_reject_message() -> str:
    return (
        "Текст после распознавания речи не прошёл автоматическую проверку. "
        "Сформулируйте ответ иначе или введите его с клавиатуры."
    )


def _check_text_after_stt_allowed(text: str) -> str | None:
    """None — можно отправлять в сценарий; иначе текст ответа пользователю."""
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        assert_user_text_allowed_after_stt(db, text)
        return None
    except HTTPException as e:
        if e.status_code == 422:
            return _stt_blacklist_reject_message()
        raise
    finally:
        db.close()


async def _download_telegram_file_bytes(client: httpx.AsyncClient, token: str, file_id: str) -> bytes:
    raw, _ = await _download_telegram_voice_payload(client, token, file_id)
    return raw


async def _download_telegram_voice_payload(
    client: httpx.AsyncClient, token: str, file_id: str
) -> tuple[bytes, str]:
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
    return r2.content, Path(fp).name or "voice.oga"


async def _download_and_transcribe_telegram_voice(
    client: httpx.AsyncClient, token: str, file_id: str
) -> str:
    """Скачивает voice/audio из Telegram и возвращает транскрипт (STT)."""
    raw, fname = await _download_telegram_voice_payload(client, token, file_id)
    return await asyncio.to_thread(
        stt_svc.transcribe_audio_bytes,
        raw,
        filename=fname,
        content_type=None,
    )


async def _delete_webhook(client: httpx.AsyncClient, token: str) -> None:
    # Сбросить «хвост» апдейтов (в т.ч. протухшие callback) при переходе на long polling.
    r = await client.post(f"{_api_base(token)}/deleteWebhook", json={"drop_pending_updates": True})
    data = r.json()
    if not data.get("ok"):
        _log.warning("telegram deleteWebhook: %s", data)


async def _send_message(
    client: httpx.AsyncClient, token: str, chat_id: int, text: str, reply_markup: dict | None = None
) -> None:
    # Telegram лимит ~4096 символов на сообщение
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size]
        payload: dict[str, Any] = {"chat_id": chat_id, "text": chunk}
        if reply_markup is not None and i == 0:
            payload["reply_markup"] = reply_markup
        r = await client.post(f"{_api_base(token)}/sendMessage", json=payload)
        data = r.json()
        if not data.get("ok"):
            _log.warning("telegram sendMessage: %s", data)


async def _answer_callback_query(
    client: httpx.AsyncClient,
    token: str,
    query_id: str,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> bool:
    """
    Подтверждение callback. Telegram ждёт ответ быстро; иначе «query is too old».
    Возвращает True при успехе.
    """
    payload: dict[str, Any] = {"callback_query_id": query_id}
    if text:
        payload["text"] = text[:200]
    if show_alert:
        payload["show_alert"] = True
    r = await client.post(f"{_api_base(token)}/answerCallbackQuery", json=payload)
    data = r.json()
    if not data.get("ok"):
        desc = str(data.get("description") or "")
        if "query is too old" in desc or "query ID is invalid" in desc:
            _log.info("telegram answerCallbackQuery (устарел, это норм после рестарта): %s", data)
        else:
            _log.warning("telegram answerCallbackQuery: %s", data)
        return False
    return True


def _run_docs_survey_callback_turn(chat_id: str, callback_data: str, query_id: str) -> Any:
    from app.db import SessionLocal

    from skill_assessment.services.telegram_docs_survey import handle_docs_survey_callback

    db = SessionLocal()
    try:
        return handle_docs_survey_callback(db, chat_id, callback_data, query_id)
    finally:
        db.close()


def _run_pd_consent_callback_turn(chat_id: str, callback_data: str, query_id: str) -> Any:
    from app.db import SessionLocal

    from skill_assessment.services.telegram_docs_survey_consent import handle_pd_consent_callback

    db = SessionLocal()
    try:
        return handle_pd_consent_callback(db, chat_id, callback_data)
    finally:
        db.close()


def _run_readiness_callback_turn(chat_id: str, callback_data: str, query_id: str) -> Any:
    from app.db import SessionLocal

    from skill_assessment.services.telegram_docs_survey_readiness import handle_docs_survey_readiness_callback

    db = SessionLocal()
    try:
        return handle_docs_survey_readiness_callback(db, chat_id, callback_data)
    finally:
        db.close()


def _run_epc_consent_callback_turn(chat_id: str, callback_data: str) -> Any:
    from app.db import SessionLocal

    from app.services.telegram_employee_consent import handle_consent_callback

    db = SessionLocal()
    try:
        return handle_consent_callback(db, chat_id, callback_data)
    finally:
        db.close()


def _run_epc_consent_message_turn(
    chat_id: str, text: str | None, is_start_command: bool
) -> list[tuple[str, dict[str, Any] | None]]:
    from app.db import SessionLocal

    from app.services.telegram_employee_consent import handle_consent_message

    db = SessionLocal()
    try:
        result = handle_consent_message(db, chat_id, text)
    finally:
        db.close()
    if result is None:
        return []
    return list(result.outgoing)


async def _deliver_consent_callback_turn(
    client: httpx.AsyncClient,
    token: str,
    chat_id: int,
    query_id: str,
    result: Any,
) -> None:
    """Исходящие после inline «Да»/«Нет» (dsp| или epc|)."""
    if result is None:
        await _answer_callback_query(client, token, query_id, None)
        return
    has_out = any((t or "").strip() for t, _ in getattr(result, "outgoing", []) or [])
    if has_out:
        await _answer_callback_query(client, token, query_id, None)
        for text, markup in result.outgoing:
            if text:
                await _send_message(client, token, chat_id, text, reply_markup=markup)
    else:
        tip = (getattr(result, "popup_text", None) or "").strip() or "Готово."
        await _answer_callback_query(client, token, query_id, tip, show_alert=True)


async def _dispatch_callback_query(client: httpx.AsyncClient, token: str, cq: dict[str, Any]) -> None:
    qid = cq.get("id")
    raw = cq.get("data")
    if qid is None or raw is None:
        return
    data = str(raw).strip()

    cid_int = _callback_query_chat_id(cq)
    if cid_int is None:
        _log.warning("telegram: callback_query без chat id, data=%r", data[:72])
        return
    cid = cid_int
    chat_id = str(cid_int)

    if data.startswith("epc|"):
        try:
            result = await asyncio.to_thread(_run_epc_consent_callback_turn, chat_id, data)
        except Exception:
            _log.exception("telegram: обработка epc| callback не удалась")
            await _answer_callback_query(
                client, token, str(qid), "Ошибка сервера, попробуйте позже.", show_alert=True
            )
            await _send_message(client, token, int(cid), "Ошибка сервера, попробуйте позже.")
            return
        await _deliver_consent_callback_turn(client, token, int(cid), str(qid), result)
        return

    if await asyncio.to_thread(
        _run_psych_telegram_turn,
        token,
        int(cid),
        None,
        False,
        callback_data=data,
        callback_query_id=str(qid),
    ):
        return

    if data.startswith("dsr|"):
        try:
            result = await asyncio.to_thread(_run_readiness_callback_turn, chat_id, data, str(qid))
        except Exception:
            _log.exception("telegram: обработка dsr| callback не удалась")
            await _answer_callback_query(client, token, str(qid), "Ошибка сервера, попробуйте позже.", show_alert=True)
            await _send_message(client, token, int(cid), "Ошибка сервера, попробуйте позже.")
            return
        if result is None:
            await _answer_callback_query(client, token, str(qid), None)
            return
        has_out = any((t or "").strip() for t, _ in result.outgoing)
        if has_out:
            await _answer_callback_query(client, token, str(qid), None)
            for text, markup in result.outgoing:
                if text:
                    await _send_message(client, token, int(cid), text, reply_markup=markup)
        else:
            tip = (result.popup_text or "").strip() or "Готово."
            await _answer_callback_query(client, token, str(qid), tip, show_alert=True)
        return
    if data.startswith("dsp|"):
        try:
            result = await asyncio.to_thread(_run_pd_consent_callback_turn, chat_id, data, str(qid))
        except Exception:
            _log.exception("telegram: обработка dsp| callback не удалась")
            await _answer_callback_query(client, token, str(qid), "Ошибка сервера, попробуйте позже.", show_alert=True)
            await _send_message(client, token, int(cid), "Ошибка сервера, попробуйте позже.")
            return
        await _deliver_consent_callback_turn(client, token, int(cid), str(qid), result)
        return
    if not data.startswith(("dsd|", "dst|")):
        return
    try:
        result = await asyncio.to_thread(_run_docs_survey_callback_turn, chat_id, data, str(qid))
    except Exception:
        _log.exception("telegram: обработка dsd/dst callback не удалась")
        await _answer_callback_query(client, token, str(qid), "Ошибка сервера, попробуйте ещё раз.", show_alert=True)
        await _send_message(client, token, int(cid), "Ошибка сервера, попробуйте ещё раз.")
        return
    if result is None:
        await _answer_callback_query(client, token, str(qid), None)
        return
    has_out = any((t or "").strip() for t, _ in result.outgoing)
    if has_out:
        await _answer_callback_query(client, token, str(qid), None)
        for text, markup in result.outgoing:
            if text:
                await _send_message(client, token, int(cid), text, reply_markup=markup)
    else:
        tip = (result.popup_text or "").strip() or "Готово."
        await _answer_callback_query(client, token, str(qid), tip, show_alert=True)


def _extract_incoming_message(update: dict[str, Any]) -> tuple[int | None, str, str | None]:
    """chat_id, подпись/текст, file_id голосового или аудио (если есть) — для STT."""
    msg = update.get("message") or update.get("edited_message")
    if not msg or not isinstance(msg, dict):
        return None, "", None
    chat = msg.get("chat")
    if not chat:
        return None, "", None
    cid = chat.get("id")
    if cid is None:
        return None, "", None
    text = str(msg.get("text") or msg.get("caption") or "").strip()
    voice = msg.get("voice")
    audio = msg.get("audio")
    file_id: str | None = None
    if isinstance(voice, dict) and voice.get("file_id"):
        file_id = str(voice["file_id"])
    elif isinstance(audio, dict) and audio.get("file_id"):
        file_id = str(audio["file_id"])
    return int(cid), text, file_id


async def run_long_polling(token: str) -> None:
    """Бесконечный цикл getUpdates; сценарий экзамена через handle_telegram_message."""
    token = token.strip()
    if not token:
        _log.error("telegram: empty TELEGRAM_BOT_TOKEN")
        return

    offset: int | None = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        await _delete_webhook(client, token)
        wh = await client.get(f"{_api_base(token)}/getWebhookInfo")
        _log.info("telegram getWebhookInfo after delete: %s", wh.json())
        _log.info(
            "skill_assessment.telegram: long polling (unified: psych_testing + skill_assessment)"
        )

        while True:
            try:
                params: dict[str, Any] = {
                    "timeout": 50,
                    "allowed_updates": ["message", "edited_message", "callback_query"],
                }
                if offset is not None:
                    params["offset"] = offset
                r = await client.get(f"{_api_base(token)}/getUpdates", params=params)
                data = r.json()
                if not data.get("ok"):
                    err = data.get("error_code") if isinstance(data, dict) else None
                    # 409 — второй long poll на тот же токен; без паузы спамим API и лог.
                    if err == 409:
                        _log.warning(
                            "telegram getUpdates 409 (другой getUpdates на этот бот) — пауза 20 с"
                        )
                        await asyncio.sleep(20)
                    else:
                        _log.warning("telegram getUpdates not ok: %s", data)
                        await asyncio.sleep(3)
                    continue
                for upd in data.get("result") or []:
                    uid = upd.get("update_id")
                    if uid is not None:
                        offset = int(uid) + 1
                    cq = upd.get("callback_query")
                    if isinstance(cq, dict):
                        await _dispatch_callback_query(client, token, cq)
                        continue
                    chat_id, text, voice_file_id = _extract_incoming_message(upd)
                    if chat_id is None:
                        continue
                    if is_cancel_command(text):
                        cancel_parts = await asyncio.to_thread(
                            _run_cancel_command_turn, chat_id, telegram_token=token
                        )
                        for txt, markup in cancel_parts:
                            if txt:
                                await _send_message(
                                    client, token, chat_id, txt, reply_markup=markup
                                )
                        continue
                    parts = text.strip().split() if text else []
                    first_cmd = parts[0] if parts else ""
                    is_start = first_cmd == "/start" or first_cmd.startswith("/start@")
                    _log.debug("telegram: chat_id=%s is_start=%s text=%r", chat_id, is_start, text)
                    voice_bytes: bytes | None = None
                    if voice_file_id:
                        try:
                            voice_bytes = await _download_telegram_file_bytes(client, token, voice_file_id)
                        except Exception:
                            _log.exception("telegram: voice download failed")
                            await _send_message(
                                client,
                                token,
                                chat_id,
                                "Не удалось загрузить голосовое. Повторите запись или ответьте текстом.",
                            )
                            continue
                        if await asyncio.to_thread(
                            _run_psych_telegram_turn,
                            token,
                            chat_id,
                            text,
                            is_start,
                            voice_bytes=voice_bytes,
                        ):
                            continue
                        try:
                            _, fname = await _download_telegram_voice_payload(
                                client, token, voice_file_id
                            )
                            transcribed = await asyncio.to_thread(
                                stt_svc.transcribe_audio_bytes,
                                voice_bytes,
                                filename=fname,
                                content_type=None,
                            )
                            transcribed = (transcribed or "").strip()
                            if not transcribed:
                                await _send_message(
                                    client,
                                    token,
                                    chat_id,
                                    "Речь не распознана. Повторите голосовое сообщение или отправьте ответ текстом.",
                                )
                                continue
                            bl = await asyncio.to_thread(_check_text_after_stt_allowed, transcribed)
                            if bl:
                                await _send_message(client, token, chat_id, bl)
                                continue
                            if text:
                                text = f"{text}\n{transcribed}".strip()
                            else:
                                text = transcribed
                        except stt_svc.SttConfigurationError:
                            await _send_message(
                                client,
                                token,
                                chat_id,
                                "Распознавание речи не настроено на сервере "
                                "(переменные SKILL_ASSESSMENT_STT_PROVIDER / ключ OpenAI). "
                                "Ответьте текстом или попросите администратора включить STT.",
                            )
                            continue
                        except ValueError as exc:
                            code = str(exc)
                            if "empty_audio" in code:
                                msg = "Пустое аудио. Запишите голосовое сообщение ещё раз."
                            elif "audio_too_large" in code:
                                msg = "Файл слишком большой. Запишите более короткое сообщение или ответьте текстом."
                            else:
                                msg = "Не удалось обработать аудио. Ответьте текстом."
                            await _send_message(client, token, chat_id, msg)
                            continue
                        except Exception:
                            _log.exception("telegram: STT voice message failed")
                            await _send_message(
                                client,
                                token,
                                chat_id,
                                "Не удалось распознать голос. Повторите запись или отправьте ответ текстом.",
                            )
                            continue
                    if await asyncio.to_thread(
                        _run_psych_telegram_turn,
                        token,
                        chat_id,
                        text,
                        is_start,
                        voice_bytes=voice_bytes,
                    ):
                        continue
                    gate_parts = await asyncio.to_thread(_run_exam_gate_turn, chat_id, text, is_start)
                    if gate_parts:
                        for txt, markup in gate_parts:
                            if txt:
                                await _send_message(client, token, chat_id, txt, reply_markup=markup)
                        continue
                    consent_parts = await asyncio.to_thread(
                        _run_docs_survey_pd_consent_turn, chat_id, text, is_start
                    )
                    if consent_parts:
                        for txt, markup in consent_parts:
                            if txt:
                                await _send_message(client, token, chat_id, txt, reply_markup=markup)
                        continue
                    epc_parts = await asyncio.to_thread(
                        _run_epc_consent_message_turn, chat_id, text, is_start
                    )
                    if epc_parts:
                        for txt, markup in epc_parts:
                            if txt:
                                await _send_message(client, token, chat_id, txt, reply_markup=markup)
                        continue
                    lines = await asyncio.to_thread(_run_dialog_dispatch_turn, chat_id, text, is_start)
                    for line in lines:
                        if line:
                            await _send_message(client, token, chat_id, line)
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("telegram polling loop error")
                await asyncio.sleep(5)


def start_background_polling(token: str) -> asyncio.Task[None]:
    return asyncio.create_task(run_long_polling(token), name="skill_assessment_telegram_poll")
