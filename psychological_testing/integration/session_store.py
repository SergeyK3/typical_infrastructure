"""In-memory active sessions (Phase 4 → ``pt_*`` tables)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from typing import Any

from psychological_testing.shared_engine.session_state_machine import SessionEngine

ProcessContext = Literal["idle", "psych_testing"]
SessionEngineHandle = SessionEngine | Any  # SessionEngine | AkmaDialogEngine


@dataclass
class ChatBinding:
    chat_id: str
    client_id: str
    employee_id: str
    context: ProcessContext = "idle"
    active_test_id: str | None = None
    mbti_delivery_mode: str | None = None


@dataclass
class PsychTestingSessionStore:
    engines: dict[str, SessionEngineHandle] = field(default_factory=dict)
    bindings: dict[str, ChatBinding] = field(default_factory=dict)

    def get_engine(self, chat_id: str) -> SessionEngineHandle | None:
        return self.engines.get(chat_id)

    def set_engine(self, chat_id: str, engine: SessionEngineHandle) -> None:
        self.engines[chat_id] = engine

    def clear_engine(self, chat_id: str) -> None:
        self.engines.pop(chat_id, None)

    def get_binding(self, chat_id: str) -> ChatBinding | None:
        return self.bindings.get(chat_id)

    def ensure_binding(
        self,
        chat_id: str,
        *,
        client_id: str,
        employee_id: str,
    ) -> ChatBinding:
        existing = self.bindings.get(chat_id)
        if existing is not None:
            return existing
        binding = ChatBinding(
            chat_id=chat_id,
            client_id=client_id,
            employee_id=employee_id,
        )
        self.bindings[chat_id] = binding
        return binding


_default_store = PsychTestingSessionStore()


def get_session_store() -> PsychTestingSessionStore:
    return _default_store


def reset_session_store() -> None:
    """Clear store between tests."""
    _default_store.engines.clear()
    _default_store.bindings.clear()
