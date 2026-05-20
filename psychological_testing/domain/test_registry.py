"""Plugin discovery: load ``tests/*/definition.yaml`` into TestDefinition."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from psychological_testing.domain.entities import TestDefinition

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = PACKAGE_ROOT / "tests"
RESEARCH_DIR = PACKAGE_ROOT / "research"

ALLOWED_SCORING_TYPES: frozenset[str] = frozenset(
    {
        "likert_sum",
        "forced_choice_count",
        "likert_per_dimension",
        "dichotomy_weighted_choice",
        "dichotomy_simple_count",
        "orchestrated_episode",
        "custom",
    }
)

_REQUIRED_FIELDS = ("test_id", "version", "scoring_type")


def package_root() -> Path:
    return PACKAGE_ROOT


def resolve_package_path(relative: str) -> Path:
    """Resolve a path relative to ``psychological_testing/``."""
    return PACKAGE_ROOT / relative


def _reject_research_path(path: Path) -> None:
    try:
        path.resolve().relative_to(RESEARCH_DIR.resolve())
    except ValueError:
        return
    raise ValueError(f"Research paths are not registered as plugins: {path}")


def _load_yaml(path: Path) -> dict[str, Any]:
    _reject_research_path(path)
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise ValueError(f"Invalid definition (expected mapping): {path}")
    return doc


def _validate_definition(doc: dict[str, Any], *, plugin_dir: Path) -> TestDefinition:
    missing = [k for k in _REQUIRED_FIELDS if not doc.get(k)]
    if missing:
        raise ValueError(f"Missing required fields {missing} in {plugin_dir / 'definition.yaml'}")

    test_id = str(doc["test_id"])
    scoring_type = str(doc["scoring_type"])
    if scoring_type not in ALLOWED_SCORING_TYPES:
        raise ValueError(f"Unknown scoring_type {scoring_type!r} for test {test_id}")

    if plugin_dir.name.startswith("_"):
        raise ValueError(f"Skipped template directory: {plugin_dir.name}")
    if test_id != plugin_dir.name:
        raise ValueError(
            f"test_id {test_id!r} does not match plugin directory {plugin_dir.name!r}"
        )

    item_bank = doc.get("item_bank")
    if item_bank:
        bank_path = resolve_package_path(str(item_bank))
        if not bank_path.is_file():
            raise FileNotFoundError(f"item_bank not found for {test_id}: {bank_path}")

    interpretation = doc.get("interpretation")
    if interpretation:
        interp_path = resolve_package_path(str(interpretation))
        if not interp_path.is_file():
            raise FileNotFoundError(f"interpretation not found for {test_id}: {interp_path}")

    known_keys = {
        "test_id",
        "version",
        "scoring_type",
        "display_name",
        "item_bank",
        "interpretation",
        "channel",
        "selection",
        "scoring",
        "normalization",
        "ai",
        "scales",
        "response_scale",
        "delivery_mode",
        "delivery_modes",
    }
    extra = {k: v for k, v in doc.items() if k not in known_keys}

    scales_raw = doc.get("scales") or []
    scales = [str(s) for s in scales_raw] if isinstance(scales_raw, list) else []

    return TestDefinition(
        test_id=test_id,
        version=str(doc["version"]),
        scoring_type=scoring_type,
        display_name=doc.get("display_name"),
        item_bank=str(item_bank) if item_bank else None,
        interpretation=str(interpretation) if interpretation else None,
        channel=dict(doc.get("channel") or {}),
        selection=dict(doc.get("selection") or {}),
        scoring=dict(doc.get("scoring") or {}),
        normalization=dict(doc.get("normalization") or {}),
        ai=dict(doc.get("ai") or {}),
        scales=scales,
        response_scale=dict(doc.get("response_scale") or {}),
        plugin_dir=str(plugin_dir.relative_to(PACKAGE_ROOT)),
        extra={
            **extra,
            **({"delivery_mode": doc["delivery_mode"]} if doc.get("delivery_mode") else {}),
            **({"delivery_modes": doc["delivery_modes"]} if doc.get("delivery_modes") else {}),
        },
    )


def load_definition(path: Path) -> TestDefinition:
    """Load a single plugin definition YAML."""
    doc = _load_yaml(path)
    return _validate_definition(doc, plugin_dir=path.parent)


def discover_plugins(*, tests_dir: Path | None = None) -> dict[str, TestDefinition]:
    """Scan ``tests/*/definition.yaml`` and return ``test_id → TestDefinition``."""
    root = tests_dir or TESTS_DIR
    if not root.is_dir():
        return {}

    definitions: dict[str, TestDefinition] = {}
    for plugin_dir in sorted(root.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
            continue
        definition_path = plugin_dir / "definition.yaml"
        if not definition_path.is_file():
            continue
        definition = load_definition(definition_path)
        if definition.test_id in definitions:
            raise ValueError(f"Duplicate test_id: {definition.test_id}")
        definitions[definition.test_id] = definition
    return definitions


class TestRegistry:
    """In-memory registry of test plugins."""

    def __init__(self, definitions: dict[str, TestDefinition] | None = None) -> None:
        self._definitions = definitions if definitions is not None else discover_plugins()

    def get(self, test_id: str) -> TestDefinition:
        try:
            return self._definitions[test_id]
        except KeyError as exc:
            raise KeyError(f"Unknown test_id: {test_id}") from exc

    def list_test_ids(self) -> list[str]:
        return sorted(self._definitions)

    def all(self) -> dict[str, TestDefinition]:
        return dict(self._definitions)
