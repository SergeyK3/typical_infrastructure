"""Single-instance guard for ``telegram_worker`` (one getUpdates per bot token)."""

from __future__ import annotations

import atexit
import ctypes
import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

_KERNEL32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
_PROCESS_QUERY_LIMITED = 0x1000


def _lock_path() -> Path:
    root = os.getenv("TYPICAL_INFRA_ROOT", "").strip()
    if root:
        base = Path(root)
    else:
        base = Path(__file__).resolve().parents[2]
    return base / ".psych_testing_telegram_worker.pid"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    handle = _KERNEL32.OpenProcess(_PROCESS_QUERY_LIMITED, False, pid)
    if handle:
        _KERNEL32.CloseHandle(handle)
        return True
    return False


def acquire_single_worker_lock() -> Path:
    """
    Exit with code 1 if another live worker holds the lock.
    Removes lock file on normal process exit.
    """
    path = _lock_path()
    if path.exists():
        try:
            old_pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            old_pid = 0
        if old_pid and old_pid != os.getpid() and _pid_alive(old_pid):
            _log.error(
                "Уже запущен telegram_worker (pid=%s). "
                "Остановите лишние процессы — иначе сессии теряются (409 Conflict). "
                "Lock: %s",
                old_pid,
                path,
            )
            sys.exit(1)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    path.write_text(str(os.getpid()), encoding="utf-8")

    def _release() -> None:
        try:
            if path.exists() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                path.unlink(missing_ok=True)
        except OSError:
            pass

    atexit.register(_release)
    return path


def probe_get_updates_available(token: str) -> None:
    """Fail fast when another process already polls this bot."""
    import httpx

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        r = httpx.get(url, params={"offset": -1, "timeout": 0, "limit": 1}, timeout=15.0)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    except Exception as e:
        _log.warning("getUpdates probe failed (continuing): %s", e)
        return

    if r.status_code == 409 or (isinstance(data, dict) and data.get("error_code") == 409):
        _log.error(
            "Telegram getUpdates 409 — другой процесс уже опрашивает бота. "
            "Остановите все python -m psychological_testing.telegram_worker "
            "(и skill_assessment polling с тем же TELEGRAM_BOT_TOKEN), затем запустите один."
        )
        sys.exit(1)
