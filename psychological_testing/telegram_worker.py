"""
Отдельный процесс: Telegram long polling только для psychological_testing.

В проде обычно достаточно одного воркера на ``TELEGRAM_BOT_TOKEN``::

    python -m skill_assessment.telegram_worker

(маршрутизация psych + skill_assessment — ``app.services.telegram_unified_router``).

Изолированная отладка psych::

    TELEGRAM_BOT_TOKEN=...
    PSYCH_TESTING_ENABLE_POLLING=1
    PSYCH_TESTING_TELEGRAM_OUTBOUND=http
    python -m psychological_testing.telegram_worker

Для быстрого MBTI в dev: ``PSYCH_TESTING_MBTI_QUESTIONS_PER_AXIS=1``
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from psychological_testing.env import load_plugin_env, telegram_bot_token

_pkg_root = Path(__file__).resolve().parent
load_plugin_env(override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from psychological_testing.bootstrap import ensure_typical_infra_working_directory

_log = logging.getLogger("psychological_testing.telegram_worker")


def main() -> None:
    ensure_typical_infra_working_directory()
    env_file = _pkg_root.parent / ".env"

    if os.getenv("PSYCH_TESTING_ENABLE_POLLING", "").strip() not in ("1", "true", "yes"):
        _log.error(
            "PSYCH_TESTING_ENABLE_POLLING не включён — установите 1 в %s", env_file
        )
        sys.exit(1)

    token = telegram_bot_token()
    if not token or len(token) < 10:
        _log.error(
            "TELEGRAM_BOT_TOKEN (или BOT_TOKEN) пуст — добавьте в %s "
            "(перенос из 07 PsychTest/.env)",
            env_file,
        )
        sys.exit(1)

    from psychological_testing.integration.worker_lock import (
        acquire_single_worker_lock,
        probe_get_updates_available,
    )

    lock_path = acquire_single_worker_lock()
    probe_get_updates_available(token)

    outbound = os.getenv("PSYCH_TESTING_TELEGRAM_OUTBOUND", "http").strip()
    stt = os.getenv("PSYCH_TESTING_STT_PROVIDER", "(auto)").strip()
    _log.info(
        "telegram_worker: pid=%s lock=%s .env=%s cwd=%s outbound=%s stt=%s",
        os.getpid(),
        lock_path,
        env_file,
        os.getcwd(),
        outbound,
        stt,
    )

    from psychological_testing.integration.telegram_poller import run_long_polling

    asyncio.run(run_long_polling(token))


if __name__ == "__main__":
    main()
