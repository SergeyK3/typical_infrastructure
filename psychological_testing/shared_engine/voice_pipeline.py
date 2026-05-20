"""Voice intake: STT provider abstraction (mock or OpenAI Whisper)."""

from __future__ import annotations

import os

from psychological_testing.env import openai_api_key
from typing import Protocol


class SttProvider(Protocol):
    def transcribe(self, audio: bytes, *, hint: str | None = None) -> str: ...


class MockSttProvider:
    """Deterministic STT for tests and local dev (no external API)."""

    def __init__(self, transcripts: dict[bytes, str] | None = None) -> None:
        self._transcripts = transcripts or {}

    def transcribe(self, audio: bytes, *, hint: str | None = None) -> str:
        if audio in self._transcripts:
            return self._transcripts[audio]
        if hint:
            return hint
        try:
            return audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            return ""


class OpenAiWhisperSttProvider:
    """Whisper via ``psychological_testing.services.stt_service`` (Phase 3)."""

    def transcribe(self, audio: bytes, *, hint: str | None = None) -> str:
        from psychological_testing.services.stt_service import transcribe_audio_bytes

        return transcribe_audio_bytes(audio, filename="voice.oga")


def default_stt_provider() -> SttProvider:
    raw = os.getenv("PSYCH_TESTING_STT_PROVIDER", "").strip().lower()
    if raw == "openai":
        return OpenAiWhisperSttProvider()
    if raw == "mock":
        return MockSttProvider()
    key = openai_api_key()
    return OpenAiWhisperSttProvider() if key else MockSttProvider()


class VoicePipeline:
    """Telegram poller downloads bytes; pipeline runs STT + answer resolver."""

    def __init__(self, provider: SttProvider | None = None) -> None:
        self._provider = provider if provider is not None else default_stt_provider()

    def transcribe(self, audio: bytes, *, hint: str | None = None) -> str:
        return self._provider.transcribe(audio, hint=hint)
