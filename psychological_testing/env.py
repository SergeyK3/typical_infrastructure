"""Load repo-root ``.env`` (``TELEGRAM_BOT_TOKEN``, ``PSYCH_TESTING_*``)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
REPO_ENV_FILE = REPO_ROOT / ".env"


def load_env_file(path: str | Path, *, override: bool = False) -> bool:
    p = Path(path)
    if not p.is_file():
        return False
    load_dotenv(p, override=override)
    return True


def load_plugin_env(*, override: bool = False) -> bool:
    """
    Load ``10 Typical_infrastructure/.env`` (same file as ``app.settings``).

    Legacy ``07 PsychTest`` used ``BOT_TOKEN``; prefer ``TELEGRAM_BOT_TOKEN`` here.
    """
    return load_env_file(REPO_ENV_FILE, override=override)


def telegram_bot_token() -> str:
    """``TELEGRAM_BOT_TOKEN`` with fallback to legacy ``BOT_TOKEN`` (07 PsychTest)."""
    return (
        os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or ""
    ).strip()


def openai_api_key() -> str:
    """OpenAI key for psych testing STT/LLM (shared infra key fallback)."""
    return (
        os.getenv("PSYCH_TESTING_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("SKILL_ASSESSMENT_OPENAI_API_KEY")
        or ""
    ).strip()
