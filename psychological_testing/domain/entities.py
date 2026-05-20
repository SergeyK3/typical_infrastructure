"""Core domain types for the psychological testing engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

InputChannel = Literal["voice", "button", "text"]


@dataclass(frozen=True)
class TestDefinition:
    """Declarative test descriptor loaded from ``tests/{test_id}/definition.yaml``."""

    test_id: str
    version: str
    scoring_type: str
    display_name: str | None = None
    item_bank: str | None = None
    interpretation: str | None = None
    channel: dict[str, Any] = field(default_factory=dict)
    selection: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)
    normalization: dict[str, Any] = field(default_factory=dict)
    ai: dict[str, Any] = field(default_factory=dict)
    scales: list[str] = field(default_factory=list)
    response_scale: dict[str, Any] = field(default_factory=dict)
    plugin_dir: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreResult:
    """Output of ``shared_engine.scoring_pipeline`` (pre-interpretation)."""

    raw_scores: dict[str, float] = field(default_factory=dict)
    normalized_scores: dict[str, float] = field(default_factory=dict)
    typology_code: str | None = None
    axis_details: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionStatus(str, Enum):
    INIT = "init"
    QUESTIONING = "questioning"
    REPROMPT = "reprompt"
    SCORING = "scoring"
    INTERPRETATION = "interpretation"
    REPORT = "report"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class StructuredAnswer:
    """One resolved response aligned with an item in the session queue."""

    item_id: str
    input_channel: InputChannel
    raw_input: str
    resolved_value: Any
    confidence: float
    resolver_method: str
    axis: str | None = None


@dataclass
class TestSession:
    """Mutable session state driven by ``SessionEngine``."""

    session_id: str
    client_id: str
    employee_id: str
    test_id: str
    test_version: str
    status: SessionStatus
    started_at: datetime
    items: list[Any]
    responses: list[StructuredAnswer] = field(default_factory=list)
    raw_transcripts: list[str] = field(default_factory=list)
    current_item_index: int = 0
    score_result: ScoreResult | None = None
    interpretation: Any | None = None
    reprompt_message: str | None = None
