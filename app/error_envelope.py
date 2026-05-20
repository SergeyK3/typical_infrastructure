# app/error_envelope.py
r"""Unified error envelope for API responses (Step 7)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.logging_middleware import get_request_id


# Human-readable messages for common error codes
_ERROR_MESSAGES: dict[str, str] = {
    "client_not_found": "Клиент не найден.",
    "template_not_found": "Шаблон предприятия не найден.",
    "org_unit_not_found": "Организационная единица не найдена.",
    "org_unit_cycle": "Обнаружен цикл в оргструктуре.",
    "parent_not_found": "Родительская единица не найдена.",
    "position_not_found": "Должность не найдена.",
    "employee_not_found": "Сотрудник не найден.",
    "employee_not_in_client": "Сотрудник не принадлежит указанному клиенту.",
    "account_not_found": "Аккаунт не найден.",
    "login_already_exists": "Пользователь с таким логином уже существует.",
    "run_not_found": "Запуск onboarding не найден.",
    "run_not_found_after_create": "Ошибка: run не найден после создания.",
    "wizard_not_found": "Мастер onboarding не найден.",
    "client_mismatch": "Несоответствие клиента.",
    "invalid_role_codes": "Указаны несуществующие коды ролей.",
    "telegram_chat_not_found": (
        "Telegram не нашёл чат сотрудника. Пусть сотрудник напишет вашему боту /start, "
        "затем укажите в карточке числовой chat_id (как в логах worker), не @username."
    ),
    "employee_no_telegram": "У сотрудника не заполнено поле Telegram в карточке.",
    "telegram_bot_token_missing": "Не задан TELEGRAM_BOT_TOKEN в .env.",
}


def _get_message_for_code(code: str, fallback: str) -> str:
    if code in _ERROR_MESSAGES:
        return _ERROR_MESSAGES[code]
    if code.startswith("invalid_role_codes:"):
        return _ERROR_MESSAGES["invalid_role_codes"]
    return fallback


def _envelope(
    code: str,
    message: str,
    details: list[dict] | None = None,
    trace_id: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build unified error envelope."""
    err: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        err["details"] = details
    if trace_id:
        err["trace_id"] = trace_id
    if extra:
        err.update(extra)
    return {"error": err}




def http_exception_handler(request: Request, exc) -> JSONResponse:
    """Convert HTTPException to unified error envelope."""
    trace_id = get_request_id()
    detail = exc.detail

    if isinstance(detail, dict):
        code = detail.get("code", "error")
        message = detail.get("message", str(detail))
        details = detail.get("details") or detail.get("errors")
        if details and "details" not in detail:
            # validation errors: [{"field": "...", "message": "..."}]
            details_list = details if isinstance(details, list) else [details]
        else:
            details_list = None
        # Preserve extra fields (e.g. existing_run_id) in error envelope
        extra = {k: v for k, v in detail.items() if k not in ("code", "message", "details", "errors")}
    else:
        extra = None
        details_list = None

    if isinstance(detail, dict):
        body = _envelope(code, message, details_list, trace_id, extra)
    else:
        code = str(detail) if isinstance(detail, str) else "error"
        message = _get_message_for_code(code, str(detail))
        body = _envelope(code, message, None, trace_id, None)

    return JSONResponse(status_code=exc.status_code, content=body)
