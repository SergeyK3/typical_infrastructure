"""LLM client for research / dialog delivery modes (mock or OpenAI-compatible)."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx

from psychological_testing.env import openai_api_key


class LlmConfigurationError(RuntimeError):
    """Missing API key or unknown provider."""


class LlmClient(Protocol):
    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> str: ...


def llm_provider() -> str:
    raw = os.getenv("PSYCH_TESTING_AI_PROVIDER", "").strip().lower()
    if raw in ("mock", "openai"):
        return raw
    if mbti_ai_enabled():
        key = _openai_api_key()
        return "openai" if key else "mock"
    return "mock"


def mbti_ai_enabled() -> bool:
    raw = os.getenv("PSYCH_TESTING_AI_ENABLED", "").strip().lower()
    return raw in ("1", "true", "yes")


def default_llm_model(role: str) -> str:
    """Role: akma | eval | report."""
    env_key = f"PSYCH_TESTING_AI_MODEL_{role.upper()}"
    return (os.getenv(env_key) or os.getenv("PSYCH_TESTING_AI_MODEL") or "gpt-4o-mini").strip()


def _openai_api_key() -> str:
    return openai_api_key()


def _openai_base_url() -> str:
    return (
        os.getenv("PSYCH_TESTING_AI_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")


class MockLlmClient:
    """Deterministic replies for unit tests and dev without API keys."""

    def __init__(
        self,
        *,
        akma_replies: list[str] | None = None,
        eval_choices: list[str] | None = None,
        report_text: str = "Mock MBTI report.",
    ) -> None:
        self._akma_replies = list(akma_replies or [])
        self._eval_choices = list(eval_choices or [])
        self._report_text = report_text
        self._akma_i = 0
        self._eval_i = 0
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append({"model": model, "messages": messages, "temperature": temperature})
        user_blob = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
        if "JSON-объектом" in user_blob or '"choice"' in user_blob:
            if self._eval_i < len(self._eval_choices):
                choice = self._eval_choices[self._eval_i]
                self._eval_i += 1
            else:
                choice = "E" if self._eval_i % 2 == 0 else "I"
                self._eval_i += 1
            return json.dumps({"choice": choice}, ensure_ascii=False)
        if "тип личности" in user_blob.lower() or "сильные стороны" in user_blob.lower():
            return self._report_text
        if self._akma_i < len(self._akma_replies):
            text = self._akma_replies[self._akma_i]
            self._akma_i += 1
            return text
        return f"Расскажите подробнее о вашей работе (mock #{self._akma_i + 1})."


class OpenAiCompatibleClient:
    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
    ) -> str:
        api_key = _openai_api_key()
        if not api_key:
            raise LlmConfigurationError("openai_api_key_missing")
        url = f"{_openai_base_url()}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        with httpx.Client(timeout=120.0) as client:
            r = client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("llm_empty_response")
        message = choices[0].get("message") or {}
        return (message.get("content") or "").strip()


def get_llm_client() -> LlmClient:
    prov = llm_provider()
    if prov == "mock":
        return MockLlmClient()
    if prov == "openai":
        return OpenAiCompatibleClient()
    raise LlmConfigurationError(f"unknown_llm_provider:{prov}")
