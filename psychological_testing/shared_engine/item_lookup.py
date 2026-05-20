"""Resolve ``item_id`` from session responses to question text in item banks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from psychological_testing.shared_engine.item_bank_loader import (
    ForcedChoiceItem,
    LikertBankItem,
    load_likert_csv_items,
    load_mbti_items,
    load_paei_items,
    load_soft_skills_items,
)

TEST_BANK_PATHS: dict[str, str] = {
    "paei": "data/banks/v1/paei_items.yaml",
    "disc": "data/banks/v1/disc_items.csv",
    "hexaco": "data/banks/v1/hexaco_items.csv",
    "soft_skills": "data/banks/v1/soft_skills_items.yaml",
    "mbti": "data/banks/v1/mbti_items.yaml",
}

LEGACY_EXPECTED_ITEMS: dict[str, int] = {
    "paei": 5,
    "disc": 8,
    "hexaco": 10,
    "soft_skills": 10,
}


@dataclass(frozen=True)
class ItemRecord:
    item_id: str
    text: str
    scale: str | None = None
    options: dict[str, str] | None = None


def _index_paei(items: list[ForcedChoiceItem]) -> dict[str, ItemRecord]:
    return {
        item.id: ItemRecord(item_id=item.id, text=item.text, options=dict(item.options))
        for item in items
    }


def _index_likert(items: list[LikertBankItem]) -> dict[str, ItemRecord]:
    return {
        item.id: ItemRecord(item_id=item.id, text=item.text, scale=item.scale)
        for item in items
    }


def _index_soft(items) -> dict[str, ItemRecord]:
    return {
        item.id: ItemRecord(item_id=item.id, text=item.text, scale=item.skill)
        for item in items
    }


def _index_mbti(items: list[dict[str, Any]]) -> dict[str, ItemRecord]:
    out: dict[str, ItemRecord] = {}
    for raw in items:
        item_id = str(raw.get("id") or "")
        if not item_id:
            continue
        text = str(raw.get("text") or raw.get("question") or "")
        axis = str(raw.get("axis") or "")
        out[item_id] = ItemRecord(item_id=item_id, text=text, scale=axis or None)
    return out


@lru_cache(maxsize=8)
def load_item_index(test_id: str) -> dict[str, ItemRecord]:
    """Cached item bank index for ``test_id``."""
    path = TEST_BANK_PATHS.get(test_id)
    if not path:
        return {}
    if test_id == "paei":
        return _index_paei(load_paei_items(path))
    if test_id in ("disc", "hexaco"):
        return _index_likert(load_likert_csv_items(path))
    if test_id == "soft_skills":
        return _index_soft(load_soft_skills_items(path))
    if test_id == "mbti":
        return _index_mbti(load_mbti_items(path))
    return {}


def format_answer_display(
    test_id: str,
    response: dict[str, Any],
    item: ItemRecord | None,
) -> str:
    """Human-readable answer for appendix."""
    value = response.get("resolved_value")
    raw = str(response.get("raw_input") or "")
    if test_id == "paei" and item and item.options:
        key = str(value or raw).strip().upper()[:1]
        if key in item.options:
            return f"{key} — {item.options[key]}"
    if value is not None:
        return str(value)
    return raw or "—"
