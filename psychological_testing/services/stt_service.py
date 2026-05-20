"""Speech-to-text for psychological testing (mock or OpenAI Whisper)."""

from __future__ import annotations

import os

import httpx

from psychological_testing.env import openai_api_key

STT_MOCK_TRANSCRIPT_PREFIX = "[STT mock]"


class SttConfigurationError(RuntimeError):
    """Missing API key or unknown provider."""


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def max_audio_bytes() -> int:
    return max(1024, _env_int("PSYCH_TESTING_STT_MAX_BYTES", 25 * 1024 * 1024))


def stt_provider() -> str:
    raw = os.getenv("PSYCH_TESTING_STT_PROVIDER", "").strip().lower()
    if raw in ("mock", "openai"):
        return raw
    key = _openai_api_key()
    return "openai" if key else "mock"


def _openai_api_key() -> str:
    return openai_api_key()


def transcribe_audio_bytes(
    data: bytes,
    *,
    filename: str = "audio.webm",
    content_type: str | None = None,
) -> str:
    if not data:
        raise ValueError("empty_audio")
    if len(data) > max_audio_bytes():
        raise ValueError("audio_too_large")

    prov = stt_provider()
    if prov == "mock":
        return f"{STT_MOCK_TRANSCRIPT_PREFIX} Получено {len(data)} байт ({filename})."

    if prov != "openai":
        raise SttConfigurationError(f"unknown_stt_provider:{prov}")

    api_key = _openai_api_key()
    if not api_key:
        raise SttConfigurationError("openai_api_key_missing")

    ct = content_type or "application/octet-stream"
    url = "https://api.openai.com/v1/audio/transcriptions"
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, data, ct)},
            data={"model": "whisper-1"},
        )
        r.raise_for_status()
        payload = r.json()
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("empty_transcript")
    return text
