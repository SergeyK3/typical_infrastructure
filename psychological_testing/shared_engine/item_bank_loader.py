"""Load versioned item banks and interpretation YAML from ``data/``."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from psychological_testing.domain.test_registry import resolve_package_path

__all__ = [
    "DimensionBankItem",
    "ForcedChoiceItem",
    "LikertBankItem",
    "load_csv_bank",
    "load_item_bank",
    "load_items_for_definition",
    "load_likert_csv_items",
    "load_mbti_items",
    "load_paei_items",
    "load_soft_skills_items",
    "load_yaml_file",
    "resolve_data_path",
]


def resolve_data_path(path: str | Path) -> Path:
    """Resolve a path relative to ``psychological_testing/``."""
    return resolve_package_path(str(path))


def load_csv_bank(path: str | Path) -> list[dict[str, str]]:
    """Load legacy item bank CSV (07 PsychTest ``data/bank/*.csv``)."""
    file_path = resolve_data_path(path)
    with file_path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    """Load YAML bank or interpretation file."""
    file_path = resolve_data_path(path)
    with file_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at root: {file_path}")
    return data


def load_item_bank(path: str | Path) -> list[dict[str, str]] | dict[str, Any]:
    """Dispatch by extension: ``.csv`` → rows, ``.yaml``/``.yml`` → document."""
    file_path = resolve_data_path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return load_csv_bank(file_path)
    if suffix in {".yaml", ".yml"}:
        return load_yaml_file(file_path)
    raise ValueError(f"Unsupported item bank format: {file_path}")


@dataclass(frozen=True)
class ForcedChoiceItem:
    id: str
    text: str
    options: dict[str, str]


def _forced_choice_item_from_dict(raw: dict[str, Any]) -> ForcedChoiceItem:
    opts = raw.get("options") or {}
    if not isinstance(opts, dict):
        opts = {}
    return ForcedChoiceItem(
        id=str(raw["id"]),
        text=str(raw.get("text", "")),
        options={str(k): str(v) for k, v in opts.items()},
    )


@dataclass(frozen=True)
class LikertBankItem:
    id: str
    text: str
    scale: str
    reverse: bool = False


def _likert_item_from_csv_row(raw: dict[str, str]) -> LikertBankItem:
    item_id = str(raw.get("item_id") or raw.get("id") or "")
    reverse_raw = str(raw.get("reverse", "0")).strip().lower()
    return LikertBankItem(
        id=item_id,
        text=str(raw.get("text", "")),
        scale=str(raw.get("scale", "")),
        reverse=reverse_raw in {"1", "true", "yes"},
    )


def load_likert_csv_items(path: str | Path) -> list[LikertBankItem]:
    """Return Likert items from legacy CSV bank (DISC, HEXACO)."""
    rows = load_csv_bank(path)
    return [_likert_item_from_csv_row(row) for row in rows]


@dataclass(frozen=True)
class DimensionBankItem:
    id: str
    dimension: str
    skill: str
    text: str


def _dimension_item_from_dict(raw: dict[str, Any]) -> DimensionBankItem:
    return DimensionBankItem(
        id=str(raw["id"]),
        dimension=str(raw.get("dimension") or raw["id"]),
        skill=str(raw.get("skill", "")),
        text=str(raw.get("text", "")),
    )


def load_soft_skills_items(
    path: str | Path = "data/banks/v1/soft_skills_items.yaml",
) -> list[DimensionBankItem]:
    """Return dimension items from Soft Skills YAML bank."""
    doc = load_yaml_file(path)
    items = doc.get("items")
    if not isinstance(items, list):
        raise ValueError("soft_skills_items.yaml must contain top-level 'items' list")
    return [_dimension_item_from_dict(item) for item in items]


def load_paei_items(path: str | Path = "data/banks/v1/paei_items.yaml") -> list[ForcedChoiceItem]:
    """Return forced-choice items from PAEI YAML bank."""
    doc = load_yaml_file(path)
    items = doc.get("items")
    if not isinstance(items, list):
        raise ValueError("paei_items.yaml must contain top-level 'items' list")
    return [_forced_choice_item_from_dict(item) for item in items]


def load_mbti_items(path: str | Path = "data/banks/v1/mbti_items.yaml") -> list[dict[str, Any]]:
    """Return ``items`` list from MBTI item bank YAML."""
    doc = load_yaml_file(path)
    items = doc.get("items")
    if not isinstance(items, list):
        raise ValueError("mbti_items.yaml must contain top-level 'items' list")
    return items


def load_items_for_definition(item_bank_path: str | Path) -> list[dict[str, Any]]:
    """Load item list for a plugin ``item_bank`` path (YAML ``items`` or CSV rows)."""
    bank = load_item_bank(item_bank_path)
    if isinstance(bank, list):
        return bank  # type: ignore[return-value]
    items = bank.get("items")
    if isinstance(items, list):
        return items
    raise ValueError(f"No 'items' list in item bank: {item_bank_path}")
