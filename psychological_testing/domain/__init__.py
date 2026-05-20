"""Domain models and plugin registry."""

from psychological_testing.domain.entities import (
    ScoreResult,
    SessionStatus,
    StructuredAnswer,
    TestDefinition,
    TestSession,
)
from psychological_testing.domain.test_registry import TestRegistry, discover_plugins

__all__ = [
    "ScoreResult",
    "SessionStatus",
    "StructuredAnswer",
    "TestDefinition",
    "TestRegistry",
    "TestSession",
    "discover_plugins",
]
